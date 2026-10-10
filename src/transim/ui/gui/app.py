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

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
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
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from transim.core.unit import EngineName, HardwareUnit
from transim.cpu import isa
from transim.cpu.assembler import AssemblyError, assemble
from transim.fpu.format import FORMATS, FloatFormat, FPResult
from transim.reference import fpu as ref

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
    )


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
    """Operandos, vista de bits, flags, etapas y métricas de una operación."""

    def __init__(self, pool: QThreadPool) -> None:
        super().__init__()
        self.pool = pool
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

        top = QHBoxLayout()
        top.addWidget(inputs, 1)
        top.addWidget(summary_box, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(bits_box)
        layout.addWidget(stages_box, 1)

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
    tabs.addTab(OperationTab(pool), "Operación")
    tabs.addTab(ProgramTab(pool), "Programa")
    window.setCentralWidget(tabs)
    window.resize(1000, 680)
    return window


def main() -> int:
    """Abre la ventana principal y entra al bucle de eventos; devuelve el código de salida.

    Ventana: entrada de dos operandos (decimal o hex) y del formato; operación; vista de
    bits signo/exponente/fracción de operandos y resultado; flags; etapas de la
    operación (buses ``dbg_``); conteo de transistores y conmutaciones; pestaña para
    cargar y ejecutar programas ``.t754`` paso a paso.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    window = create_window()
    window.show()
    return int(app.exec())
