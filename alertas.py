
from datetime import datetime


def criar_alerta(grupo, remetente, palavras_encontradas, data_mensagem=None):
    if not palavras_encontradas:
        return None

    data_mensagem = data_mensagem or datetime.now().isoformat()

    try:
        data_formatada = datetime.fromisoformat(data_mensagem)
        horario = data_formatada.strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        horario = data_mensagem

    palavras = ", ".join(
        item["palavra"] for item in palavras_encontradas
    )

    alerta = (
        f"X9 | Nova correspondência\n"
        f"Grupo: {grupo}\n"
        f"Remetente: {remetente}\n"
        f"Palavras: {palavras}\n"
        f"Data e hora da mensagem: {horario}"
    )

    return alerta


def exibir_alerta(alerta):
    if alerta:
        print("\n" + "=" * 45)
        print(alerta)
        print("=" * 45 + "\n")
