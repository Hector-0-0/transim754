"""Vista de transistores: dibuja una celda primitiva con el estado real de cada transistor.

Cada transistor se dibuja con su símbolo (compuerta, fuente, drenador y canal). El color
del canal indica si conduce, según el valor de su compuerta en el motor; los terminales
muestran el nodo al que se conectan y su valor. Los pMOS van arriba, junto al riel VDD,
y los nMOS abajo, junto a GND, como en el esquema de una compuerta CMOS.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from transim.core.node import Node, NodeKind
from transim.core.signals import Logic
from transim.core.transistor import Conduction, Transistor, TransistorType

PER_ROW = 7
"""Transistores por fila antes de pasar a la siguiente."""

CELL_W, CELL_H = 180.0, 130.0
"""Espacio que ocupa cada símbolo de transistor."""

INSET = 6.0
"""Margen, en píxeles de escena, de la placa de compuerta y de las etiquetas de riel."""

COLORS = {
    Logic.ZERO: QColor("#2f6fd6"),
    Logic.ONE: QColor("#d64545"),
    Logic.X: QColor("#e0a100"),
    Logic.Z: QColor("#9aa0a6"),
}
"""Color de cada valor lógico de nodo."""

CHANNEL = {
    Conduction.ON: QColor("#1f9d55"),
    Conduction.OFF: QColor("#b8bcc2"),
    Conduction.UNKNOWN: QColor("#e0a100"),
}
"""Color del canal según conduzca, no conduzca o sea incierto."""

ValueOf = Callable[[Node], Logic]
ConductionOf = Callable[[Transistor], Conduction]


def _short(node: Node, prefix: str) -> str:
    """Nombre del nodo relativo a la instancia dibujada."""
    if node.kind is NodeKind.VDD:
        return "VDD"
    if node.kind is NodeKind.GND:
        return "GND"
    return node.name[len(prefix) :] if prefix and node.name.startswith(prefix) else node.name


class CellScene(QGraphicsScene):
    """Escena con los transistores de una celda y su estado."""

    def __init__(self) -> None:
        super().__init__()
        self._flows: list[QGraphicsLineItem] = []
        self._offset = 0.0
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(90)

    def draw(
        self,
        transistors: Sequence[Transistor],
        value_of: ValueOf,
        conduction_of: ConductionOf,
        prefix: str = "",
        title: str = "",
    ) -> None:
        """Dibuja ``transistors`` con los valores que dan ``value_of`` y ``conduction_of``.

        ``prefix`` se quita de los nombres de nodo (por ejemplo ``"fa3."``).
        """
        self.clear()
        self._flows = []
        pmos = [t for t in transistors if t.kind is TransistorType.PMOS]
        nmos = [t for t in transistors if t.kind is TransistorType.NMOS]
        p_rows = max(1, -(-len(pmos) // PER_ROW))
        n_rows = max(1, -(-len(nmos) // PER_ROW))
        width = CELL_W * max(1, min(PER_ROW, max(len(pmos), len(nmos))))
        top, gap = 40.0, 50.0
        bottom = top + CELL_H * (p_rows + n_rows) + gap

        if title:
            label = self.addSimpleText(title, QFont("", 13, QFont.Weight.Bold))
            label.setPos(0, -40)
        for y, name in ((top - 20, "VDD"), (bottom + 20, "GND")):
            self.addLine(0, y, width, y, QPen(QColor("#555"), 3))
            self.addSimpleText(name).setPos(width + INSET, y - INSET)

        for group, y0 in ((pmos, top), (nmos, top + CELL_H * p_rows + gap)):
            for i, t in enumerate(group):
                x = CELL_W * (i % PER_ROW) + 20
                y = y0 + CELL_H * (i // PER_ROW)
                self._symbol(t, x, y, value_of, conduction_of(t), prefix, top - 20, bottom + 20)
        self.setSceneRect(QRectF(-20, -60, width + 80, bottom + 100))

    def _symbol(
        self,
        t: Transistor,
        x: float,
        y: float,
        value_of: ValueOf,
        state: Conduction,
        prefix: str,
        vdd_y: float,
        gnd_y: float,
    ) -> None:
        """Símbolo de un transistor con la esquina superior izquierda en (x, y)."""
        cx = x + 70
        ch_top, ch_bot = y + 25, y + 85
        pen_channel = QPen(CHANNEL[state], 5)
        self.addLine(cx, ch_top, cx, ch_bot, pen_channel)
        # Placa de compuerta y su terminal; los pMOS llevan el círculo de inversión.
        plate = QPen(QColor("#333"), 3)
        self.addLine(cx - 12, ch_top + INSET, cx - 12, ch_bot - INSET, plate)
        gate_end = cx - 12
        if t.kind is TransistorType.PMOS:
            bubble = QGraphicsEllipseItem(cx - 24, (ch_top + ch_bot) / 2 - 6, 12, 12)
            bubble.setPen(QPen(QColor("#333"), 2))
            bubble.setBrush(QBrush(Qt.GlobalColor.white))
            self.addItem(bubble)
            gate_end = cx - 24
        gate_value = value_of(t.gate)
        mid = (ch_top + ch_bot) / 2
        self.addLine(x, mid, gate_end, mid, QPen(COLORS[gate_value], 3))
        self._label(f"G {_short(t.gate, prefix)}={_text(gate_value)}", x - 10, mid - 22, gate_value)
        # Fuente arriba y drenador abajo (en el netlist ambos son simétricos).
        for node, y_end, dy, name in ((t.source, ch_top, -18, "S"), (t.drain, ch_bot, 4, "D")):
            v = value_of(node)
            self.addLine(cx, y_end, cx + 22, y_end, QPen(COLORS[v], 3))
            self._label(f"{name} {_short(node, prefix)}={_text(v)}", cx + 26, y_end + dy, v)
            rail = (
                vdd_y if node.kind is NodeKind.VDD else gnd_y if node.kind is NodeKind.GND else None
            )
            if rail is not None:
                self.addLine(
                    cx + 22, y_end, cx + 22, rail, QPen(QColor("#777"), 1, Qt.PenStyle.DotLine)
                )
        kind = "pMOS" if t.kind is TransistorType.PMOS else "nMOS"
        self.addSimpleText(f"{kind} {_short_name(t.name, prefix)}").setPos(x, y + 92)
        if state is Conduction.ON:
            flow = QGraphicsLineItem(cx, ch_top, cx, ch_bot)
            pen = QPen(QColor("#ffffff"), 2, Qt.PenStyle.DashLine)
            flow.setPen(pen)
            self.addItem(flow)
            self._flows.append(flow)

    def _label(self, text: str, x: float, y: float, value: Logic) -> None:
        item = QGraphicsSimpleTextItem(text)
        item.setBrush(QBrush(COLORS[value]))
        item.setPos(x, y)
        self.addItem(item)

    def _animate(self) -> None:
        """Desplaza el trazo de los canales que conducen: la corriente "fluye"."""
        self._offset = (self._offset + 1.5) % 12
        for flow in self._flows:
            pen = flow.pen()
            pen.setDashOffset(-self._offset)
            flow.setPen(pen)

    @property
    def flowing(self) -> int:
        """Transistores que conducen en el dibujo actual."""
        return len(self._flows)


def _short_name(name: str, prefix: str) -> str:
    return name[len(prefix) :] if prefix and name.startswith(prefix) else name


def _text(v: Logic) -> str:
    return {Logic.ZERO: "0", Logic.ONE: "1", Logic.X: "X", Logic.Z: "Z"}[v]


class ZoomView(QGraphicsView):
    """Vista con zoom (rueda del ratón) y desplazamiento arrastrando."""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - API de Qt
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def fit(self) -> None:
        """Ajusta el zoom para ver la celda completa."""
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


__all__ = ["CellScene", "ZoomView"]
