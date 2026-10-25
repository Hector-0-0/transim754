"""Vista de transistores: dibuja celdas primitivas con el estado real de cada transistor.

Cada transistor se dibuja con su símbolo (compuerta, fuente, drenador y canal). El color
del canal indica si conduce, según el valor de su compuerta en el motor; los terminales
muestran el nodo al que se conectan y su valor. Dentro de cada celda los pMOS van
arriba, junto al riel VDD, y los nMOS abajo, junto a GND, como en el esquema de una
compuerta CMOS. Un bloque (por ejemplo, el desempaquetado) se dibuja como el conjunto de
sus celdas en un mismo plano, cada una en su recuadro.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from transim.core.netlist import Instance, Netlist
from transim.core.node import Node, NodeKind
from transim.core.signals import Logic
from transim.core.transistor import Conduction, Transistor, TransistorType

PER_ROW = 7
"""Transistores por fila dentro de una celda."""

ANIMATED_MAX = 400
"""Con más canales conduciendo que esto no se anima el flujo (rendimiento)."""

PAPER = QColor("#ffffff")
INK = QColor("#202124")
FRAME = QColor("#c4c7cc")
RAIL = QColor("#5f6368")

COLORS = {
    Logic.ZERO: QColor("#1a5fd0"),
    Logic.ONE: QColor("#c62828"),
    Logic.X: QColor("#c77700"),
    Logic.Z: QColor("#80868b"),
}
"""Color de cada valor lógico de nodo."""

CHANNEL = {
    Conduction.ON: QColor("#1e8e3e"),
    Conduction.OFF: QColor("#bdc1c6"),
    Conduction.UNKNOWN: QColor("#c77700"),
}
"""Color del canal según conduzca, no conduzca o sea incierto."""

ValueOf = Callable[[Node], Logic]
ConductionOf = Callable[[Transistor], Conduction]

_FONT = QFont("Sans Serif", 9)
_TITLE_FONT = QFont("Sans Serif", 10, QFont.Weight.Bold)


@dataclass
class CellSpec:
    """Lo necesario para dibujar una celda.

    Attributes:
        title: texto del recuadro.
        transistors: transistores de la celda.
        names: nombre que se muestra para cada nodo (por id). Los nodos que no figuran se
            muestran con su nombre sin el ``prefix``.
        prefix: prefijo de instancia que se quita de los nombres (``"fa3."``).
    """

    title: str
    transistors: Sequence[Transistor]
    names: dict[int, str] = field(default_factory=dict)
    prefix: str = ""

    def name(self, node: Node) -> str:
        """Nombre corto de ``node`` dentro de la celda."""
        if node.kind is NodeKind.VDD:
            return "VDD"
        if node.kind is NodeKind.GND:
            return "GND"
        if node.id in self.names:
            return self.names[node.id]
        if self.prefix and node.name.startswith(self.prefix):
            return node.name[len(self.prefix) :]
        return node.name


def spec_for_cell(cell: Netlist) -> CellSpec:
    """Celda de la biblioteca: sus nodos ya se llaman como sus puertos."""
    return CellSpec(f"{cell.name} · {len(cell.transistors)} transistores", cell.transistors)


def spec_for_instance(inst: Instance, base: str = "") -> CellSpec:
    """Celda instanciada: los nodos de sus puertos se muestran con el nombre del puerto
    (``a``, ``y``…) y los internos sin el prefijo de la instancia. ``base`` se quita del
    título (por ejemplo, el bloque que se está dibujando)."""
    names = {node.id: port for port, node in inst.ports.items()}
    path = inst.path[len(base) :] if base and inst.path.startswith(base) else inst.path
    return CellSpec(f"{path} · {inst.definition.name}", inst.transistors, names, f"{inst.path}.")


def _short(t: Transistor, spec: CellSpec) -> str:
    """Nombre del transistor sin el prefijo de la instancia."""
    return t.name[len(spec.prefix) :] if spec.prefix and t.name.startswith(spec.prefix) else t.name


def _text_width(text: str, font: QFont = _FONT) -> float:
    return QFontMetricsF(font).horizontalAdvance(text)


def _v(value: Logic) -> str:
    return {Logic.ZERO: "0", Logic.ONE: "1", Logic.X: "X", Logic.Z: "Z"}[value]


@dataclass
class _Geometry:
    """Medidas de los transistores de una celda (todas las columnas iguales)."""

    lead: float  # largo del terminal de compuerta (cabe su etiqueta encima)
    label: float  # ancho de las etiquetas de fuente y drenador
    per_row: int
    p_rows: int
    n_rows: int

    SLOT_H = 96.0
    TITLE_H = 30.0
    GAP = 26.0
    PAD = 14.0

    @property
    def slot_w(self) -> float:
        return self.lead + 34 + 22 + self.label + 20

    @property
    def width(self) -> float:
        return self.slot_w * self.per_row + 2 * self.PAD

    @property
    def height(self) -> float:
        rows = self.p_rows + self.n_rows
        return self.TITLE_H + 24 + self.SLOT_H * rows + self.GAP + 24


class CellScene(QGraphicsScene):
    """Escena con los transistores de una o varias celdas y su estado."""

    def __init__(self) -> None:
        super().__init__()
        self.setBackgroundBrush(QBrush(PAPER))
        self._conducting = 0
        self._flows: list[QGraphicsLineItem] = []
        self._offset = 0.0
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(90)

    @property
    def flowing(self) -> int:
        """Transistores que conducen en el dibujo actual."""
        return self._conducting

    def draw(
        self,
        transistors: Sequence[Transistor],
        value_of: ValueOf,
        conduction_of: ConductionOf,
        prefix: str = "",
        title: str = "",
    ) -> None:
        """Dibuja una sola celda (compatibilidad con la interfaz anterior)."""
        self.draw_cells([CellSpec(title, transistors, prefix=prefix)], value_of, conduction_of)

    def draw_cells(
        self, cells: Sequence[CellSpec], value_of: ValueOf, conduction_of: ConductionOf
    ) -> None:
        """Dibuja ``cells`` en un mismo plano, cada una en su recuadro, en filas."""
        self.clear()
        self._flows = []
        self._conducting = 0
        frames = [(spec, self._geometry(spec, value_of)) for spec in cells]
        if not frames:
            return
        total_area = sum(g.width * g.height for _, g in frames)
        max_width = max(max(g.width for _, g in frames), math.sqrt(total_area) * 1.6)
        x = y = row_h = 0.0
        for spec, geo in frames:
            if x > 0 and x + geo.width > max_width:
                x, y, row_h = 0.0, y + row_h + 30, 0.0
            self._frame(spec, geo, x, y, value_of, conduction_of)
            x += geo.width + 30
            row_h = max(row_h, geo.height)
        animate = self._conducting <= ANIMATED_MAX
        if not animate:
            self._flows = []
        self.setSceneRect(self.itemsBoundingRect().adjusted(-30, -30, 30, 30))

    # ----------------------------------------------------------------- medidas
    @staticmethod
    def _geometry(spec: CellSpec, value_of: ValueOf) -> _Geometry:
        gate = [f"{spec.name(t.gate)} = {_v(value_of(t.gate))}" for t in spec.transistors]
        terms = [
            f"S: {spec.name(n)} = {_v(value_of(n))}"
            for t in spec.transistors
            for n in (t.source, t.drain)
        ]
        n_p = sum(1 for t in spec.transistors if t.kind is TransistorType.PMOS)
        n_n = len(spec.transistors) - n_p
        per_row = max(1, min(PER_ROW, max(n_p, n_n)))
        names = [
            f"{'pMOS' if t.kind is TransistorType.PMOS else 'nMOS'} {_short(t, spec)}"
            for t in spec.transistors
        ]
        lead = max([40.0] + [_text_width(g) + 6 for g in gate + names])
        label = max([30.0] + [_text_width(s) for s in terms])
        return _Geometry(
            lead, label, per_row, max(1, -(-n_p // per_row)), max(1, -(-n_n // per_row))
        )

    # ------------------------------------------------------------------ dibujo
    def _frame(
        self,
        spec: CellSpec,
        geo: _Geometry,
        x0: float,
        y0: float,
        value_of: ValueOf,
        conduction_of: ConductionOf,
    ) -> None:
        box = QGraphicsRectItem(x0, y0, geo.width, geo.height)
        box.setPen(QPen(FRAME, 1.5))
        box.setBrush(QBrush(PAPER))
        self.addItem(box)
        self._text(spec.title, x0 + geo.PAD, y0 + 7, INK, _TITLE_FONT)
        vdd_y = y0 + geo.TITLE_H + 12
        gnd_y = y0 + geo.height - 12
        for rail_y, name in ((vdd_y, "VDD"), (gnd_y, "GND")):
            self.addLine(
                x0 + geo.PAD, rail_y, x0 + geo.width - geo.PAD - 34, rail_y, QPen(RAIL, 2.5)
            )
            self._text(name, x0 + geo.width - geo.PAD - 30, rail_y - 7, RAIL)
        pmos = [t for t in spec.transistors if t.kind is TransistorType.PMOS]
        nmos = [t for t in spec.transistors if t.kind is TransistorType.NMOS]
        top = vdd_y + 12
        bottom_start = top + geo.SLOT_H * geo.p_rows + geo.GAP
        for group, start in ((pmos, top), (nmos, bottom_start)):
            for i, t in enumerate(group):
                sx = x0 + geo.PAD + geo.slot_w * (i % geo.per_row)
                sy = start + geo.SLOT_H * (i // geo.per_row)
                self._transistor(spec, geo, t, sx, sy, value_of, conduction_of(t), vdd_y, gnd_y)

    def _transistor(
        self,
        spec: CellSpec,
        geo: _Geometry,
        t: Transistor,
        x: float,
        y: float,
        value_of: ValueOf,
        state: Conduction,
        vdd_y: float,
        gnd_y: float,
    ) -> None:
        """Símbolo de un transistor en la casilla con esquina superior izquierda (x, y)."""
        pmos = t.kind is TransistorType.PMOS
        mid = y + 44
        plate_x = x + geo.lead + (14 if pmos else 0)
        chan_x = plate_x + 12
        ch_top, ch_bot = mid - 28, mid + 28

        gate_value = value_of(t.gate)
        self.addLine(x, mid, x + geo.lead, mid, QPen(COLORS[gate_value], 3))
        self._text(f"{spec.name(t.gate)} = {_v(gate_value)}", x, mid - 20, COLORS[gate_value])
        if pmos:
            bubble = QGraphicsEllipseItem(x + geo.lead, mid - 6, 12, 12)
            bubble.setPen(QPen(INK, 2))
            bubble.setBrush(QBrush(PAPER))
            self.addItem(bubble)
        self.addLine(plate_x, ch_top + 7, plate_x, ch_bot - 7, QPen(INK, 3))
        self.addLine(chan_x, ch_top, chan_x, ch_bot, QPen(CHANNEL[state], 6))

        for node, end_y, tag in ((t.source, ch_top, "S"), (t.drain, ch_bot, "D")):
            v = value_of(node)
            self.addLine(chan_x, end_y, chan_x + 20, end_y, QPen(COLORS[v], 3))
            self._text(f"{tag}: {spec.name(node)} = {_v(v)}", chan_x + 24, end_y - 7, COLORS[v])
            rails = {NodeKind.VDD: vdd_y, NodeKind.GND: gnd_y}
            if node.kind in rails:
                dotted = QPen(RAIL, 1, Qt.PenStyle.DotLine)
                self.addLine(chan_x + 20, end_y, chan_x + 20, rails[node.kind], dotted)

        kind = "pMOS" if pmos else "nMOS"
        self._text(f"{kind} {_short(t, spec)}", x, mid + 6, RAIL)
        if state is Conduction.ON:
            self._conducting += 1
            flow = QGraphicsLineItem(chan_x, ch_top + 2, chan_x, ch_bot - 2)
            flow.setPen(QPen(PAPER, 2, Qt.PenStyle.DashLine))
            self.addItem(flow)
            self._flows.append(flow)

    def _text(self, text: str, x: float, y: float, color: QColor, font: QFont = _FONT) -> None:
        item = QGraphicsSimpleTextItem(text)
        item.setFont(font)
        item.setBrush(QBrush(color))
        item.setPos(x, y)
        self.addItem(item)

    def _animate(self) -> None:
        """Desplaza el trazo de los canales que conducen: la corriente "fluye"."""
        self._offset = (self._offset + 1.5) % 12
        for flow in self._flows:
            pen = flow.pen()
            pen.setDashOffset(-self._offset)
            flow.setPen(pen)


class ZoomView(QGraphicsView):
    """Vista con zoom (rueda del ratón o botones) y desplazamiento arrastrando."""

    STEP = 1.2

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(PAPER))

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - API de Qt
        self.scale(*(2 * [self.STEP if event.angleDelta().y() > 0 else 1 / self.STEP]))

    def zoom_in(self) -> None:
        """Acerca la vista."""
        self.scale(self.STEP, self.STEP)

    def zoom_out(self) -> None:
        """Aleja la vista."""
        self.scale(1 / self.STEP, 1 / self.STEP)

    def fit(self) -> None:
        """Ajusta el zoom para ver el dibujo completo, sin agrandarlo más que su tamaño."""
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 1.0:
            self.resetTransform()


__all__ = ["CellScene", "CellSpec", "ZoomView", "spec_for_cell", "spec_for_instance"]
