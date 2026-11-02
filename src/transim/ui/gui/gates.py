"""Vista de compuertas de una celda: qué función lógica implementa cada etapa CMOS.

Cada etapa se deduce del circuito real, no de un dibujo hecho a mano. Su red pull-down
de nMOS conduce cuando su expresión vale 1, con serie = AND y paralelo = OR, y entonces
lleva la salida a 0: la etapa calcula la negación de esa expresión. Según la forma del
árbol se nombra como en un libro de diseño CMOS (Weste y Harris, 2011):

- un transistor: inversor (``y = ¬a``);
- varios en serie: NAND; varios en paralelo: NOR;
- paralelo de series: AOI (AND-OR-invertida); serie de paralelos: OAI;
- cualquier otra combinación: compuerta compleja.

Una transmission gate deja pasar su entrada cuando su control vale 1. Los transistores
que no forman una etapa se muestran como una red sin función propia.

El módulo no depende de Qt: lo usan la vista, el texto del inspector y las pruebas. La
geometría (:func:`layout`) va en píxeles a zoom 1.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache

from transim.core.netlist import Netlist
from transim.core.signals import Logic
from transim.ui.gui.circuit import (
    CellCircuit,
    Leaf,
    Loose,
    Parallel,
    PassGate,
    Series,
    Stage,
    Tree,
    analyze,
)

NOT = "¬"
AND = "·"
OR = " + "


# ---------------------------------------------------------------- compuertas
@dataclass(frozen=True, slots=True)
class Gate:
    """Una etapa de la celda vista como compuerta lógica.

    Attributes:
        element: índice del elemento en ``CellCircuit.elements``.
        kind: ``INV``, ``NAND``, ``NOR``, ``AOI``, ``OAI``, ``COMPLEJA``, ``TG`` o ``RED``.
        output: nodo (id local) que la compuerta maneja; -1 si no tiene uno solo.
        inputs: nodos de entrada, en el orden de sus pines.
        pins: nombre corto de cada pin (``e`` entrada y ``c``/``c̄`` control en una TG).
        expression: la función sin el nombre de la salida (``¬(a·b)``).
        transistors: transistores de la etapa.
    """

    element: int
    kind: str
    output: int
    inputs: tuple[int, ...]
    pins: tuple[str, ...]
    expression: str
    transistors: tuple[int, ...]

    @property
    def title(self) -> str:
        """``NAND2``, ``INV``, ``AOI``…"""
        if self.kind in ("NAND", "NOR"):
            return f"{self.kind}{len(self.inputs)}"
        return self.kind

    @property
    def inverting(self) -> bool:
        return self.kind not in ("TG", "RED")


def _gate_of(tree: Tree, circuit: CellCircuit) -> int:
    assert isinstance(tree, Leaf)
    return circuit.transistors[tree.index].gate.id


def tree_inputs(tree: Tree, circuit: CellCircuit) -> list[int]:
    """Nodos de compuerta del árbol, sin repetir, en orden de aparición."""
    if isinstance(tree, Leaf):
        return [_gate_of(tree, circuit)]
    seen: list[int] = []
    for part in tree.parts:
        for n in tree_inputs(part, circuit):
            if n not in seen:
                seen.append(n)
    return seen


def expression(tree: Tree, name: Callable[[int], str], circuit: CellCircuit) -> str:
    """Expresión que hace conducir a una red de nMOS: serie = AND, paralelo = OR."""
    if isinstance(tree, Leaf):
        return name(_gate_of(tree, circuit))
    texts = []
    for part in tree.parts:
        text = expression(part, name, circuit)
        if isinstance(tree, Series) and isinstance(part, Parallel):
            text = f"({text})"
        texts.append(text)
    return (AND if isinstance(tree, Series) else OR).join(texts)


def evaluate(tree: Tree, value: Callable[[int], Logic], circuit: CellCircuit) -> Logic:
    """Valor de la expresión de una red de nMOS con los valores de sus compuertas."""
    if isinstance(tree, Leaf):
        return value(_gate_of(tree, circuit))
    parts = [evaluate(p, value, circuit) for p in tree.parts]
    if isinstance(tree, Series):
        if Logic.ZERO in parts:
            return Logic.ZERO
        return Logic.ONE if all(p is Logic.ONE for p in parts) else Logic.X
    if Logic.ONE in parts:
        return Logic.ONE
    return Logic.ZERO if all(p is Logic.ZERO for p in parts) else Logic.X


def negate(v: Logic) -> Logic:
    return {Logic.ONE: Logic.ZERO, Logic.ZERO: Logic.ONE}.get(v, Logic.X)


def _kind(tree: Tree) -> str:
    if isinstance(tree, Leaf):
        return "INV"
    simple = all(isinstance(p, Leaf) for p in tree.parts)
    if isinstance(tree, Series):
        if simple:
            return "NAND"
        if all(isinstance(p, Leaf | Parallel) for p in tree.parts):
            return "OAI" if all(_flat(p) for p in tree.parts) else "COMPLEJA"
        return "COMPLEJA"
    if simple:
        return "NOR"
    if all(isinstance(p, Leaf | Series) for p in tree.parts):
        return "AOI" if all(_flat(p) for p in tree.parts) else "COMPLEJA"
    return "COMPLEJA"


def _flat(tree: Tree) -> bool:
    """Un transistor, o una serie o un paralelo de transistores sueltos."""
    return isinstance(tree, Leaf) or all(isinstance(p, Leaf) for p in tree.parts)


@cache
def cell_gates(netlist: Netlist) -> tuple[Gate, ...]:
    """Las compuertas de una celda primitiva, en orden de señal."""
    c = analyze(netlist)
    gates: list[Gate] = []
    for k, e in enumerate(c.elements):
        if isinstance(e, Stage):
            ins = tree_inputs(e.pull_down, c)
            expr = expression(e.pull_down, c.label, c)
            kind = _kind(e.pull_down)
            text = f"{NOT}{expr}" if kind == "INV" else f"{NOT}({expr})"
            gates.append(
                Gate(
                    k,
                    kind,
                    e.output,
                    tuple(ins),
                    tuple(c.label(n) for n in ins),
                    text,
                    tuple(e.transistors),
                )
            )
        elif isinstance(e, PassGate):
            n_gate = c.transistors[e.n].gate.id
            p_gate = c.transistors[e.p].gate.id
            gates.append(
                Gate(
                    k,
                    "TG",
                    e.right,
                    (e.left, n_gate, p_gate),
                    ("e", "c", "c̄"),
                    f"{c.label(e.left)} si {c.label(n_gate)} = 1",
                    (e.n, e.p),
                )
            )
        elif isinstance(e, Loose):
            ts = [c.transistors[i] for i in e.indices]
            ins = sorted({t.gate.id for t in ts})
            gates.append(
                Gate(
                    k,
                    "RED",
                    -1,
                    tuple(ins),
                    tuple(c.label(n) for n in ins),
                    "transistores sin etapa reconocible",
                    tuple(e.indices),
                )
            )
    return tuple(gates)


def gate_value(g: Gate, netlist: Netlist, value: Callable[[int], Logic]) -> Logic:
    """Lo que la compuerta pone en su salida según sus entradas.

    Una transmission gate abierta (control en 0) no impone nada: devuelve Z.
    """
    c = analyze(netlist)
    e = c.elements[g.element]
    if isinstance(e, Stage):
        return negate(evaluate(e.pull_down, value, c))
    if isinstance(e, PassGate):
        ctrl, ctrl_n = value(g.inputs[1]), value(g.inputs[2])
        if ctrl is Logic.ONE or ctrl_n is Logic.ZERO:
            return value(g.inputs[0])
        if ctrl is Logic.ZERO and ctrl_n is Logic.ONE:
            return Logic.Z
        return Logic.X
    return Logic.X


def explain(g: Gate, netlist: Netlist, value: Callable[[int], Logic]) -> str:
    """La compuerta con sus valores: ``y = ¬(a·b) = ¬(1·0) = 1``."""
    c = analyze(netlist)
    out = c.label(g.output) if g.output >= 0 else "?"
    e = c.elements[g.element]
    text = {Logic.ONE: "1", Logic.ZERO: "0", Logic.X: "X", Logic.Z: "Z"}
    if isinstance(e, Stage):
        numbers = expression(e.pull_down, lambda n: text[value(n)], c)
        numbers = f"{NOT}{numbers}" if g.kind == "INV" else f"{NOT}({numbers})"
        result = text[negate(evaluate(e.pull_down, value, c))]
        net = "pull-up (pMOS)" if result == "1" else "pull-down (nMOS)" if result == "0" else ""
        tail = f": conduce la red {net}" if net else ""
        return f"{out} = {g.expression} = {numbers} = {result}{tail}"
    if isinstance(e, PassGate):
        ctrl = text[value(g.inputs[1])]
        if ctrl == "1":
            return (
                f"{out} = {c.label(g.inputs[0])} = {text[value(g.inputs[0])]} (control en 1: pasa)"
            )
        return f"control {c.label(g.inputs[1])} = {ctrl}: no pasa; {out} conserva su valor"
    return f"{g.expression}"


def symbol_name(kind: str) -> str:
    """Nombre en palabras del tipo de compuerta."""
    return {
        "INV": "inversor",
        "NAND": "NAND",
        "NOR": "NOR",
        "AOI": "AND-OR invertida (AOI)",
        "OAI": "OR-AND invertida (OAI)",
        "COMPLEJA": "compuerta compleja",
        "TG": "transmission gate",
        "RED": "red de transistores",
    }[kind]


# ---------------------------------------------------------------- geometría
GATE_W = 46.0  # cuerpo de INV, NAND y NOR
PIN_GAP = 18.0  # separación entre pines de entrada
STUB = 14.0  # tramo de cable de un pin
BUBBLE = 4.5  # radio del círculo de negación
CAPTION_H = 18.0  # renglón de la fórmula debajo de la compuerta
COL_GAP = 40.0  # espacio mínimo entre columnas, sin contar los carriles
TRACK = 11.0  # separación entre cables verticales dentro de un hueco
LANE = 13.0  # separación entre carriles horizontales bajo las compuertas
ROW_GAP = 30.0  # espacio vertical entre compuertas de una columna
PAD = 22.0  # margen del recuadro
TITLE_H = 36.0
PIN_W = 30.0  # recuadro de un puerto de la celda
BOX_PAD = 12.0  # margen horizontal del texto en una compuerta de recuadro

Measure = Callable[[str], float]


@dataclass(frozen=True, slots=True)
class Box:
    """Una compuerta colocada. ``(x, y)``: esquina superior izquierda del cuerpo."""

    gate: Gate
    x: float
    y: float
    w: float
    h: float

    def pin(self, k: int) -> tuple[float, float]:
        """Punto donde el cable llega al pin de entrada ``k``."""
        n = len(self.gate.inputs)
        top = self.y + (self.h - (n - 1) * PIN_GAP) / 2
        return self.x - STUB, top + k * PIN_GAP

    @property
    def out(self) -> tuple[float, float]:
        """Punto de salida, después del círculo de negación."""
        extra = 2 * BUBBLE if self.gate.inverting else 0.0
        return self.x + self.w + extra + STUB, self.y + self.h / 2


@dataclass(frozen=True, slots=True)
class Port:
    """Un puerto de la celda: ``x`` es el borde donde se conecta el cable."""

    node: int
    name: str
    x: float
    y: float
    output: bool


@dataclass(frozen=True, slots=True)
class Wire:
    x1: float
    y1: float
    x2: float
    y2: float
    node: int


@dataclass(frozen=True, slots=True)
class Dot:
    x: float
    y: float
    node: int


@dataclass
class GateDiagram:
    """Primitivas de la vista de compuertas de una celda, en coordenadas de la celda."""

    boxes: list[Box] = field(default_factory=list)
    ports: list[Port] = field(default_factory=list)
    wires: list[Wire] = field(default_factory=list)
    dots: list[Dot] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0


def _size(g: Gate, measure: Measure) -> tuple[float, float]:
    n = len(g.inputs)
    h = max(34.0, (n - 1) * PIN_GAP + 22)
    if g.kind in ("INV",):
        return 34.0, 30.0
    if g.kind in ("NAND", "NOR"):
        return GATE_W, h
    if g.kind == "TG":
        return 54.0, h
    return max(GATE_W, measure(g.expression) + 2 * BOX_PAD), h


@cache
def _layout_cached(netlist: Netlist, measure: Measure) -> GateDiagram:
    return _layout(netlist, measure)


def layout(netlist: Netlist, measure: Measure) -> GateDiagram:
    """Coloca las compuertas en columnas según el flujo de la señal y tiende los cables.

    Cada red sale de su fuente por un cable vertical en el hueco de la derecha; si llega
    a una columna que no es la siguiente (o vuelve atrás, como en un latch), baja a un
    carril propio debajo de las compuertas y sube en el hueco anterior a su destino. Así
    ningún cable atraviesa una compuerta.
    """
    return _layout_cached(netlist, measure)


def _layout(netlist: Netlist, measure: Measure) -> GateDiagram:
    c = analyze(netlist)
    gates = cell_gates(netlist)
    inputs = list(c.inputs.items())
    outputs = list(c.outputs.items())
    driver: dict[int, int] = {}  # nodo → índice de compuerta
    for k, g in enumerate(gates):
        if g.output >= 0:
            driver.setdefault(g.output, k)
    col: dict[int, int] = {}
    for k, g in enumerate(gates):  # en orden de señal: los lazos se cortan hacia atrás
        col[k] = 1 + max((col[driver[n]] for n in g.inputs if driver.get(n, k) < k), default=0)
    n_cols = max(col.values(), default=0) + 1  # 0: entradas; n_cols: salidas

    # Tamaños y columnas.
    sizes = [_size(g, measure) for g in gates]
    caption_w = [
        measure(f"{c.label(g.output) if g.output >= 0 else ''} = {g.expression}") for g in gates
    ]
    in_w = max((measure(name) for name, _ in inputs), default=0.0) + PIN_W
    columns: dict[int, list[int]] = {}
    for k in range(len(gates)):
        columns.setdefault(col[k], []).append(k)
    col_w = {
        j: max(max(sizes[k][0] + 2 * BUBBLE + 2 * STUB, caption_w[k]) for k in columns[j])
        for j in columns
    }

    # Redes: fuente (columna y punto) y destinos (columna del pin y punto).
    # Un nodo puede tener varias fuentes: dos transmission gates que lo manejan.
    sources: dict[int, list[tuple[int, int]]] = {}  # nodo → (columna, compuerta o -1)
    for _, node in inputs:
        sources[node] = [(0, -1)]
    for k, g in enumerate(gates):
        if g.output >= 0:
            sources.setdefault(g.output, []).append((col[k], k))
    sinks: dict[int, list[tuple[int, int, int]]] = {}  # nodo → (columna, compuerta, pin)
    for k, g in enumerate(gates):
        for p, n in enumerate(g.inputs):
            sinks.setdefault(n, []).append((col[k], k, p))
    for p, (_, node) in enumerate(outputs):
        sinks.setdefault(node, []).append((n_cols, -1, p))

    # Huecos (gap j está entre la columna j y la j + 1) y carriles.
    gap_nets: dict[int, list[int]] = {}
    lanes: list[int] = []
    for node, dests in sinks.items():
        if node not in sources:
            continue
        gaps = {j for j, _ in sources[node]} | {d[0] - 1 for d in dests}
        for j in sorted(gaps):
            gap_nets.setdefault(j, []).append(node)
        if len(gaps) > 1:
            lanes.append(node)
    gap_w = {j: COL_GAP + TRACK * len(gap_nets.get(j, [])) for j in range(n_cols)}

    # Posiciones x de las columnas.
    x = PAD + in_w
    col_x: dict[int, float] = {0: x}
    for j in range(1, n_cols + 1):
        x += gap_w[j - 1]
        col_x[j] = x
        x += col_w.get(j, 0.0)
    out_w = max((measure(name) for name, _ in outputs), default=0.0) + PIN_W
    width = col_x[n_cols] + out_w + PAD

    # Posiciones y: cada columna centrada respecto de la más alta.
    def stack_h(ks: list[int]) -> float:
        return sum(sizes[k][1] + CAPTION_H for k in ks) + ROW_GAP * (len(ks) - 1)

    tallest = max(
        [stack_h(ks) for ks in columns.values()] + [len(inputs) * 36.0, len(outputs) * 36.0, 60.0]
    )
    top = TITLE_H + PAD
    d = GateDiagram()
    boxes: dict[int, Box] = {}
    for j, ks in columns.items():
        y = top + (tallest - stack_h(ks)) / 2
        for k in ks:
            w, h = sizes[k]
            x0 = col_x[j] + STUB
            boxes[k] = Box(gates[k], x0, y, w, h)
            y += h + CAPTION_H + ROW_GAP
    d.boxes = [boxes[k] for k in range(len(gates))]

    def port_ys(n: int) -> list[float]:
        span = (n - 1) * 36.0
        return [top + (tallest - span) / 2 + i * 36.0 for i in range(n)]

    in_point: dict[int, tuple[float, float]] = {}
    for (name, node), y in zip(inputs, port_ys(len(inputs)), strict=True):
        d.ports.append(Port(node, name, col_x[0], y, False))
        in_point[node] = (col_x[0], y)
    out_ys = port_ys(len(outputs))
    for (name, node), y in zip(outputs, out_ys, strict=True):
        d.ports.append(Port(node, name, col_x[n_cols], y, True))

    # Cables.
    track_x: dict[tuple[int, int], float] = {}
    for j, nets in gap_nets.items():
        start = col_x[j] + (col_w.get(j, 0.0) if j > 0 else 0.0)
        for i, node in enumerate(nets):
            track_x[(j, node)] = start + COL_GAP / 2 + i * TRACK
    lane_y = {node: top + tallest + 14 + i * LANE for i, node in enumerate(lanes)}

    def add(x1: float, y1: float, x2: float, y2: float, node: int) -> None:
        if abs(x1 - x2) > 0.01 or abs(y1 - y2) > 0.01:
            d.wires.append(Wire(x1, y1, x2, y2, node))

    for node, dests in sinks.items():
        if node not in sources:
            continue
        verticals: dict[int, list[float]] = {}
        for sj, k in sources[node]:
            sx, sy = boxes[k].out if k >= 0 else in_point[node]
            verticals.setdefault(sj, []).append(sy)
            add(sx, sy, track_x[(sj, node)], sy, node)
        for dj, k, p in dests:
            gap = dj - 1
            px, py = boxes[k].pin(p) if k >= 0 else (col_x[n_cols], out_ys[p])
            verticals.setdefault(gap, []).append(py)
            add(track_x[(gap, node)], py, px, py, node)
        if node in lane_y:
            ly = lane_y[node]
            xs = [track_x[(j, node)] for j in verticals]
            add(min(xs), ly, max(xs), ly, node)
            for j in verticals:
                verticals[j].append(ly)
            for xv in xs:
                if min(xs) < xv < max(xs):
                    d.dots.append(Dot(xv, ly, node))
        for j, ys in verticals.items():
            xv = track_x[(j, node)]
            lo, hi = min(ys), max(ys)
            add(xv, lo, xv, hi, node)
            for yv in ys:
                if lo < yv < hi:
                    d.dots.append(Dot(xv, yv, node))
    d.width = width
    d.height = top + tallest + (14 + LANE * len(lanes) if lanes else 0.0) + PAD
    return d


__all__ = [
    "Box",
    "Dot",
    "Gate",
    "GateDiagram",
    "Port",
    "Wire",
    "cell_gates",
    "evaluate",
    "explain",
    "expression",
    "gate_value",
    "layout",
    "negate",
    "symbol_name",
]
