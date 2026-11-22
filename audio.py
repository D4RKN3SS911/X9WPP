
from faster_whisper import WhisperModel
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audios"

AUDIO_DIR.mkdir(exist_ok=True)

modelo = None


def carregar_modelo():
    global modelo

    if modelo is None:
        print("X9: Carregando modelo de transcrição...")
        modelo = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

    return modelo


def transcrever_audio(caminho):
    arquivo = Path(caminho)

    if not arquivo.is_file():
        raise FileNotFoundError(arquivo)

    transcritor = carregar_modelo()

    segmentos, informacoes = transcritor.transcribe(
        str(arquivo),
        language="pt",
        vad_filter=True
    )

    texto = " ".join(
        segmento.text.strip()
        for segmento in segmentos
    )

    return texto


if __name__ == "__main__":
    print("X9: Módulo de áudio pronto.")
    print("Coloque arquivos de áudio na pasta audios.")
