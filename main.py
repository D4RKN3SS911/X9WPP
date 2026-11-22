
from database import inicializar, salvar_mensagem
from indexador import encontrar_palavras_chave
from alertas import criar_alerta, exibir_alerta


def processar_mensagem(
    message_id,
    grupo,
    remetente,
    conteudo,
    tipo="texto",
    data_mensagem=None
):
    palavras = encontrar_palavras_chave(conteudo)

    if not palavras:
        return False

    salva = salvar_mensagem(
        message_id,
        grupo,
        remetente,
        conteudo,
        tipo,
        data_mensagem
    )

    if not salva:
        print("Mensagem já registrada.")
        return False

    alerta = criar_alerta(
        grupo,
        remetente,
        palavras,
        data_mensagem
    )

    exibir_alerta(alerta)
    return True


def iniciar():
    inicializar()
    print("X9: Sistema inicializado.")

    processar_mensagem(
        message_id="teste-001",
        grupo="Grupo de teste",
        remetente="Usuário teste",
        conteudo="Comunicado sobre atendimento da Polícia Civil.",
        tipo="texto"
    )


if __name__ == "__main__":
    iniciar()
