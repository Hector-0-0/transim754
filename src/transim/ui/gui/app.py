"""Interfaz gráfica de escritorio con PySide6. ADR-0011.

Requiere el extra ``gui`` (``make install-gui``).

La interfaz solo muestra: los resultados los calculan las unidades de transistores
(``FPAddSub``, ``FPMul``, ``FPDiv``) y la máquina T754. La conversión de texto a bits
usa ``reference.fpu.from_decimal``, igual que el CLI.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from transim.cells.library import CELLS
from transim.core.engine_switch import SwitchEngine
from transim.core.netlist import Instance, Netlist
from transim.core.signals import Logic
from transim.core.transistor import TransistorType
from transim.core.unit import EngineName, HardwareUnit
from transim.cpu import isa
from transim.cpu.assembler import AssemblyError, assemble
from transim.fpu.format import FORMATS, FloatFormat, FPResult
from transim.metrics.stages import (
    GLUE,
    STAGE_NAMES,
    activity_by_stage,
    critical_stages,
    reference_period,
    schedule,
)
from transim.reference import fpu as ref
from transim.ui.gui import theme
from transim.ui.gui.canvas import CanvasView, CircuitScene, Hit, logic_text
from transim.ui.gui.circuit import Binding, active_path, bind_cell, bind_instance
from transim.ui.gui.cross_section import CrossSection, Device, explain

BLOCK_LIMIT = 2500
"""Transistores máximos de un bloque para dibujarlo completo en un plano."""

TITLE = "TranSim754 — procesador IEEE 754 de transistores simulados"
OPERATIONS = {"+  suma": "add", "−  resta": "sub", "×  multiplicación": "mul", "÷  división": "div"}


# ---------------------------------------------------------------- cálculo en hilo
class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    """Ejecuta ``fn`` fuera del hilo de la interfaz y emite su resultado."""

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


@dataclass
class Calculation:
    """Resultado de una operación en la FPU de transistores."""

    fmt: FloatFormat
    a: int
    b: int
    result: FPResult
    stages: dict[str, int | None]
    transistors: int
    toggles: int
    events: int
    seconds: float
    unit: HardwareUnit
    stage_toggles: dict[str, int]


_UNITS: dict[tuple[str, str, str], HardwareUnit] = {}


def _unit(fmt: FloatFormat, op: str, engine: EngineName) -> HardwareUnit:
    """Unidad de hardware para ``op`` (se construye una vez por formato y motor)."""
    from transim.fpu.add_sub import FPAddSub
    from transim.fpu.div import FPDiv
    from transim.fpu.mul import FPMul

    kind = "addsub" if op in ("add", "sub") else op
    key = (fmt.name, kind, engine)
    if key not in _UNITS:
        cls = {"addsub": FPAddSub, "mul": FPMul, "div": FPDiv}[kind]
        unit = cls(fmt, engine)
        # Estado de partida definido (0 op 0) para que la primera medición sea comparable.
        unit.evaluate({"a": 0, "b": 0, "sub": 0} if kind == "addsub" else {"a": 0, "b": 0})
        _UNITS[key] = unit
    return _UNITS[key]


def calculate(fmt: FloatFormat, op: str, a: int, b: int, engine: EngineName) -> Calculation:
    """Calcula ``a op b`` en la unidad de transistores y mide su actividad.

    Las conmutaciones se cuentan respecto de la operación anterior de la misma unidad
    (para la primera, respecto de 0 op 0).
    """
    unit = _unit(fmt, op, engine)
    inputs: dict[str, int] = {"a": a, "b": b}
    if op in ("add", "sub"):
        inputs["sub"] = int(op == "sub")
    unit.engine.reset_counters()
    start = time.perf_counter()
    outputs = unit.evaluate(inputs)
    seconds = time.perf_counter() - start
    stats = unit.engine.stats()
    stages = {k: v for k, v in outputs.items() if k.startswith("dbg_")}
    return Calculation(
        fmt=fmt,
        a=a,
        b=b,
        result=FPResult.from_outputs({k: v for k, v in outputs.items() if k not in stages}),
        stages=stages,
        transistors=unit.transistor_count(),
        toggles=stats.node_toggles,
        events=stats.transistor_events,
        seconds=seconds,
        unit=unit,
        stage_toggles=activity_by_stage(unit.engine),
    )


def cycle_groups(netlist: Netlist, period: int) -> tuple[int, list[tuple[str, str, str]]]:
    """Ciclos de ADR-0014 agrupados cuando ocupan las mismas etapas.

    Returns:
        (celdas del camino crítico, filas ``(ciclos, celdas, etapas)``).
    """
    stages = critical_stages(netlist)
    cycles = schedule(stages, period)
    rows = []
    i = 0
    while i < len(cycles):
        j = i
        while j + 1 < len(cycles) and cycles[j + 1].stages == cycles[i].stages:
            j += 1
        first, last = cycles[i], cycles[j]
        which = str(first.index) if i == j else f"{first.index}–{last.index}"
        rows.append((which, f"{first.first_cell}–{last.last_cell}", " · ".join(first.stages)))
        i = j + 1
    return sum(st.cells for st in stages), rows


def cycles_report(netlist: Netlist, period: int, stage_toggles: dict[str, int]) -> str:
    """Texto de la consola de ciclos (ADR-0014): el camino crítico repartido en ciclos de
    ``period`` celdas y las conmutaciones de cada etapa en la última operación."""
    total, groups = cycle_groups(netlist, period)
    n_cycles = len(schedule(critical_stages(netlist), period))
    lines = [
        f"{netlist.name} · camino crítico: {total} celdas",
        f"Periodo de reloj: {period} celdas → {n_cycles} ciclos (estimado, ADR-0014)",
        "",
    ]
    for which, cells, stages in groups:
        label = f"Ciclo {which}" if "–" not in which else f"Ciclos {which}"
        lines.append(f"{label:<14} celdas {cells:<11} {stages}")
    if stage_toggles:
        lines += ["", "Conmutaciones por etapa en esta operación:"]
        for name, n in sorted(stage_toggles.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {STAGE_NAMES.get(name, name):<28} {n:>7}")
    return "\n".join(lines)


def _table(headers: list[str]) -> QTableWidget:
    """Tabla de solo lectura con columnas ajustadas y texto que se parte en líneas."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.setWordWrap(True)
    header = table.horizontalHeader()
    for col in range(len(headers) - 1):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
    return table


def _fill(table: QTableWidget, rows: list[list[str]]) -> None:
    """Reemplaza las filas de ``table``."""
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(text))
    table.resizeRowsToContents()


def parse_operand(text: str, fmt: FloatFormat) -> int:
    """Bits del operando escrito en decimal o en hexadecimal ``0x…``.

    Raises:
        ValueError: si el texto no es un número válido o no cabe en el formato.
    """
    text = text.strip()
    if text.lower().startswith("0x"):
        bits = int(text, 16)
        if bits >> fmt.width:
            raise ValueError(f"{text} no cabe en {fmt.width} bits")
        return bits
    return ref.from_decimal(fmt, text).bits


def _mono() -> QFont:
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


# ------------------------------------------------------------- pestaña operación
class OperationTab(QWidget):
    """Operandos, vista de bits, flags, etapas, ciclos y métricas de una operación."""

    calculated = Signal(object)
    """Se emite con cada :class:`Calculation` terminado."""

    def __init__(self, pool: QThreadPool) -> None:
        super().__init__()
        self.pool = pool
        self.last: Calculation | None = None
        self.a_edit, self.b_edit = QLineEdit("1.5"), QLineEdit("2.25")
        self.fmt_box = QComboBox()
        self.fmt_box.addItems(sorted(FORMATS, reverse=True))
        self.op_box = QComboBox()
        self.op_box.addItems(list(OPERATIONS))
        self.engine_box = QComboBox()
        self.engine_box.addItems(["cached", "switch"])
        self.run_button = QPushButton("Calcular en transistores")
        self.run_button.clicked.connect(self.run)

        form = QFormLayout()
        form.addRow("Operando a (decimal o 0x…)", self.a_edit)
        form.addRow("Operando b (decimal o 0x…)", self.b_edit)
        form.addRow("Operación", self.op_box)
        form.addRow("Formato", self.fmt_box)
        form.addRow("Motor", self.engine_box)
        form.addRow(self.run_button)
        inputs = QGroupBox("Entrada")
        inputs.setLayout(form)

        self.bits = QTableWidget(3, 6)
        self.bits.setHorizontalHeaderLabels(["valor", "hex", "s", "exponente", "fracción", "clase"])
        self.bits.setVerticalHeaderLabels(["a", "b", "resultado"])
        self.bits.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bits.setFont(_mono())
        self.bits.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.bits.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.bits.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bits_box = QGroupBox("Bits (signo | exponente | fracción)")
        bits_layout = QVBoxLayout()
        bits_layout.addWidget(self.bits)
        bits_box.setLayout(bits_layout)

        self.flags = QLabel("—")
        self.metrics = {
            k: QLabel("—") for k in ("transistores", "conmutaciones", "eventos", "tiempo")
        }
        summary = QFormLayout()
        summary.addRow("Flags", self.flags)
        summary.addRow("Transistores", self.metrics["transistores"])
        summary.addRow("Conmutaciones de nodo*", self.metrics["conmutaciones"])
        summary.addRow("Eventos de transistor*", self.metrics["eventos"])
        summary.addRow("Tiempo de simulación", self.metrics["tiempo"])
        summary.addRow(QLabel("<small>* respecto de la operación anterior</small>"))
        summary_box = QGroupBox("Resultado")
        summary_box.setLayout(summary)

        # Detalle de la operación en pestañas: ciclos, actividad y buses de etapa.
        self.period = QSpinBox()
        self.period.setRange(1, 1000)
        self.period.setValue(reference_period())
        self.period.setSuffix(" celdas")
        self.period.valueChanged.connect(self._show_cycles)
        self.cycles_summary = QLabel("Calcule una operación para ver sus ciclos.")
        self.cycles = _table(["Ciclo", "Celdas del camino crítico", "Etapas que ocupa"])
        period_row = QHBoxLayout()
        period_row.addWidget(self.cycles_summary, 1)
        period_row.addWidget(QLabel("Periodo de reloj:"))
        period_row.addWidget(self.period)
        cycles_page = QWidget()
        cycles_layout = QVBoxLayout(cycles_page)
        cycles_layout.addLayout(period_row)
        cycles_layout.addWidget(self.cycles)
        cycles_layout.addWidget(
            QLabel(
                "<small>Estimación de ADR-0014: cada celda cuesta una unidad de retardo; el "
                "periodo por defecto es el camino crítico de la ALU entera.</small>"
            )
        )
        self.activity = _table(["Etapa", "Conmutaciones de nodo", "% del total"])
        self.stages = _table(["Bus", "Valor (hex)"])
        self.details = QTabWidget()
        self.details.addTab(cycles_page, "Ciclos de reloj")
        self.details.addTab(self.activity, "Actividad por etapa")
        self.details.addTab(self.stages, "Buses de etapa (dbg_)")

        top = QHBoxLayout()
        top.addWidget(inputs, 1)
        top.addWidget(summary_box, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(bits_box)
        layout.addWidget(self.details, 1)

    def run(self) -> None:
        """Lee la entrada y lanza el cálculo en un hilo de trabajo."""
        fmt = FORMATS[self.fmt_box.currentText()]
        op = OPERATIONS[self.op_box.currentText()]
        engine: EngineName = "switch" if self.engine_box.currentText() == "switch" else "cached"
        try:
            a = parse_operand(self.a_edit.text(), fmt)
            b = parse_operand(self.b_edit.text(), fmt)
        except (ValueError, ZeroDivisionError) as exc:
            QMessageBox.warning(self, "Operando inválido", str(exc))
            return
        self.run_button.setEnabled(False)
        self.metrics["tiempo"].setText("calculando…")
        task = _Task(lambda: calculate(fmt, op, a, b, engine))
        task.signals.done.connect(self.show_result)
        task.signals.failed.connect(self._failed)
        self.pool.start(task)

    def show_result(self, calc: Calculation) -> None:
        """Muestra un :class:`Calculation` en la ventana."""
        self.run_button.setEnabled(True)
        fmt = calc.fmt
        for row, bits in enumerate((calc.a, calc.b, calc.result.bits)):
            s, e, f = fmt.fields(bits)
            values = [
                f"{ref.to_float(fmt, bits):.9g}",
                f"0x{bits:0{fmt.width // 4}X}",
                str(s),
                f"{e:0{fmt.exp_bits}b}",
                f"{f:0{fmt.frac_bits}b}",
                fmt.classify(bits).value,
            ]
            for col, text in enumerate(values):
                self.bits.setItem(row, col, QTableWidgetItem(text))
        self.flags.setText(str(calc.result.flags))
        self.metrics["transistores"].setText(str(calc.transistors))
        self.metrics["conmutaciones"].setText(str(calc.toggles))
        self.metrics["eventos"].setText(str(calc.events))
        self.metrics["tiempo"].setText(f"{calc.seconds * 1000:.1f} ms")
        _fill(self.stages, [[k, "X" if v is None else f"0x{v:X}"] for k, v in calc.stages.items()])
        total = sum(calc.stage_toggles.values()) or 1
        _fill(
            self.activity,
            [
                [STAGE_NAMES.get(name, name), str(n), f"{100 * n / total:.1f} %"]
                for name, n in sorted(calc.stage_toggles.items(), key=lambda kv: -kv[1])
            ],
        )
        self.last = calc
        self._show_cycles()
        self.calculated.emit(calc)

    def _show_cycles(self) -> None:
        if self.last is None:
            return
        netlist = self.last.unit.netlist
        total, groups = cycle_groups(netlist, self.period.value())
        count = len(schedule(critical_stages(netlist), self.period.value()))
        self.cycles_summary.setText(
            f"<b>{netlist.name}</b>: camino crítico de {total} celdas → <b>{count} ciclos</b> "
            "estimados"
        )
        _fill(self.cycles, [list(g) for g in groups])

    def _failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.metrics["tiempo"].setText("error")
        QMessageBox.critical(self, "Error de simulación", message)


# -------------------------------------------------------------- pestaña programa
class ProgramTab(QWidget):
    """Carga, ensambla y ejecuta programas ``.t754`` en la máquina de transistores."""

    def __init__(self, pool: QThreadPool) -> None:
        super().__init__()
        self.pool = pool
        self.machine: Any = None
        self.source = QPlainTextEdit()
        self.source.setFont(_mono())
        self.source.setPlainText("LI F1, 1.5\nLI F2, 2.25\nFADD F3, F1, F2\nOUT F3\nHALT\n")
        open_button = QPushButton("Abrir .t754…")
        open_button.clicked.connect(self.open_file)
        self.load_button = QPushButton("Ensamblar y reiniciar")
        self.load_button.clicked.connect(self.load)
        self.step_button = QPushButton("Paso")
        self.step_button.clicked.connect(self.step)
        self.run_button = QPushButton("Ejecutar hasta HALT")
        self.run_button.clicked.connect(self.run)
        buttons = QHBoxLayout()
        for button in (open_button, self.load_button, self.step_button, self.run_button):
            buttons.addWidget(button)

        self.regs = QTableWidget(isa.N_REGS, 2)
        self.regs.setHorizontalHeaderLabels(["hex", "valor"])
        self.regs.setVerticalHeaderLabels([f"F{i}" for i in range(isa.N_REGS)])
        self.regs.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.regs.setFont(_mono())
        self.regs.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r in range(isa.N_REGS):
            for c in range(2):
                self.regs.setItem(r, c, QTableWidgetItem("—"))
        self.status = QLabel("Sin programa cargado: pulse «Ensamblar y reiniciar».")
        self.outputs = QListWidget()
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Registros</b>"))
        right.addWidget(self.regs)
        right.addWidget(self.status)
        right.addWidget(QLabel("<b>Salidas (OUT)</b>"))
        right.addWidget(self.outputs)

        intro = QLabel(
            "La FPU dentro de una CPU: el programa se ensambla y se ejecuta en la máquina "
            "T754, con el decodificador, el banco de registros y la FPU de transistores."
        )
        intro.setWordWrap(True)
        left = QVBoxLayout()
        left.addWidget(intro)
        left.addWidget(self.source)
        left.addLayout(buttons)
        layout = QHBoxLayout(self)
        layout.addLayout(left, 3)
        layout.addLayout(right, 2)
        self._set_running(False)

    def _set_running(self, ready: bool) -> None:
        self.step_button.setEnabled(ready)
        self.run_button.setEnabled(ready)

    def open_file(self) -> None:
        """Abre un archivo ``.t754`` en el editor."""
        path, _ = QFileDialog.getOpenFileName(self, "Abrir programa", "", "Programas (*.t754)")
        if path:
            self.source.setPlainText(Path(path).read_text(encoding="utf-8"))

    def load(self) -> None:
        """Ensambla el editor y crea una máquina nueva."""
        try:
            words = assemble(self.source.toPlainText(), filename="editor")
        except AssemblyError as exc:
            QMessageBox.warning(self, "Error de ensamblado", str(exc))
            return
        from transim.cpu.machine import Machine

        self.status.setText("Construyendo la máquina…")
        self.load_button.setEnabled(False)
        task = _Task(lambda: Machine(words))
        task.signals.done.connect(self._loaded)
        task.signals.failed.connect(self._failed)
        self.pool.start(task)

    def _loaded(self, machine: object) -> None:
        self.machine = machine
        self.load_button.setEnabled(True)
        self.outputs.clear()
        self.refresh()
        self._set_running(True)

    def step(self) -> None:
        """Ejecuta una instrucción."""
        self._background(lambda: self.machine.step())

    def run(self) -> None:
        """Ejecuta hasta HALT."""
        self._background(lambda: self.machine.run())

    def _background(self, fn: Callable[[], object]) -> None:
        if self.machine is None:
            return
        self._set_running(False)
        task = _Task(fn)
        task.signals.done.connect(self._after_run)
        task.signals.failed.connect(self._failed)
        self.pool.start(task)

    def _after_run(self, _result: object) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Muestra el estado arquitectónico de la máquina."""
        state = self.machine.state
        fmt = self.machine.fmt
        for r, value in enumerate(state.regs):
            self.regs.setItem(r, 0, QTableWidgetItem(f"0x{value:08X}"))
            self.regs.setItem(r, 1, QTableWidgetItem(f"{ref.to_float(fmt, value):.9g}"))
        self.outputs.clear()
        for value in state.outputs:
            self.outputs.addItem(f"0x{value:08X}  ({ref.to_float(fmt, value):.9g})")
        phase = "HALT" if state.halted else f"PC = {state.pc}"
        self.status.setText(f"{phase} · FSR = 0x{state.fsr:08X} · {state.steps} instrucciones")
        self._set_running(not state.halted)

    def _failed(self, message: str) -> None:
        self.load_button.setEnabled(True)
        self.status.setText("error")
        QMessageBox.critical(self, "Error de ejecución", message)


# ----------------------------------------------------------- pestaña transistores
LEAF_CELLS = [name for name, build in CELLS.items() if not build().instances]
"""Celdas primitivas de la biblioteca (sin sub-instancias): las que se dibujan."""


def instance_toggles(engine: SwitchEngine, inst: Instance) -> int:
    """Conmutaciones de los nodos que manejan los canales de ``inst`` (contadores actuales)."""
    nodes = {n.id for t in inst.transistors for n in (t.source, t.drain) if not n.is_source}
    return sum(engine.node_toggles[i] for i in nodes)


class TransistorTab(QWidget):
    """Microscopio: de los bloques de una unidad hasta cada transistor, en esquema o en
    silicio, con un inspector que muestra el corte transversal del transistor elegido."""

    def __init__(self) -> None:
        super().__init__()
        self.scene = CircuitScene()
        self.view = CanvasView(self.scene)
        self.info = QLabel("Elija una celda de la biblioteca o calcule una operación.")
        self.info.setWordWrap(True)
        self.unit: HardwareUnit | None = None
        self._children: dict[str | None, list[Instance]] = {}
        self._current: tuple[str, object] | None = None

        self.cell_box = QComboBox()
        self.cell_box.addItems(LEAF_CELLS)
        self.cell_box.currentTextChanged.connect(self.set_cell)
        self.inputs_row = QHBoxLayout()
        self.outputs = QLabel()
        self.outputs.setFont(_mono())
        library = QWidget()
        lib_layout = QVBoxLayout(library)
        lib_layout.addWidget(QLabel("Celda"))
        lib_layout.addWidget(self.cell_box)
        lib_layout.addWidget(QLabel("Entradas (o haga clic en ellas en el dibujo)"))
        lib_layout.addLayout(self.inputs_row)
        lib_layout.addWidget(QLabel("Salidas"))
        lib_layout.addWidget(self.outputs)
        lib_layout.addStretch(1)
        self.checks: dict[str, QCheckBox] = {}

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["instancia", "definición", "T", "conm."])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setMinimumWidth(300)
        self.tree.itemExpanded.connect(self._expand)
        self.tree.currentItemChanged.connect(self._select)

        self.sources = QTabWidget()
        self.sources.addTab(library, "Biblioteca")
        self.sources.addTab(self.tree, "Última operación")

        self.schematic_button = QPushButton("Esquema")
        self.silicon_button = QPushButton("Silicio")
        for b in (self.schematic_button, self.silicon_button):
            b.setCheckable(True)
            b.setAutoExclusive(True)
        self.schematic_button.setChecked(True)
        self.schematic_button.setToolTip("Esquema eléctrico CMOS: redes pull-up y pull-down")
        self.silicon_button.setToolTip(
            "Layout ilustrativo: difusión, polisilicio y metal, como se vería en el chip"
        )
        self.schematic_button.toggled.connect(self._redraw)
        fit = QPushButton("Ajustar")
        fit.clicked.connect(lambda: self.view.fit())
        zoom_in, zoom_out = QPushButton("+"), QPushButton("−")
        zoom_in.clicked.connect(self.view.zoom_in)
        zoom_out.clicked.connect(self.view.zoom_out)
        self.legend = QLabel()
        self.legend.setWordWrap(True)

        self.inspector_title = QLabel("<b>Inspector</b>")
        self.inspector_text = QLabel(
            "Pase el ratón por un transistor o un cable. Un clic fija el transistor."
        )
        self.inspector_text.setWordWrap(True)
        self.section = CrossSection()
        inspector = QVBoxLayout()
        inspector.addWidget(self.inspector_title)
        inspector.addWidget(self.inspector_text)
        inspector.addWidget(self.section)
        inspector.addStretch(1)
        inspector_box = QWidget()
        inspector_box.setLayout(inspector)
        inspector_box.setFixedWidth(320)

        bar = QHBoxLayout()
        bar.addWidget(self.schematic_button)
        bar.addWidget(self.silicon_button)
        bar.addWidget(self.info, 1)
        for button in (zoom_out, zoom_in, fit):
            bar.addWidget(button)
        center = QVBoxLayout()
        center.addLayout(bar)
        center.addWidget(self.view, 1)
        center.addWidget(self.legend)
        layout = QHBoxLayout(self)
        layout.addWidget(self.sources, 2)
        layout.addLayout(center, 6)
        layout.addWidget(inspector_box)

        self.scene.hovered.connect(self._hover)
        self.view.clicked.connect(self._clicked)
        self.set_cell(LEAF_CELLS[0])

    # ------------------------------------------------------------- dibujo
    @property
    def silicon(self) -> bool:
        return self.silicon_button.isChecked()

    def _legend(self) -> None:
        t = theme.current()
        if self.silicon:
            from transim.ui.gui.canvas import LAYER_COLOR, LAYER_NAMES

            parts = [
                f"<span style='color:{LAYER_COLOR[k]}'>■</span> {LAYER_NAMES[k]}"
                for k in ("pdiff", "ndiff", "poly", "metal1", "metal2")
            ]
            parts.append(f"<span style='color:{t.on}'>■</span> canal que conduce")
            self.legend.setText(" · ".join(parts) + " · layout ilustrativo, no a escala")
        else:
            self.legend.setText(
                f"<span style='color:{t.one}'>■</span> 1 · <span style='color:{t.zero}'>■</span> 0"
                f" · <span style='color:{t.unknown}'>■</span> X · canal continuo: conduce; "
                "cortado: no conduce · fondo verde: camino que fija la salida · "
                "arrastre para moverse, rueda para el zoom"
            )

    def _draw(self, bindings: list[tuple[Binding, str]], values: Any, clickable: bool) -> None:
        if self.silicon:
            self.scene.show_silicon([("", bindings)], values, clickable=clickable)
        else:
            self.scene.show_schematics(bindings, values, clickable=clickable)
        self._legend()
        self.view.fit()

    def _redraw(self) -> None:
        if self._current is None:
            return
        kind, what = self._current
        if kind == "cell":
            self.apply_inputs()
        elif isinstance(what, QTreeWidgetItem):
            self._select(what)

    # ------------------------------------------------------------- biblioteca
    def set_cell(self, name: str) -> None:
        """Muestra la celda ``name`` con todas sus entradas en 0."""
        self.cell = CELLS[name]()
        self.engine = SwitchEngine(self.cell)
        while self.inputs_row.count():
            taken = self.inputs_row.takeAt(0)
            widget = taken.widget() if taken is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.checks = {}
        for port in self.cell.inputs:
            box = QCheckBox(port)
            box.toggled.connect(self.apply_inputs)
            self.inputs_row.addWidget(box)
            self.checks[port] = box
        self._current = ("cell", name)
        self.apply_inputs()

    def apply_inputs(self) -> None:
        """Aplica las entradas marcadas a la celda y redibuja sus transistores."""
        before = {n.id: self.engine.value(n) for n in self.cell.nodes}
        self.engine.set_inputs({p: int(box.isChecked()) for p, box in self.checks.items()})
        outs = "  ".join(f"{p} = {self.engine.read(p).name}" for p in self.cell.outputs)
        self.outputs.setText(outs.replace("ZERO", "0").replace("ONE", "1"))
        n = len(self.cell.transistors)
        self._draw(
            [(bind_cell(self.cell), f"{self.cell.name} · {n} transistores")], self.engine, True
        )
        changed = {i for i, v in before.items() if v != self.engine.value(self.cell.nodes[i])}
        self._animate(changed)
        self.info.setText(
            f"Celda {self.cell.name}: {self.scene.flowing} de {n} transistores conducen. "
            "Haga clic en una entrada para cambiarla."
        )

    def _animate(self, changed: set[int]) -> None:
        """Corriente transitoria por los transistores que cargaron o descargaron un nodo."""
        from transim.ui.gui.canvas import SchematicItem

        flows = {}
        for item in self.scene.cells:
            if not isinstance(item, SchematicItem):
                continue
            state = item.binding.state(self.engine)
            path: set[int] = set()
            for stage, _, _ in item.geo.stages:
                if item.node_id(stage.output) in changed:
                    out = self.engine.value(item.binding.nodes[stage.output])
                    tree = stage.pull_up if out is Logic.ONE else stage.pull_down
                    path |= active_path(tree, state)
            flows[item] = path
        self.scene.start_flow(flows)

    # -------------------------------------------------------------- ratón
    def _clicked(self, hit: Hit | None) -> None:
        if hit is None:
            self.scene.select(None, None)
            return
        if hit.kind == "input" and hit.port in self.checks:
            box = self.checks[hit.port]
            box.setChecked(not box.isChecked())
            return
        if hit.kind == "transistor":
            self.scene.select(hit.item, hit.transistor)
            self._inspect(hit)

    def _hover(self, hit: Hit | None) -> None:
        if hit is None or hit.kind == "cell":
            if self.scene.selected_transistor is not None and self.scene.selected_item is not None:
                self._inspect(
                    Hit(self.scene.selected_item, "transistor", self.scene.selected_transistor)
                )
            return
        self._inspect(hit)

    def _inspect(self, hit: Hit) -> None:
        values = self.scene.values
        if values is None:
            return
        b = hit.binding
        if hit.kind == "transistor" and hit.transistor is not None:
            t = b.transistors[hit.transistor]
            c = b.circuit
            d = c.transistors[hit.transistor]
            dev = Device(
                pmos=t.kind is TransistorType.PMOS,
                name=d.name,
                gate=c.label(d.gate.id),
                source=c.label(d.source.id),
                drain=c.label(d.drain.id),
                gate_value=values.value(t.gate),
                source_value=values.value(t.source),
                drain_value=values.value(t.drain),
                state=values.conduction(t),
            )
            flowing = hit.item in self.scene.flows and hit.transistor in self.scene.flows[hit.item]
            self.section.show_device(dev, flowing)
            kind = "pMOS" if dev.pmos else "nMOS"
            where = f" en {b.path}" if b.path else ""
            self.inspector_title.setText(f"<b>{kind} {d.name}</b>{where}")
            self.inspector_text.setText(explain(dev))
        elif hit.node is not None:
            node = next((n for n in b.nodes.values() if n.id == hit.node), None)
            if node is None:
                return
            v = values.value(node)
            self.inspector_title.setText(f"<b>Nodo {node.name}</b>")
            self.inspector_text.setText(
                f"Valor {logic_text(v)}. Se resalta en amarillo en todas las celdas "
                "a las que llega."
            )

    # -------------------------------------------------------- última operación
    def show_calculation(self, calc: Calculation) -> None:
        """Carga la jerarquía de la unidad que hizo el último cálculo."""
        self.unit = calc.unit
        netlist = calc.unit.netlist
        self._children = {}
        for inst in netlist.instances:
            self._children.setdefault(inst.parent, []).append(inst)
        self.tree.clear()
        root = QTreeWidgetItem([netlist.name, "unidad", str(len(netlist.transistors)), ""])
        root.setData(0, Qt.ItemDataRole.UserRole, "unit")
        self.tree.addTopLevelItem(root)
        self._fill(root, None)
        root.setExpanded(True)

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
                group = QTreeWidgetItem(
                    [
                        f"{STAGE_NAMES[GLUE]} ({len(glue)} celdas)",
                        "celdas sueltas",
                        str(sum(len(i.transistors) for i in glue)),
                        "",
                    ]
                )
                group.addChildren([self._item(i) for i in glue])
                item.addChild(group)
            return
        item.addChildren([self._item(inst) for inst in children])

    def _item(self, inst: Instance) -> QTreeWidgetItem:
        assert self.unit is not None
        name = inst.path.rsplit(".", 1)[-1]
        if inst.parent is None and name in STAGE_NAMES:
            name = f"{name} · {STAGE_NAMES[name]}"
        child = QTreeWidgetItem(
            [
                name,
                inst.definition.name,
                str(len(inst.transistors)),
                str(instance_toggles(self.unit.engine, inst)),
            ]
        )
        child.setData(0, Qt.ItemDataRole.UserRole, inst)
        if not inst.is_leaf:
            child.addChild(QTreeWidgetItem(["…"]))  # se llena al expandir
        return child

    def _expand(self, item: QTreeWidgetItem) -> None:
        inst = item.data(0, Qt.ItemDataRole.UserRole)
        placeholder = item.child(0) if item.childCount() == 1 else None
        if isinstance(inst, Instance) and placeholder is not None and placeholder.text(0) == "…":
            item.takeChild(0)
            self._fill(item, inst.path)

    def _select(self, item: QTreeWidgetItem | None, _previous: object = None) -> None:
        inst = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if self.unit is None or item is None:
            return
        engine = self.unit.engine
        netlist = self.unit.netlist
        self._current = ("tree", item)
        if inst == "unit":
            groups = []
            for top in netlist.top_instances():
                if top.is_leaf:
                    continue
                cells = [c for c in netlist.leaf_instances() if c.path.startswith(f"{top.path}.")]
                groups.append((top.path, [(bind_instance(c), c.path) for c in cells]))
            glue = [c for c in netlist.top_instances() if c.is_leaf]
            groups.append((STAGE_NAMES[GLUE], [(bind_instance(c), c.path) for c in glue]))
            self.silicon_button.setChecked(True)
            n = len(netlist.transistors)
            self.scene.show_silicon(groups, engine, die=(netlist.name, f"{n} transistores"))
            self._legend()
            self.view.fit()
            self.info.setText(
                f"{netlist.name}: el chip completo, {n} transistores en filas de celdas "
                "estándar. Acérquese con la rueda hasta ver cada transistor."
            )
            return
        if not isinstance(inst, Instance):
            return
        toggles = instance_toggles(engine, inst)
        n = len(inst.transistors)
        if inst.is_leaf:
            cells = [inst]
        elif n <= BLOCK_LIMIT or self.silicon:
            cells = [c for c in netlist.leaf_instances() if c.path.startswith(f"{inst.path}.")]
        else:
            self.info.setText(
                f"{inst.path}: bloque {inst.definition.name} con {n} transistores y {toggles} "
                f"conmutaciones. Su esquema es muy grande (más de {BLOCK_LIMIT} transistores): "
                "véalo en Silicio o expándalo y elija una parte."
            )
            return
        base = "" if inst.is_leaf else f"{inst.path}."
        bindings = [(bind_instance(c), c.path[len(base) :] or c.path) for c in cells]
        self._draw(bindings, engine, False)
        what = "celda" if inst.is_leaf else f"bloque de {len(cells)} celdas"
        self.info.setText(
            f"{inst.path} ({inst.definition.name}, {what}): {self.scene.flowing} de {n} "
            f"transistores conducen; {toggles} conmutaciones en la última operación."
        )


# ------------------------------------------------------------------------ ventana
def create_window() -> QMainWindow:
    """Construye la ventana principal (``QMainWindow``) sin mostrarla.

    El título contiene "TranSim754". Separar la construcción de ``main`` permite
    probarla sin bucle de eventos (``QT_QPA_PLATFORM=offscreen``).
    """
    window = QMainWindow()
    window.setWindowTitle(TITLE)
    pool = QThreadPool.globalInstance()
    tabs = QTabWidget()
    operation = OperationTab(pool)
    transistors = TransistorTab()
    operation.calculated.connect(transistors.show_calculation)
    tabs.addTab(operation, "Operación")
    tabs.addTab(transistors, "Transistores")
    tabs.addTab(ProgramTab(pool), "Programa")
    window.setCentralWidget(tabs)
    window.resize(1360, 820)
    return window


def main() -> int:
    """Abre la ventana principal y entra al bucle de eventos; devuelve el código de salida.

    Ventana: entrada de dos operandos (decimal o hex) y del formato; operación; vista de
    bits signo/exponente/fracción de operandos y resultado; flags; etapas de la
    operación (buses ``dbg_``); ciclos de reloj estimados; conteo de transistores y
    conmutaciones; pestaña de transistores que baja de los bloques de la unidad hasta
    cada nMOS y pMOS con su estado; pestaña para ejecutar programas ``.t754`` paso a paso.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    if isinstance(app, QApplication):
        theme.apply(app, theme.DARK if theme.system_prefers_dark() else theme.LIGHT)
    window = create_window()
    window.show()
    return int(app.exec())
