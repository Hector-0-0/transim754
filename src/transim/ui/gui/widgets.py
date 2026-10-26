"""Widgets propios de la interfaz: tarjetas, botones segmentados, vista de bits IEEE 754,
chips de flags, indicadores, barra de ciclos y gráfico de barras.

Todos leen sus colores del tema activo (:mod:`transim.ui.gui.theme`) al pintarse, así
cambian de tema sin reconstruirse.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from transim.fpu.format import FloatFormat
from transim.ui.gui import theme as th
from transim.ui.gui.canvas import alpha, pen

STAGE_COLORS = [
    "#6366f1",
    "#0ea5e9",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#a855f7",
    "#ec4899",
    "#14b8a6",
    "#f97316",
    "#84cc16",
    "#3b82f6",
    "#e11d48",
]
"""Colores de las etapas del datapath (los mismos en la barra de ciclos y la actividad)."""


def stage_color(name: str) -> QColor:
    """Color estable para la etapa ``name``."""
    order = [
        "unpack_a",
        "unpack_b",
        "order",
        "exp_diff",
        "align",
        "mant_addsub",
        "mant_mul",
        "mant_div",
        "lzc",
        "normalize",
        "round",
        "special",
        "class_a",
        "class_b",
        "lzc_a",
        "lzc_b",
        "normalize_a",
        "normalize_b",
    ]
    k = order.index(name) if name in order else sum(map(ord, name))
    return QColor(STAGE_COLORS[k % len(STAGE_COLORS)])


def _font(size: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPointSizeF(size)
    f.setBold(bold)
    return f


# ---------------------------------------------------------------- tarjetas
def card(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    """Recuadro con título (estilo ``QFrame#card`` de la hoja de estilo)."""
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(9)
    if title:
        label = QLabel(title.upper())
        label.setObjectName("cardTitle")
        layout.addWidget(label)
    return frame, layout


def hint(text: str) -> QLabel:
    """Texto pequeño y atenuado."""
    label = QLabel(text)
    label.setObjectName("hint")
    label.setWordWrap(True)
    return label


class Segmented(QWidget):
    """Botones mutuamente excluyentes, como un interruptor de varias posiciones."""

    changed = Signal(str)
    """Se emite con la clave elegida."""

    def __init__(self, options: Sequence[tuple[str, str, str]], *, large: bool = False) -> None:
        """``options``: (clave, texto, ayuda)."""
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.buttons: dict[str, QPushButton] = {}
        for k, (key, text, tip) in enumerate(options):
            b = QPushButton(text)
            b.setObjectName("segment")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            position = "first" if k == 0 else "last" if k == len(options) - 1 else "middle"
            b.setProperty("position", position)
            if large:
                font = b.font()
                font.setPointSizeF(font.pointSizeF() * 1.35)
                b.setFont(font)
            fm = b.fontMetrics()
            b.setMinimumWidth(fm.horizontalAdvance(text) + (40 if large else 28))
            b.clicked.connect(lambda _=False, key=key: self.set_value(key, emit=True))
            layout.addWidget(b)
            self.buttons[key] = b
        self._value = options[0][0]
        self.buttons[self._value].setChecked(True)

    def value(self) -> str:
        return self._value

    def set_value(self, key: str, *, emit: bool = False) -> None:
        for k, b in self.buttons.items():
            b.setChecked(k == key)
        changed = key != self._value
        self._value = key
        if emit and changed:
            self.changed.emit(key)

    def set_option_enabled(self, key: str, enabled: bool, tip: str | None = None) -> None:
        self.buttons[key].setEnabled(enabled)
        if tip is not None:
            self.buttons[key].setToolTip(tip)


class StatTile(QFrame):
    """Indicador: un número grande con su nombre debajo."""

    def __init__(self, caption: str, tip: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(0)
        self.value = QLabel("—")
        self.value.setObjectName("statValue")
        self.caption = QLabel(caption)
        self.caption.setObjectName("statLabel")
        layout.addWidget(self.value)
        layout.addWidget(self.caption)
        self.setToolTip(tip)

    def set(self, text: str, tip: str | None = None) -> None:
        self.value.setText(text)
        if tip is not None:
            self.setToolTip(tip)


def thousands(n: int) -> str:
    """``13974`` → ``13 974`` (separador de miles con espacio fino, como en el español)."""
    return f"{n:,}".replace(",", " ")


# ---------------------------------------------------------------- chips
@dataclass(frozen=True)
class Chip:
    key: str
    text: str
    tip: str


class Chips(QWidget):
    """Fila de indicadores que se encienden (por ejemplo, los flags de IEEE 754)."""

    def __init__(self, chips: Sequence[Chip], *, danger: set[str] | None = None) -> None:
        super().__init__()
        self.chips = list(chips)
        self.active: set[str] = set()
        self.enabled = False
        self.danger = danger or set()
        self.setMinimumHeight(28)
        self.setMouseTracking(True)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def set_active(self, keys: set[str] | None) -> None:
        """Enciende ``keys``; None deja todos apagados y atenuados (sin datos)."""
        self.enabled = keys is not None
        self.active = set(keys or ())
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetricsF(_font(9.0, True))
        return QSize(int(sum(fm.horizontalAdvance(c.text) + 26 for c in self.chips)), 28)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetricsF(_font(9.0, True))
        widest = max((fm.horizontalAdvance(c.text) + 20 for c in self.chips), default=40.0)
        return QSize(int(widest), self.heightForWidth(int(widest)))

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        rects = self._rects(width)
        return int(max((r.bottom() for r in rects), default=26.0) + 2)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        self.setMinimumHeight(self.heightForWidth(self.width()))

    def _rects(self, width: int | None = None) -> list[QRectF]:
        """Un recuadro por chip; pasan a la fila siguiente si no caben en ``width``."""
        fm = QFontMetricsF(_font(9.0, True))
        limit = float(self.width() if width is None else width)
        x = y = 0.0
        out = []
        for c in self.chips:
            w = fm.horizontalAdvance(c.text) + 20
            if x > 0 and x + w > limit:
                x, y = 0.0, y + 30
            out.append(QRectF(x, y + 2, w, 24))
            x += w + 6
        return out

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        t = th.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(_font(9.0, True))
        for c, r in zip(self.chips, self._rects(), strict=True):
            on = c.key in self.active
            color = QColor(t.bad if c.key in self.danger else t.warn) if on else QColor(t.muted)
            if on:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                p.drawRoundedRect(r, 12, 12)
                p.setPen(pen("#ffffff", 1))
            else:
                p.setPen(pen(alpha(t.muted, 120 if self.enabled else 60), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
                p.setPen(pen(alpha(t.muted, 230 if self.enabled else 110), 1))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, c.text)
        p.end()

    def event(self, e: QEvent) -> bool:
        if e.type() == QEvent.Type.ToolTip:
            pos = self.mapFromGlobal(self.cursor().pos())
            for c, r in zip(self.chips, self._rects(), strict=True):
                if r.contains(QPointF(pos)):
                    state = "encendido" if c.key in self.active else "apagado"
                    QToolTip.showText(
                        self.cursor().pos(), f"<b>{c.text}</b> ({state})<br>{c.tip}", self
                    )
                    return True
            QToolTip.hideText()
            return True
        return super().event(e)


FLAG_CHIPS = [
    Chip(
        "NV", "NV inválida", "Operación inválida (invalid): 0/0, ∞ − ∞, 0 × ∞… El resultado es NaN."
    ),
    Chip(
        "DZ", "DZ división por 0", "División de un número finito distinto de cero entre cero: ±∞."
    ),
    Chip("OF", "OF overflow", "El resultado redondeado no cabe: se entrega ±∞ (con RNE)."),
    Chip("UF", "UF underflow", "Resultado diminuto (subnormal) e inexacto."),
    Chip("NX", "NX inexacto", "El resultado se redondeó: no es exacto."),
]
"""Los cinco flags de IEEE 754-2019 §7 (ADR-0004)."""


def flag_keys(flags: object) -> set[str]:
    """Claves de :data:`FLAG_CHIPS` encendidas en un :class:`~transim.fpu.format.Flags`."""
    text = str(flags)
    return set() if text == "—" else set(text.split("|"))


# ---------------------------------------------------------------- bits
@dataclass
class BitRow:
    """Una fila de la vista de bits."""

    name: str
    bits: int | None
    clickable: bool = False
    caption: str = ""


class BitField(QWidget):
    """Bits de varios números IEEE 754, separados en signo, exponente y fracción.

    Los bits en 1 se pintan llenos con el color de su campo. Pasar el ratón muestra qué
    bit es y su peso; en las filas que lo permiten, un clic invierte el bit.
    """

    bit_clicked = Signal(int, int)
    """Se emite con (fila, índice del bit desde el LSB)."""

    LABEL_W = 92.0
    TOP = 34.0

    def __init__(self, fmt: FloatFormat) -> None:
        super().__init__()
        self.fmt = fmt
        self.rows: list[BitRow] = []
        self.hover: tuple[int, int] | None = None
        self.flash: tuple[int, int] | None = None
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_flash)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # --------------------------------------------------------------- datos
    def set_format(self, fmt: FloatFormat) -> None:
        self.fmt = fmt
        self.updateGeometry()
        self.update()

    def set_rows(self, rows: Sequence[BitRow]) -> None:
        self.rows = list(rows)
        self.setFixedHeight(int(self.TOP + len(self.rows) * self._row_h() + 6))
        self.update()

    def flash_bit(self, row: int, bit: int) -> None:
        self.flash = (row, bit)
        self._flash_timer.start(900)
        self.update()

    def _end_flash(self) -> None:
        self.flash = None
        self.update()

    # -------------------------------------------------------------- medidas
    def _cell(self) -> float:
        groups = 2 * 10.0
        avail = self.width() - self.LABEL_W - groups - 4
        return max(12.0, min(28.0, avail / self.fmt.width))

    def _row_h(self) -> float:
        return 42.0

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(int(self.LABEL_W + self.fmt.width * 22 + 24), int(self.TOP + 3 * 46 + 6))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(int(self.LABEL_W + self.fmt.width * 12 + 24), int(self.TOP + 46))

    def _x(self, bit: int) -> float:
        """x del bit ``bit`` (0 = LSB), con un hueco entre campos."""
        f = self.fmt
        pos = f.width - 1 - bit  # 0 = signo
        gap = 0.0
        if pos >= 1:
            gap += 10.0
        if pos >= 1 + f.exp_bits:
            gap += 10.0
        return self.LABEL_W + pos * self._cell() + gap

    def _field(self, bit: int) -> tuple[str, int]:
        """(campo, índice dentro del campo) del bit ``bit``."""
        f = self.fmt
        if bit == f.width - 1:
            return "sign", 0
        if bit >= f.frac_bits:
            return "exponent", bit - f.frac_bits
        return "fraction", bit

    def _at(self, pos: QPointF) -> tuple[int, int] | None:
        cell = self._cell()
        for r in range(len(self.rows)):
            y0 = self.TOP + r * self._row_h()
            if not y0 <= pos.y() <= y0 + cell:
                continue
            for bit in range(self.fmt.width):
                x = self._x(bit)
                if x <= pos.x() <= x + cell - 1:
                    return r, bit
        return None

    # -------------------------------------------------------------- pintura
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        t = th.current()
        f = self.fmt
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cell = self._cell()
        colors = {
            "sign": QColor(t.sign),
            "exponent": QColor(t.exponent),
            "fraction": QColor(t.fraction),
        }
        # Encabezado: nombre de cada campo e índices de sus bits extremos.
        p.setFont(_font(8.0, True))
        heads = [
            ("sign", f.width - 1, f.width - 1, "s"),
            ("exponent", f.width - 2, f.frac_bits, f"exponente · {f.exp_bits} bits"),
            ("fraction", f.frac_bits - 1, 0, f"fracción · {f.frac_bits} bits"),
        ]
        for field, hi, lo, name in heads:
            x0, x1 = self._x(hi), self._x(lo) + cell
            p.setPen(pen(colors[field], 1))
            p.drawText(
                QRectF(x0, 0, max(x1 - x0, 14), 14),
                Qt.AlignmentFlag.AlignCenter,
                name if x1 - x0 > 60 or field == "sign" else "",
            )
            p.setPen(pen(t.muted, 1))
            p.setFont(_font(7.0))
            p.drawText(QRectF(x0, 15, cell, 12), Qt.AlignmentFlag.AlignCenter, str(hi))
            if lo != hi:
                p.drawText(QRectF(x1 - cell, 15, cell, 12), Qt.AlignmentFlag.AlignCenter, str(lo))
            p.setFont(_font(8.0, True))
            p.setPen(pen(alpha(colors[field], 120), 1.2))
            p.drawLine(QPointF(x0, 29), QPointF(x1 - 1, 29))
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSizeF(max(7.0, min(11.0, cell * 0.48)))
        mono.setBold(True)
        for r, row in enumerate(self.rows):
            y = self.TOP + r * self._row_h()
            p.setFont(_font(9.5, True))
            p.setPen(pen(t.text, 1))
            p.drawText(
                QRectF(0, y, self.LABEL_W - 10, cell),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                row.name,
            )
            p.setFont(mono)
            for bit in range(f.width):
                field, _ = self._field(bit)
                x = self._x(bit)
                rect = QRectF(x, y, cell - 2, cell)
                color = colors[field]
                if row.bits is None:
                    p.setPen(pen(alpha(t.muted, 70), 1))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(rect, 3, 3)
                    continue
                one = bool(row.bits >> bit & 1)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color if one else alpha(color, 34 if t.dark else 26))
                p.drawRoundedRect(rect, 3, 3)
                if self.hover == (r, bit) and row.clickable:
                    p.setPen(pen(t.text, 1.6))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 4, 4)
                if self.flash == (r, bit):
                    p.setPen(pen(t.halo if not t.dark else "#ffd54a", 2.6))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 5, 5)
                p.setPen(pen("#ffffff" if one else color, 1))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "1" if one else "0")
            if row.caption:
                p.setFont(_font(8.0))
                p.setPen(pen(t.muted, 1))
                p.drawText(
                    QRectF(self.LABEL_W, y + cell + 1, self.width() - self.LABEL_W, 14),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    row.caption,
                )
        p.end()

    # ---------------------------------------------------------------- ratón
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        at = self._at(event.position())
        if at != self.hover:
            self.hover = at
            self.update()
        clickable = at is not None and self.rows[at[0]].clickable
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor
        )
        if at is None:
            QToolTip.hideText()
            return
        r, bit = at
        row = self.rows[r]
        field, k = self._field(bit)
        names = {"sign": "signo", "exponent": "exponente", "fraction": "fracción"}
        weight = {
            "sign": "0 positivo, 1 negativo",
            "exponent": f"vale 2^{k} en el exponente con sesgo",
            "fraction": f"vale 2^−{self.fmt.frac_bits - k} en el significando",
        }[field]
        value = "—" if row.bits is None else str(row.bits >> bit & 1)
        tip = f"<b>{row.name} · bit {bit}</b> = {value}<br>{names[field]}: {weight}"
        if row.clickable:
            tip += "<br><i>clic para invertirlo y recalcular</i>"
        QToolTip.showText(event.globalPosition().toPoint(), tip, self)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self.hover = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        at = self._at(event.position())
        if at is not None and self.rows[at[0]].clickable and self.rows[at[0]].bits is not None:
            self.bit_clicked.emit(*at)


# ---------------------------------------------------------------- ciclos
@dataclass(frozen=True)
class Segment:
    key: str
    label: str
    cells: int


class CycleStrip(QWidget):
    """El camino crítico como una barra de etapas, con las fronteras de cada ciclo."""

    def __init__(self) -> None:
        super().__init__()
        self.segments: list[Segment] = []
        self.period = 1
        self.hover: int | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, segments: Sequence[Segment], period: int) -> None:
        self.segments = list(segments)
        self.period = max(1, period)
        self.update()

    @property
    def total(self) -> int:
        return sum(s.cells for s in self.segments)

    def _bar(self) -> QRectF:
        return QRectF(8.0, 26, self.width() - 16, 30)

    def _spans(self) -> list[tuple[QRectF, int, int]]:
        bar = self._bar()
        total = max(1, self.total)
        out = []
        start = 0
        for s in self.segments:
            x0 = bar.left() + bar.width() * start / total
            x1 = bar.left() + bar.width() * (start + s.cells) / total
            out.append((QRectF(x0, bar.top(), x1 - x0, bar.height()), start + 1, start + s.cells))
            start += s.cells
        return out

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        t = th.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bar = self._bar()
        if not self.segments:
            p.setPen(pen(t.muted, 1))
            p.drawText(
                QRectF(0, 0, self.width(), self.height()),
                Qt.AlignmentFlag.AlignCenter,
                "Calcule una operación para ver su camino crítico.",
            )
            p.end()
            return
        p.setFont(_font(8.0, True))
        spans = self._spans()
        for k, (seg, (r, _, _)) in enumerate(zip(self.segments, spans, strict=True)):
            color = stage_color(seg.key)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color.lighter(115) if k == self.hover else color)
            p.drawRect(r)
        # Fronteras de ciclo
        total = self.total
        n = math.ceil(total / self.period)
        p.setFont(_font(8.0, True))
        for c in range(n + 1):
            cells = min(c * self.period, total)
            x = bar.left() + bar.width() * cells / total
            p.setPen(pen(t.text, 1.4, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, bar.top() - 6), QPointF(x, bar.bottom() + 6))
            p.setPen(pen(t.muted, 1))
            p.setFont(_font(7.5))
            p.drawText(
                QRectF(x - 20, bar.bottom() + 6, 40, 14), Qt.AlignmentFlag.AlignCenter, str(cells)
            )
            if c < n:
                x2 = bar.left() + bar.width() * min((c + 1) * self.period, total) / total
                p.setFont(_font(8.0, True))
                p.setPen(pen(t.text, 1))
                p.drawText(
                    QRectF(x, 4, x2 - x, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    f"ciclo {c + 1}" if x2 - x > 52 else str(c + 1),
                )
        # Nombres de las etapas, encima de las fronteras para que se lean.
        p.setFont(_font(8.0, True))
        fm = QFontMetricsF(p.font())
        for seg, (r, _, _) in zip(self.segments, spans, strict=True):
            w = fm.horizontalAdvance(seg.label) + 10
            if r.width() > w:
                box = QRectF(r.center().x() - w / 2, r.top() + 6, w, r.height() - 12)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(alpha(stage_color(seg.key).darker(130), 200))
                p.drawRoundedRect(box, 4, 4)
                p.setPen(pen("#ffffff", 1))
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, seg.label)
        p.setPen(pen(t.muted, 1))
        p.setFont(_font(7.5))
        p.drawText(
            QRectF(0, bar.bottom() + 20, self.width(), 14),
            Qt.AlignmentFlag.AlignCenter,
            "celdas del camino crítico (una unidad de retardo cada una)",
        )
        p.end()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        hit = None
        for k, (r, first, last) in enumerate(self._spans()):
            if r.contains(pos):
                hit = k
                seg = self.segments[k]
                c0 = (first - 1) // self.period + 1
                c1 = (last - 1) // self.period + 1
                cycles = f"ciclo {c0}" if c0 == c1 else f"ciclos {c0}–{c1}"
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"<b>{seg.label}</b><br>{seg.cells} celdas "
                    f"(de la {first} a la {last})<br>{cycles}",
                    self,
                )
        if hit is None:
            QToolTip.hideText()
        if hit != self.hover:
            self.hover = hit
            self.update()

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self.hover = None
        self.update()


# ---------------------------------------------------------------- barras
@dataclass(frozen=True)
class Bar:
    key: str
    label: str
    value: int


class BarList(QWidget):
    """Gráfico de barras horizontales; doble clic en una barra emite su clave."""

    activated = Signal(str)

    ROW = 26.0

    def __init__(self, empty: str = "Sin datos.") -> None:
        super().__init__()
        self.bars: list[Bar] = []
        self.empty = empty
        self.hover: int | None = None
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_bars(self, bars: Sequence[Bar]) -> None:
        self.bars = sorted(bars, key=lambda b: -b.value)
        self.setMinimumHeight(int(max(60.0, len(self.bars) * self.ROW + 8.0)))
        self.update()

    def _label_w(self) -> float:
        fm = QFontMetricsF(_font(9.0))
        return max([fm.horizontalAdvance(b.label) for b in self.bars] + [60.0]) + 14

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        t = th.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.bars:
            p.setPen(pen(t.muted, 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.empty)
            p.end()
            return
        total = sum(b.value for b in self.bars) or 1
        top = max(b.value for b in self.bars) or 1
        lw = self._label_w()
        value_w = 110.0
        bar_w = max(40.0, self.width() - lw - value_w - 12)
        for k, b in enumerate(self.bars):
            y = 4 + k * self.ROW
            if k == self.hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(t.hover))
                p.drawRoundedRect(QRectF(0, y - 2, self.width(), self.ROW), 5, 5)
            p.setFont(_font(9.0))
            p.setPen(pen(t.text, 1))
            p.drawText(
                QRectF(4, y, lw - 10, self.ROW - 4),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                b.label,
            )
            w = bar_w * b.value / top
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(stage_color(b.key))
            p.drawRoundedRect(QRectF(lw, y + 4, max(w, 2), self.ROW - 12), 4, 4)
            p.setPen(pen(t.muted, 1))
            p.drawText(
                QRectF(lw + max(w, 2) + 8.0, y, value_w + bar_w - w, self.ROW - 4),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"{thousands(b.value)}  ·  {100 * b.value / total:.1f} %",
            )
        p.end()

    def _row_at(self, pos: QPoint | QPointF) -> int | None:
        k = int((pos.y() - 4) // self.ROW)
        return k if 0 <= k < len(self.bars) else None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        k = self._row_at(event.position())
        if k != self.hover:
            self.hover = k
            self.update()
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if k is not None else Qt.CursorShape.ArrowCursor
        )
        if k is not None:
            b = self.bars[k]
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"<b>{b.label}</b>: {thousands(b.value)} conmutaciones<br>"
                "<i>doble clic para verla en Transistores</i>",
                self,
            )

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self.hover = None
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        k = self._row_at(event.position())
        if k is not None:
            self.activated.emit(self.bars[k].key)


class _ClickFilter(QObject):
    """Convierte el clic en un QLabel en una señal (para enlaces sencillos)."""

    clicked = Signal()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonRelease:
            self.clicked.emit()
            return True
        return False


__all__ = [
    "FLAG_CHIPS",
    "Bar",
    "BarList",
    "BitField",
    "BitRow",
    "Chip",
    "Chips",
    "CycleStrip",
    "Segment",
    "Segmented",
    "StatTile",
    "card",
    "flag_keys",
    "hint",
    "stage_color",
    "thousands",
]
