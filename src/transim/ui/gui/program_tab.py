"""Pestaña Programa: la FPU dentro de una CPU.

Un programa ``.t754`` se ensambla y se ejecuta en la máquina T754 (decodificador, banco
de registros de flip-flops, ALU y FPU de transistores), paso a paso o hasta ``HALT``.
El editor marca la instrucción que sigue y la línea de un error de ensamblado; los
registros que cambian en un paso se resaltan.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, QRegularExpression, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from transim.cpu import isa
from transim.cpu.assembler import AssemblyError, assemble, disassemble
from transim.fpu.format import BINARY32
from transim.ui.gui import theme as th
from transim.ui.gui.model import CLASS_NAMES, hex_text, instruction_lines, value_text
from transim.ui.gui.operation_tab import mono, table
from transim.ui.gui.widgets import FLAG_CHIPS, Chip, Chips, card, hint
from transim.ui.gui.worker import Task

DEFAULT_PROGRAM = """; Suma simple en binary32: 1.5 + 2.25 = 3.75
LI   F1, 1.5
LI   F2, 2.25
FADD F3, F1, F2
OUT  F3
HALT
"""

EXAMPLES_DIR = Path(__file__).resolve().parents[4] / "examples"

INT_CHIPS = [
    Chip("C", "C acarreo", "Acarreo de la última suma o resta entera (ADD/SUB)."),
    Chip("V", "V desborde", "Desborde con signo de la última operación entera."),
    Chip("Z", "Z cero", "El último resultado entero fue cero."),
    Chip("N", "N negativo", "El último resultado entero fue negativo."),
]


def fsr_keys(fsr: int) -> set[str]:
    """Indicadores encendidos del registro de estado FSR (ADR-0004)."""
    keys = set()
    for k, name in enumerate(("NX", "UF", "OF", "DZ", "NV")):
        if fsr >> k & 1:
            keys.add(name)
    for bit, name in ((isa.FSR_C, "C"), (isa.FSR_V, "V"), (isa.FSR_Z, "Z"), (isa.FSR_N, "N")):
        if fsr >> bit & 1:
            keys.add(name)
    return keys


# ---------------------------------------------------------------- editor
class Highlighter(QSyntaxHighlighter):
    """Colores del ensamblador: mnemónicos, registros, literales y comentarios."""

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - API de Qt
        t = th.current()

        def fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            f.setFontItalic(italic)
            return f

        names = "|".join(op.name for op in isa.Opcode)
        rules = [
            (rf"^\s*({names})\b", fmt(t.accent, bold=True)),
            (r"\b[fF][0-7]\b", fmt(t.exponent)),
            (
                r"\b0[xX][0-9A-Fa-f]+\b|-?\b\d+(\.\d+)?([eE][-+]?\d+)?(/\d+)?\b|\b(inf|nan)\b",
                fmt(t.warn),
            ),
        ]
        for pattern, f in rules:
            it = QRegularExpression(
                pattern, QRegularExpression.PatternOption.CaseInsensitiveOption
            ).globalMatch(text)
            while it.hasNext():
                m = it.next()
                cap = 1 if pattern.startswith("^") else 0
                self.setFormat(m.capturedStart(cap), m.capturedLength(cap), f)
        cut = [i for i in (text.find(";"), text.find("#")) if i >= 0]
        if cut:
            self.setFormat(min(cut), len(text) - min(cut), fmt(t.muted, italic=True))


class _LineNumbers(QWidget):
    def __init__(self, editor: CodeEditor) -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        self.editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    """Editor con números de línea, la línea del PC y la de un error."""

    def __init__(self) -> None:
        super().__init__()
        self.gutter = _LineNumbers(self)
        self.pc_line: int | None = None
        self.error_line: int | None = None
        self.setFont(mono(11.0))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.blockCountChanged.connect(self._update_width)
        self.updateRequest.connect(self._update_gutter)
        self.highlighter = Highlighter(self.document())
        self._update_width()

    def gutter_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * max(2, digits)

    def _update_width(self, _count: int = 0) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event: QPaintEvent) -> None:
        t = th.current()
        p = QPainter(self.gutter)
        p.fillRect(event.rect(), QColor(t.surface_alt))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line = number + 1
                color = t.muted
                if line == self.pc_line:
                    color = t.accent
                if line == self.error_line:
                    color = t.bad
                p.setPen(QColor(color))
                f = p.font()
                f.setBold(line in (self.pc_line, self.error_line))
                p.setFont(f)
                mark = "▶ " if line == self.pc_line else ""
                p.drawText(
                    0,
                    top,
                    self.gutter.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    mark + str(line),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1
        p.end()

    def mark(self, pc_line: int | None = None, error_line: int | None = None) -> None:
        """Resalta la línea de la instrucción que sigue y la de un error."""
        t = th.current()
        self.pc_line, self.error_line = pc_line, error_line
        selections = []
        for line, color in ((pc_line, t.accent), (error_line, t.bad)):
            if line is None:
                continue
            block = self.document().findBlockByNumber(line - 1)
            if not block.isValid():
                continue
            sel = QTextEdit.ExtraSelection()
            c = QColor(color)
            c.setAlpha(50)
            sel.format.setBackground(c)
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            cursor = QTextCursor(block)
            sel.cursor = cursor
            selections.append(sel)
        self.setExtraSelections(selections)
        if pc_line is not None:
            block = self.document().findBlockByNumber(pc_line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                self.setTextCursor(cursor)
                self.ensureCursorVisible()
        self.gutter.update()


# ---------------------------------------------------------------- pestaña
class ProgramTab(QWidget):
    """Carga, ensambla y ejecuta programas ``.t754`` en la máquina de transistores."""

    status = Signal(str)

    def __init__(self, pool: QThreadPool) -> None:
        super().__init__()
        self.pool = pool
        self.machine: Any = None
        self.words: list[int] = []
        self.lines: dict[int, int] = {}
        self._previous: list[int] = []
        self._dirty = False

        self.source = CodeEditor()
        self.source.setPlainText(DEFAULT_PROGRAM)
        self.source.textChanged.connect(self._edited)
        open_button = QPushButton("Abrir…")
        open_button.setToolTip("Abrir un programa .t754 (Ctrl+O)")
        open_button.clicked.connect(self.open_file)
        self.examples = QPushButton("Ejemplos ▾")
        menu = QMenu(self.examples)
        for path in sorted(EXAMPLES_DIR.glob("*.t754")) if EXAMPLES_DIR.is_dir() else []:
            first = path.read_text(encoding="utf-8").splitlines()[0].lstrip("; ").strip()
            action = menu.addAction(f"{path.stem}   —   {first}")
            action.triggered.connect(lambda _=False, p=path: self.load_file(p))
        if menu.isEmpty():
            menu.addAction("suma_simple").triggered.connect(
                lambda: self.source.setPlainText(DEFAULT_PROGRAM)
            )
        self.examples.setMenu(menu)
        save = QPushButton("Guardar…")
        save.setToolTip("Guardar el programa del editor")
        save.clicked.connect(self.save_file)
        self.load_button = QPushButton("Ensamblar y reiniciar")
        self.load_button.setObjectName("primary")
        self.load_button.setToolTip("Ensambla el editor y crea una máquina nueva (F5)")
        self.load_button.clicked.connect(self.load)
        self.step_button = QPushButton("Paso ▸")
        self.step_button.setToolTip("Ejecuta una instrucción (F10)")
        self.step_button.clicked.connect(self.step)
        self.run_button = QPushButton("Ejecutar hasta HALT ▸▸")
        self.run_button.setToolTip("Ejecuta hasta HALT (F8)")
        self.run_button.clicked.connect(self.run)
        tools = QHBoxLayout()
        for b in (open_button, self.examples, save):
            tools.addWidget(b)
        tools.addStretch(1)
        runs = QHBoxLayout()
        for b in (self.load_button, self.step_button, self.run_button):
            runs.addWidget(b)
        runs.addStretch(1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setObjectName("hint")

        left_card, left = card("Programa .t754")
        left.addWidget(
            hint(
                "La FPU dentro de una CPU: el programa se ensambla y corre en la máquina "
                "T754 (decodificador, banco de registros de flip-flops, ALU y FPU, todo de "
                "transistores). Instrucciones: LI, MOV, FADD, FSUB, FMUL, FDIV, ADD, SUB, "
                "OUT, CLRF, NOP y HALT."
            )
        )
        left.addLayout(tools)
        left.addLayout(runs)
        left.addWidget(self.source, 1)
        left.addWidget(self.message)

        # Estado
        self.state_label = QLabel("Sin programa cargado: pulse «Ensamblar y reiniciar».")
        self.state_label.setWordWrap(True)
        self.fsr_float = Chips(FLAG_CHIPS, danger={"NV", "DZ", "OF"})
        self.fsr_int = Chips(INT_CHIPS)
        self.fsr_float.set_active(None)
        self.fsr_int.set_active(None)
        state_card, state = card("Estado")
        state.addWidget(self.state_label)
        state.addWidget(QLabel("FSR · flags de punto flotante (acumulativos)"))
        state.addWidget(self.fsr_float)
        state.addWidget(QLabel("FSR · indicadores enteros"))
        state.addWidget(self.fsr_int)

        self.regs = table(["Reg.", "hex", "valor", "clase"])
        self.regs.setRowCount(isa.N_REGS)
        self.regs.setFont(mono())
        for r in range(isa.N_REGS):
            for c, text in enumerate((f"F{r}", "—", "—", "—")):
                self.regs.setItem(r, c, QTableWidgetItem(text))
        regs_card, regs = card("Registros F0–F7")
        regs.addWidget(self.regs)
        self.outputs = QListWidget()
        self.outputs.setFont(mono())
        out_card, out = card("Salidas (OUT)")
        out.addWidget(self.outputs)
        self.memory = table(["Dir.", "palabra", "instrucción"])
        self.memory.setFont(mono())
        mem_card, mem = card("Memoria de programa")
        mem.addWidget(self.memory)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(state_card)
        rl.addWidget(regs_card, 3)
        lower = QHBoxLayout()
        lower.addWidget(out_card, 1)
        lower.addWidget(mem_card, 2)
        rl.addLayout(lower, 2)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left_card)
        split.addWidget(right)
        split.setSizes([620, 700])
        split.setChildrenCollapsible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(split)

        for keys, fn in (("F5", self.load), ("F10", self.step), ("F8", self.run)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
        self._set_running(False)

    # ----------------------------------------------------------------- archivo
    def open_file(self) -> None:
        """Abre un archivo ``.t754`` en el editor."""
        start = str(EXAMPLES_DIR) if EXAMPLES_DIR.is_dir() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir programa", start, "Programas T754 (*.t754);;Todos (*)"
        )
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path) -> None:
        self.source.setPlainText(path.read_text(encoding="utf-8"))
        self.status.emit(f"Programa abierto: {path.name}")
        self.load()

    def save_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar programa", "programa.t754", "Programas T754 (*.t754)"
        )
        if path:
            Path(path).write_text(self.source.toPlainText(), encoding="utf-8")
            self.status.emit(f"Programa guardado en {path}")

    # ----------------------------------------------------------------- máquina
    def _set_running(self, ready: bool) -> None:
        self.step_button.setEnabled(ready)
        self.run_button.setEnabled(ready)

    def _edited(self) -> None:
        if self.machine is not None and not self._dirty:
            self._dirty = True
            self._set_running(False)
            self.message.setObjectName("hint")
            self.message.setText("El programa cambió: vuelva a ensamblarlo (F5) para ejecutarlo.")
            self._repolish(self.message)
        self.source.mark(None, None)

    def load(self) -> None:
        """Ensambla el editor y crea una máquina nueva."""
        text = self.source.toPlainText()
        try:
            words = assemble(text, filename="editor")
        except AssemblyError as exc:
            self.source.mark(None, exc.line)
            self.message.setObjectName("error")
            self.message.setText(
                f"Error de ensamblado en la línea {exc.line}, columna {exc.column}: {exc.message}"
            )
            self._repolish(self.message)
            self.status.emit(str(exc))
            return
        from transim.cpu.machine import Machine

        self.words = words
        self.lines = instruction_lines(text, words)
        self.state_label.setText("Construyendo la máquina de transistores…")
        self.load_button.setEnabled(False)
        self._set_running(False)
        task = Task(lambda: Machine(words))
        task.signals.done.connect(self._loaded)
        task.signals.failed.connect(self._failed)
        self.pool.start(task)

    def _loaded(self, machine: object) -> None:
        self.machine = machine
        self._dirty = False
        if not self.words:
            self.words = list(getattr(machine, "program", []))
            self.lines = instruction_lines(self.source.toPlainText(), self.words)
        self.load_button.setEnabled(True)
        self.message.setObjectName("hint")
        self.message.setText(
            f"Ensamblado: {len(self.words)} palabras. F10 ejecuta un paso; F8, todo."
        )
        self._repolish(self.message)
        self._fill_memory()
        self._previous = []
        self.refresh()

    def step(self) -> None:
        """Ejecuta una instrucción."""
        self._background(self._do_step)

    def run(self) -> None:
        """Ejecuta hasta HALT."""
        self._background(self._do_run)

    def _do_step(self) -> object:
        self.machine.step()
        return None

    def _do_run(self) -> object:
        return self.machine.run()

    def _background(self, fn: Any) -> None:
        if self.machine is None or self._dirty or self.machine.halted:
            return
        self._previous = [int(v) for v in self.machine.state.regs]
        self._set_running(False)
        self.load_button.setEnabled(False)
        task = Task(fn)
        task.signals.done.connect(self._after_run)
        task.signals.failed.connect(self._failed)
        self.pool.start(task)

    def _after_run(self, _result: object) -> None:
        self.load_button.setEnabled(True)
        self.refresh()

    def _fill_memory(self) -> None:
        lines = disassemble(self.words)
        rows = []
        pc = 0
        for text in lines:
            instr = isa.decode(self.words[pc])
            rows.append([str(pc), f"0x{self.words[pc]:08X}", text])
            if instr.words == 2 and pc + 1 < len(self.words):
                rows.append([str(pc + 1), f"0x{self.words[pc + 1]:08X}", "  (literal de LI)"])
            pc += instr.words
        self.memory.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                self.memory.setItem(r, c, QTableWidgetItem(text))
        self.memory.resizeRowsToContents()

    def refresh(self) -> None:
        """Muestra el estado arquitectónico de la máquina."""
        state = self.machine.state
        fmt = getattr(self.machine, "fmt", BINARY32)
        t = th.current()
        for r, value in enumerate(state.regs):
            changed = bool(self._previous) and self._previous[r] != value
            items = [
                f"F{r}",
                hex_text(fmt, value),
                value_text(fmt, value),
                CLASS_NAMES[fmt.classify(value)],
            ]
            for c, text in enumerate(items):
                item = QTableWidgetItem(text)
                if changed:
                    color = QColor(t.accent)
                    color.setAlpha(60)
                    item.setBackground(color)
                    item.setToolTip("Cambió en el último paso")
                self.regs.setItem(r, c, item)
        self.outputs.clear()
        for value in state.outputs:
            self.outputs.addItem(f"{hex_text(fmt, value)}   {value_text(fmt, value)}")
        self.fsr_float.set_active(fsr_keys(state.fsr) & {"NV", "DZ", "OF", "UF", "NX"})
        self.fsr_int.set_active(fsr_keys(state.fsr) & {"C", "V", "Z", "N"})
        if state.halted:
            phase = "<b>HALT</b>: el programa terminó"
            line = None
        else:
            phase = f"siguiente instrucción en PC = <b>{state.pc}</b>"
            line = self.lines.get(state.pc)
        self.state_label.setText(
            f"{phase} · {state.steps} instrucciones ejecutadas · FSR = 0x{state.fsr:08X}"
        )
        self.source.mark(line, None)
        for r in range(self.memory.rowCount()):
            first = self.memory.item(r, 0)
            here = first is not None and first.text() == str(state.pc) and not state.halted
            for c in range(self.memory.columnCount()):
                cell = self.memory.item(r, c)
                if cell is not None:
                    color = QColor(t.accent)
                    color.setAlpha(55 if here else 0)
                    cell.setBackground(color if here else QColor(0, 0, 0, 0))
            if here and first is not None:
                self.memory.scrollToItem(first)
        self._set_running(not state.halted)
        self.status.emit(re.sub("<[^>]+>", "", self.state_label.text()))

    def _failed(self, message: str) -> None:
        self.load_button.setEnabled(True)
        self.message.setObjectName("error")
        self.message.setText(f"Error de ejecución: {message}")
        self._repolish(self.message)
        self.state_label.setText("error")
        self.status.emit(message)
        self._set_running(self.machine is not None and not self.machine.halted)

    @staticmethod
    def _repolish(w: QWidget) -> None:
        w.style().unpolish(w)
        w.style().polish(w)

    def apply_theme(self) -> None:
        self.source.highlighter.rehighlight()
        self.source.mark(self.source.pc_line, self.source.error_line)
        self.fsr_float.update()
        self.fsr_int.update()
        if self.machine is not None:
            self.refresh()


__all__ = ["CodeEditor", "ProgramTab", "fsr_keys"]
