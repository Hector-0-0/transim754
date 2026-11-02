"""Lienzo de la pestaña de transistores: pinta esquemas y layouts con el estado del motor.

Cada celda es un ítem que pinta su geometría (calculada una vez por definición) con los
valores actuales del motor:

- :class:`SchematicItem`: el esquema eléctrico; el color de cada cable es el valor de su
  nodo y el canal de cada transistor se dibuja continuo si conduce y cortado si no.
- :class:`SiliconItem`: el layout físico ilustrativo (difusión, polisilicio, metal); el
  canal de cada transistor se ilumina cuando conduce.

Pasar el ratón por un cable resalta el nodo completo, también en las otras celdas a las
que llega; un clic en un transistor lo selecciona. Con poco zoom las celdas se pintan
simplificadas (nivel de detalle), así un bloque de miles de transistores se mueve con
fluidez.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)

from transim.core.signals import Logic
from transim.core.transistor import Conduction
from transim.ui.gui import floorplan, gates, silicon
from transim.ui.gui import theme as th
from transim.ui.gui.circuit import Binding, ValueReader, active_path
from transim.ui.gui.schematic import (
    CHANNEL_X,
    DEV_H,
    GATE_X,
    GATE_Y,
    LEAD_Y,
    PLATE_X,
    Device,
    Schematic,
    build,
)


def _font(size: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPointSizeF(size)
    f.setBold(bold)
    return f


LABEL_FONT = _font(9.0)
SMALL_FONT = _font(7.5)
TITLE_FONT = _font(10.0, bold=True)
BADGE_FONT = _font(7.0, bold=True)
PIN_FONT = _font(6.5, bold=True)

# Colores de las capas del layout (convención de los editores de layout: difusión p
# ocre, difusión n verde, polisilicio rojo, metal 1 azul, metal 2 violeta).
# Las capas usan tonos que no son los de los valores lógicos (rojo = 1, azul = 0, verde =
# conduce): así un mismo color no significa dos cosas en el esquema y en el silicio.
DIM_OPACITY = 0.16
PAIR_GAP = 90.0
"""Espacio entre el esquema y el silicio de una celda dibujada lado a lado."""
PIN_RISE = 26.0
"""Altura de los nombres de los puertos sobre la celda de silicio."""
GATE_MARGIN = 4.0
"""Margen alrededor de una compuerta para el ratón y el resaltado."""
"""Opacidad de lo que no forma parte del paso mostrado en el esquema."""

LAYER_COLOR = {
    "nwell": "#a39338",
    "pdiff": "#c8913a",
    "ndiff": "#3c9c50",
    "poly": "#a35fc0",
    "metal1": "#8c97a8",
    "metal2": "#0e9aa7",
    "contact": "#121212",
    "via": "#f1f1f1",
}
LAYER_ALPHA = {"pdiff": 215, "ndiff": 215, "poly": 230, "metal1": 255, "metal2": 255}
TOGGLE_LAYERS = ("nwell", "pdiff", "ndiff", "poly", "contact", "metal1", "via", "metal2")
"""Capas que el usuario puede ocultar en la vista de silicio (el canal siempre se ve)."""
LAYER_NAMES = {
    "nwell": "pozo n (n-well)",
    "pdiff": "difusión p+ (pMOS)",
    "ndiff": "difusión n+ (nMOS)",
    "poly": "polisilicio (compuertas)",
    "metal1": "metal 1",
    "metal2": "metal 2",
    "contact": "contacto",
    "via": "vía",
}


def measure(text: str) -> float:
    """Ancho de ``text`` con la fuente de las etiquetas del esquema (con la insignia)."""
    return QFontMetricsF(LABEL_FONT).horizontalAdvance(text) + 16


def pen(
    color: QColor | str,
    width: float,
    style: Qt.PenStyle = Qt.PenStyle.SolidLine,
    cap: Qt.PenCapStyle = Qt.PenCapStyle.RoundCap,
) -> QPen:
    """Lápiz con color, ancho, estilo y remate."""
    p = QPen(QColor(color))
    p.setWidthF(width)
    p.setStyle(style)
    p.setCapStyle(cap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return p


def alpha(color: QColor | str, a: int) -> QColor:
    c = QColor(color)
    c.setAlpha(a)
    return c


def logic_text(value: Logic) -> str:
    return {Logic.ZERO: "0", Logic.ONE: "1", Logic.X: "X", Logic.Z: "Z"}[value]


# ---------------------------------------------------------------- impactos
@dataclass(frozen=True)
class Hit:
    """Lo que hay bajo el ratón: un transistor, un nodo, una entrada o la celda.

    ``node`` es el id del nodo real (del netlist dibujado); ``transistor`` el índice
    dentro de la definición de la celda; ``port`` el nombre de la entrada de la celda.
    """

    item: CellItem
    kind: str  # "transistor" | "node" | "input" | "gate" | "cell"
    transistor: int | None = None
    node: int | None = None
    port: str | None = None
    element: int | None = None
    """Elemento de la celda (etapa o transmission gate) en la vista de compuertas."""

    @property
    def binding(self) -> Binding:
        return self.item.binding


def _dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _aligned(x: float, w: float, align: str) -> float:
    return x - w if align == "right" else x - w / 2 if align == "center" else x


# ------------------------------------------------------------------ celdas
class CellItem(QGraphicsItem):
    """Base de las celdas pintadas: enlace con el netlist, ratón y resaltado."""

    def __init__(self, binding: Binding, title: str, board: CircuitScene) -> None:
        super().__init__()
        self.binding = binding
        self.title = title
        self.board = board
        self.heat = 0.0
        self.real_nodes = {n.id for n in binding.nodes.values()}
        self._local = {n.id: k for k, n in binding.nodes.items()}
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)

    def linked(self, other: object) -> bool:
        """True si ``other`` dibuja la misma celda (por ejemplo, su esquema y su silicio)."""
        if other is self:
            return True
        return (
            isinstance(other, CellItem)
            and other.binding.path == self.binding.path
            and other.binding.netlist is self.binding.netlist
        )

    def node_id(self, local: int) -> int:
        """Id real del nodo ``local`` de la definición."""
        return self.binding.nodes[local].id

    def local_node(self, real: int) -> int | None:
        return self._local.get(real)

    def value_fn(self) -> Callable[[int], Logic]:
        values, nodes = self.board.values, self.binding.nodes
        assert values is not None
        return lambda n: values.value(nodes[n])

    def input_port(self, local: int) -> str | None:
        for port, node in self.binding.circuit.inputs.items():
            if node == local:
                return port
        return None

    def hit(self, pos: QPointF) -> Hit | None:  # pragma: no cover - lo implementan las hijas
        raise NotImplementedError

    def transistor_rect(self, index: int) -> QRectF:  # pragma: no cover
        raise NotImplementedError

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        self.board.set_hover(self.hit(event.pos()))

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        self.board.set_hover(None)

    def _paint_heat(self, painter: QPainter, rect: QRectF) -> None:
        """Mapa de actividad: transparente si la celda no conmutó, de ámbar a rojo cuanto
        más conmutó en la última operación."""
        if self.board.show_heat and self.heat > 0:
            h = self.heat
            color = QColor.fromHsvF(max(0.0, 0.13 - 0.13 * h), 0.95, 1.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(alpha(color, int(40 + 190 * h * h))))
            painter.drawRect(rect)


# ---------------------------------------------------------------- esquema
class SchematicItem(CellItem):
    """Una celda pintada como esquema eléctrico."""

    def __init__(self, binding: Binding, title: str, board: CircuitScene) -> None:
        super().__init__(binding, title, board)
        self.geo: Schematic = build(binding.netlist, measure)

    def boundingRect(self) -> QRectF:  # noqa: N802 - API de Qt
        return QRectF(-4, -4, self.geo.width + 8.0, self.geo.height + 8.0)

    def transistor_rect(self, index: int) -> QRectF:
        for d in self.geo.devices:
            if d.index == index:
                x0, y0, x1, y1 = d.bounds()
                return QRectF(x0, y0, x1 - x0, y1 - y0)
        return QRectF()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        t = th.current()
        if self.board.values is None:
            return
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        rect = QRectF(0, 0, self.geo.width, self.geo.height)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, lod > 0.2)
        painter.setPen(pen(t.frame, 1.2))
        painter.setBrush(QBrush(QColor(t.paper)))
        painter.drawRoundedRect(rect, 10, 10)
        if self.board.selected_item is self and self.board.selected_transistor is None:
            painter.setPen(pen(t.select, 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 12, 12)
        value = self.value_fn()
        state = self.binding.state(self.board.values)
        if lod < 0.22:
            self._paint_far(painter, t, state, rect)
            self._paint_heat(painter, rect)
            return
        for band in self.geo.bands:
            tint = t.one if band.kind == "up" else t.zero
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(alpha(tint, 22 if t.dark else 16)))
            painter.drawRect(QRectF(band.x0, band.y0, band.x1 - band.x0, band.y1 - band.y0))
        self._paint_halos(painter, t, state, value)
        for s in self.geo.rails:
            painter.setPen(pen(t.logic(value(s.node)), 3.2))
            painter.drawLine(QPointF(s.x1, s.y1), QPointF(s.x2, s.y2))
        hover_node = self.board.hover_node
        local_hover = self.local_node(hover_node) if hover_node is not None else None
        toggled = self.board.toggled_nodes if self.board.show_toggles else set()
        focus = self.board.step_filter

        def dim(on: bool) -> None:
            painter.setOpacity(1.0 if focus is None or on else DIM_OPACITY)

        for s in self.geo.segs:
            dim(focus is None or s.node in focus[1] or s.node in (0, 1))
            if local_hover is not None and s.node == local_hover:
                painter.setPen(pen(alpha(t.halo, 170), 9))
                painter.drawLine(QPointF(s.x1, s.y1), QPointF(s.x2, s.y2))
            elif toggled and self.node_id(s.node) in toggled:
                painter.setPen(pen(alpha("#ff9f1a", 110), 7))
                painter.drawLine(QPointF(s.x1, s.y1), QPointF(s.x2, s.y2))
            painter.setPen(wire_pen(t, value(s.node)))
            painter.drawLine(QPointF(s.x1, s.y1), QPointF(s.x2, s.y2))
        painter.setPen(Qt.PenStyle.NoPen)
        for j in self.geo.joints:
            dim(focus is None or j.node in focus[1])
            painter.setBrush(QBrush(t.logic(value(j.node))))
            painter.drawEllipse(QPointF(j.x, j.y), 3.4, 3.4)
        for d in self.geo.devices:
            dim(focus is None or d.index in focus[0])
            self._paint_device(painter, t, d, state[d.index], value)
        painter.setOpacity(1.0)
        if lod > 0.42:
            self._paint_texts(painter, t, value, local_hover)
        else:
            self._paint_title(painter, t, rect, lod)
        self._paint_flow(painter, t)
        self._paint_heat(painter, rect)

    def _paint_title(self, painter: QPainter, t: th.Theme, rect: QRectF, lod: float) -> None:
        """Con poco zoom, el título se pinta a tamaño de pantalla constante."""
        if rect.width() * lod < 44:
            return
        painter.save()
        painter.translate(rect.left() + 6, rect.top() + 4)
        painter.scale(1 / lod, 1 / lod)
        font = _font(8.5, bold=True)
        painter.setFont(font)
        fm = QFontMetricsF(font)
        text = fm.elidedText(self.title, Qt.TextElideMode.ElideRight, rect.width() * lod - 12)
        box = QRectF(0, 0, fm.horizontalAdvance(text) + 8.0, fm.height() + 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(alpha(t.surface, 215)))
        painter.drawRoundedRect(box, 4, 4)
        painter.setPen(pen(t.text, 1))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _paint_far(
        self, painter: QPainter, t: th.Theme, state: Sequence[Conduction], rect: QRectF
    ) -> None:
        """Vista lejana: el título y una barra con la proporción de canales que conducen."""
        on = sum(1 for s in state if s is Conduction.ON)
        r = rect.adjusted(14, 14, -14, -14)
        bar = QRectF(r.left(), r.bottom() - 18, r.width(), 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(t.off)))
        painter.drawRoundedRect(bar, 6, 6)
        painter.setBrush(QBrush(QColor(t.on)))
        painter.drawRoundedRect(
            QRectF(bar.left(), bar.top(), bar.width() * on / max(1, len(state)), 18), 6, 6
        )
        painter.setPen(pen(t.ink, 1))
        painter.setFont(_font(max(10.0, min(r.width(), r.height()) / 7), bold=True))
        painter.drawText(
            r.adjusted(0, 0, 0, -24),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.title,
        )

    def _paint_halos(
        self,
        painter: QPainter,
        t: th.Theme,
        state: Sequence[Conduction],
        value: Callable[[int], Logic],
    ) -> None:
        """Fondo verde detrás del camino conductor que fija el valor de cada salida."""
        if not self.board.show_paths:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(alpha(t.on, 46 if t.dark else 36)))
        path: set[int] = set()
        for stage, _, _ in self.geo.stages:
            out = value(stage.output)
            if out in (Logic.ONE, Logic.ZERO):
                path |= active_path(stage.pull_up if out is Logic.ONE else stage.pull_down, state)
        for d in self.geo.devices:
            if d.index in path:
                x0, y0, x1, y1 = d.bounds()
                painter.drawRoundedRect(QRectF(x0 + 14, y0 - 3, x1 - x0 - 2, y1 - y0 + 6), 7, 7)

    def _paint_device(
        self,
        painter: QPainter,
        t: th.Theme,
        d: Device,
        state: Conduction,
        value: Callable[[int], Logic],
    ) -> None:
        painter.save()
        painter.translate(d.x, d.y)
        if d.angle:
            painter.rotate(d.angle)
        sel = self.linked(self.board.selected_item) and self.board.selected_transistor == d.index
        hov = self.linked(self.board.hover_item) and self.board.hover_transistor == d.index
        if sel or hov:
            painter.setPen(pen(t.select, 1.6) if sel else Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(alpha(t.select, 64 if sel else 36)))
            painter.drawRoundedRect(QRectF(GATE_X - 4, -4, -GATE_X + 12, DEV_H + 8.0), 7, 7)
        top, bottom, gate = value(d.top), value(d.bottom), value(d.gate)
        painter.setPen(wire_pen(t, top))
        painter.drawPolyline([QPointF(0, 0), QPointF(0, LEAD_Y), QPointF(CHANNEL_X, LEAD_Y)])
        painter.setPen(wire_pen(t, bottom))
        painter.drawPolyline(
            [QPointF(CHANNEL_X, DEV_H - LEAD_Y), QPointF(0, DEV_H - LEAD_Y), QPointF(0, DEV_H)]
        )
        # Canal: continuo si conduce (interruptor cerrado), cortado si no.
        y0, y1 = LEAD_Y - 3, DEV_H - LEAD_Y + 3
        color = t.channel(state)
        if state is Conduction.ON:
            painter.setPen(pen(color, 4.0))
            painter.drawLine(QPointF(CHANNEL_X, y0), QPointF(CHANNEL_X, y1))
        elif state is Conduction.OFF:
            painter.setPen(pen(color, 3.0, cap=Qt.PenCapStyle.FlatCap))
            third = (y1 - y0) / 3
            for k in range(3):
                painter.drawLine(
                    QPointF(CHANNEL_X, y0 + k * third + 2),
                    QPointF(CHANNEL_X, y0 + (k + 1) * third - 2),
                )
        else:
            painter.setPen(pen(color, 3.0, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(CHANNEL_X, y0), QPointF(CHANNEL_X, y1))
        painter.setPen(pen(t.ink, 2.6, cap=Qt.PenCapStyle.FlatCap))
        painter.drawLine(QPointF(PLATE_X, LEAD_Y), QPointF(PLATE_X, DEV_H - LEAD_Y))
        lead_end = PLATE_X
        if d.pmos:
            painter.setPen(pen(t.ink, 1.8))
            painter.setBrush(QBrush(QColor(t.paper)))
            painter.drawEllipse(QPointF(PLATE_X - 5, GATE_Y), 4.0, 4.0)
            lead_end = PLATE_X - 9
        painter.setPen(wire_pen(t, gate))
        painter.drawLine(QPointF(GATE_X, GATE_Y), QPointF(lead_end, GATE_Y))
        painter.restore()

    def _paint_texts(
        self,
        painter: QPainter,
        t: th.Theme,
        value: Callable[[int], Logic],
        local_hover: int | None,
    ) -> None:
        shown: set[str] = set()  # nombres de transistores: solo el del ratón o el elegido
        names = self.binding.circuit.transistors
        for owner, index in (
            (self.board.hover_item, self.board.hover_transistor),
            (self.board.selected_item, self.board.selected_transistor),
        ):
            if self.linked(owner) and index is not None:
                shown.add(names[index].name)
        for text in self.geo.texts:
            if text.kind == "name" and text.text not in shown:
                continue
            if text.kind == "band":
                painter.setFont(SMALL_FONT)
                painter.setPen(pen(t.muted, 1))
                painter.drawText(QPointF(text.x, text.y + 4), text.text)
                continue
            if text.kind == "title":
                painter.setFont(TITLE_FONT)
                painter.setPen(pen(t.ink, 1))
                painter.drawText(QPointF(text.x, text.y + 5), self.title)
            elif text.kind == "name":
                painter.setFont(SMALL_FONT)
                painter.setPen(pen(t.muted, 1))
                fm = QFontMetricsF(SMALL_FONT)
                x = _aligned(text.x, fm.horizontalAdvance(text.text), text.align)
                painter.drawText(QPointF(x, text.y + fm.ascent() / 2 - 1), text.text)
            elif text.kind == "rail":
                painter.setFont(SMALL_FONT)
                color = t.logic(value(text.node)) if text.node is not None else QColor(t.ink)
                painter.setPen(pen(color, 1))
                painter.drawText(QPointF(text.x, text.y + 4), text.text)
            elif text.node is not None:
                label(
                    painter,
                    t,
                    text.text,
                    text.x,
                    text.y,
                    text.align,
                    value(text.node),
                    text.kind,
                    text.node == local_hover,
                    clickable=self.node_id(text.node) in self.board.clickable_nodes,
                )

    def _paint_flow(self, painter: QPainter, t: th.Theme) -> None:
        """Corriente transitoria: puntos que bajan por los transistores que cargaron o
        descargaron una salida justo después de un cambio de entrada."""
        flows = self.board.flows.get(self)
        if not flows:
            return
        phase = self.board.flow_phase
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#ffcc33")))
        for d in self.geo.devices:
            if d.index not in flows:
                continue
            for k in range(3):
                f = (phase + k / 3) % 1.0
                x, y = d.to_scene(0.0, f * DEV_H)
                painter.drawEllipse(QPointF(x, y), 2.8, 2.8)

    def hit(self, pos: QPointF) -> Hit | None:
        x, y = pos.x(), pos.y()
        for text in self.geo.texts:
            if text.node is None or text.kind not in ("gate", "pin_in", "net", "pin_out"):
                continue
            w = measure(text.text)
            x0 = _aligned(text.x, w, text.align)
            if x0 - 4 <= x <= x0 + w + 4 and abs(y - text.y) <= 10:
                real = self.node_id(text.node)
                if real in self.board.clickable_nodes:
                    return Hit(self, "input", node=real, port=self.input_port(text.node))
                return Hit(self, "node", node=real)
        for d in self.geo.devices:
            x0, y0, x1, y1 = d.bounds()
            if x0 + 4 <= x <= x1 + 4 and y0 - 2 <= y <= y1 + 2:
                return Hit(self, "transistor", transistor=d.index)
        best: tuple[float, int] | None = None
        for s in self.geo.segs + self.geo.rails:
            dist = _dist(x, y, s.x1, s.y1, s.x2, s.y2)
            if dist <= 5 and (best is None or dist < best[0]):
                best = (dist, s.node)
        if best is not None:
            return Hit(self, "node", node=self.node_id(best[1]))
        return Hit(self, "cell")


def label(
    painter: QPainter,
    t: th.Theme,
    text: str,
    x: float,
    y: float,
    align: str,
    v: Logic,
    kind: str,
    hovered: bool,
    clickable: bool = False,
) -> None:
    """Etiqueta de nodo con una insignia de su valor. Los puertos llevan recuadro."""
    fm = QFontMetricsF(LABEL_FONT)
    w = fm.horizontalAdvance(text)
    total = w + 16
    x0 = _aligned(x, total, align)
    color = t.logic(v)
    if kind in ("pin_in", "pin_out") or hovered:
        box = QRectF(x0 - 5, y - 9.5, total + 8.0, 19)
        painter.setPen(pen(color, 1.8 if clickable else 1.2))
        painter.setBrush(QBrush(alpha(color, 52 if hovered else 24)))
        painter.drawRoundedRect(box, 5, 5)
    painter.setFont(LABEL_FONT)
    painter.setPen(pen(color, 1))
    painter.drawText(QPointF(x0, y + fm.ascent() / 2 - 1.5), text)
    badge = QRectF(x0 + w + 3, y - 6, 12, 12)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color))
    painter.drawRoundedRect(badge, 3, 3)
    painter.setFont(BADGE_FONT)
    painter.setPen(pen(t.paper, 1))
    painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, logic_text(v))


# ---------------------------------------------------------------- silicio
class SiliconItem(CellItem):
    """Una celda pintada como layout físico. ``flipped`` la refleja en vertical (las filas
    impares de celdas estándar se reflejan para compartir los rieles)."""

    def __init__(
        self, binding: Binding, title: str, board: CircuitScene, flipped: bool = False
    ) -> None:
        super().__init__(binding, title, board)
        self.lay = silicon.build(binding.netlist)
        self.flipped = flipped
        self.pins_outside = False
        """Nombres de los puertos encima de la celda, con una línea hasta su metal."""
        self._by_layer = {name: self.lay.layer(name) for name in silicon.LAYERS}

    def _r(self, s: silicon.Shape) -> QRectF:
        if self.flipped:
            h = self.lay.height
            return QRectF(s.x0, h - s.y1, s.x1 - s.x0, s.y1 - s.y0)
        return QRectF(s.x0, s.y0, s.x1 - s.x0, s.y1 - s.y0)

    def _y(self, y: float) -> float:
        return self.lay.height - y if self.flipped else y

    def transistor_rect(self, index: int) -> QRectF:
        for s in self._by_layer["channel"]:
            if s.transistor == index:
                return self._r(s)
        return QRectF()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if self.board.values is None:
            return
        t = th.current()
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        rect = QRectF(0, 0, self.lay.width, self.lay.height)
        well = self._r(silicon.Shape("nwell", 0, 0, self.lay.width, self.lay.well_bottom))
        state = self.binding.state(self.board.values)
        if lod < 0.09:
            self._paint_far(painter, rect, well, state)
            self._paint_heat(painter, rect)
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(silicon_background(t))))
        painter.drawRect(rect)
        shown = self.board.visible_layers
        if "nwell" in shown:
            painter.setBrush(QBrush(alpha(LAYER_COLOR["nwell"], 40)))
            painter.drawRect(well)
            if lod > 0.25:
                painter.setPen(pen(alpha(LAYER_COLOR["nwell"], 170), 1.0, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(well)
        value = self.value_fn()
        by_value = self.board.color_by_value
        detail = lod > 0.3
        for layer in ("pdiff", "ndiff", "poly"):
            if layer in shown:
                self._fill(painter, t, layer, value, by_value, detail)
        # Canales: se iluminan cuando el transistor conduce.
        for s in self._by_layer["channel"]:
            assert s.transistor is not None
            st = state[s.transistor]
            r = self._r(s)
            if st is Conduction.ON:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(alpha(t.on, 235)))
                painter.drawRect(r)
                if detail:
                    painter.setBrush(QBrush(alpha("#eafff1", 150)))
                    painter.drawRect(r.adjusted(r.width() * 0.3, 2, -r.width() * 0.3, -2))
            elif st is Conduction.UNKNOWN:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(alpha(t.unknown, 220)))
                painter.drawRect(r)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(alpha("#3a2a2a", 200)))
                painter.drawRect(r)
        if detail and "contact" in shown:
            self._contacts(painter, "contact")
        if "metal1" in shown:
            self._fill(painter, t, "metal1", value, by_value, detail)
        if detail and "via" in shown:
            self._contacts(painter, "via")
        if "metal2" in shown:
            self._fill(painter, t, "metal2", value, by_value, detail)
        self._paint_marks(painter, t)
        if self.pins_outside:
            self._paint_pins_outside(painter, t, value)
        elif lod > 0.55:
            self._paint_pins(painter, t, value)
        if lod > 0.2:
            painter.setPen(pen(alpha(t.ink, 60), 0.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
        self._paint_heat(painter, rect)

    def _paint_far(
        self, painter: QPainter, rect: QRectF, well: QRectF, state: Sequence[Conduction]
    ) -> None:
        """Vista lejana: la celda como un bloque de silicio con su pozo y sus rieles."""
        t = th.current()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#3a4152" if t.dark else "#b9c3d6")))
        painter.drawRect(rect)
        painter.setBrush(QBrush(QColor("#5b5a3c" if t.dark else "#d3cc9c")))
        painter.drawRect(well)
        on = sum(1 for s in state if s is Conduction.ON) / max(1, len(state))
        painter.setBrush(QBrush(alpha(t.on, int(60 + 120 * on))))
        painter.drawRect(
            rect.adjusted(
                rect.width() * 0.2, rect.height() * 0.35, -rect.width() * 0.2, -rect.height() * 0.35
            )
        )
        painter.setPen(pen(QColor("#202634" if t.dark else "#7f8aa3"), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

    def _fill(
        self,
        painter: QPainter,
        t: th.Theme,
        layer: str,
        value: Callable[[int], Logic],
        by_value: bool,
        detail: bool,
    ) -> None:
        base = QColor(LAYER_COLOR[layer])
        a = LAYER_ALPHA.get(layer, 200)
        hover = self.board.hover_node
        local_hover = self.local_node(hover) if hover is not None else None
        for s in self._by_layer[layer]:
            r = self._r(s)
            color = t.logic(value(s.node)) if by_value and s.node is not None else base
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(alpha(color, a)))
            painter.drawRect(r)
            if detail:
                painter.setPen(pen(color.darker(140) if not by_value else color, 0.8))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(r)
            if local_hover is not None and s.node == local_hover:
                painter.setPen(pen(QColor("#ffe14d"), 2.2))
                painter.setBrush(QBrush(alpha("#ffe14d", 70)))
                painter.drawRect(r)

    def _contacts(self, painter: QPainter, layer: str) -> None:
        dark = layer == "contact"
        fill = QColor(LAYER_COLOR[layer])
        cross = QColor("#d9d9d9" if dark else "#333333")
        for s in self._by_layer[layer]:
            r = self._r(s)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill))
            painter.drawRect(r)
            painter.setPen(pen(cross, 0.9, cap=Qt.PenCapStyle.FlatCap))
            painter.drawLine(r.topLeft(), r.bottomRight())
            painter.drawLine(r.topRight(), r.bottomLeft())

    def _paint_marks(self, painter: QPainter, t: th.Theme) -> None:
        """Transistor seleccionado o bajo el ratón."""
        for index, color, w in (
            (
                self.board.hover_transistor if self.linked(self.board.hover_item) else None,
                t.halo,
                2.0,
            ),
            (
                self.board.selected_transistor if self.linked(self.board.selected_item) else None,
                t.select,
                2.6,
            ),
        ):
            if index is None:
                continue
            r = self.transistor_rect(index)
            painter.setPen(pen(color, w))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r.adjusted(-3, -3, 3, 3))

    def _paint_pins(self, painter: QPainter, t: th.Theme, value: Callable[[int], Logic]) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        lod = painter.worldTransform().m11()
        shrink = min(1.0, 1.5 / lod) if lod > 0 else 1.0  # con mucho zoom no crecen más
        fm = QFontMetricsF(PIN_FONT)
        for p in self.lay.pins:
            text = f"{p.text}={logic_text(value(p.node))}"
            w = fm.horizontalAdvance(text) + 6
            painter.save()
            painter.translate(p.x, self._y(p.y))
            painter.scale(shrink, shrink)
            box = QRectF(-w / 2, -6.5, w, 13)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(alpha("#0b0c10", 200)))
            painter.drawRoundedRect(box, 3, 3)
            painter.setFont(PIN_FONT)
            painter.setPen(pen(t.logic(value(p.node)).lighter(130), 1))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()

    def _paint_pins_outside(
        self, painter: QPainter, t: th.Theme, value: Callable[[int], Logic]
    ) -> None:
        """Puertos encima de la celda, en orden de izquierda a derecha, sin taparla."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        fm = QFontMetricsF(LABEL_FONT)
        next_x = -1e9
        for p in sorted(self.lay.pins, key=lambda q: q.x):
            v = value(p.node)
            text = f"{p.text} = {logic_text(v)}"
            w = fm.horizontalAdvance(text) + 10
            x = max(p.x - w / 2, next_x + 4)
            next_x = x + w
            box = QRectF(x, -PIN_RISE - 18, w, 18)
            color = t.logic(v)
            painter.setPen(pen(alpha(color, 200), 1.0, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(box.center().x(), box.bottom()), QPointF(p.x, self._y(p.y)))
            painter.setPen(pen(color, 1.2))
            painter.setBrush(QBrush(alpha(t.surface, 235)))
            painter.drawRoundedRect(box, 4, 4)
            painter.setFont(LABEL_FONT)
            painter.setPen(pen(color, 1))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def boundingRect(self) -> QRectF:  # noqa: N802
        top = -PIN_RISE - 22 if self.pins_outside else 0.0
        return QRectF(
            -40 if self.pins_outside else 0,
            top,
            self.lay.width + (80 if self.pins_outside else 0),
            self.lay.height - top,
        )

    def hit(self, pos: QPointF) -> Hit | None:
        x, y = pos.x(), self._y(pos.y())
        for s in self._by_layer["channel"]:
            if s.x0 - 1 <= x <= s.x1 + 1 and s.y0 <= y <= s.y1:
                return Hit(self, "transistor", transistor=s.transistor)
        for layer in ("metal2", "via", "metal1", "contact", "poly", "pdiff", "ndiff"):
            for s in self._by_layer[layer]:
                if s.node is not None and s.x0 <= x <= s.x1 and s.y0 <= y <= s.y1:
                    real = self.node_id(s.node)
                    if real in self.board.clickable_nodes:
                        return Hit(self, "input", node=real, port=self.input_port(s.node))
                    return Hit(self, "node", node=real)
        return Hit(self, "cell")


def silicon_background(t: th.Theme) -> str:
    """Color del sustrato p en el layout."""
    return "#121418" if t.dark else "#f4f1e8"


GAP_LABEL = 70.0
"""Espacio entre bloques del plano del chip (deja sitio para sus nombres)."""


class FrameItem(QGraphicsItem):
    """Recuadro de un bloque (o del chip) en la vista de silicio, con su nombre.

    El nombre mantiene su tamaño en pantalla con cualquier zoom y se recorta al ancho
    del recuadro, así los nombres de bloques vecinos no se pisan."""

    def __init__(self, rect: QRectF, title: str, subtitle: str, die: bool = False) -> None:
        super().__init__()
        self.rect = rect
        self.title = title
        self.subtitle = subtitle
        self.die = die
        self.setZValue(-1 if die else 2)
        self.setAcceptHoverEvents(False)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self.rect.adjusted(-12, -400 if self.die else -GAP_LABEL, 12, 12)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        t = th.current()
        lod = max(option.levelOfDetailFromTransform(painter.worldTransform()), 1e-4)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.die:
            painter.setPen(pen("#8a8f99" if t.dark else "#6b7280", 2.0 / lod))
            painter.setBrush(QBrush(QColor("#0b0c0f" if t.dark else "#e4e1d6")))
            painter.drawRect(self.rect)
            painter.setPen(pen("#4b505a" if t.dark else "#9ca3af", 1.0 / lod))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect.adjusted(8.0 / lod, 8.0 / lod, -8.0 / lod, -8.0 / lod))
        else:
            painter.setPen(pen(alpha(t.accent, 210), 1.6 / lod, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect.adjusted(-5, -5, 5, 5))
        on_screen = self.rect.width() * lod
        if on_screen < 46:
            return
        painter.save()
        inset = 6 / lod
        outside = self.die or GAP_LABEL * lod >= 30  # hay sitio encima del recuadro
        top = (
            self.rect.top() - (30 if self.die else 28) / lod if outside else self.rect.top() + inset
        )
        painter.translate(self.rect.left() + (0 if outside else inset), top)
        painter.scale(1 / lod, 1 / lod)
        painter.setFont(_font(12.0 if self.die else 9.5, bold=True))
        fm = QFontMetricsF(painter.font())
        text = f"{self.title}  ·  {self.subtitle}" if self.subtitle else self.title
        text = fm.elidedText(text, Qt.TextElideMode.ElideRight, on_screen - 2 * inset * lod - 12)
        w = fm.horizontalAdvance(text) + 12
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(alpha(t.surface, 230)))
        painter.drawRoundedRect(QRectF(0, 0, w, fm.height() + 6), 5, 5)
        painter.setPen(pen(t.text, 1))
        painter.drawText(QPointF(6, fm.ascent() + 3), text)
        painter.restore()


# ------------------------------------------------------------ plano del chip
CHIP_W = 1600.0
CHIP_H = 1100.0
BLOCK_GAP = 14.0
ROW_PITCH = 9.0
"""Separación de las líneas tenues que sugieren filas de celdas dentro de un bloque."""


class BlockItem(QGraphicsItem):
    """Un bloque en el plano del chip: área proporcional a sus transistores."""

    def __init__(self, tile: floorplan.Tile, rect: QRectF, subtitle: str, board: CircuitScene):
        super().__init__()
        self.tile = tile
        self.rect = rect
        self.subtitle = subtitle
        self.board = board
        self.heat = 0.0
        self.setAcceptHoverEvents(True)
        self.setToolTip(f"{tile.title}\n{subtitle}\nDoble clic para entrar")

    def boundingRect(self) -> QRectF:  # noqa: N802 - API de Qt
        return self.rect.adjusted(-4, -4, 4, 4)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        self.board.hover_block = self
        self.update()
        self.board.hovered.emit(BlockHit(self))

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        if self.board.hover_block is self:
            self.board.hover_block = None
        self.update()
        self.board.hovered.emit(None)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        t = th.current()
        lod = max(option.levelOfDetailFromTransform(painter.worldTransform()), 1e-4)
        r = self.rect
        base = QColor(self.tile.color)
        hover = self.board.hover_block is self
        selected = self.board.selected_block is self
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(
            QBrush(alpha(base, (110 if hover else 78) if t.dark else (95 if hover else 62)))
        )
        painter.drawRect(r)
        # Textura de filas de celdas estándar: líneas finas y tenues, sin dibujar celdas.
        if r.height() * lod > 30:
            painter.setPen(pen(alpha(base, 60 if t.dark else 70), 1.0 / lod))
            y = r.top() + ROW_PITCH
            while y < r.bottom() - 1:
                painter.drawLine(QPointF(r.left() + 3, y), QPointF(r.right() - 3, y))
                y += ROW_PITCH
        if self.board.show_heat and self.heat > 0:
            h = self.heat
            color = QColor.fromHsvF(max(0.0, 0.13 - 0.13 * h), 0.95, 1.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(alpha(color, int(40 + 170 * h * h))))
            painter.drawRect(r)
        border = pen(t.select if selected else base, (3.0 if selected or hover else 1.6) / lod)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)
        # Nombre a tamaño de pantalla constante, recortado al ancho del bloque.
        width = r.width() * lod
        if width < 40 or r.height() * lod < 22:
            return
        painter.save()
        painter.translate(r.left(), r.top())
        painter.scale(1 / lod, 1 / lod)
        title_font = _font(10.5, bold=True)
        sub_font = _font(8.5)
        fm, fs = QFontMetricsF(title_font), QFontMetricsF(sub_font)
        pad = 8.0
        title = fm.elidedText(self.tile.title, Qt.TextElideMode.ElideRight, width - 2 * pad)
        lines = [(title, title_font, fm, t.text)]
        if r.height() * lod > fm.height() + fs.height() + 2 * pad:
            sub = fs.elidedText(self.subtitle, Qt.TextElideMode.ElideRight, width - 2 * pad)
            lines.append((sub, sub_font, fs, t.muted))
        box_w = max(m.horizontalAdvance(text) for text, _, m, _ in lines) + 2 * pad
        box_h = sum(m.height() for _, _, m, _ in lines) + pad
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(alpha(t.surface, 225)))
        painter.drawRoundedRect(QRectF(4, 4, box_w, box_h), 5, 5)
        y = 4 + pad / 2
        for text, font, m, ink in lines:
            painter.setFont(font)
            painter.setPen(pen(ink, 1))
            painter.drawText(QPointF(4 + pad, y + m.ascent()), text)
            y += m.height()
        painter.restore()


@dataclass(frozen=True)
class BlockHit:
    """Un bloque del plano bajo el ratón."""

    item: BlockItem

    @property
    def key(self) -> str:
        return self.item.tile.key


# ------------------------------------------------------------ rejilla de bits
TILE_W = 46.0
TILE_H = 24.0
TILE_GAP = 6.0
GRID_LEFT = 74.0
GRID_TOP = 58.0
MARK_W = 8.0
"""Ancho reservado a la marca de la segunda salida de un recuadro de la rejilla."""
LABEL_EVERY_COLUMN = 40
"""Con hasta estas columnas se rotula cada bit; con más, uno de cada cuatro."""


class TileItem(CellItem):
    """Una celda en la rejilla de bits: su tipo, pintado con el valor de su salida."""

    def __init__(self, binding: Binding, title: str, board: CircuitScene) -> None:
        super().__init__(binding, title, board)
        self.outputs = list(binding.circuit.outputs.values())

    def boundingRect(self) -> QRectF:  # noqa: N802 - API de Qt
        return QRectF(-3, -3, TILE_W + 6, TILE_H + 6)

    def transistor_rect(self, index: int) -> QRectF:
        return QRectF(0, 0, TILE_W, TILE_H)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        t = th.current()
        if self.board.values is None:
            return
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        value = self.value_fn()
        main = value(self.outputs[0]) if self.outputs else Logic.X
        rect = QRectF(0, 0, TILE_W, TILE_H)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, lod > 0.3)
        color = t.logic(main)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(alpha(color, 200 if main is Logic.ONE else 70)))
        painter.drawRoundedRect(rect, 4, 4)
        flash = self.binding.path in self.board.flash_cells
        hover = self.board.hover_item is self
        selected = self.board.selected_item is self
        if flash:
            painter.setPen(pen(t.halo, 3.0))
        elif selected or hover:
            painter.setPen(pen(t.select, 2.2))
        else:
            painter.setPen(pen(alpha(t.ink, 90), 0.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)
        # Segunda salida (por ejemplo, el acarreo de un FA): una marca a la derecha.
        for k, node in enumerate(self.outputs[1:3]):
            v = value(node)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(t.logic(v)))
            painter.drawRect(QRectF(TILE_W - 7, 3 + k * 9, 4, 7))
        if TILE_W * lod > 26:
            painter.setFont(SMALL_FONT)
            painter.setPen(pen(t.paper if main is Logic.ONE else t.text, 1))
            painter.drawText(
                rect.adjusted(2, 0, -MARK_W, 0),
                Qt.AlignmentFlag.AlignCenter,
                self.binding.circuit.name,
            )
        self._paint_heat(painter, rect)

    def hit(self, pos: QPointF) -> Hit | None:
        return Hit(self, "cell")


class GridFrameItem(QGraphicsItem):
    """Ejes de la rejilla: el número de bit arriba y el nivel lógico a la izquierda."""

    def __init__(self, columns: int, row_y: Sequence[float], width: float, height: float):
        super().__init__()
        self.columns = columns
        self.row_y = list(row_y)
        self.width = width
        self.height = height
        self.setZValue(-1)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(0, 0, self.width, self.height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        t = th.current()
        painter.setPen(pen(t.frame, 1.2))
        painter.setBrush(QBrush(QColor(t.paper)))
        painter.drawRoundedRect(QRectF(0, 0, self.width, self.height), 10, 10)
        painter.setFont(SMALL_FONT)
        painter.setPen(pen(t.muted, 1))
        step = 1 if self.columns <= LABEL_EVERY_COLUMN else 4
        for col in range(0, self.columns, step):
            x = GRID_LEFT + (self.columns - 1 - col) * (TILE_W + TILE_GAP)
            painter.drawText(
                QRectF(x, GRID_TOP - 20, TILE_W, 14), Qt.AlignmentFlag.AlignCenter, f"bit {col}"
            )
        for row, y in enumerate(self.row_y):
            painter.drawText(
                QRectF(6, y, GRID_LEFT - 12, TILE_H),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                f"nivel {row}",
            )
        painter.setFont(TITLE_FONT)
        painter.setPen(pen(t.ink, 1))
        painter.drawText(QPointF(16, 24), "Rejilla de bits: columna = bit · fila = nivel lógico")


# ------------------------------------------------------------------- escena
# ---------------------------------------------------------------- compuertas
def wire_pen(t: th.Theme, v: Logic) -> QPen:
    """Cable con su valor: un 1 se dibuja grueso para que se vea de lejos."""
    width = 2.8 if v is Logic.ONE else 1.6
    style = Qt.PenStyle.DashLine if v in (Logic.X, Logic.Z) else Qt.PenStyle.SolidLine
    return pen(t.logic(v), width, style)


class GateItem(CellItem):
    """Una celda pintada como compuertas lógicas, una por etapa CMOS."""

    def __init__(self, binding: Binding, title: str, board: CircuitScene) -> None:
        super().__init__(binding, title, board)
        self.gates = gates.cell_gates(binding.netlist)
        self.geo: gates.GateDiagram = gates.layout(binding.netlist, measure)

    def boundingRect(self) -> QRectF:  # noqa: N802 - API de Qt
        return QRectF(-4, -4, self.geo.width + 8.0, self.geo.height + 8.0)

    def _gate_rect(self, b: gates.Box) -> QRectF:
        right = b.out[0]
        return QRectF(
            b.x - gates.STUB, b.y - GATE_MARGIN, right - b.x + gates.STUB, b.h + 2 * GATE_MARGIN
        )

    def transistor_rect(self, index: int) -> QRectF:
        for b in self.geo.boxes:
            if index in b.gate.transistors:
                return self._gate_rect(b)
        return QRectF()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        t = th.current()
        if self.board.values is None:
            return
        rect = QRectF(0, 0, self.geo.width, self.geo.height)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(pen(t.frame, 1.2))
        painter.setBrush(QBrush(QColor(t.paper)))
        painter.drawRoundedRect(rect, 10, 10)
        if self.board.selected_item is self and self.board.selected_transistor is None:
            painter.setPen(pen(t.select, 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 12, 12)
        value = self.value_fn()
        hover_node = self.board.hover_node
        local_hover = self.local_node(hover_node) if hover_node is not None else None
        focus = self.board.step_filter
        toggled = self.board.toggled_nodes if self.board.show_toggles else set()

        def lit_node(n: int) -> bool:
            return focus is None or n in focus[1]

        def lit_gate(g: gates.Gate) -> bool:
            return focus is None or set(g.transistors) <= focus[0]

        painter.setFont(TITLE_FONT)
        painter.setPen(pen(t.ink, 1))
        painter.drawText(QPointF(gates.PAD, gates.PAD + 6), self.title)

        for w in self.geo.wires:
            painter.setOpacity(1.0 if lit_node(w.node) else DIM_OPACITY)
            a, b = QPointF(w.x1, w.y1), QPointF(w.x2, w.y2)
            if local_hover is not None and w.node == local_hover:
                painter.setPen(pen(alpha(t.halo, 170), 9))
                painter.drawLine(a, b)
            elif toggled and self.node_id(w.node) in toggled:
                painter.setPen(pen(alpha("#ff9f1a", 110), 7))
                painter.drawLine(a, b)
            painter.setPen(wire_pen(t, value(w.node)))
            painter.drawLine(a, b)
        painter.setPen(Qt.PenStyle.NoPen)
        for d in self.geo.dots:
            painter.setOpacity(1.0 if lit_node(d.node) else DIM_OPACITY)
            painter.setBrush(QBrush(t.logic(value(d.node))))
            painter.drawEllipse(QPointF(d.x, d.y), 3.4, 3.4)
        for k, box in enumerate(self.geo.boxes):
            painter.setOpacity(1.0 if lit_gate(box.gate) else DIM_OPACITY)
            self._paint_gate(painter, t, k, box, value)
        painter.setOpacity(1.0)
        for p in self.geo.ports:
            label(
                painter,
                t,
                p.name,
                p.x + 6 if p.output else p.x - 6,
                p.y,
                "left" if p.output else "right",
                value(p.node),
                "pin_out" if p.output else "pin_in",
                p.node == local_hover,
                clickable=self.node_id(p.node) in self.board.clickable_nodes,
            )
        self._paint_heat(painter, rect)

    def _paint_gate(
        self,
        painter: QPainter,
        t: th.Theme,
        k: int,
        box: gates.Box,
        value: Callable[[int], Logic],
    ) -> None:
        g = box.gate
        hov = self.board.hover_item is self and self.board.hover_element == g.element
        sel = (
            self.board.selected_item is self
            and self.board.selected_transistor is not None
            and self.board.selected_transistor in g.transistors
        )
        if hov or sel:
            painter.setPen(pen(t.select, 1.6) if sel else Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(alpha(t.select, 60 if sel else 34)))
            painter.drawRoundedRect(self._gate_rect(box).adjusted(-4, -4, 4, 4), 7.5, 7.5)
        # Pines de entrada y de salida, con el valor de su cable.
        for p, n in enumerate(g.inputs):
            px, py = box.pin(p)
            reach = box.x + (5.0 if g.kind == "NOR" else 0.0)
            painter.setPen(wire_pen(t, value(n)))
            painter.drawLine(QPointF(px, py), QPointF(reach, py))
        out = value(g.output) if g.output >= 0 else Logic.X
        ox, oy = box.out
        body_right = box.x + box.w + (2 * gates.BUBBLE if g.inverting else 0.0)
        painter.setPen(wire_pen(t, out))
        painter.drawLine(QPointF(body_right, oy), QPointF(ox, oy))
        # Cuerpo.
        x, y, w, h = box.x, box.y, box.w, box.h
        path = QPainterPath()
        if g.kind == "INV":
            path.moveTo(x, y)
            path.lineTo(x + w, y + h / 2)
            path.lineTo(x, y + h)
            path.closeSubpath()
        elif g.kind == "NAND":
            path.moveTo(x, y)
            path.lineTo(x + w - h / 2, y)
            path.arcTo(QRectF(x + w - h, y, h, h), 90, -180)
            path.lineTo(x, y + h)
            path.closeSubpath()
        elif g.kind == "NOR":
            path.moveTo(x, y)
            path.quadTo(x + w * 0.6, y, x + w, y + h / 2)
            path.quadTo(x + w * 0.6, y + h, x, y + h)
            path.quadTo(x + w * 0.28, y + h / 2, x, y)
        else:
            path.addRoundedRect(QRectF(x, y, w, h), 7, 7)
        painter.setBrush(QBrush(QColor(t.surface)))
        border = pen(t.ink, 1.7)
        if g.kind == "RED":
            border.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(border)
        painter.drawPath(path)
        if g.inverting:
            painter.setBrush(QBrush(QColor(t.surface)))
            painter.drawEllipse(
                QPointF(x + w + gates.BUBBLE, y + h / 2), gates.BUBBLE, gates.BUBBLE
            )
        # Texto dentro de las compuertas de recuadro.
        if g.kind in ("AOI", "OAI", "COMPLEJA", "RED"):
            painter.setFont(LABEL_FONT)
            painter.setPen(pen(t.ink, 1))
            painter.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, g.expression)
            painter.setFont(SMALL_FONT)
            painter.setPen(pen(t.muted, 1))
            painter.drawText(QPointF(x + 2, y - 4), gates.symbol_name(g.kind))
        elif g.kind == "TG":
            painter.setFont(TITLE_FONT)
            painter.setPen(pen(t.ink, 1))
            painter.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, "TG")
            painter.setFont(PIN_FONT)
            painter.setPen(pen(t.muted, 1))
            for p, name in enumerate(g.pins):
                px, py = box.pin(p)
                painter.drawText(QPointF(x + 3, py + 3), name)
        # Debajo, la fórmula (las compuertas de recuadro ya la llevan dentro: solo la salida).
        name = self.binding.circuit.label(g.output) if g.output >= 0 else ""
        boxed = g.kind in ("AOI", "OAI", "COMPLEJA", "RED")
        caption = f"→ {name}" if boxed else f"{name} = {g.expression}" if name else ""
        painter.setFont(SMALL_FONT)
        painter.setPen(pen(t.muted, 1))
        fm = QFontMetricsF(SMALL_FONT)
        cx = x + w / 2 - fm.horizontalAdvance(caption) / 2
        painter.drawText(QPointF(max(x - gates.STUB, cx), y + h + 13), caption)

    def hit(self, pos: QPointF) -> Hit | None:
        x, y = pos.x(), pos.y()
        for p in self.geo.ports:
            w = measure(p.name) + 24
            x0 = p.x + 2 if p.output else p.x - 6 - w
            if x0 <= x <= x0 + w and abs(y - p.y) <= 10:
                real = self.node_id(p.node)
                if real in self.board.clickable_nodes:
                    return Hit(self, "input", node=real, port=self.input_port(p.node))
                return Hit(self, "node", node=real)
        for b in self.geo.boxes:
            if self._gate_rect(b).contains(pos):
                out = self.node_id(b.gate.output) if b.gate.output >= 0 else None
                return Hit(self, "gate", node=out, element=b.gate.element)
        best: tuple[float, int] | None = None
        for s in self.geo.wires:
            dist = _dist(x, y, s.x1, s.y1, s.x2, s.y2)
            if dist <= 5 and (best is None or dist < best[0]):
                best = (dist, s.node)
        if best is not None:
            return Hit(self, "node", node=self.node_id(best[1]))
        return Hit(self, "cell")

    def gate_center(self, element: int) -> QPointF:
        """Centro de la compuerta del elemento ``element``, en la escena (para pruebas)."""
        for b in self.geo.boxes:
            if b.gate.element == element:
                return self.mapToScene(QPointF(b.x + b.w / 2, b.y + b.h / 2))
        return self.mapToScene(QPointF())


class CircuitScene(QGraphicsScene):
    """Escena con una o varias celdas y el estado de su motor."""

    hovered = Signal(object)
    """Se emite con el :class:`Hit` bajo el ratón (o None)."""

    def __init__(self) -> None:
        super().__init__()
        self.values: ValueReader | None = None
        self.cells: list[CellItem] = []
        self.mode = "schematic"
        self.hover_node: int | None = None
        self.hover_item: CellItem | None = None
        self.hover_transistor: int | None = None
        self.hover_element: int | None = None
        self.hover_block: BlockItem | None = None
        self.selected_block: BlockItem | None = None
        self.blocks: list[BlockItem] = []
        self.pair = False
        """True si se dibuja una celda dos veces: su esquema y su silicio, lado a lado."""
        self.flash_cells: frozenset[str] = frozenset()
        """Celdas de la rejilla que cambiaron en el instante mostrado de la propagación."""
        self.selected_item: CellItem | None = None
        self.selected_transistor: int | None = None
        self.clickable_nodes: set[int] = set()
        """Nodos reales que se pueden cambiar con un clic (las entradas de la celda)."""
        self.show_paths = True
        self.show_heat = False
        self.show_toggles = False
        self.color_by_value = False
        self.visible_layers: set[str] = set(TOGGLE_LAYERS)
        self.step_filter: tuple[frozenset[int], frozenset[int]] | None = None
        """Paso a paso del esquema: (transistores, nodos) que se resaltan; el resto se atenúa."""
        """Capas del silicio que se dibujan (se eligen con las casillas de la pestaña)."""
        self.toggled_nodes: set[int] = set()
        self.flows: dict[CellItem, set[int]] = {}
        self.flow_phase = 0.0
        self._flow_until = 0.0
        self._by_node: dict[int, list[CellItem]] = {}
        self._timer = QTimer()
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self.apply_theme()

    def apply_theme(self) -> None:
        t = th.current()
        bg = silicon_background(t) if self.mode == "silicon" else t.window
        if (self.mode == "silicon" and len(self.cells) > 1) or self.mode == "floorplan":
            bg = "#08090b" if t.dark else "#d9dce3"
        self.setBackgroundBrush(QBrush(QColor(bg)))
        self.update()

    # ----------------------------------------------------------- contenido
    @property
    def inputs_clickable(self) -> bool:
        return bool(self.clickable_nodes)

    def _reset(self, values: ValueReader, clickable: set[int], mode: str) -> None:
        self.clear()
        self.cells = []
        self.flows = {}
        self.hover_node = self.hover_item = self.hover_transistor = None
        self.hover_element = None
        self.hover_block = self.selected_block = None
        self.blocks = []
        self.pair = False
        self.flash_cells = frozenset()
        self.selected_item = self.selected_transistor = None
        self.values = values
        self.clickable_nodes = set(clickable)
        self.mode = mode

    def _index(self) -> None:
        self._by_node = {}
        for item in self.cells:
            for n in item.real_nodes:
                self._by_node.setdefault(n, []).append(item)
        margin = 60.0 if self.mode == "silicon" and len(self.cells) > 1 else 40.0
        self.setSceneRect(self.itemsBoundingRect().adjusted(-margin, -margin, margin, margin))
        self.apply_theme()

    def show_schematics(
        self,
        cells: Sequence[tuple[Binding, str]],
        values: ValueReader,
        *,
        clickable: set[int] | None = None,
    ) -> None:
        """Dibuja ``cells`` (enlace, título) como esquemas, en filas."""
        self._reset(values, clickable or set(), "schematic")
        items = [SchematicItem(b, title, self) for b, title in cells]
        area = sum(i.geo.width * i.geo.height for i in items)
        max_w = max([i.geo.width for i in items] + [math.sqrt(area) * 1.5]) if items else 0
        x = y = row_h = 0.0
        for item in items:
            if x > 0 and x + item.geo.width > max_w:
                x, y, row_h = 0.0, y + row_h + 26, 0.0
            item.setPos(x, y)
            self.addItem(item)
            x += item.geo.width + 26
            row_h = max(row_h, item.geo.height)
        self.cells = list(items)
        self._index()

    def show_grid(
        self,
        slots: Sequence[tuple[Binding, int, int, int]],
        columns: int,
        values: ValueReader,
    ) -> None:
        """Dibuja la rejilla de bits de un bloque: (enlace, columna, fila, sub) por celda.

        El bit 0 queda a la derecha, como al escribir un número.
        """
        self._reset(values, set(), "gates")
        rows: dict[int, int] = {}
        for _, _, row, sub in slots:
            rows[row] = max(rows.get(row, 0), sub + 1)
        row_y: list[float] = []
        y = GRID_TOP
        for row in range(max(rows, default=-1) + 1):
            row_y.append(y)
            y += rows.get(row, 1) * (TILE_H + 3) + TILE_GAP
        width = GRID_LEFT + columns * (TILE_W + TILE_GAP) + 16
        self.addItem(GridFrameItem(columns, row_y, width, y + 12))
        items: list[CellItem] = []
        for binding, col, row, sub in slots:
            item = TileItem(binding, binding.path, self)
            x = GRID_LEFT + (columns - 1 - col) * (TILE_W + TILE_GAP)
            item.setPos(x, row_y[row] + sub * (TILE_H + 3))
            self.addItem(item)
            items.append(item)
        self.cells = items
        self._index()

    def show_pair(
        self,
        binding: Binding,
        title: str,
        values: ValueReader,
        *,
        clickable: set[int] | None = None,
    ) -> None:
        """Una celda dos veces, lado a lado: su esquema y su silicio, enlazados.

        Pasar el ratón por un transistor lo resalta en los dos dibujos.
        """
        self._reset(values, clickable or set(), "silicon")
        self.pair = True
        schematic = SchematicItem(binding, title, self)
        chip = SiliconItem(binding, title, self)
        chip.pins_outside = True
        scale = min(2.4, max(0.6, schematic.geo.height * 0.82 / max(1.0, chip.lay.height)))
        chip.setScale(scale)
        schematic.setPos(0, 0)
        chip.setPos(
            schematic.geo.width + PAIR_GAP,
            (schematic.geo.height - chip.lay.height * scale) / 2,
        )
        for item in (schematic, chip):
            self.addItem(item)
        self.cells = [schematic, chip]
        self._index()

    def show_floorplan(
        self,
        tiles: Sequence[floorplan.Tile],
        subtitles: Sequence[str],
        values: ValueReader,
        die: tuple[str, str],
    ) -> None:
        """Dibuja el plano: un rectángulo por bloque, de área proporcional a su peso."""
        self._reset(values, set(), "floorplan")
        for tile, sub, (x, y, w, h) in zip(
            tiles, subtitles, floorplan.plan(tiles, CHIP_W, CHIP_H, BLOCK_GAP), strict=True
        ):
            item = BlockItem(tile, QRectF(x, y, w, h), sub, self)
            self.addItem(item)
            self.blocks.append(item)
        frame = QRectF(0, 0, CHIP_W, CHIP_H).adjusted(-40, -40, 40, 40)
        self.addItem(FrameItem(frame, die[0], die[1], die=True))
        self._index()

    def select_block(self, item: BlockItem | None) -> None:
        old, self.selected_block = self.selected_block, item
        for i in {old, item}:
            if i is not None:
                i.update()

    def set_block_heat(self, heat_of: Callable[[BlockItem], float] | None) -> None:
        """Actividad (0–1) de cada bloque del plano; None la apaga."""
        self.show_heat = heat_of is not None
        for item in self.blocks:
            item.heat = heat_of(item) if heat_of is not None else 0.0
            item.update()

    def show_gates(
        self,
        cells: Sequence[tuple[Binding, str]],
        values: ValueReader,
        *,
        clickable: set[int] | None = None,
    ) -> None:
        """Dibuja ``cells`` (enlace, título) como compuertas lógicas, en filas."""
        self._reset(values, clickable or set(), "gates")
        items = [GateItem(b, title, self) for b, title in cells]
        area = sum(i.geo.width * i.geo.height for i in items)
        max_w = max([i.geo.width for i in items] + [math.sqrt(area) * 1.5]) if items else 0
        x = y = row_h = 0.0
        for item in items:
            if x > 0 and x + item.geo.width > max_w:
                x, y, row_h = 0.0, y + row_h + 26, 0.0
            item.setPos(x, y)
            self.addItem(item)
            x += item.geo.width + 26
            row_h = max(row_h, item.geo.height)
        self.cells = list(items)
        self._index()

    def show_silicon(
        self,
        cells: Sequence[tuple[Binding, str]],
        values: ValueReader,
        *,
        clickable: set[int] | None = None,
    ) -> None:
        """Dibuja unas pocas celdas como layout, en filas de celdas estándar.

        Un bloque o el chip entero no se dibujan así sino con su plano
        (:meth:`show_floorplan`); una sola celda, junto a su esquema (:meth:`show_pair`).
        """
        self._reset(values, clickable or set(), "silicon")
        items = [SiliconItem(b, title, self) for b, title in cells]
        _rows(items)
        for item in items:
            self.addItem(item)
        self.cells = list(items)
        self._index()

    @property
    def flowing(self) -> int:
        """Transistores que conducen en el dibujo actual."""
        if self.values is None:
            return 0
        values = self.values
        return sum(
            1
            for item in self.cells
            for t in item.binding.transistors
            if values.conduction(t) is Conduction.ON
        )

    def refresh(self) -> None:
        """Repinta con los valores actuales del motor."""
        for item in self.cells:
            item.update()

    def set_heat(self, heat_of: Callable[[CellItem], float] | None) -> None:
        """Intensidad de actividad (0–1) de cada celda; None la apaga."""
        self.show_heat = heat_of is not None
        for item in self.cells:
            item.heat = heat_of(item) if heat_of is not None else 0.0
            item.update()

    # --------------------------------------------------------------- ratón
    def set_hover(self, hit: Hit | None) -> None:
        node = hit.node if hit is not None and hit.kind in ("node", "input") else None
        item = hit.item if hit is not None else None
        transistor = hit.transistor if hit is not None else None
        element = hit.element if hit is not None else None
        if (node, item, transistor, element) == (
            self.hover_node,
            self.hover_item,
            self.hover_transistor,
            self.hover_element,
        ):
            return
        touched: set[CellItem] = set()
        for n in (self.hover_node, node):
            if n is not None:
                touched |= set(self._by_node.get(n, []))
        touched |= {i for i in (self.hover_item, item) if i is not None}
        if self.pair:
            touched |= set(self.cells)
        self.hover_node, self.hover_item, self.hover_transistor = node, item, transistor
        self.hover_element = element
        for i in touched:
            i.update()
        self.hovered.emit(hit)

    def select(self, item: CellItem | None, transistor: int | None) -> None:
        old = self.selected_item
        self.selected_item, self.selected_transistor = item, transistor
        for i in {old, item} | (set(self.cells) if self.pair else set()):
            if i is not None:
                i.update()

    def items_with_node(self, node: int) -> list[CellItem]:
        return list(self._by_node.get(node, []))

    # -------------------------------------------------------- transitorio
    def start_flow(self, flows: dict[CellItem, set[int]], seconds: float = 1.6) -> None:
        """Anima los transistores que cargaron o descargaron una salida."""
        self.flows = {k: v for k, v in flows.items() if v}
        if not self.flows:
            return
        self._flow_until = time.monotonic() + seconds
        self._timer.start()

    def _tick(self) -> None:
        self.flow_phase = (self.flow_phase + 0.06) % 1.0
        if time.monotonic() > self._flow_until:
            self._timer.stop()
            done, self.flows = self.flows, {}
            for item in done:
                item.update()
            return
        for item in self.flows:
            item.update()


def _rows(items: Sequence[SiliconItem], target: float | None = None) -> tuple[float, float]:
    """Coloca ``items`` en filas de celdas estándar de ancho ``target`` (por defecto, una
    proporción cercana a 1,5 : 1); las filas impares se reflejan para compartir el riel
    con la fila vecina, como en un chip. Devuelve el ancho y el alto del bloque."""
    if not items:
        return 0.0, 0.0
    h = max(i.lay.height for i in items)
    total = sum(i.lay.width for i in items)
    widest = max(i.lay.width for i in items)
    if target is None:
        target = math.sqrt(total * h * 1.5)
    target = max(widest, target)
    x = 0.0
    row = 0
    width = 0.0
    for item in items:
        if x > 0 and x + item.lay.width > target + 0.5:
            row += 1
            x = 0.0
        item.flipped = row % 2 == 1
        item.setPos(x, row * h)
        x += item.lay.width
        width = max(width, x)
    return width, (row + 1) * h


# ------------------------------------------------------------------- vista
class CanvasView(QGraphicsView):
    """Vista con zoom (rueda, teclas o botones), arrastre para moverse y clic para elegir.

    Un clic es soltar el botón sin haber arrastrado; así el arrastre mueve la vista en
    cualquier punto y el clic sigue siendo preciso.
    """

    clicked = Signal(object)
    """Se emite con el :class:`Hit` del clic (o None en el fondo)."""
    double_clicked = Signal(object)
    zoom_changed = Signal(float)

    STEP = 1.25
    MIN, MAX = 0.004, 12.0

    def __init__(self, scene: CircuitScene) -> None:
        super().__init__(scene)
        self.board = scene
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._press: QPointF | None = None
        self._anim: QVariantAnimation | None = None
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        scene.hovered.connect(self._on_hover)

    # ---------------------------------------------------------------- zoom
    @property
    def zoom(self) -> float:
        return self.transform().m11()

    def _scale_to(self, factor: float) -> None:
        target = max(self.MIN, min(self.MAX, self.zoom * factor))
        f = target / self.zoom
        self.scale(f, f)
        self.zoom_changed.emit(self.zoom)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - API de Qt
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta:
            self._scale_to(self.STEP ** (delta / 120))

    def zoom_in(self) -> None:
        self._animate_zoom(self.STEP * self.STEP)

    def zoom_out(self) -> None:
        self._animate_zoom(1 / (self.STEP * self.STEP))

    def actual_size(self) -> None:
        """Zoom 1:1."""
        self._animate_zoom(1 / self.zoom)

    def _animate_zoom(self, factor: float) -> None:
        start = self.zoom
        end = max(self.MIN, min(self.MAX, start * factor))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        anim = QVariantAnimation(self)
        anim.setDuration(170)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.valueChanged.connect(self._set_zoom)
        anim.finished.connect(self._restore_anchor)
        self._anim = anim
        anim.start()

    def _set_zoom(self, value: object) -> None:
        z = float(value)  # type: ignore[arg-type]
        self.scale(z / self.zoom, z / self.zoom)
        self.zoom_changed.emit(self.zoom)

    def _restore_anchor(self) -> None:
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def fit(self, rect: QRectF | None = None, max_zoom: float = 1.6) -> None:
        """Ajusta el zoom para ver ``rect`` (o todo), sin agrandar más de ``max_zoom``."""
        target = rect if rect is not None else self.scene().sceneRect()
        if target.isEmpty():
            return
        self.fitInView(target, Qt.AspectRatioMode.KeepAspectRatio)
        if self.zoom > max_zoom:
            self.setTransform(QTransform.fromScale(max_zoom, max_zoom))
            self.centerOn(target.center())
        self.zoom_changed.emit(self.zoom)

    def focus_on(self, rect: QRectF, max_zoom: float = 2.2) -> None:
        """Acerca la vista a ``rect`` con una animación corta."""
        start_t = self.transform()
        start_c = self.mapToScene(self.viewport().rect().center())
        self.fit(rect.adjusted(-30, -30, 30, 30), max_zoom)
        end_t = self.transform()
        end_c = rect.center()
        self.setTransform(start_t)
        self.centerOn(start_c)
        anim = QVariantAnimation(self)
        anim.setDuration(260)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        def step(v: object) -> None:
            f = float(v)  # type: ignore[arg-type]
            f = 1 - (1 - f) ** 3
            z0, z1 = start_t.m11(), end_t.m11()
            z = z0 * (z1 / z0) ** f
            self.setTransform(QTransform.fromScale(z, z))
            self.centerOn(start_c + (end_c - start_c) * f)
            self.zoom_changed.emit(self.zoom)

        anim.valueChanged.connect(step)
        self._anim = anim
        anim.start()

    # ---------------------------------------------------------------- ratón
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        press, self._press = self._press, None
        if event.button() != Qt.MouseButton.LeftButton or press is None:
            return
        if (event.position() - press).manhattanLength() <= 4:
            self.clicked.emit(self.hit_at(event.position()))
        self._update_cursor(self._clickable(self.hit_at(event.position())))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.hit_at(event.position()))

    def hit_at(self, pos: QPointF) -> Hit | BlockHit | None:
        scene_pos = self.mapToScene(pos.toPoint())
        for item in self.scene().items(scene_pos):
            if isinstance(item, CellItem):
                return item.hit(item.mapFromScene(scene_pos))
            if isinstance(item, BlockItem) and item.rect.contains(scene_pos):
                return BlockHit(item)
        return None

    def _clickable(self, hit: Hit | BlockHit | None) -> bool:
        if hit is None:
            return False
        if isinstance(hit, BlockHit):
            return True
        if hit.kind in ("transistor", "input"):
            return True
        return hit.kind == "cell" and len(self.board.cells) > 1 and not self.board.pair

    def _on_hover(self, hit: Hit | None) -> None:
        if self._press is None:
            self._update_cursor(self._clickable(hit))

    def _update_cursor(self, clickable: bool) -> None:
        shape = Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.OpenHandCursor
        self.viewport().setCursor(shape)


__all__ = [
    "LAYER_COLOR",
    "LAYER_NAMES",
    "CanvasView",
    "CellItem",
    "CircuitScene",
    "FrameItem",
    "Hit",
    "SchematicItem",
    "SiliconItem",
    "label",
    "logic_text",
    "measure",
    "pen",
]
