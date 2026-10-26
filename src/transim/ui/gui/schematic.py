"""Geometría del esquema eléctrico de una celda, como en un libro de diseño CMOS.

Cada etapa se dibuja entre un riel VDD arriba y un riel GND abajo: la red pull-up de
pMOS, el nodo de salida y la red pull-down de nMOS. Los transistores en serie se
apilan y los en paralelo se colocan lado a lado, unidos por cables. Las etapas se
ordenan en columnas según el flujo de la señal; cuando una salida entra a la etapa
siguiente por su borde izquierdo (un inversor o una transmission gate), se dibuja el
cable; en los demás casos la conexión se indica con el nombre del nodo, como hacen los
esquemas profesionales.

La geometría no depende de Qt: el pintor (:mod:`transim.ui.gui.canvas`) solo dibuja
estas primitivas con los valores del motor. Unidades: píxeles a zoom 1.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache

from transim.core.netlist import Netlist
from transim.core.transistor import TransistorType
from transim.ui.gui.circuit import (
    CellCircuit,
    Element,
    Leaf,
    Loose,
    PassGate,
    Series,
    Stage,
    Tree,
    analyze,
)

Measure = Callable[[str], float]

# Símbolo del transistor en vertical, relativo a su terminal superior (0, 0).
DEV_H = 48.0  # de terminal a terminal
CHANNEL_X = -10.0  # línea del canal
PLATE_X = -16.0  # placa de la compuerta
GATE_X = -36.0  # terminal de la compuerta
GATE_Y = 24.0
LEAD_Y = 12.0  # altura a la que el canal se une al terminal

WIRE_GAP = 12.0  # cable entre transistores en serie
BAR = 12.0  # barra que une transistores en paralelo
PAR_GAP = 16.0  # espacio entre transistores en paralelo
RAIL_GAP = 16.0  # del riel al primer transistor
OUT_GAP = 30.0  # tramo vertical del nodo de salida
OUT_LEN = 18.0  # cable de salida a la derecha de la etapa
IN_LEN = 18.0  # cable de entrada de un inversor
TG_W = 76.0  # ancho de una transmission gate
TG_BAR = 22.0  # semialtura de las barras de una transmission gate
COL_GAP = 34.0  # espacio mínimo entre columnas
TRACK = 12.0  # separación entre cables verticales de un canal
ROW_GAP = 34.0  # espacio vertical entre elementos de una columna
PAD = 18.0  # margen del recuadro de la celda
TITLE_H = 40.0


def approx_width(text: str) -> float:
    """Ancho aproximado de un texto a 9 pt (para usar sin Qt, por ejemplo en pruebas)."""
    return 6.6 * len(text)


# ---------------------------------------------------------------- primitivas
@dataclass(frozen=True, slots=True)
class Seg:
    """Tramo de cable del nodo ``node``."""

    x1: float
    y1: float
    x2: float
    y2: float
    node: int


@dataclass(frozen=True, slots=True)
class Joint:
    """Punto de unión de cables (una T)."""

    x: float
    y: float
    node: int


@dataclass(frozen=True, slots=True)
class Device:
    """Símbolo de un transistor.

    ``(x, y)`` es su terminal superior en vertical; ``angle`` gira el símbolo alrededor
    de ese punto (0: compuerta a la izquierda; 90: compuerta arriba; −90: abajo).
    ``top`` y ``bottom`` son los nodos de los terminales del canal.
    """

    index: int
    x: float
    y: float
    angle: int
    pmos: bool
    gate: int
    top: int
    bottom: int

    def to_scene(self, lx: float, ly: float) -> tuple[float, float]:
        """Punto local del símbolo vertical → coordenadas de la celda."""
        if self.angle == 90:
            return self.x - ly, self.y + lx
        if self.angle == -90:
            return self.x + ly, self.y - lx
        return self.x + lx, self.y + ly

    def bounds(self) -> tuple[float, float, float, float]:
        """Rectángulo (x0, y0, x1, y1) que ocupa el símbolo."""
        pts = [self.to_scene(GATE_X, 0.0), self.to_scene(0.0, DEV_H)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass(frozen=True, slots=True)
class Text:
    """Etiqueta. ``kind``: ``gate`` (compuerta), ``net`` (nodo), ``pin_in``/``pin_out``
    (puerto de la celda), ``rail``, ``name`` (nombre del transistor) o ``title``.
    ``align``: ``left``, ``right`` o ``center`` respecto de ``x``; ``y`` es el centro."""

    text: str
    x: float
    y: float
    kind: str
    node: int | None = None
    align: str = "left"


@dataclass
class Schematic:
    """Primitivas del esquema de una celda, en coordenadas de la celda."""

    circuit: CellCircuit
    width: float = 0.0
    height: float = 0.0
    segs: list[Seg] = field(default_factory=list)
    joints: list[Joint] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    rails: list[Seg] = field(default_factory=list)
    stages: list[tuple[Stage, float, float]] = field(default_factory=list)
    """Cada etapa con la posición (x, y) de su riel VDD sobre la columna de la salida."""

    def translate(self, dx: float, dy: float) -> None:
        self.segs = [Seg(s.x1 + dx, s.y1 + dy, s.x2 + dx, s.y2 + dy, s.node) for s in self.segs]
        self.rails = [Seg(s.x1 + dx, s.y1 + dy, s.x2 + dx, s.y2 + dy, s.node) for s in self.rails]
        self.joints = [Joint(j.x + dx, j.y + dy, j.node) for j in self.joints]
        self.devices = [
            Device(d.index, d.x + dx, d.y + dy, d.angle, d.pmos, d.gate, d.top, d.bottom)
            for d in self.devices
        ]
        self.texts = [Text(t.text, t.x + dx, t.y + dy, t.kind, t.node, t.align) for t in self.texts]
        self.stages = [(s, x + dx, y + dy) for s, x, y in self.stages]


# ------------------------------------------------------------ redes SP
@dataclass(frozen=True, slots=True)
class _Box:
    left: float  # extensión a la izquierda de la columna vertebral
    right: float  # extensión a la derecha
    height: float


class _Builder:
    """Construye el esquema de una celda."""

    def __init__(self, circuit: CellCircuit, measure: Measure) -> None:
        self.c = circuit
        self.w = measure
        self.out = Schematic(circuit)
        self.joined: set[int] = set()  # transistores de inversores con compuertas unidas

    # ---------------------------------------------------------- medidas
    def _gate_label(self, index: int) -> str:
        return self.c.label(self.c.transistors[index].gate.id)

    def _name(self, index: int) -> str:
        return self.c.transistors[index].name

    def box(self, tree: Tree) -> _Box:
        if isinstance(tree, Leaf):
            label = 0.0 if tree.index in self.joined else self.w(self._gate_label(tree.index)) + 6
            return _Box(-GATE_X + label, 7 + self.w(self._name(tree.index)) * 0.85, DEV_H)
        boxes = [self.box(p) for p in tree.parts]
        if isinstance(tree, Series):
            h = sum(b.height for b in boxes) + WIRE_GAP * (len(boxes) - 1)
            return _Box(max(b.left for b in boxes), max(b.right for b in boxes), h)
        x = 0.0
        for k in range(1, len(boxes)):
            x += boxes[k - 1].right + PAR_GAP + boxes[k].left
        return _Box(boxes[0].left, x + boxes[-1].right, max(b.height for b in boxes) + 2 * BAR)

    # ---------------------------------------------------------- dibujo
    def seg(self, x1: float, y1: float, x2: float, y2: float, node: int) -> None:
        if (x1, y1) != (x2, y2):
            self.out.segs.append(Seg(x1, y1, x2, y2, node))

    def emit(self, tree: Tree, x: float, y: float) -> None:
        """Dibuja ``tree`` con su columna vertebral en ``x`` y su terminal superior en ``y``."""
        if isinstance(tree, Leaf):
            t = self.c.transistors[tree.index]
            self.out.devices.append(
                Device(
                    tree.index,
                    x,
                    y,
                    0,
                    t.kind is TransistorType.PMOS,
                    t.gate.id,
                    tree.top,
                    tree.bottom,
                )
            )
            if tree.index not in self.joined:
                self.out.texts.append(
                    Text(
                        self._gate_label(tree.index),
                        x + GATE_X - 4,
                        y + GATE_Y,
                        "gate",
                        t.gate.id,
                        "right",
                    )
                )
            self.out.texts.append(Text(self._name(tree.index), x + 6, y + GATE_Y, "name"))
            return
        boxes = [self.box(p) for p in tree.parts]
        if isinstance(tree, Series):
            cy = y
            for k, (part, b) in enumerate(zip(tree.parts, boxes, strict=True)):
                self.emit(part, x, cy)
                cy += b.height
                if k < len(boxes) - 1:
                    self.seg(x, cy, x, cy + WIRE_GAP, part.bottom)
                    cy += WIRE_GAP
            return
        # Paralelo
        xs = [x]
        for k in range(1, len(boxes)):
            xs.append(xs[-1] + boxes[k - 1].right + PAR_GAP + boxes[k].left)
        inner = max(b.height for b in boxes)
        top_bar, bottom_bar = y + BAR, y + BAR + inner
        self.seg(x, y, x, top_bar, tree.top)
        self.seg(xs[0], top_bar, xs[-1], top_bar, tree.top)
        self.seg(xs[0], bottom_bar, xs[-1], bottom_bar, tree.bottom)
        self.seg(x, bottom_bar, x, bottom_bar + BAR, tree.bottom)
        for k, (part, b, px) in enumerate(zip(tree.parts, boxes, xs, strict=True)):
            self.emit(part, px, top_bar)
            self.seg(px, top_bar + b.height, px, bottom_bar, tree.bottom)
            if k < len(boxes) - 1:
                self.out.joints.append(Joint(px, top_bar, tree.top))
                self.out.joints.append(Joint(px, bottom_bar, tree.bottom))

    # ---------------------------------------------------------- elementos
    def element_box(self, e: Element) -> tuple[float, float, float, float]:
        """(izquierda, derecha, arriba, abajo) del elemento respecto de su ancla: el borde
        izquierdo del elemento a la altura de su riel VDD (etapa) o de su eje (pase)."""
        if isinstance(e, Stage):
            if e.is_inverter:
                self.joined |= set(e.transistors)
            up, down = self.box(e.pull_up), self.box(e.pull_down)
            left = max(up.left, down.left, self.w("VDD") + 10)
            if e.is_inverter:
                left = -GATE_X + IN_LEN + self.w(self.c.label(self._gate(e))) + 8.0
            h = RAIL_GAP + up.height + OUT_GAP + down.height + RAIL_GAP
            return 0.0, left + self._out_reach(e, up, down), 0.0, h
        if isinstance(e, PassGate):
            left = self.w(self.c.label(e.left)) + 8.0
            reach = TG_BAR - GATE_X + 20
            return 0.0, left + TG_W + self._label_w(e.right), -reach, reach
        n = len(e.indices)
        cols = min(n, 4)
        return 0.0, cols * 150.0, 0.0, -(-n // cols) * 110.0

    def _gate(self, stage: Stage) -> int:
        return self.c.transistors[stage.transistors[0]].gate.id

    def _label_w(self, node: int) -> float:
        extra = 18.0 if self.c.is_port(node) else 4.0
        return self.w(self.c.label(node)) + extra

    def _out_reach(self, e: Stage, up: _Box, down: _Box) -> float:
        """De la columna vertebral al extremo del cable de salida."""
        return max(max(up.right, down.right) + OUT_LEN, self._label_w(e.output) + 14)

    def emit_element(
        self, e: Element, x: float, y: float
    ) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        """Dibuja el elemento con su ancla en (x, y).

        Returns:
            (punto de salida, punto de entrada izquierda), o None si no tiene.
        """
        if isinstance(e, Stage):
            return self._emit_stage(e, x, y)
        if isinstance(e, PassGate):
            return self._emit_pass(e, x, y)
        self._emit_loose(e, x, y)
        return None, None

    def _emit_stage(
        self, e: Stage, x: float, y: float
    ) -> tuple[tuple[float, float], tuple[float, float] | None]:
        _, width, _, h = self.element_box(e)
        up, down = self.box(e.pull_up), self.box(e.pull_down)
        vdd, gnd = e.pull_up.top, e.pull_down.bottom
        x_out = x + width
        spine = x_out - self._out_reach(e, up, down)
        self.out.stages.append((e, spine, y))
        self.out.rails.append(Seg(x, y, x_out - OUT_LEN / 2, y, vdd))
        self.out.rails.append(Seg(x, y + h, x_out - OUT_LEN / 2, y + h, gnd))
        self.out.texts.append(Text("VDD", x, y - 9, "rail", vdd))
        self.out.texts.append(Text("GND", x, y + h + 10, "rail", gnd))
        self.seg(spine, y, spine, y + RAIL_GAP, vdd)
        self.out.joints.append(Joint(spine, y, vdd))
        self.emit(e.pull_up, spine, y + RAIL_GAP)
        y1 = y + RAIL_GAP + up.height
        y_out = y1 + OUT_GAP / 2
        self.seg(spine, y1, spine, y1 + OUT_GAP, e.output)
        self.out.joints.append(Joint(spine, y_out, e.output))
        self.seg(spine, y_out, x_out, y_out, e.output)
        self._out_label(e.output, x_out, y_out)
        y2 = y1 + OUT_GAP
        self.emit(e.pull_down, spine, y2)
        self.seg(spine, y2 + down.height, spine, y + h, gnd)
        self.out.joints.append(Joint(spine, y + h, gnd))
        if not e.is_inverter:
            return (x_out, y_out), None
        gate = self._gate(e)
        gx = spine + GATE_X
        self.seg(gx, y + RAIL_GAP + GATE_Y, gx, y2 + GATE_Y, gate)
        self.seg(gx - IN_LEN, y_out, gx, y_out, gate)
        self.out.joints.append(Joint(gx, y_out, gate))
        self._in_label(gate, gx - IN_LEN, y_out)
        return (x_out, y_out), (gx - IN_LEN, y_out)

    def _out_label(self, node: int, x: float, y: float) -> None:
        """Nombre del nodo sobre el cable, justificado a la derecha en ``x``."""
        kind = "pin_out" if node in self.c.outputs.values() else "net"
        self.out.texts.append(Text(self.c.label(node), x - 2, y - 10, kind, node, "right"))

    def _in_label(self, node: int, x: float, y: float) -> None:
        kind = "pin_in" if node in self.c.inputs.values() else "net"
        self.out.texts.append(Text(self.c.label(node), x - 4, y, kind, node, "right"))

    def _emit_pass(
        self, e: PassGate, x: float, y: float
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        ts = self.c.transistors
        x_in = x + self.w(self.c.label(e.left)) + 8.0
        self._in_label(e.left, x_in, y)
        bx1, bx2 = x_in + 14, x_in + TG_W - 14
        self.seg(x_in, y, bx1, y, e.left)
        self.seg(bx1, y - TG_BAR, bx1, y + TG_BAR, e.left)
        self.out.joints.append(Joint(bx1, y, e.left))
        self.seg(bx2, y - TG_BAR, bx2, y + TG_BAR, e.right)
        self.out.joints.append(Joint(bx2, y, e.right))
        x_out = x_in + TG_W + self._label_w(e.right)
        self.seg(bx2, y, x_out, y, e.right)
        for index, upper in ((e.n, True), (e.p, False)):
            t = ts[index]
            pmos = t.kind is TransistorType.PMOS
            if upper:  # compuerta hacia arriba; el terminal superior queda a la derecha
                d = Device(index, bx2, y - TG_BAR, 90, pmos, t.gate.id, e.right, e.left)
                gy = y - TG_BAR + GATE_X - 10
            else:  # compuerta hacia abajo; el terminal superior queda a la izquierda
                d = Device(index, bx1, y + TG_BAR, -90, pmos, t.gate.id, e.left, e.right)
                gy = y + TG_BAR - GATE_X + 10
            self.out.devices.append(d)
            gx, gyt = d.to_scene(GATE_X, GATE_Y)
            self.seg(gx, gyt, gx, gyt, t.gate.id)
            self.out.texts.append(
                Text(self.c.label(t.gate.id), gx, gy, "gate", t.gate.id, "center")
            )
        name = ts[e.n].name.rsplit(".", 1)[0]
        self.out.texts.append(Text(name, (bx1 + bx2) / 2, y + 10, "name", None, "center"))
        self._out_label(e.right, x_out, y)
        return (x_out, y), (x_in, y)

    def _emit_loose(self, e: Loose, x: float, y: float) -> None:
        label = self.c.label
        for k, index in enumerate(e.indices):
            t = self.c.transistors[index]
            dx, dy = x + 70 + (k % 4) * 150.0, y + 20 + (k // 4) * 110.0
            pmos = t.kind is TransistorType.PMOS
            self.out.devices.append(
                Device(index, dx, dy, 0, pmos, t.gate.id, t.source.id, t.drain.id)
            )
            self.out.texts.append(
                Text(label(t.gate.id), dx + GATE_X - 4, dy + GATE_Y, "gate", t.gate.id, "right")
            )
            self.out.texts.append(Text(label(t.source.id), dx + 5, dy - 4, "net", t.source.id))
            self.out.texts.append(
                Text(label(t.drain.id), dx + 5, dy + DEV_H + 4, "net", t.drain.id)
            )
            self.out.texts.append(Text(t.name, dx + 6, dy + GATE_Y, "name"))


# ------------------------------------------------------------ celda completa
def _produces(e: Element, node: int) -> bool:
    return (isinstance(e, Stage) and e.output == node) or (
        isinstance(e, PassGate) and e.right == node
    )


def _sources(c: CellCircuit, node: int) -> list[int]:
    """Elementos que producen ``node``."""
    return [k for k, e in enumerate(c.elements) if _produces(e, node)]


def _left_input(e: Element, c: CellCircuit) -> int | None:
    """Nodo que entra por el borde izquierdo del elemento (se puede cablear)."""
    if isinstance(e, Stage) and e.is_inverter:
        return c.transistors[e.transistors[0]].gate.id
    if isinstance(e, PassGate):
        return e.left
    return None


def _columns(c: CellCircuit) -> list[int]:
    """Columna de cada elemento: una más que la del último elemento que le da señal."""
    col = [0] * len(c.elements)
    for k, e in enumerate(c.elements):
        deps = {c.transistors[i].gate.id for i in e.transistors}
        if isinstance(e, PassGate):
            deps.add(e.left)
        before = [s for n in deps for s in _sources(c, n) if s < k]
        col[k] = max((col[s] + 1 for s in before), default=0)
    return col


def build(netlist: Netlist, measure: Measure = approx_width) -> Schematic:
    """Esquema de una celda primitiva. Se calcula una vez por definición y medida."""
    return _build(netlist, measure)


@cache
def _build(netlist: Netlist, measure: Measure) -> Schematic:
    c = analyze(netlist)
    b = _Builder(c, measure)
    cols = _columns(c)
    n_cols = max(cols, default=-1) + 1
    boxes = [b.element_box(e) for e in c.elements]
    by_col: list[list[int]] = [[] for _ in range(n_cols)]
    for k, col in enumerate(cols):
        by_col[col].append(k)

    out_pin: dict[int, tuple[float, float]] = {}
    in_pin: dict[int, tuple[float, float]] = {}
    prev_right = PAD
    for col, members in enumerate(by_col):
        wired = _wired(c, members, cols, col)
        tracks = len({node for node, _ in wired})
        x = prev_right + COL_GAP + max(0, tracks - 1) * TRACK if col else PAD
        cursor = PAD + TITLE_H
        col_right = x
        for k in members:
            e = c.elements[k]
            left, right, top, bottom = boxes[k]
            anchor_y = cursor - top
            node = _left_input(e, c)
            srcs = _sources(c, node) if node is not None else []
            if len(srcs) == 1 and srcs[0] in out_pin and cols[srcs[0]] == col - 1:
                anchor_y = max(anchor_y, out_pin[srcs[0]][1] - _pin_offset(e, b))
            out_point, in_point = b.emit_element(e, x, anchor_y)
            if out_point is not None:
                out_pin[k] = out_point
            if in_point is not None:
                in_pin[k] = in_point
            cursor = anchor_y + bottom + ROW_GAP
            col_right = max(col_right, x + left + right)
        _route_channel(b, c, wired, out_pin, in_pin, prev_right)
        prev_right = col_right
    b.out.texts.append(Text(c.name, PAD, PAD + 6, "title"))
    _fit(b.out, measure)
    return b.out


def _fit(out: Schematic, measure: Measure) -> None:
    """Mueve el dibujo para que empiece en (PAD, PAD) y calcula su tamaño."""
    lines = out.segs + out.rails
    xs = [s.x1 for s in lines] + [s.x2 for s in lines]
    ys = [s.y1 for s in lines] + [s.y2 for s in lines]
    for t in out.texts:
        w = measure(t.text) + (16 if t.kind in ("pin_in", "pin_out") else 0)
        x0 = t.x - (w if t.align == "right" else w / 2 if t.align == "center" else 0)
        xs += [x0, x0 + w]
        ys += [t.y - 9, t.y + 9]
    for d in out.devices:
        x0, y0, x1, y1 = d.bounds()
        xs += [x0, x1]
        ys += [y0, y1]
    min_x, min_y = min(xs) - PAD, min(ys) - PAD
    out.translate(-min_x, -min_y)
    out.width = max(xs) - min_x + PAD
    out.height = max(ys) - min_y + PAD


def _pin_offset(e: Element, b: _Builder) -> float:
    """Distancia vertical del ancla del elemento a su entrada izquierda."""
    if isinstance(e, Stage):
        return RAIL_GAP + b.box(e.pull_up).height + OUT_GAP / 2
    return 0.0


def _wired(c: CellCircuit, members: list[int], cols: list[int], col: int) -> list[tuple[int, int]]:
    """(nodo, elemento) de las entradas izquierdas que vienen de la columna anterior."""
    wired = []
    for k in members:
        node = _left_input(c.elements[k], c)
        if node is None:
            continue
        srcs = _sources(c, node)
        if srcs and all(cols[s] == col - 1 for s in srcs):
            wired.append((node, k))
    return wired


def _route_channel(
    b: _Builder,
    c: CellCircuit,
    wired: list[tuple[int, int]],
    out_pin: dict[int, tuple[float, float]],
    in_pin: dict[int, tuple[float, float]],
    left_x: float,
) -> None:
    """Cables entre dos columnas: un tramo vertical por nodo y ramas horizontales."""
    nets: dict[int, list[int]] = {}
    for node, k in wired:
        nets.setdefault(node, []).append(k)
    order = sorted(nets, key=lambda n: min(out_pin[s][1] for s in _sources(c, n)))
    for t, node in enumerate(order):
        sources = [out_pin[s] for s in _sources(c, node) if s in out_pin]
        dests = [in_pin[k] for k in nets[node] if k in in_pin]
        for _, py in dests:
            _drop_label(b, node, py)
        if len(sources) == 1 and len(dests) == 1 and abs(sources[0][1] - dests[0][1]) < 0.5:
            b.seg(sources[0][0], sources[0][1], dests[0][0], dests[0][1], node)
            continue
        tx = left_x + COL_GAP / 2 + t * TRACK
        for px, py in sources:
            b.seg(px, py, tx, py, node)
        for px, py in dests:
            b.seg(tx, py, px, py, node)
        ys = sorted(p[1] for p in sources + dests)
        b.seg(tx, ys[0], tx, ys[-1], node)
        for py in ys[1:-1]:
            b.out.joints.append(Joint(tx, py, node))


def _drop_label(b: _Builder, node: int, y: float) -> None:
    """Quita la etiqueta de entrada de un pin que ya tiene cable."""
    b.out.texts = [
        t
        for t in b.out.texts
        if not (t.node == node and t.align == "right" and t.kind == "net" and abs(t.y - y) < 0.5)
    ]


__all__ = [
    "DEV_H",
    "Device",
    "Joint",
    "Schematic",
    "Seg",
    "Text",
    "approx_width",
    "build",
]
