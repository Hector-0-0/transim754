"""Diagrama de flujo de datos de una operación: sus bloques de primer nivel y cómo se conectan.

Cada bloque (desempaquetar, comparar, sumar mantisas, redondear…) es una caja con sus
salidas y el valor que tienen. Una flecha va de un bloque a otro cuando una de sus salidas
llega a una entrada del siguiente, a través de celdas sueltas del nivel superior (las de
"pegamento", como un inversor entre dos bloques). Hacer clic en una caja abre su
esquema en la pestaña Transistores.

El grafo se calcula a partir del netlist; no cambia la simulación.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from transim.core.netlist import Instance, Netlist
from transim.core.node import Node
from transim.core.signals import Logic
from transim.ui.gui import theme as th
from transim.ui.gui.widgets import thousands

BOX_W = 230.0
LINE_H = 16.0
HEAD_H = 40.0
MAX_OUTS = 5
GAP_X = 100.0
GAP_Y = 22.0
PAD = 14.0
TITLE_TOP = 7.0
ARROW = 9.0
ZOOM = 0.9
"""Escala inicial: legible, con desplazamiento para ver todo el diagrama."""


@dataclass(frozen=True)
class Block:
    """Un bloque de primer nivel.

    Attributes:
        path: camino jerárquico de la instancia (``"order"``).
        title: nombre de su definición.
        transistors: transistores que contiene.
        ins, outs: nombre de la entrada o salida (bus o puerto) → nodos del netlist padre.
    """

    path: str
    title: str
    transistors: int
    ins: dict[str, tuple[Node, ...]]
    outs: dict[str, tuple[Node, ...]]


@dataclass(frozen=True)
class Link:
    """Conexión de ``src`` a ``dst`` (índices de bloque) con los nombres que la llevan."""

    src: int
    dst: int
    labels: tuple[str, ...]


@dataclass(frozen=True)
class Graph:
    blocks: list[Block]
    links: list[Link]
    ranks: list[int]
    """Columna de cada bloque: el camino más largo desde una entrada del chip."""


def _ports(inst: Instance) -> tuple[dict[str, tuple[Node, ...]], dict[str, tuple[Node, ...]]]:
    """Entradas y salidas de una instancia, con los buses agrupados por nombre."""
    d = inst.definition
    ins: dict[str, tuple[Node, ...]] = {}
    outs: dict[str, tuple[Node, ...]] = {}
    for bus in d.input_buses:
        if bus in inst.buses:
            ins[bus] = tuple(inst.buses[bus])
    for bus in d.output_buses:
        if bus in inst.buses:
            outs[bus] = tuple(inst.buses[bus])
    for port in d.inputs:
        if "[" not in port and port in inst.ports:
            ins[port] = (inst.ports[port],)
    for port in d.outputs:
        if "[" not in port and port in inst.ports:
            outs[port] = (inst.ports[port],)
    return ins, outs


def graph(netlist: Netlist) -> Graph:
    """Bloques de primer nivel y sus conexiones, por el camino de las celdas de pegamento."""
    top = netlist.top_instances()
    blocks_inst = [i for i in top if not i.is_leaf]
    glue = [i for i in top if i.is_leaf]
    blocks: list[Block] = []
    for inst in blocks_inst:
        ins, outs = _ports(inst)
        blocks.append(Block(inst.path, inst.definition.name, len(inst.transistors), ins, outs))

    # Dirección de la señal dentro de cada celda suelta: de sus entradas a sus salidas.
    succ: dict[int, set[int]] = {}
    for g in glue:
        g_ins, g_outs = _ports(g)
        for src in (n for nodes in g_ins.values() for n in nodes):
            succ.setdefault(src.id, set()).update(n.id for nodes in g_outs.values() for n in nodes)

    # Qué bloque recibe cada nodo como entrada.
    in_index: dict[int, set[int]] = {}
    for j, b in enumerate(blocks):
        for nodes in b.ins.values():
            for n in nodes:
                in_index.setdefault(n.id, set()).add(j)

    links: list[Link] = []
    for i, b in enumerate(blocks):
        hits: dict[int, list[str]] = {}
        for label, nodes in b.outs.items():
            for start in nodes:
                seen = {start.id}
                stack = [start.id]
                while stack:
                    x = stack.pop()
                    for j in in_index.get(x, ()):
                        if j != i and label not in hits.setdefault(j, []):
                            hits[j].append(label)
                    if x in in_index:
                        continue  # la señal llega a un bloque: no sigue más allá
                    for y in succ.get(x, ()):
                        if y not in seen:
                            seen.add(y)
                            stack.append(y)
        for j in sorted(hits):
            links.append(Link(i, j, tuple(hits[j])))

    ranks = [0] * len(blocks)
    for _ in range(len(blocks)):  # acotado: un lazo no hace crecer el rango sin fin
        changed = False
        for link in links:
            if ranks[link.dst] < ranks[link.src] + 1:
                ranks[link.dst] = ranks[link.src] + 1
                changed = True
        if not changed:
            break
    return Graph(blocks, links, ranks)


def _value_text(read: object, nodes: tuple[Node, ...]) -> str:
    """Valor de un bus (LSB primero) en hexadecimal; X si algún bit no es 0 ni 1."""
    bits = [read(n) for n in nodes]  # type: ignore[operator]
    if any(b not in (Logic.ZERO, Logic.ONE) for b in bits):
        return "X"
    if len(bits) == 1:
        return "1" if bits[0] is Logic.ONE else "0"
    value = sum((1 << k) for k, b in enumerate(bits) if b is Logic.ONE)
    return f"0x{value:X}"


class FlowView(QGraphicsView):
    """Vista del diagrama de flujo. Un clic en un bloque emite su camino jerárquico."""

    block_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMinimumHeight(360)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._unit: object | None = None

    def show_unit(self, unit: object) -> None:
        """Dibuja los bloques de la unidad de la última operación."""
        self._unit = unit
        self.refresh()

    def refresh(self) -> None:
        """Vuelve a dibujar con el tema actual y los valores de la última operación."""
        self._scene.clear()
        unit = self._unit
        if unit is None:
            return
        g = graph(unit.netlist)  # type: ignore[attr-defined]
        if not g.blocks:
            self._scene.addText("La operación no tiene bloques de primer nivel.")
            return
        read = unit.engine.value  # type: ignore[attr-defined]
        t = th.current()
        columns: dict[int, list[int]] = {}
        for k, r in enumerate(g.ranks):
            columns.setdefault(r, []).append(k)
        box_h = HEAD_H + LINE_H * min(MAX_OUTS, max(len(b.outs) for b in g.blocks)) + PAD
        rects: dict[int, QGraphicsRectItem] = {}
        geom: dict[int, tuple[float, float]] = {}
        for rank in sorted(columns):
            for slot, k in enumerate(columns[rank]):
                b = g.blocks[k]
                x = rank * (BOX_W + GAP_X)
                y = slot * (box_h + GAP_Y)
                rect = QGraphicsRectItem(QRectF(0, 0, BOX_W, box_h))
                rect.setPos(x, y)
                geom[k] = (x, y)
                rect.setBrush(QBrush(QColor(t.surface)))
                rect.setPen(QPen(QColor(t.frame), 1.2))
                rect.setData(0, b.path)
                rect.setCursor(Qt.CursorShape.PointingHandCursor)
                rect.setToolTip(f"Abrir el esquema de «{b.path}» en Transistores")
                self._scene.addItem(rect)
                rects[k] = rect
                title = QGraphicsSimpleTextItem(b.title, rect)
                f = QFont()
                f.setBold(True)
                f.setPointSizeF(9.5)
                title.setFont(f)
                title.setBrush(QBrush(QColor(t.text)))
                title.setPos(PAD, TITLE_TOP)
                sub = QGraphicsSimpleTextItem(
                    f"{b.path} · {thousands(b.transistors)} transistores", rect
                )
                sub.setBrush(QBrush(QColor(t.muted)))
                sub.setPos(PAD, 24)
                lines = list(b.outs.items())[:MAX_OUTS]
                for line, (label, nodes) in enumerate(lines):
                    text = QGraphicsSimpleTextItem(f"{label}  {_value_text(read, nodes)}", rect)
                    text.setBrush(QBrush(QColor(t.accent)))
                    text.setPos(PAD, HEAD_H + LINE_H * line)
        for link in g.links:
            if link.src not in geom or link.dst not in geom:
                continue
            sx, sy = geom[link.src]
            dx, dy = geom[link.dst]
            start = sx + BOX_W, sy + box_h / 2
            end = dx, dy + box_h / 2
            path = QPainterPath(QPointF(*start))
            mid = (start[0] + end[0]) / 2
            path.cubicTo(QPointF(mid, start[1]), QPointF(mid, end[1]), QPointF(*end))
            item = QGraphicsPathItem(path)
            item.setPen(QPen(QColor(t.accent), 1.6))
            self._scene.addItem(item)
            head = QPolygonF(
                [
                    QPointF(end[0], end[1]),
                    QPointF(end[0] - ARROW, end[1] - ARROW / 2),
                    QPointF(end[0] - ARROW, end[1] + ARROW / 2),
                ]
            )
            arrow = QGraphicsPolygonItem(head)
            arrow.setBrush(QBrush(QColor(t.accent)))
            arrow.setPen(QPen(Qt.PenStyle.NoPen))
            self._scene.addItem(arrow)
            link_text = QGraphicsSimpleTextItem(", ".join(link.labels))
            link_text.setBrush(QBrush(QColor(t.muted)))
            link_text.setPos(mid - 30, (start[1] + end[1]) / 2 - 16)
            self._scene.addItem(link_text)
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-16, -16, 16, 16))
        self.resetTransform()
        self.scale(ZOOM, ZOOM)
        self.verticalScrollBar().setValue(0)
        self.horizontalScrollBar().setValue(0)

    def wheelEvent(self, event: object) -> None:  # noqa: N802 - API de Qt
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15  # type: ignore[attr-defined]
        self.scale(factor, factor)

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - API de Qt
        item: QGraphicsItem | None = self.itemAt(event.position().toPoint())  # type: ignore[attr-defined]
        while item is not None and item.data(0) is None:
            item = item.parentItem()
        if item is not None:
            self.block_clicked.emit(str(item.data(0)))
        super().mousePressEvent(event)  # type: ignore[arg-type]


__all__ = ["Block", "FlowView", "Graph", "Link", "graph"]
