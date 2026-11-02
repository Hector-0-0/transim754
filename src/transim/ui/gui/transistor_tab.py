"""Pestaña Transistores: el microscopio de la FPU.

A la izquierda se elige qué mirar: una celda de la biblioteca (con sus entradas y su
tabla de verdad) o la jerarquía de la unidad que hizo la última operación. En el centro
se dibuja en dos vistas: **Esquema** (el circuito CMOS) y **Silicio** (cómo se vería en
el chip, hasta la unidad completa). A la derecha, el inspector describe lo que hay bajo
el ratón y muestra el corte transversal del transistor elegido.

Ratón: arrastrar mueve la vista, la rueda acerca y aleja, pasar por un cable resalta su
nodo, un clic fija un transistor (o cambia una entrada de la celda), el doble clic
entra en una celda o en un bloque y el clic derecho abre un menú.
"""

from __future__ import annotations

import math
from functools import cache

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from transim.cells.library import CELLS
from transim.core.engine_switch import SwitchEngine
from transim.core.netlist import Instance, Netlist
from transim.core.node import NodeKind
from transim.core.signals import Logic
from transim.core.transistor import Conduction, TransistorType
from transim.core.unit import HardwareUnit
from transim.metrics.critical_path import cell_depth
from transim.metrics.stages import GLUE, STAGE_NAMES
from transim.ui.gui import gates as gl
from transim.ui.gui import theme as th
from transim.ui.gui.bitgrid import Grid, grid
from transim.ui.gui.canvas import (
    LAYER_COLOR,
    LAYER_NAMES,
    TOGGLE_LAYERS,
    BlockHit,
    CanvasView,
    CellItem,
    CircuitScene,
    GateItem,
    Hit,
    SchematicItem,
    logic_text,
)
from transim.ui.gui.circuit import Binding, active_path, bind_cell, bind_instance
from transim.ui.gui.cross_section import CrossSection, Device, explain
from transim.ui.gui.floorplan import Tile
from transim.ui.gui.model import Calculation, instance_toggles, unit_title
from transim.ui.gui.propagation import Replay, ReplayReader
from transim.ui.gui.steps import Step, cell_steps, input_ids
from transim.ui.gui.widgets import Segmented, card, hint, stage_color, thousands

BLOCK_LIMIT = 2500
TIME_MS = 140
"""Duración de cada retardo de celda al reproducir la propagación."""
GROUP_CELLS = 24
"""Con más celdas sueltas que esto, el plano de un bloque las agrupa por tipo."""
"""Transistores máximos de un bloque para dibujar su esquema completo."""

DESCRIPTIONS = {
    "INV": "y = ¬a",
    "NAND2": "y = ¬(a·b)",
    "NOR2": "y = ¬(a + b)",
    "AND2": "y = a·b",
    "OR2": "y = a + b",
    "XOR2": "y = a ⊕ b",
    "XNOR2": "y = ¬(a ⊕ b)",
    "MUX2": "y = a si s = 0; b si s = 1",
    "HA": "s = a ⊕ b, cout = a·b",
    "FA": "s = a ⊕ b ⊕ cin, cout = mayoría",
    "DLATCH": "q sigue a d mientras clk = 1",
    "DFF": "q ← d en el flanco de subida de clk",
}
"""Función lógica de cada celda de la biblioteca."""

LEAF_CELLS = [name for name, build in CELLS.items() if not build().instances]
"""Celdas primitivas de la biblioteca (sin sub-instancias)."""


@cache
def truth_table(name: str) -> list[tuple[dict[str, int], dict[str, Logic]]]:
    """Tabla de verdad de una celda combinacional, calculada con sus transistores."""
    cell = CELLS[name]()
    engine = SwitchEngine(cell)
    ports = list(cell.inputs)
    rows = []
    for k in range(1 << len(ports)):
        inputs = {p: (k >> (len(ports) - 1 - i)) & 1 for i, p in enumerate(ports)}
        engine.set_inputs(inputs)
        rows.append((inputs, {p: engine.read(p) for p in cell.outputs}))
    return rows


def _v(value: Logic) -> str:
    return logic_text(value)


def _capital(text: str) -> str:
    """Primera letra en mayúscula: «sumar/restar mantisas» → «Sumar/restar mantisas»."""
    return text[:1].upper() + text[1:]


def _children(item: QTreeWidgetItem) -> list[QTreeWidgetItem]:
    """Hijos de un elemento del árbol."""
    return [c for k in range(item.childCount()) if (c := item.child(k)) is not None]


# ------------------------------------------------------------------ biblioteca
class LibraryPanel(QWidget):
    """Lista de celdas, entradas, salidas y tabla de verdad."""

    changed = Signal()
    """Cambió la celda o una entrada."""

    def __init__(self) -> None:
        super().__init__()
        self.cells = QListWidget()
        self.cells.setToolTip("Celdas de la biblioteca (capa L1)")
        for name, build in CELLS.items():
            n = len(build().transistors)
            item = QListWidgetItem(f"{name}  ({n} transistores)\n{DESCRIPTIONS.get(name, '')}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip((build.__doc__ or "").strip().split("\n")[0])
            self.cells.addItem(item)
        self.cells.currentItemChanged.connect(self._cell_changed)
        self.inputs_box = QHBoxLayout()
        self.inputs_box.setSpacing(6)
        self.step = QPushButton("Siguiente combinación ▸")
        self.step.setToolTip("Recorre las combinaciones de entrada en orden binario")
        self.step.clicked.connect(self.next_combination)
        self.outputs = QLabel()
        self.outputs.setTextFormat(Qt.TextFormat.RichText)
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setToolTip("Clic en una fila para aplicar esas entradas")
        self.table.cellClicked.connect(self._row_clicked)
        self.table_note = hint("")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(self.cells, 3)
        box, box_layout = card("Entradas y salidas")
        box_layout.addLayout(self.inputs_box)
        box_layout.addWidget(self.step)
        box_layout.addWidget(self.outputs)
        layout.addWidget(box)
        tt, tt_layout = card("Tabla de verdad")
        tt_layout.addWidget(self.table, 1)
        tt_layout.addWidget(self.table_note)
        layout.addWidget(tt, 3)
        self.cells.setMinimumHeight(150)
        self.table.setMinimumHeight(90)
        self.buttons: dict[str, QPushButton] = {}
        self.cell: Netlist = CELLS["INV"]()
        self.engine = SwitchEngine(self.cell)
        self.name = "INV"

    # ------------------------------------------------------------- celda
    def select(self, name: str) -> None:
        for k in range(self.cells.count()):
            if self.cells.item(k).data(Qt.ItemDataRole.UserRole) == name:
                self.cells.setCurrentRow(k)
                return

    def _cell_changed(self, item: QListWidgetItem | None, _prev: object = None) -> None:
        if item is None:
            return
        self.name = str(item.data(Qt.ItemDataRole.UserRole))
        self.cell = CELLS[self.name]()
        self.engine = SwitchEngine(self.cell)
        while self.inputs_box.count():
            taken = self.inputs_box.takeAt(0)
            w = taken.widget() if taken is not None else None
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.buttons = {}
        for port in self.cell.inputs:
            b = QPushButton()
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(f"Entrada {port}: clic para cambiarla")
            b.toggled.connect(self._apply)
            self.inputs_box.addWidget(b)
            self.buttons[port] = b
        self.inputs_box.addStretch(1)
        sequential = self.cell.sequential
        self.step.setText("Pulso de reloj ⏵" if sequential else "Siguiente combinación ▸")
        self.step.setToolTip(
            "Sube y baja clk para capturar d"
            if sequential
            else "Recorre las combinaciones de entrada"
        )
        self._fill_table()
        self._apply()

    def _fill_table(self) -> None:
        ports_in, ports_out = list(self.cell.inputs), list(self.cell.outputs)
        if self.cell.sequential:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.table.hide()
            self.table_note.setText(
                "Celda secuencial: su salida depende de lo que guardó. Ponga d y dé un "
                "pulso de reloj (o cambie clk) para capturarlo."
            )
            return
        self.table.show()
        self.table_note.setText("")
        rows = truth_table(self.name)
        self.table.setColumnCount(len(ports_in) + len(ports_out))
        self.table.setHorizontalHeaderLabels(ports_in + ports_out)
        self.table.setRowCount(len(rows))
        for r, (ins, outs) in enumerate(rows):
            for c, p in enumerate(ports_in):
                self.table.setItem(r, c, self._cell_item(str(ins[p])))
            for c, p in enumerate(ports_out, len(ports_in)):
                item = self._cell_item(_v(outs[p]))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                self.table.setItem(r, c, item)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.resizeRowsToContents()

    @staticmethod
    def _cell_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    # ------------------------------------------------------------ entradas
    def inputs(self) -> dict[str, int]:
        return {p: int(b.isChecked()) for p, b in self.buttons.items()}

    def toggle(self, port: str) -> None:
        if port in self.buttons:
            self.buttons[port].toggle()

    def set_inputs(self, values: dict[str, int]) -> None:
        for p, b in self.buttons.items():
            b.blockSignals(True)
            b.setChecked(bool(values.get(p, 0)))
            b.blockSignals(False)
        self._apply()

    def next_combination(self) -> None:
        if self.cell.sequential:
            if "clk" in self.buttons:
                self.buttons["clk"].setChecked(True)
                self.buttons["clk"].setChecked(False)
            return
        ports = list(self.buttons)
        value = sum(self.inputs()[p] << (len(ports) - 1 - i) for i, p in enumerate(ports))
        value = (value + 1) % (1 << len(ports))
        self.set_inputs({p: (value >> (len(ports) - 1 - i)) & 1 for i, p in enumerate(ports)})

    def _row_clicked(self, row: int, _col: int) -> None:
        self.set_inputs(truth_table(self.name)[row][0])

    def _apply(self) -> None:
        self.before = {n.id: self.engine.value(n) for n in self.cell.nodes}
        self.engine.set_inputs(self.inputs())
        self.refresh_labels()
        self.changed.emit()

    def refresh_labels(self) -> None:
        t = th.current()
        for p, b in self.buttons.items():
            v = Logic.ONE if b.isChecked() else Logic.ZERO
            color = t.one if v is Logic.ONE else t.zero
            b.setText(f"{p} = {_v(v)}")
            b.setStyleSheet(
                f"QPushButton {{ color: {color}; border: 1.5px solid {color}; font-weight: 700;"
                f" padding: 5px 12px; border-radius: 7px; }}"
                f"QPushButton:checked {{ background: {color}; color: #ffffff; }}"
            )
        parts = []
        for p in self.cell.outputs:
            v = self.engine.read(p)
            parts.append(
                f"<span style='font-size:15px; font-weight:700; color:{t.logic(v).name()}'>"
                f"{p} = {_v(v)}</span>"
            )
        self.outputs.setText("&nbsp;&nbsp;&nbsp;".join(parts))
        if not self.cell.sequential:
            ports = list(self.buttons)
            value = sum(self.inputs()[p] << (len(ports) - 1 - i) for i, p in enumerate(ports))
            self.table.blockSignals(True)
            self.table.selectRow(value)
            self.table.blockSignals(False)


# ------------------------------------------------------------------ jerarquía
class HierarchyPanel(QWidget):
    """Árbol de la unidad de la última operación, con buscador."""

    go_operation = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.header = QLabel()
        self.header.setWordWrap(True)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar instancia o celda (p. ej. mux12, FA, round)…")
        self.search.setClearButtonEnabled(True)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Parte", "Transistores", "Cambios"])
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.headerItem().setToolTip(2, "Nodos que cambiaron en la última operación")
        self.tree.setToolTip(
            "La unidad muestra el chip completo; un bloque, sus celdas; una celda, sus "
            "transistores."
        )
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.addStretch(1)
        msg = QLabel(
            "Todavía no hay una operación.\n\nCalcule una en la pestaña Operación y aquí "
            "podrá recorrer su hardware: del chip a los bloques, a las celdas y a cada "
            "transistor."
        )
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        go = QPushButton("Ir a Operación")
        go.clicked.connect(self.go_operation)
        empty_layout.addWidget(msg)
        empty_layout.addWidget(go, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch(2)
        full = QWidget()
        full_layout = QVBoxLayout(full)
        full_layout.setContentsMargins(0, 0, 0, 0)
        full_layout.addWidget(self.header)
        full_layout.addWidget(self.search)
        full_layout.addWidget(self.tree, 1)
        self.stack = QStackedWidget()
        self.stack.addWidget(empty)
        self.stack.addWidget(full)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(self.stack)


# ------------------------------------------------------------------ inspector
class Inspector(QFrame):
    """Lo que hay bajo el ratón o elegido: transistor (con su corte), nodo o celda."""

    open_cell = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        self.title = QLabel("<b>Inspector</b>")
        self.title.setWordWrap(True)
        self.body = QLabel(
            "Pase el ratón por un transistor, un cable o una celda. Un clic fija el transistor."
        )
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.section = CrossSection()
        self.explain = QLabel()
        self.explain.setWordWrap(True)
        self.explain.setObjectName("hint")
        self.open_button = QPushButton("Abrir esta celda")
        self.open_button.clicked.connect(self.open_cell)
        self.open_button.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        label = QLabel("QUÉ ESTÁ PASANDO")
        label.setObjectName("cardTitle")
        layout.addWidget(label)
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        layout.addWidget(self.section)
        layout.addWidget(self.explain)
        layout.addWidget(self.open_button)
        layout.addStretch(1)
        self.setMinimumWidth(290)


# ------------------------------------------------------------------ pestaña
LAYER_SHORT = {
    "nwell": "Pozo n",
    "pdiff": "Difusión p",
    "ndiff": "Difusión n",
    "poly": "Polisilicio",
    "contact": "Contactos",
    "metal1": "Metal 1",
    "via": "Vías",
    "metal2": "Metal 2",
}


class TransistorTab(QWidget):
    """Microscopio: de los bloques de una unidad hasta cada transistor."""

    go_operation = Signal()
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.scene = CircuitScene()
        self.view = CanvasView(self.scene)
        self.unit: HardwareUnit | None = None
        self.calc: Calculation | None = None
        self._children: dict[str | None, list[Instance]] = {}
        self._instances: dict[str, Instance] = {}
        self._target: tuple[str, str] = ("library", "INV")
        self._pending: Calculation | None = None

        # Izquierda
        self.library = LibraryPanel()
        self.library.changed.connect(self._library_changed)
        self.hierarchy = HierarchyPanel()
        self.hierarchy.go_operation.connect(self.go_operation)
        self.tree = self.hierarchy.tree
        self.tree.itemExpanded.connect(self._expand)
        self.tree.currentItemChanged.connect(self._select)
        self.hierarchy.search.textChanged.connect(self._search)
        self.sources = QTabWidget()
        self.sources.setObjectName("subtabs")
        self.sources.addTab(self.library, "Biblioteca")
        self.sources.addTab(self.hierarchy, "Última operación")
        self.sources.currentChanged.connect(self._source_changed)

        # Centro: barra
        self.breadcrumb = QLabel()
        self.breadcrumb.setObjectName("breadcrumb")
        self.breadcrumb.setTextFormat(Qt.TextFormat.RichText)
        self.breadcrumb.linkActivated.connect(self._crumb)
        self.mode = Segmented(
            [
                (
                    "gates",
                    "Compuertas",
                    "Qué función lógica calcula cada etapa CMOS, con sus valores",
                ),
                (
                    "schematic",
                    "Transistores",
                    "Esquema eléctrico CMOS: pull-up de pMOS y pull-down de nMOS",
                ),
                (
                    "silicon",
                    "Silicio",
                    "Cómo se vería en el chip: difusión, polisilicio y metal",
                ),
            ]
        )
        self.mode.changed.connect(self._mode_chosen)
        self._preferred = "gates"
        self._tips = {k: self.mode.buttons[k].toolTip() for k in ("gates", "schematic")}
        self.paths = self._toggle(
            "Camino activo",
            False,
            "Fondo verde en los transistores que fijan el valor de cada salida",
        )
        self.toggles = self._toggle(
            "Conmutaciones",
            False,
            "Resalta en naranja los nodos que cambiaron en la última operación",
        )
        self.heat = self._toggle(
            "Mapa de actividad",
            False,
            "Tiñe cada celda según cuánto conmutó en la última operación",
        )
        self.by_value = self._toggle(
            "Color por valor",
            False,
            "En el silicio, pinta el metal y el polisilicio con el valor lógico de su nodo",
        )
        self.zoom_label = QToolButton()
        self.zoom_label.setText("100 %")
        self.zoom_label.setToolTip("Zoom (clic: tamaño real)")
        self.zoom_label.clicked.connect(self.view.actual_size)
        self.view.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z * 100:.0f} %"))
        zoom_out = self._tool("−", "Alejar", self.view.zoom_out)
        zoom_in = self._tool("+", "Acercar", self.view.zoom_in)
        fit = self._tool("Ajustar", "Ver todo el dibujo", lambda: self.view.fit())
        self.view_menu = QMenu(self)
        for action in (self.paths, self.toggles, self.heat, self.by_value):
            self.view_menu.addAction(action)
        self.view_menu.addSeparator()
        export_action = QAction("Exportar imagen…", self)
        export_action.triggered.connect(self.export_dialog)
        self.view_menu.addAction(export_action)
        self.view_button = QToolButton()
        self.view_button.setText("Ver ▾")
        self.view_button.setToolTip("Opciones del dibujo: camino activo, conmutaciones, actividad")
        self.view_button.setMenu(self.view_menu)
        self.view_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.panel_button = QToolButton()
        self.panel_button.setText("☰")
        self.panel_button.setCheckable(True)
        self.panel_button.setToolTip("Mostrar u ocultar la biblioteca y las partes de la unidad")
        self.panel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.panel_button.clicked.connect(self._panel_clicked)
        self._panel_choice: bool | None = None
        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addWidget(self.panel_button)
        bar.addWidget(self.mode)
        bar.addStretch(1)
        for w in (self.view_button, zoom_out, self.zoom_label, zoom_in, fit):
            bar.addWidget(w)
        # Capas del silicio: solo se ven en esa vista; ocultar una deja ver las demás.
        self.layer_row = QWidget()
        lr = QHBoxLayout(self.layer_row)
        lr.setContentsMargins(0, 0, 0, 0)
        lr.setSpacing(12)
        caption = QLabel("Capas:")
        caption.setObjectName("hint")
        lr.addWidget(caption)
        self.layer_boxes: dict[str, QCheckBox] = {}
        for layer in TOGGLE_LAYERS:
            box = QCheckBox(LAYER_SHORT[layer])
            box.setChecked(True)
            box.setToolTip(f"Mostrar u ocultar: {LAYER_NAMES[layer]}")
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.toggled.connect(lambda on, k=layer: self._layer_toggled(k, on))
            self.layer_boxes[layer] = box
            lr.addWidget(box)
        lr.addStretch(1)
        self.layer_row.setVisible(False)
        # Paso a paso del esquema: una etapa a la vez, en orden de dependencia.
        self.step_row = QWidget()
        sr = QHBoxLayout(self.step_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(6)
        step_caption = QLabel("Paso a paso:")
        step_caption.setObjectName("hint")
        sr.addWidget(step_caption)
        self.step_back = self._tool("◀ Anterior", "Etapa anterior", lambda: self._step_move(-1))
        self.step_next = self._tool(
            "Siguiente ▶",
            "Siguiente etapa, en el orden en que sus entradas ya tienen valor",
            lambda: self._step_move(1),
        )
        self.step_all = self._tool(
            "Ver todo", "Quitar el filtro y ver todas las etapas", self._step_reset
        )
        self.step_text = QLabel()
        self.step_text.setObjectName("hint")
        self.step_text.setWordWrap(True)
        for w in (self.step_back, self.step_next, self.step_all):
            sr.addWidget(w)
        sr.addWidget(self.step_text, 1)
        self.step_row.setVisible(False)
        # Propagación con retardo unitario (ADR-0018), sobre la rejilla de un bloque.
        self.time_t: int = 0
        self._worst = 0
        self.time_row = QWidget()
        tr_layout = QHBoxLayout(self.time_row)
        tr_layout.setContentsMargins(0, 0, 0, 0)
        tr_layout.setSpacing(6)
        caption2 = QLabel("Propagación:")
        caption2.setObjectName("hint")
        tr_layout.addWidget(caption2)
        self.time_first = self._tool(
            "⏮", "Al instante 0: recién llegan las entradas", lambda: self.set_time(0)
        )
        self.time_back = self._tool("◀", "Un retardo atrás", lambda: self.set_time(self.time_t - 1))
        self.time_next = self._tool(
            "▶", "Un retardo adelante", lambda: self.set_time(self.time_t + 1)
        )
        self.time_play = self._tool(
            "⏵ Reproducir", "Ver cómo se propaga el cambio", self.toggle_time
        )
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimumWidth(140)
        self.time_slider.valueChanged.connect(self.set_time)
        self.time_text = QLabel()
        self.time_text.setObjectName("hint")
        self.time_text.setWordWrap(True)
        for w in (self.time_first, self.time_back, self.time_next, self.time_play):
            tr_layout.addWidget(w)
        tr_layout.addWidget(self.time_slider, 1)
        tr_layout.addWidget(self.time_text, 2)
        self.time_row.setVisible(False)
        self.replay: Replay | None = None
        self._time_timer = QTimer(self)
        self._time_timer.setInterval(TIME_MS)
        self._time_timer.timeout.connect(self._time_tick)
        self.steps: list[Step] = []
        self.step_pos = -1
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setObjectName("hint")
        self.legend = QLabel()
        self.legend.setWordWrap(True)
        self.legend.setObjectName("hint")
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        cl.addWidget(self.breadcrumb)
        cl.addLayout(bar)
        cl.addWidget(self.layer_row)
        cl.addWidget(self.step_row)
        cl.addWidget(self.time_row)
        cl.addWidget(self.info)
        frame = QFrame()
        frame.setObjectName("card")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(1, 1, 1, 1)
        fl.addWidget(self.view)
        cl.addWidget(frame, 1)
        cl.addWidget(self.legend)

        # Derecha
        self.inspector = Inspector()
        self.inspector.open_cell.connect(self._open_inspected)
        self._inspected: Hit | None = None
        self._block_inspected: str | None = None
        self._tile_members: dict[str, list[Instance]] = {}
        """Celdas de cada región agrupada del plano (por la clave de la región)."""

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.sources)
        split.addWidget(center)
        split.addWidget(self.inspector)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        self.sources.setMinimumWidth(270)
        split.setSizes([330, 860, 320])
        split.setChildrenCollapsible(False)
        self.splitter = split
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.addWidget(split)

        self.scene.hovered.connect(self._hover)
        self.view.clicked.connect(self._clicked)
        self.view.double_clicked.connect(self._double_clicked)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.presentation = False
        self.shortcuts: list[QShortcut] = []
        for keys, fn in (
            ("Escape", self._clear_selection),
            ("Backspace", self._go_up),
            ("Ctrl+0", lambda: self.view.fit()),
            ("Ctrl++", self.view.zoom_in),
            ("Ctrl+=", self.view.zoom_in),
            ("Ctrl+-", self.view.zoom_out),
            ("Alt+C", lambda: self._set_mode("gates")),
            ("Alt+E", lambda: self._set_mode("schematic")),
            ("Alt+T", lambda: self._set_mode("schematic")),
            ("Ctrl+F", self.open_search),
            ("Alt+S", lambda: self._set_mode("silicon")),
        ):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
            if "+" in keys:  # atajos con Ctrl o Alt; Esc y Retroceso siempre sirven
                self.shortcuts.append(sc)
        self.library.select("INV")

    def set_presentation(self, on: bool) -> None:
        """Modo exposición (ADR-0019): sin el panel de detalle, la línea de descripción ni
        las casillas de capas, y sin atajos con Ctrl o Alt. Nada se elimina."""
        self.presentation = on
        self.inspector.setVisible(not on)
        self.info.setVisible(not on)
        for sc in self.shortcuts:
            sc.setEnabled(not on)
        self._update_controls()

    # ------------------------------------------------------------- controles
    def _toggle(self, text: str, checked: bool, tip: str) -> QAction:
        action = QAction(text, self)
        action.setCheckable(True)
        action.setChecked(checked)
        action.setToolTip(tip)
        action.setStatusTip(tip)
        action.toggled.connect(self._options_changed)
        return action

    def _tool(self, text: str, tip: str, fn: object) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("tool")
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(fn)
        return b

    def _mode_chosen(self, mode: str) -> None:
        """El usuario eligió una vista: se recuerda para los próximos dibujos."""
        self._preferred = mode
        self.redraw()

    def _allow_schematic(self, allowed: bool, why: str = "", gates: bool | None = None) -> bool:
        """Habilita o no las vistas Compuertas y Transistores y elige la del próximo dibujo.

        ``gates`` habilita Compuertas aparte (la rejilla de un bloque no tiene límite).

        Returns:
            True si se pasó a Silicio porque la vista elegida no está disponible.
        """
        ok = {"gates": allowed if gates is None else gates, "schematic": allowed, "silicon": True}
        for key in ("gates", "schematic"):
            self.mode.set_option_enabled(key, ok[key], self._tips[key] if ok[key] else why)
        wanted = self._preferred if ok[self._preferred] else "silicon"
        self.mode.set_value(wanted)
        return not ok[self._preferred]

    def _set_mode(self, mode: str) -> None:
        if self.mode.buttons[mode].isEnabled():
            self.mode.set_value(mode, emit=True)

    @property
    def silicon(self) -> bool:
        return self.mode.value() == "silicon"

    @property
    def gates(self) -> bool:
        return self.mode.value() == "gates"

    # ----------------------------------------------------------- panel izquierdo
    def _panel_clicked(self, shown: bool) -> None:
        self._panel_choice = shown
        self._update_panel()

    def _update_panel(self) -> None:
        """El panel se ve en la biblioteca; con una operación, solo si se pidió."""
        shown = self._panel_choice
        if shown is None:
            shown = self._target[0] == "library"
        self.sources.setVisible(shown)
        self.panel_button.setChecked(shown)

    def open_search(self) -> None:
        """Ctrl+F: muestra el panel y pone el foco en el buscador."""
        self._panel_choice = True
        self._update_panel()
        if self.unit is not None:
            self.sources.setCurrentIndex(1)
            self.hierarchy.search.setFocus()
            self.hierarchy.search.selectAll()

    def _options_changed(self) -> None:
        self.scene.show_paths = self.paths.isChecked()
        self.scene.show_toggles = self.toggles.isChecked()
        self.scene.color_by_value = self.by_value.isChecked()
        self._apply_heat()
        self.scene.refresh()
        self._update_controls()

    def _update_controls(self) -> None:
        op = self._target[0] != "library"
        self.paths.setEnabled(self.mode.value() == "schematic")
        self.toggles.setEnabled(op and not self.silicon)
        self.heat.setEnabled(op)
        cell_silicon = self.silicon and not self.scene.blocks
        self.by_value.setEnabled(cell_silicon)
        self.layer_row.setVisible(cell_silicon and not self.presentation)

    def _steps_refresh(self) -> None:
        """Prepara los pasos de la celda dibujada (solo si es un esquema de una celda)."""
        cells = self.scene.cells
        single = len(cells) == 1 and isinstance(cells[0], SchematicItem | GateItem)
        self.steps = cell_steps(cells[0].binding.netlist) if single else []
        if self.step_pos >= len(self.steps):
            self.step_pos = -1
        self._apply_step()

    def _apply_step(self) -> None:
        """Resalta las etapas hasta el paso elegido y atenúa el resto."""
        n = len(self.steps)
        shown = bool(n) and not self.silicon
        self.step_row.setVisible(shown)
        if not shown:
            self.scene.step_filter = None
            return
        cell = self.scene.cells[0]
        if self.step_pos < 0:
            self.scene.step_filter = None
            self.step_text.setText(f"{n} etapas")
        else:
            done = self.steps[: self.step_pos + 1]
            transistors = frozenset().union(*(st.transistors for st in done))
            nodes = set(input_ids(cell.binding.netlist)) | {0, 1}
            for st in done:
                nodes.update(st.outputs)
            self.scene.step_filter = (transistors, frozenset(nodes))
            step = self.steps[self.step_pos]
            gate = next(
                (
                    g
                    for g in gl.cell_gates(cell.binding.netlist)
                    if set(g.transistors) == set(step.transistors)
                ),
                None,
            )
            if gate is not None:
                said = gl.explain(gate, cell.binding.netlist, cell.value_fn())
            else:
                said = f"{step.label} = {logic_text(cell.value_fn()(step.outputs[0]))}"
            self.step_text.setText(f"<b>Etapa {self.step_pos + 1} de {n}</b>: {said}")
        self.step_back.setEnabled(self.step_pos >= 0)
        self.step_next.setEnabled(self.step_pos < n - 1)
        self.step_all.setEnabled(self.step_pos >= 0)
        self.scene.refresh()

    def _step_move(self, delta: int) -> None:
        self.step_pos = max(-1, min(len(self.steps) - 1, self.step_pos + delta))
        self._apply_step()

    def _step_reset(self) -> None:
        self.step_pos = -1
        self._apply_step()

    # ------------------------------------------------------------ propagación
    def _grid_shown(self) -> bool:
        return self.gates and self._target[0] == "instance" and self._many()

    def _time_refresh(self) -> None:
        """Prepara la propagación de la última operación si se dibuja una rejilla."""
        self._time_timer.stop()
        self.time_play.setText("⏵ Reproducir")
        shown = self._grid_shown() and self.calc is not None
        self.time_row.setVisible(shown)
        if not shown or self.calc is None:
            self.replay = None
            return
        self.replay = self.calc.propagation()
        if not self.replay.valid:
            for w in (self.time_first, self.time_back, self.time_next, self.time_play):
                w.setEnabled(False)
            self.time_slider.setEnabled(False)
            self.time_text.setText(f"No se puede reproducir: {self.replay.reason}.")
            return
        for w in (self.time_first, self.time_back, self.time_next, self.time_play):
            w.setEnabled(True)
        self.time_slider.setEnabled(True)
        if self.unit is not None:
            self._worst = cell_depth(self.unit.netlist)
        self.time_slider.blockSignals(True)
        self.time_slider.setRange(0, self.replay.length)
        self.time_slider.blockSignals(False)
        self.set_time(self.replay.length)

    def set_time(self, t: int) -> None:
        """Muestra la rejilla en el instante ``t`` (en retardos de celda)."""
        r = self.replay
        if r is None or not r.valid or self.unit is None:
            return
        t = max(0, min(r.length, t))
        self.time_t = t
        if self.time_slider.value() != t:
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(t)
            self.time_slider.blockSignals(False)
        self.scene.values = ReplayReader(r.values_at(t), self.unit.engine)
        self.scene.flash_cells = r.cells_changed[t - 1] if t > 0 else frozenset()
        self.scene.refresh()
        paths = frozenset(c.binding.path for c in self.scene.cells)
        last = r.last_change(paths)
        worst = self._worst
        moving = len(self.scene.flash_cells & paths)
        self.time_text.setText(
            f"<b>Retardo {t} de {r.length}</b>. Este bloque termina en el retardo {last}."
        )
        self.time_text.setToolTip(
            f"En este instante cambian {moving} celdas. El peor caso de la unidad es de "
            f"{worst} retardos (su camino crítico)."
        )
        self.time_back.setEnabled(t > 0)
        self.time_next.setEnabled(t < r.length)

    def toggle_time(self) -> None:
        if self._time_timer.isActive():
            self._time_timer.stop()
            self.time_play.setText("⏵ Reproducir")
            return
        if self.replay is None or not self.replay.valid:
            return
        if self.time_t >= self.replay.length:
            self.set_time(0)
        self._time_timer.start()
        self.time_play.setText("⏸ Pausa")

    def _time_tick(self) -> None:
        if self.replay is None or self.time_t >= self.replay.length:
            self._time_timer.stop()
            self.time_play.setText("⏵ Reproducir")
            return
        self.set_time(self.time_t + 1)

    def show_propagation(self, path: str, play: bool = True) -> None:
        """Abre la rejilla del bloque ``path`` y, si ``play``, reproduce su propagación."""
        self.reveal(path)
        if self.mode.buttons["gates"].isEnabled() and not self.gates:
            self._set_mode("gates")
        if play and self.time_row.isVisible() and self.replay is not None and self.replay.valid:
            self.set_time(0)
            self.toggle_time()

    def _layer_toggled(self, layer: str, shown: bool) -> None:
        """Muestra u oculta una capa del silicio y repinta."""
        if shown:
            self.scene.visible_layers.add(layer)
        else:
            self.scene.visible_layers.discard(layer)
        self.scene.refresh()

    def _apply_heat(self) -> None:
        if not (self.heat.isChecked() and self.heat.isEnabled() and self.unit is not None):
            self.scene.set_heat(None)
            self.scene.set_block_heat(None)
            return
        engine = self.unit.engine
        if self.scene.blocks:
            per = {b: self._tile_toggles(b.tile.key) for b in self.scene.blocks}
            top_b = max(per.values(), default=0) or 1
            self.scene.set_block_heat(lambda b: math.sqrt(per[b] / top_b))
            return
        toggles = engine.node_toggles

        def driven(item: CellItem) -> int:
            nodes = {
                n.id
                for t in item.binding.transistors
                for n in (t.source, t.drain)
                if not n.is_source
            }
            return sum(toggles[i] for i in nodes)

        counts = {item: driven(item) for item in self.scene.cells}
        top = max(counts.values(), default=0) or 1
        self.scene.set_heat(lambda item: math.sqrt(counts[item] / top))

    def _tile_toggles(self, key: str) -> int:
        """Conmutaciones de una región del plano: un bloque o un grupo de celdas."""
        if self.unit is None:
            return 0
        engine = self.unit.engine
        members = self._tile_members.get(key)
        if members is not None:
            return sum(instance_toggles(engine, c) for c in members)
        return instance_toggles(engine, self._instances[key])

    def _tiles(self, children: list[Instance], top_level: bool) -> tuple[list[Tile], list[str]]:
        """Regiones del plano para ``children`` y su subtítulo.

        Los sub-bloques son una región cada uno. Las celdas sueltas también, salvo que sean
        muchas: entonces se agrupan por tipo («OR2 × 120») y el doble clic abre la primera.
        """
        tiles: list[Tile] = []
        subs: list[str] = []
        leaves = [c for c in children if c.is_leaf]
        group = len(leaves) > GROUP_CELLS
        for inst in children:
            if group and inst.is_leaf:
                continue
            name = inst.path.rsplit(".", 1)[-1]
            if top_level and name in STAGE_NAMES:
                title = f"{STAGE_NAMES[name][:1].upper()}{STAGE_NAMES[name][1:]}"
                color = stage_color(name).name()
            else:
                title = f"{name} ({inst.definition.name})"
                color = stage_color(inst.definition.name).name()
            tiles.append(Tile(inst.path, title, len(inst.transistors), color))
            subs.append(f"{thousands(len(inst.transistors))} transistores")
        if group:
            kinds: dict[str, list[Instance]] = {}
            for c in leaves:
                kinds.setdefault(c.definition.name, []).append(c)
            for kind, cells in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
                key = cells[0].path
                self._tile_members[key] = cells
                n = sum(len(c.transistors) for c in cells)
                tiles.append(Tile(key, f"{kind} × {len(cells)}", n, stage_color(kind).name()))
                subs.append(f"{thousands(n)} transistores")
        return tiles, subs

    def _legend(self) -> None:
        """Leyenda corta: solo los colores, sin explicaciones largas."""
        t = th.current()
        gap = "&nbsp;" * 5

        def swatch(color: str, text: str, mark: str = "■") -> str:
            return f"<span style='color:{color}; font-size:14px'>{mark}</span>&nbsp;{text}"

        values = [
            swatch(t.one, "1", "━"),
            swatch(t.zero, "0", "─"),
            swatch(t.unknown, "X", "┄"),
        ]
        if self.silicon and self.scene.blocks:
            parts = ["El área de cada bloque es proporcional a sus transistores"]
        elif self.silicon:
            parts = [
                swatch(LAYER_COLOR[k], LAYER_NAMES[k])
                for k in ("pdiff", "ndiff", "poly", "metal1", "metal2")
            ]
            parts.append(swatch(t.on, "canal que conduce"))
        elif self._grid_shown():
            parts = [
                swatch(t.one, "salida en 1"),
                swatch(t.zero, "salida en 0"),
                swatch(t.halo, "cambia en este instante", "□"),
            ]
        elif self.gates:
            parts = values
        else:
            parts = [*values, swatch(t.on, "canal que conduce")]
        self.legend.setText(gap.join(parts))

    # --------------------------------------------------------------- dibujo
    def redraw(self) -> None:
        """Dibuja de nuevo lo elegido en el modo actual."""
        if self._target[0] == "library":
            self._draw_library(fit=True)
        else:
            self._draw_target(fit=True)

    def _draw(
        self,
        cells: list[tuple[Binding, str]],
        values: object,
        clickable: set[int],
        fit: bool,
        floor: tuple[list[Tile], list[str], tuple[str, str]] | None = None,
        bits: Grid | None = None,
    ) -> None:
        """Dibuja ``cells`` en el modo actual. En Silicio: el plano ``floor`` si se da; una
        sola celda, junto a su esquema; unas pocas celdas, en una fila."""
        keep_view = not fit
        center = self.view.mapToScene(self.view.viewport().rect().center())
        zoom = self.view.zoom
        if self.silicon and floor is not None:
            self.scene.show_floorplan(floor[0], floor[1], values, floor[2])  # type: ignore[arg-type]
        elif self.silicon and len(cells) == 1:
            self.scene.show_pair(cells[0][0], cells[0][1], values, clickable=clickable)  # type: ignore[arg-type]
        elif self.silicon:
            self.scene.show_silicon(cells, values, clickable=clickable)  # type: ignore[arg-type]
        elif self.gates and bits is not None:
            by_path = {b.path: b for b, _ in cells}
            slots = [(by_path[s.inst.path], s.column, s.row, s.sub) for s in bits.slots]
            self.scene.show_grid(slots, bits.columns, values)  # type: ignore[arg-type]
        elif self.gates:
            self.scene.show_gates(cells, values, clickable=clickable)  # type: ignore[arg-type]
        else:
            self.scene.show_schematics(cells, values, clickable=clickable)  # type: ignore[arg-type]
        self.scene.show_paths = self.paths.isChecked()
        self.scene.show_toggles = self.toggles.isChecked()
        self.scene.color_by_value = self.by_value.isChecked()
        self.scene.toggled_nodes = self._toggled_nodes() if self._target[0] != "library" else set()
        self._apply_heat()
        self._legend()
        self._update_controls()
        self.step_pos = -1
        self._steps_refresh()
        self._update_panel()
        self._time_refresh()
        if keep_view:
            self.view.resetTransform()
            self.view.scale(zoom, zoom)
            self.view.centerOn(center)
        else:
            self.view.fit()
        self._clear_inspector()

    def _toggled_nodes(self) -> set[int]:
        if self.unit is None:
            return set()
        return {i for i, n in enumerate(self.unit.engine.node_toggles) if n}

    # ------------------------------------------------------------ biblioteca
    def _source_changed(self, index: int) -> None:
        self._flush()
        if index == 0:
            self._target = ("library", self.library.name)
            self._draw_library(fit=True)
        elif self.unit is not None:
            item = self.tree.currentItem() or self.tree.topLevelItem(0)
            if item is not None:
                self._select(item)

    def _library_changed(self) -> None:
        fresh = self._target != ("library", self.library.name)
        self._target = ("library", self.library.name)
        if self.sources.currentIndex() != 0:
            return
        self._draw_library(fit=fresh)
        if not fresh:
            self._animate(self.library.before)

    def _library_bindings(self) -> list[tuple[Binding, str]]:
        cell = self.library.cell
        n = len(cell.transistors)
        if not cell.instances:
            return [(bind_cell(cell), f"{cell.name}, {n} transistores")]
        return [
            (bind_instance(i), f"{i.path} ({i.definition.name})") for i in cell.leaf_instances()
        ]

    def _draw_library(self, fit: bool) -> None:
        cell = self.library.cell
        engine = self.library.engine
        clickable = {n.id for n in cell.inputs.values()}
        self._allow_schematic(True)
        self._draw(self._library_bindings(), engine, clickable, fit)
        n = len(cell.transistors)
        on = sum(1 for t in cell.transistors if engine.conduction(t) is Conduction.ON)
        self.breadcrumb.setText(
            f"Biblioteca › <b>{cell.name}</b> — {DESCRIPTIONS.get(cell.name, '')}"
        )
        self.info.setText(
            f"{cell.name}: {on} de {n} transistores conducen con estas entradas. Haga clic en "
            "una entrada (en el dibujo o a la izquierda) y mire cómo cambian los canales."
        )

    def _animate(self, before: dict[int, Logic]) -> None:
        """Corriente transitoria por los transistores que cargaron o descargaron un nodo."""
        engine = self.library.engine
        changed = {i for i, v in before.items() if v != engine.value(self.library.cell.nodes[i])}
        flows: dict[CellItem, set[int]] = {}
        for item in self.scene.cells:
            if not isinstance(item, SchematicItem):
                continue
            state = item.binding.state(engine)
            path: set[int] = set()
            for stage, _, _ in item.geo.stages:
                if item.node_id(stage.output) in changed:
                    out = engine.value(item.binding.nodes[stage.output])
                    tree = stage.pull_up if out is Logic.ONE else stage.pull_down
                    path |= active_path(tree, state)
            flows[item] = path
        self.scene.start_flow(flows)

    # ------------------------------------------------------- última operación
    def show_calculation(self, calc: Calculation) -> None:
        """Carga la jerarquía de la unidad que hizo el último cálculo.

        Si la pestaña no está a la vista, solo se anota: se dibuja al mostrarla, así un
        cálculo en la pestaña Operación no espera a que se pinte el chip.
        """
        if not self.isVisible():
            self._pending = calc
            return
        self._load(calc)

    def _flush(self) -> None:
        """Carga el cálculo pendiente, si lo hay."""
        if self._pending is not None:
            self._load(self._pending)

    def _load(self, calc: Calculation) -> None:
        self._pending = None
        same_unit = self.unit is calc.unit
        self.calc = calc
        self.unit = calc.unit
        netlist = calc.unit.netlist
        self._children = {}
        self._instances = {i.path: i for i in netlist.instances}
        for inst in netlist.instances:
            self._children.setdefault(inst.parent, []).append(inst)
        flags = str(calc.result.flags)
        self.hierarchy.header.setText(
            f"<b>{unit_title(netlist.name)}</b><br>{calc.expression}"
            f"{'' if flags == '—' else ', ' + flags}<br>"
            f"<span style='color:{th.current().muted}'>{thousands(len(netlist.transistors))} "
            f"transistores</span>"
        )
        self.hierarchy.stack.setCurrentIndex(1)
        previous = self._target if same_unit and self._target[0] != "library" else None
        self.tree.blockSignals(True)
        self.tree.clear()
        root = QTreeWidgetItem(
            [unit_title(netlist.name), thousands(len(netlist.transistors)), thousands(calc.toggles)]
        )
        root.setData(0, Qt.ItemDataRole.UserRole, "unit")
        root.setToolTip(0, "El chip completo (vista de silicio)")
        self.tree.addTopLevelItem(root)
        self._fill(root, None)
        root.setExpanded(True)
        self.tree.blockSignals(False)
        if self.sources.currentIndex() == 1:
            if previous is not None:
                self.reveal(previous[1] if previous[0] == "instance" else previous[0])
            else:
                self.tree.setCurrentItem(root)

    def _fill(self, item: QTreeWidgetItem, parent: str | None) -> None:
        """Agrega los hijos de ``parent``. En el primer nivel, las celdas sueltas se agrupan
        en un nodo de enlace para que destaquen los bloques del datapath."""
        children = self._children.get(parent, [])
        if parent is None:
            glue = [i for i in children if i.is_leaf]
            for inst in children:
                if not inst.is_leaf:
                    item.addChild(self._item(inst))
            if glue:
                assert self.unit is not None
                toggles = sum(instance_toggles(self.unit.engine, i) for i in glue)
                group = QTreeWidgetItem(
                    [
                        f"{STAGE_NAMES[GLUE]} ({len(glue)} celdas)",
                        thousands(sum(len(i.transistors) for i in glue)),
                        thousands(toggles),
                    ]
                )
                group.setData(0, Qt.ItemDataRole.UserRole, "glue")
                group.setToolTip(
                    0,
                    "Celdas colocadas directamente en la unidad: multiplexores y "
                    "compuertas que unen las etapas",
                )
                group.addChild(QTreeWidgetItem(["…"]))
                item.addChild(group)
            return
        item.addChildren([self._item(inst) for inst in children])

    def _item(self, inst: Instance) -> QTreeWidgetItem:
        assert self.unit is not None
        name = inst.path.rsplit(".", 1)[-1]
        if inst.parent is None and name in STAGE_NAMES:
            name = _capital(STAGE_NAMES[name])
        elif inst.is_leaf:
            name = f"{name} ({inst.definition.name})"
        child = QTreeWidgetItem(
            [
                name,
                thousands(len(inst.transistors)),
                thousands(instance_toggles(self.unit.engine, inst)),
            ]
        )
        child.setData(0, Qt.ItemDataRole.UserRole, inst)
        child.setToolTip(0, f"{inst.path} ({inst.definition.name})")
        if not inst.is_leaf:
            child.addChild(QTreeWidgetItem(["…"]))  # se llena al expandir
        return child

    def _expand(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        placeholder = item.child(0) if item.childCount() == 1 else None
        if placeholder is None or placeholder.text(0) != "…":
            return
        item.takeChild(0)
        if isinstance(data, Instance):
            self._fill(item, data.path)
        elif data == "glue" and self.unit is not None:
            item.addChildren(
                [self._item(i) for i in self.unit.netlist.top_instances() if i.is_leaf]
            )

    def reveal(self, path: str) -> None:
        """Busca ``path`` en el árbol (expandiendo lo necesario) y lo elige."""
        self._flush()
        root = self.tree.topLevelItem(0)
        if root is None:
            return
        self.sources.setCurrentIndex(1)
        self.hierarchy.search.clear()
        if path in ("unit", ""):
            self.tree.setCurrentItem(root)
            return
        if path == "glue":
            for child in _children(root):
                if child.data(0, Qt.ItemDataRole.UserRole) == "glue":
                    self.tree.setCurrentItem(child)
            return
        inst = self._instances.get(path)
        if inst is None:
            return
        chain = []
        p: str | None = path
        while p is not None:
            chain.append(p)
            p = self._instances[p].parent
        chain.reverse()
        node = root
        if self._instances[chain[0]].is_leaf:
            for child in _children(root):
                if child.data(0, Qt.ItemDataRole.UserRole) == "glue":
                    node = child
                    node.setExpanded(True)
        for step in chain:
            node.setExpanded(True)
            found = None
            for child in _children(node):
                d = child.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(d, Instance) and d.path == step:
                    found = child
                    break
            if found is None:
                return
            node = found
        self.tree.setCurrentItem(node)
        self.tree.scrollToItem(node)

    def _search(self, text: str) -> None:
        """Con texto, el árbol muestra las instancias que coinciden; sin texto, la jerarquía."""
        self._flush()
        if self.unit is None:
            return
        text = text.strip().lower()
        self.tree.blockSignals(True)
        if not text:
            self.tree.blockSignals(False)
            calc = self.calc
            if calc is not None:
                self._load(calc)
            return
        self.tree.clear()
        matches = [
            i
            for i in self.unit.netlist.instances
            if text in i.path.lower() or text == i.definition.name.lower()
        ]
        for inst in matches[:300]:
            item = self._item(inst)
            item.setText(0, inst.path)
            item.takeChildren()
            self.tree.addTopLevelItem(item)
        if len(matches) > 300:
            more = QTreeWidgetItem([f"… y {len(matches) - 300} más: afine la búsqueda"])
            more.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tree.addTopLevelItem(more)
        if not matches:
            none = QTreeWidgetItem(["Sin resultados"])
            none.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tree.addTopLevelItem(none)
        self.tree.blockSignals(False)

    def _select(self, item: QTreeWidgetItem | None, _previous: object = None) -> None:
        if self.unit is None or item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data == "unit":
            self._target = ("unit", "")
        elif data == "glue":
            self._target = ("glue", "")
        elif isinstance(data, Instance):
            self._target = ("instance", data.path)
        else:
            return
        self._draw_target(fit=True)

    def _draw_target(self, fit: bool) -> None:
        if self.unit is None:
            return
        self._tile_members = {}
        kind, path = self._target
        netlist = self.unit.netlist
        engine = self.unit.engine
        n_total = len(netlist.transistors)
        if kind == "unit":
            self._allow_schematic(
                False,
                "La unidad completa tiene demasiados transistores para un esquema: elija un bloque",
            )
            blocks = [c for c in netlist.top_instances() if not c.is_leaf]
            tiles, subs = self._tiles(blocks, top_level=True)
            glue = [c for c in netlist.top_instances() if c.is_leaf]
            if glue:
                self._tile_members["glue"] = glue
                n_glue = sum(len(c.transistors) for c in glue)
                tiles.append(Tile("glue", "Selección y enlace", n_glue, stage_color(GLUE).name()))
                subs.append(f"{len(glue)} celdas, {thousands(n_glue)} transistores")
            self._draw(
                [],
                engine,
                set(),
                fit,
                floor=(
                    tiles,
                    subs,
                    (unit_title(netlist.name), f"{thousands(n_total)} transistores"),
                ),
            )
            self.breadcrumb.setText(f"<b>{unit_title(netlist.name)}</b>, el chip completo")
            self.info.setText(
                f"{netlist.name}: {thousands(n_total)} transistores en {len(tiles)} regiones. "
                "Cada bloque ocupa un área proporcional a sus transistores; doble clic en uno "
                "para entrar."
            )
            return
        if kind == "glue":
            cells = [c for c in netlist.top_instances() if c.is_leaf]
            title, what = STAGE_NAMES[GLUE], "celdas sueltas de la unidad"
            n = sum(len(c.transistors) for c in cells)
            base = ""
        else:
            inst = self._instances[path]
            n = len(inst.transistors)
            if inst.is_leaf:
                cells = [inst]
                what = "celda"
            else:
                cells = [c for c in netlist.leaf_instances() if c.path.startswith(f"{inst.path}.")]
                what = f"bloque de {len(cells)} celdas"
            title = f"{path} ({inst.definition.name})"
            base = "" if inst.is_leaf else f"{inst.path}."
        allowed = n <= BLOCK_LIMIT
        block = kind == "instance" and not self._instances[path].is_leaf
        forced = self._allow_schematic(
            allowed,
            f"Más de {thousands(BLOCK_LIMIT)} transistores: véalo en Silicio o abra una parte",
            gates=True if block else None,
        )
        bindings = [(bind_instance(c), c.path[len(base) :] if base else c.path) for c in cells]
        floor = None
        if len(cells) > 1:
            children = (
                [c for c in netlist.top_instances() if c.is_leaf]
                if kind == "glue"
                else self._children.get(path, [])
            )
            tiles, subs = self._tiles(children, top_level=False)
            floor = (tiles, subs, (title, f"{thousands(n)} transistores"))
        bits = grid(netlist, path) if block else None
        self._draw(bindings, engine, set(), fit, floor=floor, bits=bits)
        on = sum(1 for c in cells for t in c.transistors if engine.conduction(t) is Conduction.ON)
        toggles = sum(instance_toggles(engine, c) for c in cells)
        self.breadcrumb.setText(self._crumbs(kind, path))
        note = (
            f" Su esquema tendría {thousands(n)} transistores: se muestra su plano."
            if forced
            else ""
        )
        self.info.setText(
            f"{title}, {what}: {on} de {thousands(n)} transistores conducen; "
            f"{thousands(toggles)} conmutaciones en la última operación.{note}"
        )

    def _crumbs(self, kind: str, path: str) -> str:
        assert self.unit is not None
        t = th.current()
        link = f"color:{t.accent}; text-decoration:none"
        parts = [f"<a style='{link}' href='unit'>{unit_title(self.unit.netlist.name)}</a>"]
        if kind == "glue":
            parts.append(f"<b>{STAGE_NAMES[GLUE]}</b>")
        elif kind == "instance":
            chain: list[str] = []
            p: str | None = path
            while p is not None:
                chain.append(p)
                p = self._instances[p].parent
            chain.reverse()
            if self._instances[chain[0]].is_leaf:
                parts.append(f"<a style='{link}' href='glue'>{STAGE_NAMES[GLUE]}</a>")
            for k, step in enumerate(chain):
                name = step.rsplit(".", 1)[-1]
                label = _capital(STAGE_NAMES[name]) if k == 0 and name in STAGE_NAMES else name
                if k == len(chain) - 1:
                    parts.append(f"<b>{label}</b> ({self._instances[step].definition.name})")
                else:
                    parts.append(f"<a style='{link}' href='{step}'>{label}</a>")
        return " › ".join(parts)

    def _crumb(self, href: str) -> None:
        self.reveal(href)

    def _go_up(self) -> None:
        kind, path = self._target
        if kind == "instance":
            parent = self._instances[path].parent
            if parent is None:
                self.reveal("glue" if self._instances[path].is_leaf else "unit")
            else:
                self.reveal(parent)
        elif kind == "glue":
            self.reveal("unit")

    # ------------------------------------------------------------------ ratón
    def _many(self) -> bool:
        """True si se dibujan varias celdas distintas (no una celda con su silicio)."""
        return len(self.scene.cells) > 1 and not self.scene.pair

    def _clicked(self, hit: Hit | BlockHit | None) -> None:
        if hit is None:
            self._clear_selection()
            self.scene.select_block(None)
            return
        if isinstance(hit, BlockHit):
            self.scene.select_block(hit.item)
            self._inspect_block(hit)
            return
        if hit.kind == "input" and self._target[0] == "library":
            port = self._port_of(hit.node)
            if port is not None:
                self.library.toggle(port)
            return
        if hit.kind == "transistor":
            if (
                self.scene.selected_item is hit.item
                and self.scene.selected_transistor == hit.transistor
            ):
                self._clear_selection()
                return
            self.scene.select(hit.item, hit.transistor)
            self._inspect(hit)
            return
        if hit.kind == "gate" and hit.element is not None:
            first = gl.cell_gates(hit.binding.netlist)
            gate = next(g for g in first if g.element == hit.element)
            self.scene.select(hit.item, gate.transistors[0])
            self._inspect(hit)
            return
        if hit.kind == "cell" and self._many():
            self.scene.select(hit.item, None)
            self._inspect(hit)

    def _port_of(self, node: int | None) -> str | None:
        for port, n in self.library.cell.inputs.items():
            if n.id == node:
                return port
        return None

    def _double_clicked(self, hit: Hit | BlockHit | None) -> None:
        if hit is None:
            self.view.fit()
            return
        if isinstance(hit, BlockHit):
            self.reveal(hit.key)
            return
        if hit.kind == "transistor" and hit.transistor is not None:
            rect = hit.item.mapRectToScene(hit.item.transistor_rect(hit.transistor))
            self.view.focus_on(rect, 3.0)
            return
        if hit.kind == "gate" and hit.element is not None and len(self.scene.cells) == 1:
            self.show_gate_transistors(hit.element)
            return
        if self._many() and self._target[0] != "library":
            self._open(hit.item)

    def show_gate_transistors(self, element: int) -> None:
        """Pasa a la vista de transistores con la etapa ``element`` resaltada."""
        if not self.mode.buttons["schematic"].isEnabled():
            return
        self._set_mode("schematic")
        cell = self.scene.cells[0]
        gate = next(g for g in gl.cell_gates(cell.binding.netlist) if g.element == element)
        steps = [set(st.transistors) for st in self.steps]
        if set(gate.transistors) in steps:
            self.step_pos = steps.index(set(gate.transistors))
            self._apply_step()
        self.status.emit(f"Transistores de la etapa {gl.symbol_name(gate.kind)}")

    def _open(self, item: CellItem) -> None:
        path = item.binding.path
        if not path:
            return
        if self._target[0] == "unit":
            top = path.split(".", 1)[0]
            self.reveal(top if not self._instances[top].is_leaf else "glue")
        else:
            self.reveal(path)

    def _open_inspected(self) -> None:
        if self._inspected is not None:
            self._open(self._inspected.item)
        elif self._block_inspected is not None:
            self.reveal(self._block_inspected)

    def _clear_selection(self) -> None:
        self.scene.select(None, None)
        self._clear_inspector()

    def _context_menu(self, pos: QPoint) -> None:
        menu = self.context_menu(pos)
        menu.exec(self.view.viewport().mapToGlobal(pos))

    def context_menu(self, pos: QPoint) -> QMenu:
        """Menú del clic derecho en ``pos`` (coordenadas de la vista)."""
        hit = self.view.hit_at(pos.toPointF())
        menu = QMenu(self)
        fit = QAction("Ajustar a la vista", menu)
        fit.triggered.connect(lambda: self.view.fit())
        menu.addAction(fit)
        if isinstance(hit, BlockHit):
            action = QAction(f"Abrir {hit.item.tile.title}", menu)
            action.triggered.connect(lambda: self.reveal(hit.key))
            menu.addAction(action)
        elif hit is not None and self._many() and self._target[0] != "library":
            cell = hit.item
            action = QAction(f"Abrir {cell.binding.path}", menu)
            action.triggered.connect(lambda: self._open(cell))
            menu.addAction(action)
        if isinstance(hit, Hit) and hit.kind == "transistor" and hit.transistor is not None:
            zoom = QAction("Acercarse a este transistor", menu)
            zoom.triggered.connect(lambda: self._double_clicked(hit))
            menu.addAction(zoom)
        if self._target[0] != "library":
            up = QAction("Subir un nivel (Retroceso)", menu)
            up.triggered.connect(self._go_up)
            up.setEnabled(self._target[0] != "unit")
            menu.addAction(up)
        menu.addSeparator()
        for key, text in (
            ("gates", "Ver como compuertas"),
            ("schematic", "Ver sus transistores"),
            ("silicon", "Ver como silicio"),
        ):
            a = QAction(text, menu)
            a.setCheckable(True)
            a.setChecked(self.mode.value() == key)
            a.setEnabled(self.mode.buttons[key].isEnabled())
            a.triggered.connect(lambda _=False, key=key: self._set_mode(key))
            menu.addAction(a)
        menu.addSeparator()
        export = QAction("Exportar imagen…", menu)
        export.triggered.connect(self.export_dialog)
        menu.addAction(export)
        return menu

    # -------------------------------------------------------------- inspector
    def _hover(self, hit: Hit | BlockHit | None) -> None:
        if isinstance(hit, BlockHit):
            self._inspect_block(hit)
            return
        if hit is None and self.scene.blocks:
            if self.scene.selected_block is not None:
                self._inspect_block(BlockHit(self.scene.selected_block))
            else:
                self._clear_inspector()
            return
        if hit is None or (hit.kind == "cell" and not self._many()):
            selected = self.scene.selected_item
            if selected is not None:
                self._inspect(
                    Hit(
                        selected,
                        "transistor" if self.scene.selected_transistor is not None else "cell",
                        self.scene.selected_transistor,
                    )
                )
            elif hit is None:
                self.status.emit("")
            return
        self._inspect(hit)

    def _clear_inspector(self) -> None:
        self._inspected = None
        self._block_inspected = None
        ins = self.inspector
        ins.section.show_device(None)
        ins.open_button.hide()
        cells = self.scene.cells
        if len(cells) == 1 and not self.silicon and self.scene.values is not None:
            cell = cells[0]
            netlist = cell.binding.netlist
            lines = [
                f"{k + 1}. {gl.explain(g, netlist, cell.value_fn())}"
                for k, g in enumerate(gl.cell_gates(netlist))
            ]
            ins.title.setText(f"<b>{cell.binding.circuit.name}</b>: cómo calcula sus salidas")
            ins.body.setText("<br>".join(lines))
            ins.explain.setText(
                "Una línea por etapa, en orden de señal, con los valores de ahora. Pase el "
                "ratón por una compuerta o un transistor para ver el detalle."
            )
            return
        if self.scene.blocks:
            ins.title.setText("<b>Plano</b>")
            ins.body.setText(
                "Pase el ratón por un bloque para ver qué hace, cuántos transistores tiene y "
                "cuánto conmutó. Doble clic para entrar."
            )
            ins.explain.setText("")
            return
        if self.scene.pair:
            ins.title.setText("<b>La celda y su silicio</b>")
            ins.body.setText(
                "A la izquierda, el esquema; a la derecha, la misma celda en silicio. Pase el "
                "ratón por un transistor en cualquiera de los dos: se resalta en ambos."
            )
            ins.explain.setText("")
            return
        ins.title.setText("<b>Nada elegido</b>")
        ins.body.setText(
            "Pase el ratón por un transistor, un cable o una celda. Un clic fija el "
            "transistor; Esc lo suelta."
        )
        ins.explain.setText("")

    def _inspect_block(self, hit: BlockHit) -> None:
        """Lo que se sabe de un bloque del plano."""
        ins = self.inspector
        ins.section.show_device(None)
        tile = hit.item.tile
        members = self._tile_members.get(tile.key)
        if tile.key == "glue":
            what = "Multiplexores y compuertas que unen las etapas."
        elif members is not None:
            what = f"{len(members)} celdas {members[0].definition.name}; la primera es {tile.key}."
        else:
            what = f"Instancia {tile.key} ({self._instances[tile.key].definition.name})."
        total = len(self.unit.netlist.transistors) if self.unit is not None else 0
        share = 100 * tile.weight / total if total else 0.0
        ins.title.setText(f"<b>{tile.title}</b>")
        ins.body.setText(
            f"{what}<br>{thousands(tile.weight)} transistores ({share:.1f} % de la unidad), "
            f"{thousands(self._tile_toggles(tile.key))} conmutaciones en la última operación."
        )
        ins.explain.setText("Doble clic para entrar.")
        ins.open_button.setVisible(True)
        ins.open_button.setText(f"Abrir {tile.title}")
        self._inspected = None
        self._block_inspected = tile.key
        self.status.emit(f"{tile.title}: {thousands(tile.weight)} transistores")

    def _inspect(self, hit: Hit) -> None:
        values = self.scene.values
        if values is None:
            return
        self._inspected = hit
        ins = self.inspector
        b = hit.binding
        c = b.circuit
        t = th.current()
        ins.open_button.setVisible(self._many() and self._target[0] != "library")
        ins.open_button.setText(
            "Abrir su bloque" if self._target[0] == "unit" else f"Abrir {b.path or c.name}"
        )
        where = b.path or c.name
        if hit.kind == "gate" and hit.element is not None:
            gate = next(g for g in gl.cell_gates(b.netlist) if g.element == hit.element)
            ins.section.show_device(None)
            out = c.label(gate.output) if gate.output >= 0 else ""
            ins.title.setText(f"<b>{gl.symbol_name(gate.kind)}</b> → {out}")
            ins.body.setText(gl.explain(gate, b.netlist, hit.item.value_fn()))
            names = ", ".join(c.transistors[i].name for i in gate.transistors)
            ins.explain.setText(
                f"{len(gate.transistors)} transistores ({names}). Doble clic para verlos."
            )
            self.status.emit(f"{gl.symbol_name(gate.kind)} de {where}: {out} = {gate.expression}")
            return
        if hit.kind == "transistor" and hit.transistor is not None:
            real = b.transistors[hit.transistor]
            d = c.transistors[hit.transistor]
            dev = Device(
                pmos=real.kind is TransistorType.PMOS,
                name=d.name,
                gate=c.label(d.gate.id),
                source=c.label(d.source.id),
                drain=c.label(d.drain.id),
                gate_value=values.value(real.gate),
                source_value=values.value(real.source),
                drain_value=values.value(real.drain),
                state=values.conduction(real),
            )
            flowing = hit.item in self.scene.flows and hit.transistor in self.scene.flows[hit.item]
            ins.section.show_device(dev, flowing)
            kind = "pMOS" if dev.pmos else "nMOS"
            state = {
                Conduction.ON: f"<b style='color:{t.on}'>conduce</b>",
                Conduction.OFF: "<b>no conduce</b>",
                Conduction.UNKNOWN: f"<b style='color:{t.unknown}'>incierto</b>",
            }[dev.state]
            ins.title.setText(f"<b>{kind} {d.name}</b>")
            place = f"en {where} ({c.name})" if b.path else f"en la celda {c.name}"

            def term(name: str, label: str, value: Logic) -> str:
                color = t.logic(value).name()
                return f"{name} <b style='color:{color}'>{label} = {_v(value)}</b>"

            ins.body.setText(
                f"{place}, {state}<br>"
                + ", ".join(
                    (
                        term("compuerta", dev.gate, dev.gate_value),
                        term("fuente", dev.source, dev.source_value),
                        term("drenador", dev.drain, dev.drain_value),
                    )
                )
            )
            ins.explain.setText(explain(dev))
            word = "conduce" if dev.state is Conduction.ON else "no conduce"
            self.status.emit(f"{kind} {where}.{d.name}: {word}")
            return
        ins.section.show_device(None)
        if hit.node is not None:
            node = next((n for n in b.nodes.values() if n.id == hit.node), None)
            if node is None:
                return
            v = values.value(node)
            gates = sum(1 for tr in b.transistors if tr.gate.id == node.id)
            chans = sum(1 for tr in b.transistors if node.id in (tr.source.id, tr.drain.id))
            local = next(k for k, n in b.nodes.items() if n.id == node.id)
            toggles = ""
            if self.unit is not None and self._target[0] != "library":
                count = self.unit.engine.node_toggles[node.id]
                veces = "vez" if count == 1 else "veces"
                toggles = f"<br>Conmutó {count} {veces} en la última operación."
            role = {
                NodeKind.VDD: "riel de alimentación",
                NodeKind.GND: "riel de tierra",
            }.get(node.kind, "nodo interno")
            if local in c.outputs.values():
                role = "salida"
            elif local in c.inputs.values():
                role = "entrada"
            others = len(self.scene.items_with_node(node.id)) - 1
            extra = (
                f" y llega a {others} celda{'s' if others != 1 else ''} más (resaltadas)"
                if others > 0
                else ""
            )
            ins.title.setText(
                f"<b>Nodo {c.label(local)}</b> = <b style='color:{t.logic(v).name()}'>{_v(v)}</b>"
            )
            owner = f"de {where} ({c.name})" if b.path else f"de la celda {c.name}"
            ins.body.setText(
                f"{role} {owner}<br>Llega a {gates} compuerta{'s' if gates != 1 else ''} y a "
                f"{chans} canal{'es' if chans != 1 else ''} de esta celda{extra}.{toggles}"
            )
            click = (
                " Clic para cambiarla."
                if hit.kind == "input" and self._target[0] == "library"
                else ""
            )
            ins.explain.setText(f"Nombre en el netlist: {node.name}.{click}")
            self.status.emit(f"Nodo {node.name} = {_v(v)}")
            return
        # Celda
        on = sum(1 for tr in b.transistors if values.conduction(tr) is Conduction.ON)
        toggles = ""
        if self.unit is not None and self._target[0] != "library":
            inst = self._instances.get(b.path)
            if inst is not None:
                toggles = f", {instance_toggles(self.unit.engine, inst)} conmutaciones"
        ins.title.setText(f"<b>Celda {where}</b> ({c.name})")
        n = len(b.transistors)
        ins.body.setText(
            f"{DESCRIPTIONS.get(c.name, '')}<br>{n} transistores, {on} conducen{toggles}"
        )
        ins.explain.setText(
            "Doble clic para abrirla."
            if self._target[0] != "unit"
            else "Doble clic para abrir su bloque."
        )
        self.status.emit(f"Celda {where} ({c.name})")

    # ---------------------------------------------------------------- imagen
    def export_image(self, path: str, scale: float = 2.0) -> bool:
        """Guarda el dibujo completo como PNG (el lado mayor, hasta 8000 px)."""
        rect = self.scene.sceneRect()
        if rect.isEmpty():
            return False
        scale = min(scale, 8000.0 / max(rect.width(), rect.height()))
        image = QImage(
            max(1, int(rect.width() * scale)),
            max(1, int(rect.height() * scale)),
            QImage.Format.Format_ARGB32,
        )
        image.fill(QColor(self.scene.backgroundBrush().color()))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, QRectF(0, 0, image.width(), image.height()), rect)
        painter.end()
        return image.save(path)

    def export_dialog(self) -> None:
        kind, path = self._target
        name = self.library.name if kind == "library" else (path or kind).replace(".", "_")
        mode = {"silicon": "silicio", "gates": "compuertas"}.get(self.mode.value(), "esquema")
        target, _ = QFileDialog.getSaveFileName(
            self, "Exportar imagen", f"{name}_{mode}.png", "Imagen PNG (*.png)"
        )
        if target:
            if not target.lower().endswith(".png"):
                target += ".png"
            ok = self.export_image(target)
            self.status.emit(
                f"Imagen guardada en {target}" if ok else "No se pudo guardar la imagen"
            )

    def showEvent(self, event: object) -> None:  # noqa: N802 - API de Qt
        super().showEvent(event)  # type: ignore[arg-type]
        self._flush()

    def apply_theme(self) -> None:
        self.scene.apply_theme()
        self.library.refresh_labels()
        self._legend()
        if self._target[0] != "library" and self.unit is not None:
            self.breadcrumb.setText(
                self._crumbs(*self._target) if self._target[0] != "unit" else self.breadcrumb.text()
            )
        self.scene.refresh()
        self.inspector.section.update()


__all__ = ["BLOCK_LIMIT", "DESCRIPTIONS", "LEAF_CELLS", "TransistorTab", "truth_table"]
