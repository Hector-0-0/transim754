"""Interfaz gráfica de escritorio con PySide6. ADR-0011.

Requiere el extra ``gui`` (``make install-gui``). Ver ``ui/gui/GUIA.md``.

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
from transim.ui.gui.transistor_view import CellScene, ZoomView

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


def cycles_report(netlist: Netlist, period: int, stage_toggles: dict[str, int]) -> str:
    """Texto de la consola de ciclos (ADR-0014): el camino crítico repartido en ciclos de
    ``period`` celdas y las conmutaciones de cada etapa en la última operación."""
    stages = critical_stages(netlist)
    total = sum(st.cells for st in stages)
    cycles = schedule(stages, period)
    lines = [
        f"{netlist.name} · camino crítico: {total} celdas",
        f"Periodo de reloj: {period} celdas → {len(cycles)} ciclos (estimado, ADR-0014)",
        "",
    ]
    i = 0
    while i < len(cycles):
        j = i
        while j + 1 < len(cycles) and cycles[j + 1].stages == cycles[i].stages:
            j += 1
        first, last = cycles[i], cycles[j]
        which = f"Ciclo {first.index}" if i == j else f"Ciclos {first.index}–{last.index}"
        cells = f"celdas {first.first_cell}–{last.last_cell}"
        lines.append(f"{which:<14} {cells:<18} {' · '.join(first.stages)}")
        i = j + 1
    if stage_toggles:
        lines += ["", "Conmutaciones por etapa en esta operación:"]
        for name, n in sorted(stage_toggles.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {STAGE_NAMES.get(name, name):<28} {n:>7}")
    return "\n".join(lines)


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
        self.bits.setMinimumHeight(130)
        self.bits.setMaximumHeight(150)
        bits_box = QGroupBox("Bits (signo | exponente | fracción)")
        bits_layout = QVBoxLayout()
        bits_layout.addWidget(self.bits)
        bits_box.setLayout(bits_layout)

        self.flags = QLabel("—")
        self.metrics = {
            k: QLabel("—") for k in ("transistores", "conmutaciones", "eventos", "tiempo")
        }
        self.stages = QPlainTextEdit()
        self.stages.setReadOnly(True)
        self.stages.setFont(_mono())
        summary = QFormLayout()
        summary.addRow("Flags", self.flags)
        summary.addRow("Transistores", self.metrics["transistores"])
        summary.addRow("Conmutaciones de nodo*", self.metrics["conmutaciones"])
        summary.addRow("Eventos de transistor*", self.metrics["eventos"])
        summary.addRow("Tiempo de simulación", self.metrics["tiempo"])
        summary.addRow(QLabel("<small>* respecto de la operación anterior</small>"))
        summary_box = QGroupBox("Resultado")
        summary_box.setLayout(summary)
        stages_box = QGroupBox("Etapas (buses dbg_ de la unidad)")
        stages_layout = QVBoxLayout()
        stages_layout.addWidget(self.stages)
        stages_box.setLayout(stages_layout)

        self.period = QSpinBox()
        self.period.setRange(1, 1000)
        self.period.setValue(reference_period())
        self.period.setSuffix(" celdas")
        self.period.valueChanged.connect(self._show_cycles)
        self.cycles = QPlainTextEdit()
        self.cycles.setReadOnly(True)
        self.cycles.setFont(_mono())
        self.cycles.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("Periodo de reloj (por defecto, la ALU entera):"))
        period_row.addWidget(self.period)
        period_row.addStretch(1)
        cycles_box = QGroupBox("Ciclos de reloj estimados a partir del camino crítico")
        cycles_layout = QVBoxLayout()
        cycles_layout.addLayout(period_row)
        cycles_layout.addWidget(self.cycles)
        cycles_box.setLayout(cycles_layout)
        bottom = QHBoxLayout()
        bottom.addWidget(stages_box, 1)
        bottom.addWidget(cycles_box, 3)

        top = QHBoxLayout()
        top.addWidget(inputs, 1)
        top.addWidget(summary_box, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(bits_box)
        layout.addLayout(bottom, 1)

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
        self.stages.setPlainText(
            "\n".join(f"{k:<14} {'X' if v is None else hex(v)}" for k, v in calc.stages.items())
            or "(la unidad no expone etapas)"
        )
        self.last = calc
        self._show_cycles()
        self.calculated.emit(calc)

    def _show_cycles(self) -> None:
        if self.last is not None:
            self.cycles.setPlainText(
                cycles_report(self.last.unit.netlist, self.period.value(), self.last.stage_toggles)
            )

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
        self.status = QLabel("Sin programa cargado.")
        self.outputs = QListWidget()
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Registros</b>"))
        right.addWidget(self.regs)
        right.addWidget(self.status)
        right.addWidget(QLabel("<b>Salidas (OUT)</b>"))
        right.addWidget(self.outputs)

        left = QVBoxLayout()
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
    """Microscopio: de los bloques de una unidad hasta cada transistor y su estado."""

    def __init__(self) -> None:
        super().__init__()
        self.scene = CellScene()
        self.view = ZoomView(self.scene)
        self.info = QLabel("Elija una celda de la biblioteca o calcule una operación.")
        self.info.setWordWrap(True)
        self.unit: HardwareUnit | None = None
        self._children: dict[str | None, list[Instance]] = {}

        # Fuente 1: una celda de la biblioteca con entradas elegidas por el usuario.
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
        lib_layout.addWidget(QLabel("Entradas"))
        lib_layout.addLayout(self.inputs_row)
        lib_layout.addWidget(QLabel("Salidas"))
        lib_layout.addWidget(self.outputs)
        lib_layout.addStretch(1)
        self.checks: dict[str, QCheckBox] = {}

        # Fuente 2: la jerarquía de la unidad de la última operación.
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["instancia", "definición", "T", "conm."])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setMinimumWidth(330)
        self.tree.itemExpanded.connect(self._expand)
        self.tree.currentItemChanged.connect(self._select)

        self.sources = QTabWidget()
        self.sources.addTab(library, "Biblioteca")
        self.sources.addTab(self.tree, "Última operación")
        fit = QPushButton("Ajustar vista")
        fit.clicked.connect(self.view.fit)
        legend = QLabel(
            "<span style='color:#1f9d55'>■</span> conduce · "
            "<span style='color:#b8bcc2'>■</span> no conduce · "
            "<span style='color:#d64545'>1</span> / <span style='color:#2f6fd6'>0</span> / "
            "<span style='color:#e0a100'>X</span> valor del nodo · rueda: zoom"
        )
        right = QVBoxLayout()
        right.addWidget(self.info)
        right.addWidget(self.view, 1)
        bar = QHBoxLayout()
        bar.addWidget(legend, 1)
        bar.addWidget(fit)
        right.addLayout(bar)
        layout = QHBoxLayout(self)
        layout.addWidget(self.sources, 2)
        layout.addLayout(right, 5)
        self.set_cell(LEAF_CELLS[0])

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
        self.apply_inputs()
        self.view.fit()

    def apply_inputs(self) -> None:
        """Aplica las entradas marcadas a la celda y redibuja sus transistores."""
        self.engine.set_inputs({p: int(box.isChecked()) for p, box in self.checks.items()})
        outs = "  ".join(f"{p} = {self.engine.read(p).name}" for p in self.cell.outputs)
        self.outputs.setText(outs.replace("ZERO", "0").replace("ONE", "1"))
        n = len(self.cell.transistors)
        self.scene.draw(
            self.cell.transistors,
            self.engine.value,
            self.engine.conduction,
            title=f"{self.cell.name} · {n} transistores",
        )
        self.info.setText(
            f"Celda {self.cell.name}: {self.scene.flowing} de {n} transistores conducen con "
            "estas entradas. Cambie una entrada para ver qué transistores conmutan."
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
        if not isinstance(inst, Instance) or self.unit is None:
            return
        engine = self.unit.engine
        toggles = instance_toggles(engine, inst)
        if not inst.is_leaf:
            self.info.setText(
                f"{inst.path}: bloque {inst.definition.name} con {len(inst.transistors)} "
                f"transistores y {toggles} conmutaciones en la última operación. "
                "Expándalo hasta una celda para ver sus transistores."
            )
            return
        self.scene.draw(
            inst.transistors,
            engine.value,
            engine.conduction,
            prefix=f"{inst.path}.",
            title=f"{inst.path} · {inst.definition.name}",
        )
        self.view.fit()
        self.info.setText(
            f"{inst.path} ({inst.definition.name}) en la última operación: "
            f"{self.scene.flowing} de {len(inst.transistors)} transistores conducen; "
            f"{toggles} conmutaciones de sus nodos."
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
    window.resize(1100, 720)
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
    window = create_window()
    window.show()
    return int(app.exec())
