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

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
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
from transim.metrics.stages import GLUE, STAGE_NAMES
from transim.ui.gui import theme as th
from transim.ui.gui.canvas import (
    LAYER_COLOR,
    LAYER_NAMES,
    CanvasView,
    CellItem,
    CircuitScene,
    Hit,
    SchematicItem,
    logic_text,
)
from transim.ui.gui.circuit import Binding, active_path, bind_cell, bind_instance
from transim.ui.gui.cross_section import CrossSection, Device, explain
from transim.ui.gui.model import Calculation, instance_toggles
from transim.ui.gui.widgets import Segmented, card, hint, thousands

BLOCK_LIMIT = 2500
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
            item = QListWidgetItem(f"{name}   ·   {n} T\n{DESCRIPTIONS.get(name, '')}")
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
        box_layout.addWidget(hint("También puede hacer clic en una entrada del dibujo."))
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
        self.table_note.setText("Calculada con los transistores de la celda.")
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
        self.tree.setHeaderLabels(["instancia", "T", "conm."])
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.headerItem().setToolTip(1, "Transistores")
        self.tree.headerItem().setToolTip(2, "Conmutaciones en la última operación")
        self.tree.setToolTip(
            "La unidad muestra el chip completo; un bloque, sus celdas; una celda, sus "
            "transistores. «conm.»: conmutaciones en la última operación."
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
        label = QLabel("INSPECTOR")
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
                    "schematic",
                    "Esquema",
                    "Esquema eléctrico CMOS: pull-up de pMOS y pull-down de nMOS (Alt+E)",
                ),
                (
                    "silicon",
                    "Silicio",
                    "Layout ilustrativo: difusión, polisilicio y metal, como en el chip (Alt+S)",
                ),
            ]
        )
        self.mode.changed.connect(self._mode_chosen)
        self._preferred = "schematic"
        self._schematic_tip = self.mode.buttons["schematic"].toolTip()
        self.paths = self._toggle(
            "Camino activo",
            True,
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
        zoom_out = self._tool("−", "Alejar (Ctrl+−)", self.view.zoom_out)
        zoom_in = self._tool("+", "Acercar (Ctrl++)", self.view.zoom_in)
        fit = self._tool(
            "Ajustar",
            "Ver todo el dibujo (Ctrl+0 o doble clic en el fondo)",
            lambda: self.view.fit(),
        )
        export = self._tool(
            "Exportar…", "Guardar el dibujo como imagen PNG (Ctrl+E)", self.export_dialog
        )
        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addWidget(self.mode)
        bar.addStretch(1)
        for w in (zoom_out, self.zoom_label, zoom_in, fit, export):
            bar.addWidget(w)
        options = QHBoxLayout()
        options.setSpacing(14)
        for box in (self.paths, self.toggles, self.heat, self.by_value):
            options.addWidget(box)
        options.addStretch(1)
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
        cl.addLayout(options)
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
        for keys, fn in (
            ("Escape", self._clear_selection),
            ("Backspace", self._go_up),
            ("Ctrl+0", lambda: self.view.fit()),
            ("Ctrl++", self.view.zoom_in),
            ("Ctrl+=", self.view.zoom_in),
            ("Ctrl+-", self.view.zoom_out),
            ("Alt+E", lambda: self._set_mode("schematic")),
            ("Alt+S", lambda: self._set_mode("silicon")),
        ):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
        self.library.select("INV")

    # ------------------------------------------------------------- controles
    def _toggle(self, text: str, checked: bool, tip: str) -> QCheckBox:
        box = QCheckBox(text)
        box.setChecked(checked)
        box.setToolTip(tip)
        box.setCursor(Qt.CursorShape.PointingHandCursor)
        box.toggled.connect(self._options_changed)
        return box

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

    def _allow_schematic(self, allowed: bool, why: str = "") -> bool:
        """Habilita o no la vista Esquema y elige la vista del próximo dibujo.

        Returns:
            True si se pasó a Silicio porque el esquema no está disponible.
        """
        self.mode.set_option_enabled("schematic", allowed, self._schematic_tip if allowed else why)
        wanted = self._preferred if allowed else "silicon"
        self.mode.set_value(wanted)
        return not allowed and self._preferred == "schematic"

    def _set_mode(self, mode: str) -> None:
        if self.mode.buttons[mode].isEnabled():
            self.mode.set_value(mode, emit=True)

    @property
    def silicon(self) -> bool:
        return self.mode.value() == "silicon"

    def _options_changed(self) -> None:
        self.scene.show_paths = self.paths.isChecked()
        self.scene.show_toggles = self.toggles.isChecked()
        self.scene.color_by_value = self.by_value.isChecked()
        self._apply_heat()
        self.scene.refresh()
        self._update_controls()

    def _update_controls(self) -> None:
        op = self._target[0] != "library"
        self.paths.setEnabled(not self.silicon)
        self.toggles.setEnabled(op and not self.silicon)
        self.heat.setEnabled(op)
        self.by_value.setEnabled(self.silicon)

    def _apply_heat(self) -> None:
        if not (self.heat.isChecked() and self.heat.isEnabled() and self.unit is not None):
            self.scene.set_heat(None)
            return
        engine = self.unit.engine
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

    def _legend(self) -> None:
        t = th.current()
        if self.silicon:
            parts = [
                f"<span style='color:{LAYER_COLOR[k]}; font-size:14px'>■</span> {LAYER_NAMES[k]}"
                for k in ("pdiff", "ndiff", "poly", "metal1", "metal2")
            ]
            parts.append(
                f"<span style='color:{LAYER_COLOR['nwell']}; font-size:14px'>▭</span> pozo n"
            )
            parts.append(f"<span style='color:{t.on}; font-size:14px'>■</span> canal que conduce")
            text = " · ".join(parts) + ". Layout ilustrativo generado del netlist, no a escala."
        else:
            text = (
                f"<span style='color:{t.one}; font-size:14px'>■</span> 1 · "
                f"<span style='color:{t.zero}; font-size:14px'>■</span> 0 · "
                f"<span style='color:{t.unknown}; font-size:14px'>■</span> X (sin valor) · "
                "canal continuo: conduce; cortado: no conduce · fondo verde: camino que fija la "
                "salida. Arrastre para moverse, rueda para el zoom, doble clic para entrar."
            )
        self.legend.setText(text)

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
        die: tuple[str, str] | None = None,
        groups: list[tuple[str, list[tuple[Binding, str]]]] | None = None,
    ) -> None:
        keep_view = not fit
        center = self.view.mapToScene(self.view.viewport().rect().center())
        zoom = self.view.zoom
        if self.silicon:
            self.scene.show_silicon(groups or [("", cells)], values, clickable=clickable, die=die)  # type: ignore[arg-type]
        else:
            self.scene.show_schematics(cells, values, clickable=clickable)  # type: ignore[arg-type]
        self.scene.show_paths = self.paths.isChecked()
        self.scene.show_toggles = self.toggles.isChecked()
        self.scene.color_by_value = self.by_value.isChecked()
        self.scene.toggled_nodes = self._toggled_nodes() if self._target[0] != "library" else set()
        self._apply_heat()
        self._legend()
        self._update_controls()
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
            return [(bind_cell(cell), f"{cell.name} · {n} transistores")]
        return [
            (bind_instance(i), f"{i.path} · {i.definition.name}") for i in cell.leaf_instances()
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
            f"<b>{netlist.name}</b><br>{calc.expression}"
            f"{'' if flags == '—' else '  ·  ' + flags}<br>"
            f"<span style='color:{th.current().muted}'>{thousands(len(netlist.transistors))} "
            f"transistores · {thousands(calc.toggles)} conmutaciones</span>"
        )
        self.hierarchy.stack.setCurrentIndex(1)
        previous = self._target if same_unit and self._target[0] != "library" else None
        self.tree.blockSignals(True)
        self.tree.clear()
        root = QTreeWidgetItem(
            [netlist.name, thousands(len(netlist.transistors)), thousands(calc.toggles)]
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
            name = f"{name} · {STAGE_NAMES[name]}"
        elif inst.is_leaf:
            name = f"{name} · {inst.definition.name}"
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
        kind, path = self._target
        netlist = self.unit.netlist
        engine = self.unit.engine
        n_total = len(netlist.transistors)
        if kind == "unit":
            self._allow_schematic(
                False,
                "La unidad completa tiene demasiados transistores para un esquema: elija un bloque",
            )
            groups: list[tuple[str, list[tuple[Binding, str]]]] = []
            for top in netlist.top_instances():
                if top.is_leaf:
                    continue
                cells = [c for c in netlist.leaf_instances() if c.path.startswith(f"{top.path}.")]
                label = f"{top.path} · {STAGE_NAMES.get(top.path, top.definition.name)}"
                groups.append((label, [(bind_instance(c), c.path) for c in cells]))
            glue = [c for c in netlist.top_instances() if c.is_leaf]
            if glue:
                groups.append((STAGE_NAMES[GLUE], [(bind_instance(c), c.path) for c in glue]))
            cells_all = [c for _, cs in groups for c in cs]
            self._draw(
                cells_all,
                engine,
                set(),
                fit,
                die=(netlist.name, f"{thousands(n_total)} transistores"),
                groups=groups,
            )
            self.breadcrumb.setText(f"<b>{netlist.name}</b> — el chip completo")
            self.info.setText(
                f"{netlist.name}: {thousands(n_total)} transistores en {len(cells_all)} celdas "
                "estándar, agrupadas por bloque. Acérquese con la rueda hasta ver cada "
                "transistor; doble clic en una celda para abrir su bloque."
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
        forced = self._allow_schematic(
            allowed,
            f"Más de {thousands(BLOCK_LIMIT)} transistores: véalo en Silicio o abra una parte",
        )
        bindings = [(bind_instance(c), c.path[len(base) :] if base else c.path) for c in cells]
        self._draw(bindings, engine, set(), fit)
        on = sum(1 for c in cells for t in c.transistors if engine.conduction(t) is Conduction.ON)
        toggles = sum(instance_toggles(engine, c) for c in cells)
        self.breadcrumb.setText(self._crumbs(kind, path))
        note = (
            f" Su esquema tendría {thousands(n)} transistores: se muestra el silicio."
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
        parts = [f"<a style='{link}' href='unit'>{self.unit.netlist.name}</a>"]
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
                label = f"{name} · {STAGE_NAMES[name]}" if k == 0 and name in STAGE_NAMES else name
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
    def _clicked(self, hit: Hit | None) -> None:
        if hit is None:
            self._clear_selection()
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
        if hit.kind == "cell" and len(self.scene.cells) > 1:
            self.scene.select(hit.item, None)
            self._inspect(hit)

    def _port_of(self, node: int | None) -> str | None:
        for port, n in self.library.cell.inputs.items():
            if n.id == node:
                return port
        return None

    def _double_clicked(self, hit: Hit | None) -> None:
        if hit is None:
            self.view.fit()
            return
        if hit.kind == "transistor" and hit.transistor is not None:
            rect = hit.item.mapRectToScene(hit.item.transistor_rect(hit.transistor))
            self.view.focus_on(rect, 3.0)
            return
        if len(self.scene.cells) > 1 and self._target[0] != "library":
            self._open(hit.item)

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
        if hit is not None and len(self.scene.cells) > 1 and self._target[0] != "library":
            name = hit.item.binding.path
            action = QAction(f"Abrir {name}", menu)
            action.triggered.connect(lambda: self._open(hit.item))
            menu.addAction(action)
        if hit is not None and hit.kind == "transistor" and hit.transistor is not None:
            zoom = QAction("Acercarse a este transistor", menu)
            zoom.triggered.connect(lambda: self._double_clicked(hit))
            menu.addAction(zoom)
        if self._target[0] != "library":
            up = QAction("Subir un nivel (Retroceso)", menu)
            up.triggered.connect(self._go_up)
            up.setEnabled(self._target[0] != "unit")
            menu.addAction(up)
        menu.addSeparator()
        for key, text in (("schematic", "Ver como esquema"), ("silicon", "Ver como silicio")):
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
    def _hover(self, hit: Hit | None) -> None:
        if hit is None or (hit.kind == "cell" and len(self.scene.cells) <= 1):
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
        ins = self.inspector
        ins.title.setText("<b>Nada elegido</b>")
        ins.body.setText(
            "Pase el ratón por un transistor, un cable o una celda. Un clic fija el "
            "transistor; Esc lo suelta."
        )
        ins.section.show_device(None)
        ins.explain.setText("")
        ins.open_button.hide()

    def _inspect(self, hit: Hit) -> None:
        values = self.scene.values
        if values is None:
            return
        self._inspected = hit
        ins = self.inspector
        b = hit.binding
        c = b.circuit
        t = th.current()
        ins.open_button.setVisible(len(self.scene.cells) > 1 and self._target[0] != "library")
        ins.open_button.setText(
            "Abrir su bloque" if self._target[0] == "unit" else f"Abrir {b.path or c.name}"
        )
        where = b.path or c.name
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
                f"{place} · {state}<br>"
                + " · ".join(
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
                toggles = f" · {instance_toggles(self.unit.engine, inst)} conmutaciones"
        ins.title.setText(f"<b>Celda {where}</b> ({c.name})")
        n = len(b.transistors)
        ins.body.setText(
            f"{DESCRIPTIONS.get(c.name, '')}<br>{n} transistores · {on} conducen{toggles}"
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
        mode = "silicio" if self.silicon else "esquema"
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
