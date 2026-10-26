"""Pestaña Operación: la FPU vista desde afuera.

Dos operandos, la operación y el formato; el resultado de la FPU de transistores con sus
flags, verificado contra el modelo de referencia; los bits de los tres números (un clic
invierte un bit y recalcula); y el detalle de la operación: ciclos estimados, actividad
por etapa, buses internos e historial.
"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, QThreadPool, Signal
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from transim.core.unit import EngineName
from transim.fpu.format import FORMATS, FloatFormat
from transim.metrics.stages import STAGE_NAMES, critical_stages, reference_period, schedule
from transim.ui.gui import model
from transim.ui.gui.model import (
    CLASS_NAMES,
    EXAMPLES,
    OPS,
    Calculation,
    decode_text,
    exact_text,
    hex_text,
    parse_operand,
    value_text,
)
from transim.ui.gui.widgets import (
    FLAG_CHIPS,
    Bar,
    BarList,
    BitField,
    BitRow,
    Chips,
    CycleStrip,
    Segment,
    Segmented,
    StatTile,
    card,
    flag_keys,
    hint,
    thousands,
)
from transim.ui.gui.worker import Task


def mono(size: float | None = None) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    if size is not None:
        font.setPointSizeF(size)
    return font


def table(headers: list[str]) -> QTableWidget:
    """Tabla de solo lectura: columnas ajustadas y la última estirada."""
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setWordWrap(True)
    t.setShowGrid(False)
    header = t.horizontalHeader()
    for col in range(len(headers) - 1):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
    return t


def fill(t: QTableWidget, rows: list[list[str]], font: QFont | None = None) -> None:
    """Reemplaza las filas de ``t``."""
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            item = QTableWidgetItem(text)
            if font is not None and c > 0:
                item.setFont(font)
            t.setItem(r, c, item)
    t.resizeRowsToContents()


class OperandEdit(QWidget):
    """Campo de un operando con su validación y vista previa debajo."""

    changed = Signal()
    submitted = Signal()

    def __init__(self, name: str, text: str) -> None:
        super().__init__()
        self.name = name
        self.edit = QLineEdit(text)
        self.edit.setFont(mono(13.0))
        self.edit.setClearButtonEnabled(True)
        self.edit.setPlaceholderText("1.5   −2e−3   1/3   inf   nan   0x3FC00000")
        self.edit.setToolTip(
            "Decimal (1.5, -2e-3), fracción exacta (1/3), inf, nan o los bits en "
            "hexadecimal (0x3FC00000). El decimal se redondea al formato con RNE."
        )
        self.edit.textChanged.connect(self.changed)
        self.edit.returnPressed.connect(self.submitted)
        self.info = QLabel()
        self.info.setObjectName("hint")
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label = QLabel(f"<b>{name}</b>")
        label.setFixedWidth(18)
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(self.edit, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addLayout(row)
        layout.addWidget(self.info)
        self.bits: int | None = None

    def text(self) -> str:
        return self.edit.text()

    def set_text(self, text: str) -> None:
        self.edit.setText(text)

    def validate(self, fmt: FloatFormat) -> int | None:
        """Interpreta el texto en ``fmt``; muestra el resultado o el error debajo."""
        try:
            bits = parse_operand(self.edit.text(), fmt)
        except ValueError as exc:
            self.bits = None
            self.info.setObjectName("error")
            self.info.setText(str(exc))
            self._mark(True)
            return None
        self.bits = bits
        self.info.setObjectName("hint")
        cls = CLASS_NAMES[fmt.classify(bits)]
        exact = exact_text(fmt, bits)
        typed = self.edit.text().strip()
        note = ""
        if not typed.lower().startswith("0x") and _differs(typed, exact):
            note = f" · se guarda como {exact[:34]}{'…' if len(exact) > 34 else ''}"
        self.info.setText(f"{hex_text(fmt, bits)} · {cls}{note}")
        self.info.setToolTip(f"Valor exacto: {exact}")
        self._mark(False)
        return bits

    def _mark(self, invalid: bool) -> None:
        self.edit.setProperty("invalid", "true" if invalid else "false")
        for w in (self.edit, self.info):
            w.style().unpolish(w)
            w.style().polish(w)


def _differs(typed: str, exact: str) -> bool:
    """True si el número escrito no se representa exactamente."""
    from fractions import Fraction

    try:
        t = typed.replace("−", "-").lower()
        if t in ("inf", "+inf", "-inf", "nan", "infinity", "-0", "0", "+0"):
            return False
        return Fraction(t) != Fraction(exact.replace("−", "-").rstrip("…"))
    except (ValueError, ZeroDivisionError):
        return False


class OperationTab(QWidget):
    """Operandos, resultado verificado, bits, ciclos, actividad e historial."""

    calculated = Signal(object)
    """Se emite con cada :class:`Calculation` terminado."""
    open_stage = Signal(str)
    """Pide ver una etapa en la pestaña de transistores."""
    status = Signal(str)
    """Mensaje para la barra de estado."""

    def __init__(self, pool: QThreadPool) -> None:
        super().__init__()
        self.pool = pool
        self.last: Calculation | None = None
        self.history: list[Calculation] = []
        self._busy = False
        self._fmt_name = "binary32"

        # ------------------------------------------------------------ entrada
        self.a = OperandEdit("a", "1.5")
        self.b = OperandEdit("b", "2.25")
        self.op = Segmented(
            [(k, sym, f"{name.capitalize()} ({ins})") for k, (sym, name, ins) in OPS.items()],
            large=True,
        )
        self.fmt = Segmented(
            [
                (
                    "binary32",
                    "binary32",
                    "Precisión simple: 1 bit de signo, 8 de exponente y 23 de fracción",
                ),
                (
                    "binary16",
                    "binary16",
                    "Media precisión: 1 bit de signo, 5 de exponente y 10 de fracción",
                ),
            ]
        )
        self.engine_box = QComboBox()
        self.engine_box.addItem("cached · rápido", "cached")
        self.engine_box.addItem("switch · transistor por transistor", "switch")
        self.engine_box.setToolTip(
            "cached usa las tablas de verdad extraídas de cada celda; switch simula cada "
            "transistor. Los dos dan los mismos bits (ADR-0008); switch tarda más."
        )
        self.examples = QPushButton("Ejemplos ▾")
        self.examples.setToolTip("Casos notables de IEEE 754 para mostrar")
        menu = QMenu(self.examples)
        for ex in EXAMPLES:
            action = menu.addAction(f"{ex.title}   —   {ex.note}")
            action.triggered.connect(lambda _=False, ex=ex: self.load_example(ex))
        self.examples.setMenu(menu)
        self.swap = QPushButton("⇄  a ↔ b")
        self.swap.setToolTip("Intercambiar los operandos")
        self.swap.clicked.connect(self.swap_operands)
        self.run_button = QPushButton("Calcular en transistores")
        self.run_button.setObjectName("primary")
        self.run_button.setToolTip("Calcular (Enter)")
        self.run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_button.clicked.connect(self.run)

        in_card, in_layout = card("Entrada")
        in_layout.addWidget(self.a)
        op_row = QHBoxLayout()
        op_row.addWidget(self.op)
        op_row.addStretch(1)
        op_row.addWidget(self.swap)
        in_layout.addLayout(op_row)
        in_layout.addWidget(self.b)
        options = QHBoxLayout()
        options.addWidget(QLabel("Formato"))
        options.addWidget(self.fmt)
        options.addSpacing(12)
        options.addWidget(QLabel("Motor"))
        options.addWidget(self.engine_box, 1)
        in_layout.addLayout(options)
        actions = QHBoxLayout()
        actions.addWidget(self.examples)
        actions.addStretch(1)
        actions.addWidget(self.run_button)
        in_layout.addLayout(actions)

        # ---------------------------------------------------------- resultado
        self.expr = QLabel("Escriba dos números y pulse Calcular.")
        self.expr.setObjectName("bigResult")
        self.expr.setWordWrap(True)
        self.expr.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.hexline = QLabel("—")
        self.hexline.setFont(mono(11.0))
        self.hexline.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.verify = QLabel("")
        self.verify.setObjectName("ok")
        self.stale = QLabel("Cambiaron los datos: pulse Calcular para actualizar el resultado.")
        self.stale.setObjectName("hint")
        self.stale.hide()
        self.flags = Chips(FLAG_CHIPS, danger={"NV", "DZ", "OF"})
        self.flags.set_active(None)
        self.tiles = {
            "transistores": StatTile(
                "transistores", "Transistores de la unidad que hizo la operación"
            ),
            "conmutaciones": StatTile(
                "conmutaciones*", "Nodos que cambiaron de valor respecto de la operación anterior"
            ),
            "eventos": StatTile("eventos*", "Transistores que pasaron a conducir o a cortarse"),
            "ciclos": StatTile(
                "ciclos estimados",
                "Camino crítico repartido en ciclos del periodo elegido (ADR-0014)",
            ),
            "tiempo": StatTile("tiempo", "Lo que tardó el simulador en evaluar la operación"),
        }
        out_card, out_layout = card("Resultado de la FPU de transistores")
        out_layout.addWidget(self.expr)
        out_layout.addWidget(self.hexline)
        out_layout.addWidget(self.verify)
        out_layout.addWidget(self.stale)
        out_layout.addWidget(self.flags)
        tiles = QGridLayout()
        tiles.setSpacing(9)
        for k, tile in enumerate(self.tiles.values()):
            tiles.addWidget(tile, 0, k)
        out_layout.addLayout(tiles)
        out_layout.addWidget(hint("* respecto de la operación anterior en la misma unidad."))
        out_layout.addStretch(1)

        # -------------------------------------------------------------- bits
        self.bitfield = BitField(FORMATS["binary32"])
        self.bitfield.bit_clicked.connect(self._flip_bit)
        bits_card, bits_layout = card("Bits IEEE 754 · signo | exponente | fracción")
        bits_layout.addWidget(self.bitfield)
        bits_layout.addWidget(
            hint("Haga clic en un bit de a o de b para invertirlo: la FPU recalcula al instante.")
        )

        # ----------------------------------------------------------- detalle
        self.period = QSpinBox()
        self.period.setRange(1, 1000)
        self.period.setValue(reference_period())
        self.period.setSuffix(" celdas")
        self.period.setToolTip(
            "Celdas que caben en un ciclo de reloj. Por defecto, el camino crítico de la "
            "ALU entera de 32 bits (una operación entera por ciclo)."
        )
        self.period.valueChanged.connect(self._show_cycles)
        self.cycles_summary = QLabel("Calcule una operación para ver sus ciclos.")
        self.strip = CycleStrip()
        self.cycles = table(["Ciclo", "Celdas del camino crítico", "Etapas que ocupa"])
        period_row = QHBoxLayout()
        period_row.addWidget(self.cycles_summary, 1)
        period_row.addWidget(QLabel("Periodo de reloj:"))
        period_row.addWidget(self.period)
        cycles_page = QWidget()
        cycles_layout = QVBoxLayout(cycles_page)
        cycles_layout.addLayout(period_row)
        cycles_layout.addWidget(self.strip)
        cycles_layout.addWidget(self.cycles, 1)
        cycles_layout.addWidget(
            hint(
                "Estimación de ADR-0014: cada celda del camino crítico cuesta una unidad de "
                "retardo y el reloj tiene un periodo fijo de celdas."
            )
        )
        self.activity = BarList("Calcule una operación para ver qué etapas trabajaron.")
        self.activity.activated.connect(self._open_stage)
        activity_page = QWidget()
        activity_layout = QVBoxLayout(activity_page)
        activity_layout.addWidget(
            hint(
                "Conmutaciones de los nodos de cada etapa del datapath en esta operación. "
                "Doble clic en una etapa para verla en la pestaña Transistores."
            )
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.activity)
        activity_layout.addWidget(scroll, 1)
        self.stages = table(["Bus interno", "Hex", "Binario"])
        self.history_list = QListWidget()
        self.history_list.setToolTip("Doble clic para repetir esa operación")
        self.history_list.itemDoubleClicked.connect(self._restore)
        self.details = QTabWidget()
        self.details.setObjectName("subtabs")
        self.details.addTab(cycles_page, "Ciclos de reloj")
        self.details.addTab(activity_page, "Actividad por etapa")
        self.details.addTab(self.stages, "Buses internos (dbg_)")
        self.details.addTab(self.history_list, "Historial")
        details_card, details_layout = card()
        details_layout.addWidget(self.details)
        details_card.setMinimumHeight(230)

        # ------------------------------------------------------------ armado
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(in_card, 5)
        top.addWidget(out_card, 6)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addWidget(bits_card)
        layout.addWidget(details_card, 1)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(area)

        for w in (self.a, self.b):
            w.changed.connect(self._inputs_changed)
            w.submitted.connect(self.run)
        self.op.changed.connect(lambda _: self._inputs_changed())
        self.fmt.changed.connect(self._format_changed)
        self.engine_box.currentIndexChanged.connect(lambda _: self._inputs_changed())
        submit = QShortcut(QKeySequence("Ctrl+Return"), self)
        submit.activated.connect(self.run)
        self._inputs_changed()

    # ---------------------------------------------------------------- estado
    @property
    def format(self) -> FloatFormat:
        return FORMATS[self.fmt.value()]

    @property
    def engine(self) -> EngineName:
        return "switch" if self.engine_box.currentData() == "switch" else "cached"

    def _inputs_changed(self) -> None:
        fmt = self.format
        a, b = self.a.validate(fmt), self.b.validate(fmt)
        self.run_button.setEnabled(a is not None and b is not None and not self._busy)
        stale = self.last is None or (self.last.fmt, self.last.op, self.last.a, self.last.b) != (
            fmt,
            self.op.value(),
            a,
            b,
        )
        result = None if stale or self.last is None else self.last.result.bits
        self.stale.setVisible(self.last is not None and stale and not self._busy)
        self.bitfield.set_format(fmt)
        self.bitfield.set_rows(
            [
                BitRow("a", a, True, decode_text(fmt, a) if a is not None else ""),
                BitRow("b", b, True, decode_text(fmt, b) if b is not None else ""),
                BitRow(
                    "resultado",
                    result,
                    False,
                    decode_text(fmt, result) if result is not None else "pulse Calcular",
                ),
            ]
        )

    def _format_changed(self, name: str) -> None:
        """Al cambiar de formato, los operandos en hex se pasan a decimal para que sigan
        valiendo lo mismo (o lo más cercano) en el formato nuevo."""
        old = FORMATS[self._fmt_name]
        self._fmt_name = name
        for w in (self.a, self.b):
            if w.text().strip().lower().startswith("0x") and w.bits is not None:
                w.set_text(value_text(old, w.bits).replace("−", "-"))
        self._inputs_changed()

    def swap_operands(self) -> None:
        a, b = self.a.text(), self.b.text()
        self.a.set_text(b)
        self.b.set_text(a)

    def load_example(self, ex: model.Example) -> None:
        a, b = ex.operands(self.format)
        self.a.set_text(a)
        self.b.set_text(b)
        self.op.set_value(ex.op)
        self._inputs_changed()
        self.status.emit(f"Ejemplo: {ex.title} — {ex.note}")
        self.run()

    def _flip_bit(self, row: int, bit: int) -> None:
        fmt = self.format
        target = self.a if row == 0 else self.b
        if target.bits is None:
            return
        target.set_text(hex_text(fmt, target.bits ^ (1 << bit)))
        self.bitfield.flash_bit(row, bit)
        self.run()

    # ---------------------------------------------------------------- cálculo
    def run(self) -> None:
        """Lee la entrada y lanza el cálculo en un hilo de trabajo."""
        if self._busy:
            return
        fmt = self.format
        a, b = self.a.validate(fmt), self.b.validate(fmt)
        if a is None or b is None:
            (self.a if a is None else self.b).edit.setFocus()
            return
        op, engine = self.op.value(), self.engine
        self._busy = True
        self.run_button.setEnabled(False)
        self.run_button.setText("Calculando…")
        QGuiApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        first = not model.is_built(fmt, op, engine)
        what = f"{OPS[op][2]} {fmt.name}, motor {engine}"
        self.status.emit(
            f"Construyendo la unidad {what} (solo la primera vez)…"
            if first
            else f"Calculando en {what}…"
        )
        task = Task(lambda: model.calculate(fmt, op, a, b, engine))
        task.signals.done.connect(self.show_result)
        task.signals.failed.connect(self._failed)
        self.pool.start(task)

    def _finish(self) -> None:
        self._busy = False
        self.run_button.setText("Calcular en transistores")
        if QGuiApplication.overrideCursor() is not None:
            QGuiApplication.restoreOverrideCursor()
        self._inputs_changed()

    def show_result(self, calc: Calculation) -> None:
        """Muestra un :class:`Calculation` en la ventana."""
        self.last = calc
        self._finish()
        fmt = calc.fmt
        bits = calc.result.bits
        self.expr.setText(calc.expression)
        self.expr.setToolTip(f"Valor exacto del resultado: {exact_text(fmt, bits)}")
        self.hexline.setText(
            f"{hex_text(fmt, bits)}  ·  {CLASS_NAMES[fmt.classify(bits)]}  ·  {fmt.name}"
        )
        if calc.matches:
            self.verify.setObjectName("ok")
            self.verify.setText("✓ Coincide con el modelo de referencia (bits y flags)")
        else:
            self.verify.setObjectName("error")
            ref = calc.reference
            self.verify.setText(
                "✗ Difiere del modelo de referencia"
                + (f": esperado {hex_text(fmt, ref.bits)} {ref.flags}" if ref else "")
            )
        self.verify.style().unpolish(self.verify)
        self.verify.style().polish(self.verify)
        self.flags.set_active(flag_keys(calc.result.flags))
        self.tiles["transistores"].set(thousands(calc.transistors))
        self.tiles["conmutaciones"].set(thousands(calc.toggles))
        self.tiles["eventos"].set(thousands(calc.events))
        self.tiles["tiempo"].set(f"{calc.seconds * 1000:.1f} ms")
        fill(
            self.stages,
            [
                [k, "X" if v is None else f"0x{v:X}", "X" if v is None else f"{v:b}"]
                for k, v in calc.stages.items()
            ],
            mono(),
        )
        self.activity.set_bars(
            [Bar(name, STAGE_NAMES.get(name, name), n) for name, n in calc.stage_toggles.items()]
        )
        self._show_cycles()
        self.history.insert(0, calc)
        flags = str(calc.result.flags)
        extra = "" if flags == "—" else f" · {flags}"
        item = QListWidgetItem(f"{calc.expression}    [{fmt.name} · {calc.engine}{extra}]")
        self.history_list.insertItem(0, item)
        self.status.emit(
            f"{calc.expression} · {thousands(calc.transistors)} transistores · "
            f"{calc.seconds * 1000:.1f} ms"
        )
        self.calculated.emit(calc)

    def _show_cycles(self) -> None:
        if self.last is None:
            return
        netlist = self.last.unit.netlist
        period = self.period.value()
        total, groups = model.cycle_groups(netlist, period)
        stages = critical_stages(netlist)
        count = len(schedule(stages, period))
        self.cycles_summary.setText(
            f"<b>{netlist.name}</b>: camino crítico de {total} celdas → <b>{count} ciclos</b> "
            f"de {period} celdas"
        )
        self.strip.set_data([Segment(s.instance, s.label, s.cells) for s in stages], period)
        fill(self.cycles, [list(g) for g in groups])
        self.tiles["ciclos"].set(
            str(count), f"{total} celdas en el camino crítico; periodo de {period} celdas"
        )

    def _failed(self, message: str) -> None:
        self._finish()
        self.expr.setText("Error de simulación")
        self.verify.setObjectName("error")
        self.verify.setText(message)
        self.verify.style().unpolish(self.verify)
        self.verify.style().polish(self.verify)
        self.status.emit(f"Error: {message}")

    def _restore(self, item: QListWidgetItem) -> None:
        calc = self.history[self.history_list.row(item)]
        with QSignalBlocker(self.fmt):
            self.fmt.set_value(calc.fmt.name)
        self._fmt_name = calc.fmt.name
        self.op.set_value(calc.op)
        self.engine_box.setCurrentIndex(self.engine_box.findData(calc.engine))
        self.a.set_text(
            value_text(calc.fmt, calc.a).replace("−", "-")
            if not calc.fmt.classify(calc.a).is_nan
            else hex_text(calc.fmt, calc.a)
        )
        self.b.set_text(
            value_text(calc.fmt, calc.b).replace("−", "-")
            if not calc.fmt.classify(calc.b).is_nan
            else hex_text(calc.fmt, calc.b)
        )
        if parse_operand(self.a.text(), calc.fmt) != calc.a:
            self.a.set_text(hex_text(calc.fmt, calc.a))
        if parse_operand(self.b.text(), calc.fmt) != calc.b:
            self.b.set_text(hex_text(calc.fmt, calc.b))
        self.run()

    def _open_stage(self, key: str) -> None:
        if key != "(entradas)":
            self.open_stage.emit(key)

    def apply_theme(self) -> None:
        for w in (self.bitfield, self.flags, self.strip, self.activity, *self.tiles.values()):
            w.update()


__all__ = ["OperandEdit", "OperationTab", "fill", "mono", "table"]
