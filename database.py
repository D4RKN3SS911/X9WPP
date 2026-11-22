
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "x9.db"


def conectar():
    return sqlite3.connect(DB_PATH)


def inicializar():
    with conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                grupo TEXT,
                remetente TEXT,
                conteudo TEXT,
                tipo TEXT,
                data_mensagem TEXT,
                processada INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def salvar_mensagem(
    message_id,
    grupo,
    remetente,
    conteudo,
    tipo,
    data_mensagem=None
):
    data_mensagem = data_mensagem or datetime.now().isoformat()

    try:
        with conectar() as conn:
            conn.execute("""
                INSERT INTO mensagens (
                    message_id, grupo, remetente,
                    conteudo, tipo, data_mensagem
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                grupo,
                remetente,
                conteudo,
                tipo,
                data_mensagem
            ))
            conn.commit()
            return True

    except sqlite3.IntegrityError:
        return False


if __name__ == "__main__":
    inicializar()
    print("X9: Banco de dados inicializado.")
