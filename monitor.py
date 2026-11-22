
import asyncio
import hashlib
import re
import sqlite3
from pathlib import Path

from playwright.async_api import async_playwright, Error as PlaywrightError

from grupos import GRUPOS_MONITORADOS, GRUPO_DESTINO_ALERTAS
from database import inicializar, salvar_mensagem
from indexador import encontrar_palavras_chave
from alertas import criar_alerta, exibir_alerta


BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "opera_x9_profile"
OPERA_PATH = BASE_DIR / "OpegaGX" / "opera.exe"
DB_PATH = BASE_DIR / "data" / "x9.db"

INTERVALO_GRUPOS = 3


def conectar_notificacoes():
    return sqlite3.connect(DB_PATH, timeout=15)


def inicializar_notificacoes():
    with conectar_notificacoes() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notificacoes_enviadas (
                message_id TEXT PRIMARY KEY,
                destino TEXT NOT NULL,
                data_envio TEXT NOT NULL
            )
        """)


def notificacao_ja_enviada(message_id):
    with conectar_notificacoes() as conn:
        resultado = conn.execute(
            """
            SELECT 1
            FROM notificacoes_enviadas
            WHERE message_id = ?
            """,
            (message_id,)
        ).fetchone()

    return resultado is not None


def registrar_notificacao(message_id, destino):
    from datetime import datetime

    with conectar_notificacoes() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO notificacoes_enviadas
            (message_id, destino, data_envio)
            VALUES (?, ?, ?)
            """,
            (message_id, destino, datetime.now().isoformat())
        )


def gerar_id(grupo, identificador, remetente, data, conteudo):
    base = (
        f"{grupo}|{identificador}|{remetente}|"
        f"{data}|{conteudo}"
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def conteudo_permitido_para_alerta(conteudo):
    """
    Evita encaminhar mensagens com indicadores explícitos
    de localização ou movimentação operacional em tempo real.
    """
    texto = (conteudo or "").casefold()

    termos_operacionais = [
        "localização",
        "coordenadas",
        "viatura",
        "vtr ",
        "deslocamento",
        "posição da equipe",
        "rota da equipe",
        "cerco policial",
        "perseguição",
        "em patrulhamento",
        "operação em andamento",
        "equipe a caminho",
        "equipe se deslocando",
    ]

    return not any(termo in texto for termo in termos_operacionais)


async def localizar_busca(page):
    seletores = [
        'div[contenteditable="true"][data-tab="3"]',
        'div[role="textbox"][contenteditable="true"]',
        'input[placeholder*="Pesquisar"]',
    ]

    for seletor in seletores:
        campo = page.locator(seletor).first

        try:
            if await campo.count() > 0 and await campo.is_visible():
                return campo
        except PlaywrightError:
            continue

    return None


async def abrir_grupo(page, nome):
    resultado = page.get_by_text(nome, exact=True).first

    try:
        if await resultado.count() > 0 and await resultado.is_visible():
            await resultado.click(timeout=3000)
            await page.wait_for_timeout(1200)
            return True
    except PlaywrightError:
        pass

    campo = await localizar_busca(page)

    if campo is None:
        print(f"X9: Campo de busca não localizado: {nome}")
        return False

    try:
        await campo.click()
        await campo.fill(nome)
        await page.wait_for_timeout(1500)

        resultado = page.get_by_text(nome, exact=True).last

        if await resultado.count() == 0:
            print(f"X9: Grupo não encontrado: {nome}")
            return False

        await resultado.click(timeout=5000)
        await page.wait_for_timeout(1200)

        print(f"X9: Grupo aberto: {nome}")
        return True

    except PlaywrightError as erro:
        print(f"X9: Falha ao abrir {nome}: {erro}")
        return False


async def abrir_grupo_destino(page):
    campo = await localizar_busca(page)

    if campo is None:
        print("X9: Não encontrei a busca para abrir o grupo de avisos.")
        return False

    try:
        await campo.click()
        await campo.fill(GRUPO_DESTINO_ALERTAS)
        await page.wait_for_timeout(1500)

        resultado = page.get_by_text(
            GRUPO_DESTINO_ALERTAS,
            exact=True
        ).last

        if await resultado.count() == 0:
            print(
                "X9: Grupo de destino não encontrado: "
                f"{GRUPO_DESTINO_ALERTAS}"
            )
            return False

        await resultado.click(timeout=5000)
        await page.wait_for_timeout(1200)

        return True

    except PlaywrightError as erro:
        print(f"X9: Erro ao abrir grupo de destino: {erro}")
        return False


async def enviar_alerta_whatsapp(page, mensagem):
    abriu = await abrir_grupo_destino(page)

    if not abriu:
        return False

    seletores_compositor = [
        'footer [contenteditable="true"][role="textbox"]',
        'footer div[contenteditable="true"]',
    ]

    compositor = None

    for seletor in seletores_compositor:
        campo = page.locator(seletor).last

        try:
            if await campo.count() > 0 and await campo.is_visible():
                compositor = campo
                break
        except PlaywrightError:
            continue

    if compositor is None:
        print("X9: Campo de mensagem do grupo não encontrado.")
        return False

    try:
        await compositor.fill(mensagem)
        await compositor.press("Enter")
        await page.wait_for_timeout(1000)

        print(
            "X9: Aviso enviado para "
            f"{GRUPO_DESTINO_ALERTAS}"
        )
        return True

    except PlaywrightError as erro:
        print(f"X9: Falha ao enviar aviso: {erro}")
        return False


async def ler_mensagens(page, grupo):
    mensagens = page.locator('[data-testid="msg-container"]')
    quantidade = await mensagens.count()

    if quantidade == 0:
        print(f"X9: Nenhuma mensagem visível em {grupo}.")
        return

    candidatas = []

    for i in range(quantidade):
        mensagem = mensagens.nth(i)

        try:
            meta = mensagem.locator(
                '[data-pre-plain-text]'
            ).first

            if await meta.count() == 0:
                continue

            informacao = await meta.get_attribute(
                "data-pre-plain-text"
            )

            texto_elemento = mensagem.locator(".selectable-text")
            conteudo = " ".join(
                await texto_elemento.all_inner_texts()
            ).strip()

            if not conteudo:
                continue

            correspondencia = re.match(
                r"\[(.*?)\]\s*(.*?):\s*$",
                informacao or ""
            )

            if correspondencia:
                data_mensagem = correspondencia.group(1)
                remetente = correspondencia.group(2)
            else:
                data_mensagem = informacao or ""
                remetente = "Não identificado"

            identificador = await mensagem.get_attribute("data-id")

            if not identificador:
                identificador = str(i)

            message_id = gerar_id(
                grupo,
                identificador,
                remetente,
                data_mensagem,
                conteudo
            )

            palavras = encontrar_palavras_chave(conteudo)

            if not palavras:
                continue

            salva = salvar_mensagem(
                message_id,
                grupo,
                remetente,
                conteudo,
                "texto",
                data_mensagem
            )

            if salva:
                print(
                    f"X9: CORRESPONDÊNCIA ENCONTRADA em {grupo}"
                )

                alerta = criar_alerta(
                    grupo,
                    remetente,
                    palavras,
                    data_mensagem
                )
                exibir_alerta(alerta)

            if not notificacao_ja_enviada(message_id):
                candidatas.append({
                    "message_id": message_id,
                    "grupo": grupo,
                    "remetente": remetente,
                    "data": data_mensagem,
                    "conteudo": conteudo,
                })

        except PlaywrightError as erro:
            print(f"X9: Erro ao ler mensagem: {erro}")

    # Só abre o grupo de destino depois de terminar a leitura.
    # Assim, a troca de conversa não interrompe a leitura da origem.
    for item in candidatas:
        if not conteudo_permitido_para_alerta(item["conteudo"]):
            print(
                "X9: Aviso não encaminhado por conter "
                "indicadores de localização ou movimentação operacional."
            )
            continue

        texto_alerta = (
            "X9 — NOVA CORRESPONDÊNCIA\n"
            f"Grupo de origem: {item['grupo']}\n"
            f"Remetente: {item['remetente']}\n"
            f"Data e horário: {item['data']}\n"
            "Conteúdo:\n"
            f"{item['conteudo']}"
        )

        enviado = await enviar_alerta_whatsapp(
            page,
            texto_alerta
        )

        if enviado:
            registrar_notificacao(
                item["message_id"],
                GRUPO_DESTINO_ALERTAS
            )


async def iniciar_x9():
    if not OPERA_PATH.is_file():
        raise FileNotFoundError(
            f"Opera GX não encontrado: {OPERA_PATH}"
        )

    inicializar()
    inicializar_notificacoes()
    PROFILE_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=str(OPERA_PATH),
            headless=False,
            args=["--no-first-run"]
        )

        page = (
            context.pages[0]
            if context.pages
            else await context.new_page()
        )

        try:
            print("X9: Abrindo WhatsApp Web...")

            await page.goto(
                "https://web.whatsapp.com",
                wait_until="commit",
                timeout=60000
            )

            print("X9: Aguardando conexão...")
            await page.wait_for_timeout(15000)

            print("\nX9 INICIADO")
            print(f"Grupos monitorados: {len(GRUPOS_MONITORADOS)}")
            print(f"Grupo de avisos: {GRUPO_DESTINO_ALERTAS}")

            while True:
                for grupo in GRUPOS_MONITORADOS:
                    print(f"\nX9: Verificando {grupo}")

                    abriu = await abrir_grupo(page, grupo)

                    if abriu:
                        await ler_mensagens(page, grupo)

                    await asyncio.sleep(INTERVALO_GRUPOS)

        except KeyboardInterrupt:
            print("\nX9: Encerrando.")

        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(iniciar_x9())
