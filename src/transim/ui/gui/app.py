"""Interfaz gráfica de escritorio con PySide6. ADR-0011.

Requiere el extra ``gui`` (``make install-gui``).

La interfaz solo muestra: los resultados los calculan las unidades de transistores
(``FPAddSub``, ``FPMul``, ``FPDiv``) y la máquina T754. La conversión de texto a bits
usa ``reference.fpu.from_decimal``, igual que el CLI.

Tres pestañas: **Operación** (la FPU vista desde afuera), **Transistores** (por dentro,
en esquema y en silicio) y **Programa** (la FPU dentro de una CPU).
"""

from __future__ import annotations

import sys

from PySide6.QtCore import (
    QByteArray,
    QLibraryInfo,
    QLocale,
    QPointF,
    QRectF,
    QSettings,
    Qt,
    QThreadPool,
    QTranslator,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from transim.metrics.stages import GLUE
from transim.ui.gui import theme
from transim.ui.gui.canvas import pen
from transim.ui.gui.model import (
    Calculation,
    calculate,
    cycle_groups,
    cycles_report,
    instance_toggles,
    parse_operand,
)
from transim.ui.gui.operation_tab import OperationTab
from transim.ui.gui.program_tab import ProgramTab
from transim.ui.gui.transistor_tab import BLOCK_LIMIT, LEAF_CELLS, TransistorTab

TITLE = "TranSim754 — procesador IEEE 754 de transistores simulados"
VERSION = "0.2.0"

HELP = """
<h2>Guía rápida de TranSim754</h2>
<p>TranSim754 es una FPU IEEE 754 (suma, resta, multiplicación y división en binary32 y
binary16) construida con transistores nMOS y pMOS simulados como interruptores.</p>

<h3>Pestaña Operación: la FPU vista desde afuera</h3>
<ul>
<li>Escriba los operandos en decimal (<code>1.5</code>, <code>-2e-3</code>, fracción
<code>1/3</code>, <code>inf</code>, <code>nan</code>) o sus bits en hexadecimal
(<code>0x3FC00000</code>). Debajo de cada campo se ve cómo queda guardado.</li>
<li>Elija la operación y el formato y pulse <b>Calcular</b> (o Enter). El resultado se
verifica contra el modelo de referencia.</li>
<li>En la vista de bits, <b>haga clic en un bit</b> de a o de b para invertirlo: la FPU
recalcula al instante.</li>
<li><b>Ejemplos</b> trae casos notables: redondeo, división por cero, NaN, overflow,
subnormales.</li>
<li>Abajo: ciclos de reloj estimados, actividad por etapa (doble clic para verla en
Transistores), buses internos e historial (doble clic para repetir).</li>
</ul>

<h3>Pestaña Transistores: la FPU por dentro</h3>
<ul>
<li><b>Biblioteca</b>: una celda (INV, NAND2, FA…) con sus entradas. Haga clic en una
entrada (a la izquierda, en la tabla de verdad o en el dibujo) y mire qué canales se
abren y cuáles se cierran; los puntos amarillos son la corriente que carga o descarga
la salida.</li>
<li><b>Última operación</b>: la unidad que hizo el cálculo. La unidad muestra el chip
completo; un bloque, sus celdas; una celda, sus transistores.</li>
<li><b>Esquema</b> dibuja el circuito CMOS: pMOS arriba (a VDD), nMOS abajo (a GND).
Canal continuo: conduce; cortado: no conduce. Fondo verde: el camino que fija la
salida.</li>
<li><b>Silicio</b> dibuja cómo se vería en el chip: difusión p+ (ocre) dentro del pozo
n, difusión n+ (verde), polisilicio (rojo), metal 1 (azul) y metal 2 (violeta). El canal
de un transistor que conduce se ilumina en verde.</li>
<li>El <b>inspector</b> (derecha) muestra el corte transversal del transistor bajo el
ratón: la capa de inversión aparece cuando conduce.</li>
</ul>

<h3>Ratón y teclado en el dibujo</h3>
<table cellspacing="6">
<tr><td>Arrastrar</td><td>mover la vista</td></tr>
<tr><td>Rueda · Ctrl+ / Ctrl−</td><td>acercar y alejar (hacia el puntero)</td></tr>
<tr><td>Pasar el ratón</td><td>resaltar un nodo en todas las celdas a las que llega</td></tr>
<tr><td>Clic</td><td>fijar un transistor · cambiar una entrada de la celda</td></tr>
<tr><td>Doble clic</td><td>entrar en una celda o bloque · acercarse a un transistor ·
en el fondo, ajustar</td></tr>
<tr><td>Clic derecho</td><td>menú (abrir, subir, cambiar de vista, exportar)</td></tr>
<tr><td>Esc · Retroceso · Ctrl+0</td><td>soltar la selección · subir un nivel ·
ajustar</td></tr>
<tr><td>Alt+E · Alt+S</td><td>vista Esquema · vista Silicio</td></tr>
</table>

<h3>Pestaña Programa: la FPU dentro de una CPU</h3>
<p>Escriba o abra un programa <code>.t754</code>, ensámblelo (F5) y ejecútelo paso a paso
(F10) o hasta HALT (F8). El editor marca la instrucción que sigue; los registros que
cambian se resaltan.</p>

<h3>Atajos generales</h3>
<p>Ctrl+1, Ctrl+2, Ctrl+3: pestañas · Ctrl+O: abrir programa · Ctrl+E: exportar el dibujo
· F11: pantalla completa · F1: esta guía.</p>
"""


def app_icon() -> QIcon:
    """Icono de la aplicación: un chip con un transistor."""
    size = 128
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#c9a227"))
    for k in range(5):
        offset = 26 + k * 19
        for x, y, w, h in (
            (offset, 4, 9, 20),
            (offset, 104, 9, 20),
            (4, offset, 20, 9),
            (104, offset, 20, 9),
        ):
            p.drawRoundedRect(QRectF(x, y, w, h), 2, 2)
    p.setBrush(QColor("#2b2f3a"))
    p.drawRoundedRect(QRectF(18, 18, 92, 92), 14, 14)
    p.setPen(pen("#3ddc84", 7))
    p.drawLine(QPointF(70, 40), QPointF(70, 88))
    p.setPen(pen("#e7e9ed", 6))
    p.drawLine(QPointF(56, 44), QPointF(56, 84))
    p.drawLine(QPointF(34, 64), QPointF(56, 64))
    p.setPen(pen("#ff6a5c", 5))
    p.drawLine(QPointF(70, 46), QPointF(92, 46))
    p.drawLine(QPointF(92, 46), QPointF(92, 30))
    p.setPen(pen("#5aa2ff", 5))
    p.drawLine(QPointF(70, 82), QPointF(92, 82))
    p.drawLine(QPointF(92, 82), QPointF(92, 98))
    p.end()
    return QIcon(pm)


class HelpDialog(QDialog):
    """Guía rápida de uso (F1)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guía rápida · TranSim754")
        browser = QTextBrowser()
        browser.setHtml(HELP)
        browser.setOpenExternalLinks(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(browser)
        layout.addWidget(buttons)
        self.resize(720, 720)


class MainWindow(QMainWindow):
    """Ventana principal con las tres pestañas, menús y barra de estado."""

    def __init__(self, *, persist: bool = False) -> None:
        super().__init__()
        self.persist = persist
        self.setWindowTitle(TITLE)
        self.setWindowIcon(app_icon())
        pool = QThreadPool.globalInstance()
        self.operation = OperationTab(pool)
        self.transistors = TransistorTab()
        self.program = ProgramTab(pool)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.addTab(self.operation, "Operación")
        self.tabs.addTab(self.transistors, "Transistores")
        self.tabs.addTab(self.program, "Programa")
        self.tabs.setTabToolTip(
            0, "La FPU vista desde afuera: operandos, resultado, bits, ciclos (Ctrl+1)"
        )
        self.tabs.setTabToolTip(
            1, "La FPU por dentro: esquema y silicio hasta cada transistor (Ctrl+2)"
        )
        self.tabs.setTabToolTip(
            2, "La FPU dentro de una CPU: programas .t754 en la máquina T754 (Ctrl+3)"
        )
        brand = QLabel(
            "<span style='font-size:15px; font-weight:800'>TranSim754</span>"
            "&nbsp;&nbsp;<span style='color:gray'>FPU IEEE 754 de transistores</span>"
        )
        brand.setContentsMargins(12, 0, 16, 0)
        self.tabs.setCornerWidget(brand, Qt.Corner.TopLeftCorner)
        self.setCentralWidget(self.tabs)

        self.operation.calculated.connect(self.transistors.show_calculation)
        self.operation.open_stage.connect(self._open_stage)
        self.transistors.go_operation.connect(self._go_operation)
        for tab in (self.operation, self.transistors, self.program):
            tab.status.connect(self._status)
        self.statusBar().addPermanentWidget(QLabel("F1: guía rápida"))
        self._menus()
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._system_theme_changed)
        screen = QGuiApplication.primaryScreen()
        w, h = 1440, 900
        if screen is not None:
            avail = screen.availableGeometry()
            w, h = min(w, int(avail.width() * 0.94)), min(h, int(avail.height() * 0.92))
        self.resize(w, h)
        if persist:
            self._restore()
        self.operation.a.edit.setFocus()

    # ------------------------------------------------------------------ menús
    def _menus(self) -> None:
        bar = self.menuBar()
        archivo = bar.addMenu("&Archivo")
        self._action(archivo, "Abrir programa .t754…", "Ctrl+O", self._open_program)
        self._action(archivo, "Exportar el dibujo de transistores…", "Ctrl+E", self._export)
        archivo.addSeparator()
        self._action(archivo, "Salir", "Ctrl+Q", self.close)

        ver = bar.addMenu("&Ver")
        for k, name in enumerate(("Operación", "Transistores", "Programa")):
            self._action(
                ver, name, f"Ctrl+{k + 1}", lambda _=False, k=k: self.tabs.setCurrentIndex(k)
            )
        ver.addSeparator()
        tema = ver.addMenu("Tema")
        group = QActionGroup(self)
        self.theme_actions: dict[str, QAction] = {}
        for key, text in (("sistema", "Como el sistema"), ("claro", "Claro"), ("oscuro", "Oscuro")):
            a = QAction(text, self)
            a.setCheckable(True)
            a.triggered.connect(lambda _=False, key=key: self.set_theme(key))
            group.addAction(a)
            tema.addAction(a)
            self.theme_actions[key] = a
        self.theme_choice = "sistema"
        self.theme_actions["sistema"].setChecked(True)
        ver.addSeparator()
        self._action(ver, "Pantalla completa", "F11", self._fullscreen)

        ayuda = bar.addMenu("A&yuda")
        self._action(ayuda, "Guía rápida", "F1", self.show_help)
        self._action(ayuda, "Acerca de TranSim754", None, self._about)

    def _action(self, menu: object, text: str, keys: str | None, fn: object) -> QAction:
        a = QAction(text, self)
        if keys:
            a.setShortcut(QKeySequence(keys))
        a.triggered.connect(fn)
        menu.addAction(a)  # type: ignore[attr-defined]
        return a

    def _status(self, text: str) -> None:
        if text:
            self.statusBar().showMessage(text, 8000)
        else:
            self.statusBar().clearMessage()

    def _open_stage(self, key: str) -> None:
        self.tabs.setCurrentWidget(self.transistors)
        self.transistors.reveal("glue" if key == GLUE else key)

    def _go_operation(self) -> None:
        self.tabs.setCurrentWidget(self.operation)
        self.operation.a.edit.setFocus()

    def _open_program(self) -> None:
        self.tabs.setCurrentWidget(self.program)
        self.program.open_file()

    def _export(self) -> None:
        self.tabs.setCurrentWidget(self.transistors)
        self.transistors.export_dialog()

    def _fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def show_help(self) -> None:
        HelpDialog(self).exec()

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "Acerca de TranSim754",
            f"<h3>TranSim754 {VERSION}</h3>"
            "<p>Procesador con transistores simulados: una FPU IEEE 754 (FADD, FSUB, FMUL, "
            "FDIV en binary32 y binary16) construida desde transistores nMOS y pMOS en un "
            "simulador de nivel de interruptor, y la máquina T754 que la usa.</p>"
            "<p>Héctor David Flores Sánchez<br>SI421U · FIIS · Universidad Nacional de "
            "Ingeniería · 2026-II</p><p>Licencia MIT.</p>",
        )

    # ------------------------------------------------------------------- tema
    def set_theme(self, key: str) -> None:
        """Aplica el tema ``sistema``, ``claro`` u ``oscuro``."""
        if key not in self.theme_actions:
            key = "sistema"
        self.theme_choice = key
        self.theme_actions[key].setChecked(True)
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        dark = theme.system_prefers_dark() if key == "sistema" else key == "oscuro"
        theme.apply(app, theme.DARK if dark else theme.LIGHT)
        for tab in (self.operation, self.transistors, self.program):
            tab.apply_theme()

    def _system_theme_changed(self, *_args: object) -> None:
        if self.theme_choice == "sistema":
            self.set_theme("sistema")

    # ------------------------------------------------------------- persistencia
    def _settings(self) -> QSettings:
        return QSettings("TranSim754", "TranSim754")

    def _restore(self) -> None:
        s = self._settings()
        geometry = s.value("geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        self.set_theme(str(s.value("theme", "sistema")))
        tab = str(s.value("tab", 0))
        if tab.isdigit():
            self.tabs.setCurrentIndex(int(tab))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - API de Qt
        if self.persist:
            s = self._settings()
            s.setValue("geometry", self.saveGeometry())
            s.setValue("theme", self.theme_choice)
            s.setValue("tab", self.tabs.currentIndex())
        super().closeEvent(event)


def create_window(*, persist: bool = False) -> MainWindow:
    """Construye la ventana principal sin mostrarla.

    El título contiene "TranSim754". Separar la construcción de ``main`` permite
    probarla sin bucle de eventos (``QT_QPA_PLATFORM=offscreen``). Con ``persist`` la
    ventana recuerda su tamaño, la pestaña y el tema entre sesiones.
    """
    return MainWindow(persist=persist)


def install_spanish(app: QApplication) -> QTranslator | None:
    """Traduce al español los textos propios de Qt (botones y diálogos estándar)."""
    translator = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale(QLocale.Language.Spanish), "qtbase", "_", path):
        app.installTranslator(translator)
        return translator
    return None


def main() -> int:
    """Abre la ventana principal y entra al bucle de eventos; devuelve el código de salida.

    Ventana: entrada de dos operandos (decimal o hex) y del formato; operación; vista de
    bits signo/exponente/fracción de operandos y resultado; flags; etapas de la
    operación (buses ``dbg_``); ciclos de reloj estimados; conteo de transistores y
    conmutaciones; pestaña de transistores que baja de los bloques de la unidad hasta
    cada nMOS y pMOS con su estado, en esquema y en silicio; pestaña para ejecutar
    programas ``.t754`` paso a paso.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    if isinstance(app, QApplication):
        app.setApplicationName("TranSim754")
        install_spanish(app)
        app.setWindowIcon(app_icon())
        font = QFont(app.font())
        if font.pointSizeF() < 9.5:
            font.setPointSizeF(9.5)
            app.setFont(font)
        theme.apply(app, theme.DARK if theme.system_prefers_dark() else theme.LIGHT)
    window = create_window(persist=True)
    window.show()
    return int(app.exec())


__all__ = [
    "BLOCK_LIMIT",
    "LEAF_CELLS",
    "TITLE",
    "Calculation",
    "MainWindow",
    "OperationTab",
    "ProgramTab",
    "TransistorTab",
    "calculate",
    "create_window",
    "cycle_groups",
    "cycles_report",
    "instance_toggles",
    "main",
    "parse_operand",
]
