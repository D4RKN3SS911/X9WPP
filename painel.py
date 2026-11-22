
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QHeaderView,
    QFrame, QAbstractItemView
)
from PySide6.QtCore import QTimer, Qt

from grupos import GRUPOS_MONITORADOS
from indexador import encontrar_palavras_chave, normalizar


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "x9.db"

LIMITE_LOG = 100
LIMITE_REGISTROS = 500
INTERVALO_ATUALIZACAO = 3000


ESTILO = """
QMainWindow, QWidget#central {
    background-color: #0b1120;
    color: #e5edf7;
    font-family: 'Segoe UI';
    font-size: 10pt;
}

QFrame#topbar {
    background-color: #111c30;
    border: 1px solid #20304a;
    border-radius: 16px;
}

QLabel#logo {
    background-color: #00c9d4;
    color: #07111c;
    font-size: 22px;
    font-weight: 900;
    border-radius: 12px;
    min-width: 52px;
    max-width: 52px;
    min-height: 52px;
    max-height: 52px;
}

QLabel#titulo {
    font-size: 23px;
    font-weight: 800;
    color: #f2f7ff;
}

QLabel#subtitulo {
    color: #8293ad;
    font-size: 10pt;
}

QFrame.card {
    background-color: #111c30;
    border: 1px solid #20304a;
    border-radius: 15px;
}

QLabel#status {
    background-color: #263449;
    color: #aabbd0;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 700;
}

QLabel#status.active {
    background-color: #103b35;
    color: #45e0a2;
}

QPushButton {
    background-color: #1a2940;
    color: #e5edf7;
    border: 1px solid #30435f;
    border-radius: 10px;
    padding: 11px 18px;
    font-weight: 700;
}

QPushButton:hover {
    background-color: #263b59;
    border-color: #00c9d4;
}

QPushButton#btn_start {
    background-color: #00c9a7;
    color: #061a19;
    border: none;
}

QPushButton#btn_stop {
    background-color: #352333;
    color: #ff9baf;
    border: 1px solid #674052;
}

QTableWidget {
    background-color: #101a2b;
    alternate-background-color: #142137;
    color: #dce7f5;
    border: 1px solid #20304a;
    border-radius: 12px;
    gridline-color: #20304a;
    selection-background-color: #164b5a;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #1a2940;
    color: #9fb3cc;
    border: none;
    border-bottom: 1px solid #30435f;
    padding: 12px 8px;
    font-weight: 800;
}

QTableWidget::item {
    padding: 8px;
    border: none;
}

QTextEdit {
    background-color: #0e1828;
    color: #72dfc1;
    border: 1px solid #20304a;
    border-radius: 12px;
    padding: 10px;
    font-family: Consolas;
    font-size: 9pt;
}

QLabel#rodape {
    color: #63748e;
    font-size: 9pt;
}
"""


def converter_data(valor):
    if not valor:
        return None

    valor = str(valor).strip()

    formatos = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%H:%M, %d/%m/%Y",
        "%H:%M:%S, %d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            continue

    return None


class PainelX9(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("X9 | Central de Indexação")
        self.resize(1250, 790)
        self.setMinimumSize(950, 650)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.carregar_registros)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(18)

        # CABEÇALHO
        topbar = QFrame()
        topbar.setObjectName("topbar")

        topo = QHBoxLayout(topbar)
        topo.setContentsMargins(20, 16, 20, 16)

        logo = QLabel("X9")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        identidade = QVBoxLayout()

        titulo = QLabel("CENTRAL X9")
        titulo.setObjectName("titulo")

        subtitulo = QLabel(
            "Indexação filtrada | WhatsApp Web | Banco local"
        )
        subtitulo.setObjectName("subtitulo")

        identidade.addWidget(titulo)
        identidade.addWidget(subtitulo)

        self.status = QLabel("● PAINEL PARADO")
        self.status.setObjectName("status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        topo.addWidget(logo)
        topo.addSpacing(14)
        topo.addLayout(identidade)
        topo.addStretch()
        topo.addWidget(self.status)

        layout.addWidget(topbar)

        # CARTÕES
        cards = QHBoxLayout()
        cards.setSpacing(14)

        self.total_card = self.criar_card(
            "REGISTROS ÚNICOS", "0", "#00c9d4"
        )

        self.hoje_card = self.criar_card(
            "REGISTROS DE HOJE", "0", "#45e0a2"
        )

        self.ultimo_card = self.criar_card(
            "ÚLTIMA ATUALIZAÇÃO", "--:--", "#a78bfa"
        )

        cards.addWidget(self.total_card)
        cards.addWidget(self.hoje_card)
        cards.addWidget(self.ultimo_card)

        layout.addLayout(cards)

        # CONTROLES
        controles = QHBoxLayout()

        titulo_registros = QLabel(
            "Histórico de correspondências"
        )
        titulo_registros.setStyleSheet(
            "font-size: 13pt; font-weight: 800; color: #e8f0fb;"
        )

        self.btn_iniciar = QPushButton("INICIAR ATUALIZAÇÃO")
        self.btn_iniciar.setObjectName("btn_start")

        self.btn_parar = QPushButton("PARAR")
        self.btn_parar.setObjectName("btn_stop")

        self.btn_atualizar = QPushButton("ATUALIZAR AGORA")

        self.btn_iniciar.clicked.connect(self.iniciar)
        self.btn_parar.clicked.connect(self.parar)
        self.btn_atualizar.clicked.connect(
            self.carregar_registros
        )

        controles.addWidget(titulo_registros)
        controles.addStretch()
        controles.addWidget(self.btn_iniciar)
        controles.addWidget(self.btn_parar)
        controles.addWidget(self.btn_atualizar)

        layout.addLayout(controles)

        # TABELA
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(6)

        self.tabela.setHorizontalHeaderLabels([
            "ID", "GRUPO", "REMETENTE",
            "CONTEÚDO", "TIPO", "DATA"
        ])

        self.tabela.setAlternatingRowColors(True)
        self.tabela.setShowGrid(False)

        self.tabela.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.tabela.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(42)

        cabecalho = self.tabela.horizontalHeader()

        cabecalho.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        cabecalho.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        cabecalho.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        cabecalho.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        cabecalho.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        cabecalho.setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )

        layout.addWidget(self.tabela, 1)

        # LOG
        log_titulo = QLabel("ATIVIDADE DO SISTEMA")
        log_titulo.setStyleSheet(
            "font-weight: 800; color: #91a2bc;"
        )

        layout.addWidget(log_titulo)

        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumHeight(105)

        layout.addWidget(self.logs)

        rodape = QLabel(
            "X9 • Banco de dados local • Versão de desenvolvimento"
        )
        rodape.setObjectName("rodape")
        rodape.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(rodape)

        self.registrar_log("Painel iniciado.")
        self.carregar_registros()

    # CARTÕES
    def criar_card(self, titulo, valor, cor):
        card = QFrame()
        card.setProperty("class", "card")

        card.setStyleSheet(
            "QFrame { background-color: #111c30; "
            "border: 1px solid #20304a; border-radius: 15px; }"
        )

        caixa = QVBoxLayout(card)
        caixa.setContentsMargins(18, 15, 18, 15)

        nome = QLabel(titulo)
        nome.setStyleSheet(
            "color: #91a2bc; font-size: 9pt; font-weight: 700;"
        )

        numero = QLabel(valor)
        numero.setStyleSheet(
            f"color: {cor}; font-size: 25px; font-weight: 900;"
        )

        caixa.addWidget(nome)
        caixa.addWidget(numero)

        card.valor = numero
        return card

    # LOG COM LIMPEZA AUTOMÁTICA
    def registrar_log(self, mensagem):
        horario = datetime.now().strftime("%H:%M:%S")
        mensagem = str(mensagem).replace("\n", " ")[:120]

        self.logs.append(f"[{horario}] {mensagem}")

        documento = self.logs.document()

        while documento.blockCount() > LIMITE_LOG:
            cursor = self.logs.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

        self.logs.moveCursor(
            self.logs.textCursor().MoveOperation.End
        )

    # CONTROLES
    def iniciar(self):
        if not self.timer.isActive():
            self.timer.start(INTERVALO_ATUALIZACAO)

        self.status.setText("● PAINEL ATUALIZANDO")
        self.status.setProperty("class", "active")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

        self.registrar_log("Atualização automática iniciada.")
        self.carregar_registros()

    def parar(self):
        self.timer.stop()

        self.status.setText("● PAINEL PARADO")
        self.status.setProperty("class", "")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

        self.registrar_log("Atualização automática parada.")

    # CARREGAMENTO E DEDUPLICAÇÃO
    def carregar_registros(self):
        if not DB_PATH.exists():
            self.registrar_log("Banco de dados não encontrado.")
            return

        try:
            with sqlite3.connect(DB_PATH) as conn:
                registros = conn.execute("""
                    SELECT id, grupo, remetente,
                           conteudo, tipo, data_mensagem
                    FROM mensagens
                    ORDER BY id DESC
                """).fetchall()

            grupos_permitidos = set(GRUPOS_MONITORADOS)
            unicos = {}

            for registro in registros:
                (
                    identificador,
                    grupo,
                    remetente,
                    conteudo,
                    tipo,
                    data_mensagem,
                ) = registro

                if grupo not in grupos_permitidos:
                    continue

                if not encontrar_palavras_chave(conteudo):
                    continue

                chave = " ".join(
                    normalizar(conteudo).split()
                )

                if not chave:
                    continue

                data = converter_data(data_mensagem)

                data_ordem = (
                    data.timestamp()
                    if data else float("-inf")
                )

                candidato = (
                    data_ordem,
                    identificador,
                    registro
                )

                atual = unicos.get(chave)

                if atual is None or candidato[:2] > atual[:2]:
                    unicos[chave] = candidato

            registros_filtrados = [
                item[2] for item in unicos.values()
            ]

            registros_filtrados.sort(
                key=lambda registro: (
                    converter_data(registro[5]).timestamp()
                    if converter_data(registro[5])
                    else float("-inf"),
                    registro[0]
                ),
                reverse=True
            )

            hoje = datetime.now().date()

            total = len(registros_filtrados)

            total_hoje = sum(
                1
                for registro in registros_filtrados
                if (
                    converter_data(registro[5])
                    and converter_data(registro[5]).date() == hoje
                )
            )

            registros_exibidos = registros_filtrados[
                :LIMITE_REGISTROS
            ]

            self.tabela.setRowCount(
                len(registros_exibidos)
            )

            for linha, registro in enumerate(
                registros_exibidos
            ):
                for coluna, valor in enumerate(registro):
                    item = QTableWidgetItem(
                        str(valor)
                        if valor is not None
                        else ""
                    )

                    self.tabela.setItem(
                        linha,
                        coluna,
                        item
                    )

            self.total_card.valor.setText(str(total))
            self.hoje_card.valor.setText(str(total_hoje))

            self.ultimo_card.valor.setText(
                datetime.now().strftime("%H:%M:%S")
            )

        except sqlite3.Error as erro:
            self.registrar_log(
                f"Erro no banco: {str(erro)[:100]}"
            )

        except Exception as erro:
            self.registrar_log(
                f"Erro na atualização: {str(erro)[:100]}"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(ESTILO)

    janela = PainelX9()
    janela.show()

    sys.exit(app.exec())
