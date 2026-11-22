import re
import unicodedata


PALAVRAS_CHAVE = {
    "instituicoes": [
        "Polícia Civil",
        "Polícia Militar",
        "Polícia Federal",
        "Polícia Rodoviária Federal",
        "Guarda Municipal",
        "Segurança Pública",
        "Delegacia",
        "Distrito Policial",
        "Batalhão",
        "Corporação",
        "PM",
        "PC",
        "PF",
        "PRF",
        "GCM",
        "GM",
        "BOPE",
    ],

    "termos_administrativos": [
        "Boletim de ocorrência",
        "Registro de ocorrência",
        "B.O.",
        "BO",
        "Denúncia",
        "Investigação",
        "Inquérito",
        "Delegado",
        "Investigador",
        "Escrivão",
        "Ocorrência",
        "Atendimento policial",
        "Procedimento administrativo",
        "Relatório policial",
        "Comunicado oficial",
        "Nota oficial",
        "Audiência",
        "Intimação",
        "Mandado",
        "Processo",
    ],

    "termos_gerais": [
        "Policial",
        "Policiais",
        "Polícia",
        "Poliça",
        "Puliça",
        "Pulissa",
        "Delegado",
        "Delegada",
        "Delegacia",
        "Segurança",
        "Agente",
        "Oficial",
        "Comando",
        "Força pública",
        "Autoridade",
        "Patrulhamento",
        "Fiscalização",
    ],

    "termos_informais": [
        "Os homi",
        "Os home",
        "Os homens",
        "Homi",
        "Home",
        "Gambé",
        "Gambe",
        "Gambézada",
        "Cana",
        "Os cana",
        "Tira",
        "Os tira",
        "Meganhas",
        "Cop",
        "Os cops",
        "A civil",
        "Os federais",
        "Federal",
        "Farda",
        "De farda",
        "PM",
        "Os PM",
        "Os policiais",
        "Os agentes",
        "Puliça",
        "Poliça",
    ],
}


def normalizar(texto):
    texto = str(texto or "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    return texto.casefold()


def encontrar_palavras_chave(conteudo):
    if not conteudo:
        return []

    texto = normalizar(conteudo)
    encontradas = []
    termos_encontrados = set()

    for categoria, palavras in PALAVRAS_CHAVE.items():
        for palavra in palavras:
            termo = normalizar(palavra)

            if termo in termos_encontrados:
                continue

            padrao = r"(?<!\w)" + re.escape(termo) + r"(?!\w)"

            if re.search(padrao, texto):
                encontradas.append({
                    "categoria": categoria,
                    "palavra": palavra,
                })
                termos_encontrados.add(termo)

    return encontradas