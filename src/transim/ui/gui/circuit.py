"""Estructura de una celda CMOS para dibujarla: etapas, redes serie-paralelo y pases.

Las vistas de la pestaña de transistores no dibujan los transistores sueltos: los
agrupan como en un libro de diseño CMOS (Weste y Harris, 2011). Una **etapa** es una
red pull-up de pMOS entre VDD y una salida y una red pull-down de nMOS entre esa salida
y GND. Si una red se reduce a combinaciones serie y paralelo, se guarda como árbol
(:class:`Series`, :class:`Parallel`, :class:`Leaf`). Una **transmission gate** (nMOS y
pMOS en paralelo entre dos nodos de señal) es un elemento de paso aparte.

Este módulo no depende de Qt: lo usan el esquema, el layout y las pruebas.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from typing import Protocol

from transim.core.netlist import Instance, Netlist
from transim.core.node import Node, NodeKind
from transim.core.signals import Logic
from transim.core.transistor import Conduction, Transistor, TransistorType


# ------------------------------------------------------------------ árboles SP
@dataclass(frozen=True, slots=True)
class Leaf:
    """Un transistor dentro de una red, orientado de ``top`` a ``bottom``."""

    index: int
    top: int
    bottom: int


@dataclass(frozen=True, slots=True)
class Series:
    """Partes en serie, de arriba abajo: ``parts[i].bottom == parts[i + 1].top``."""

    parts: tuple[Tree, ...]
    top: int
    bottom: int


@dataclass(frozen=True, slots=True)
class Parallel:
    """Partes en paralelo entre los mismos dos nodos."""

    parts: tuple[Tree, ...]
    top: int
    bottom: int


Tree = Leaf | Series | Parallel


def flip(tree: Tree) -> Tree:
    """El mismo árbol orientado al revés (``top`` ↔ ``bottom``)."""
    if isinstance(tree, Leaf):
        return Leaf(tree.index, tree.bottom, tree.top)
    if isinstance(tree, Series):
        return Series(tuple(flip(p) for p in reversed(tree.parts)), tree.bottom, tree.top)
    return Parallel(tuple(flip(p) for p in tree.parts), tree.bottom, tree.top)


def leaves(tree: Tree) -> list[int]:
    """Índices de los transistores del árbol, en orden de dibujo."""
    if isinstance(tree, Leaf):
        return [tree.index]
    return [i for p in tree.parts for i in leaves(p)]


def conducts(tree: Tree, state: Sequence[Conduction]) -> Conduction:
    """Si el árbol conecta sus extremos, según el estado de cada transistor."""
    if isinstance(tree, Leaf):
        return state[tree.index]
    parts = [conducts(p, state) for p in tree.parts]
    if isinstance(tree, Series):
        if all(c is Conduction.ON for c in parts):
            return Conduction.ON
        return Conduction.OFF if Conduction.OFF in parts else Conduction.UNKNOWN
    if Conduction.ON in parts:
        return Conduction.ON
    return Conduction.UNKNOWN if Conduction.UNKNOWN in parts else Conduction.OFF


def active_path(tree: Tree, state: Sequence[Conduction]) -> set[int]:
    """Transistores que forman el camino conductor entre los extremos (vacío si no hay)."""
    if conducts(tree, state) is not Conduction.ON:
        return set()
    if isinstance(tree, Leaf):
        return {tree.index}
    return set().union(*(active_path(p, state) for p in tree.parts))


def reduce_sp(edges: list[Tree], top: int, bottom: int, keep: set[int]) -> Tree | None:
    """Reduce una red de dos terminales a un árbol serie-paralelo.

    Args:
        edges: un :class:`Leaf` por transistor de la red.
        top, bottom: nodos terminales (por ejemplo VDD y la salida).
        keep: nodos que no pueden desaparecer en una serie (usados fuera de la red).

    Returns:
        El árbol orientado de ``top`` a ``bottom``, o None si la red no es serie-paralelo.
    """
    edges = list(edges)
    if not edges:
        return None
    changed = True
    while changed and len(edges) > 1:
        changed = False
        # Paralelo: partes con los mismos dos extremos.
        groups: dict[frozenset[int], list[Tree]] = {}
        for e in edges:
            groups.setdefault(frozenset((e.top, e.bottom)), []).append(e)
        merged: list[Tree] = []
        for group in groups.values():
            if len(group) == 1:
                merged.append(group[0])
                continue
            u, v = group[0].top, group[0].bottom
            parts: list[Tree] = []
            for e in group:
                e = e if e.top == u else flip(e)
                parts.extend(e.parts if isinstance(e, Parallel) else [e])
            merged.append(Parallel(tuple(parts), u, v))
            changed = True
        edges = merged
        # Serie: un nodo interno con exactamente dos partes.
        degree: dict[int, list[Tree]] = {}
        for e in edges:
            for n in (e.top, e.bottom):
                degree.setdefault(n, []).append(e)
        for node, incident in degree.items():
            if node in (top, bottom) or node in keep or len(incident) != 2:
                continue
            e1, e2 = incident
            if e1 is e2:
                continue
            e1 = e1 if e1.bottom == node else flip(e1)
            e2 = e2 if e2.top == node else flip(e2)
            parts = [
                *(e1.parts if isinstance(e1, Series) else [e1]),
                *(e2.parts if isinstance(e2, Series) else [e2]),
            ]
            edges = [e for e in edges if e is not incident[0] and e is not incident[1]]
            edges.append(Series(tuple(parts), e1.top, e2.bottom))
            changed = True
            break
    if len(edges) != 1 or {edges[0].top, edges[0].bottom} != {top, bottom}:
        return None
    return edges[0] if edges[0].top == top else flip(edges[0])


# ------------------------------------------------------------------ elementos
@dataclass(frozen=True, slots=True)
class Stage:
    """Etapa CMOS: pull-up de VDD a ``output`` y pull-down de ``output`` a GND."""

    output: int
    pull_up: Tree
    pull_down: Tree

    @property
    def transistors(self) -> list[int]:
        return leaves(self.pull_up) + leaves(self.pull_down)

    @property
    def is_inverter(self) -> bool:
        return isinstance(self.pull_up, Leaf) and isinstance(self.pull_down, Leaf)


@dataclass(frozen=True, slots=True)
class PassGate:
    """Transmission gate: ``n`` y ``p`` en paralelo entre ``left`` y ``right``."""

    n: int
    p: int
    left: int
    right: int

    @property
    def transistors(self) -> list[int]:
        return [self.n, self.p]


@dataclass(frozen=True, slots=True)
class Loose:
    """Transistores que no forman una etapa reconocible: se dibujan sueltos."""

    indices: tuple[int, ...]

    @property
    def transistors(self) -> list[int]:
        return list(self.indices)


Element = Stage | PassGate | Loose


@dataclass
class CellCircuit:
    """Una celda analizada.

    Attributes:
        name: nombre de la definición (``"NAND2"``).
        transistors: transistores de la definición, en su orden.
        nodes: nodos de la definición por id.
        inputs, outputs: puerto → id de nodo.
        elements: etapas, transmission gates y grupos sueltos, en orden de señal.
        gate_nets: ids de nodo que llegan a alguna compuerta.
    """

    name: str
    transistors: list[Transistor]
    nodes: dict[int, Node]
    inputs: dict[str, int]
    outputs: dict[str, int]
    elements: list[Element] = field(default_factory=list)
    gate_nets: set[int] = field(default_factory=set)

    def label(self, node: int) -> str:
        """Nombre del nodo para mostrar (los rieles, en mayúsculas)."""
        n = self.nodes[node]
        if n.kind is NodeKind.VDD:
            return "VDD"
        if n.kind is NodeKind.GND:
            return "GND"
        return n.name

    def is_port(self, node: int) -> bool:
        return node in self.inputs.values() or node in self.outputs.values()

    def is_rail(self, node: int) -> bool:
        return self.nodes[node].kind in (NodeKind.VDD, NodeKind.GND)


def _pass_gates(ts: list[Transistor], rails: set[int]) -> tuple[list[PassGate], set[int]]:
    """Empareja nMOS y pMOS con los mismos extremos de canal, ninguno un riel."""
    found: list[PassGate] = []
    used: set[int] = set()
    by_ends: dict[frozenset[int], list[Transistor]] = {}
    for t in ts:
        ends = frozenset((t.source.id, t.drain.id))
        if ends & rails:
            continue
        by_ends.setdefault(ends, []).append(t)
    for group in by_ends.values():
        ns = [t for t in group if t.kind is TransistorType.NMOS]
        ps = [t for t in group if t.kind is TransistorType.PMOS]
        for n, p in zip(ns, ps, strict=False):
            found.append(PassGate(n.id, p.id, n.source.id, n.drain.id))
            used |= {n.id, p.id}
    return found, used


def _components(ts: list[Transistor], rails: set[int]) -> list[list[Transistor]]:
    """Grupos de transistores unidos por sus canales sin pasar por los rieles."""
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for t in ts:
        ends = [n.id for n in (t.source, t.drain) if n.id not in rails]
        for n in ends:
            find(n)
        if len(ends) == 2:
            parent[find(ends[0])] = find(ends[1])
    groups: dict[int, list[Transistor]] = {}
    for t in ts:
        ends = [n.id for n in (t.source, t.drain) if n.id not in rails]
        key = find(ends[0]) if ends else -1 - t.id
        groups.setdefault(key, []).append(t)
    return list(groups.values())


def _stage(group: list[Transistor], vdd: int, gnd: int, keep: set[int]) -> Stage | None:
    """Etapa CMOS formada por ``group``, si la tiene."""
    p_nodes = {n.id for t in group if t.kind is TransistorType.PMOS for n in (t.source, t.drain)}
    n_nodes = {n.id for t in group if t.kind is TransistorType.NMOS for n in (t.source, t.drain)}
    outputs = (p_nodes & n_nodes) - {vdd, gnd}
    if len(outputs) != 1:
        return None
    out = outputs.pop()
    edges_p: list[Tree] = [
        Leaf(t.id, t.source.id, t.drain.id) for t in group if t.kind is TransistorType.PMOS
    ]
    edges_n: list[Tree] = [
        Leaf(t.id, t.source.id, t.drain.id) for t in group if t.kind is TransistorType.NMOS
    ]
    up = reduce_sp(edges_p, vdd, out, keep)
    down = reduce_sp(edges_n, out, gnd, keep)
    if up is None or down is None:
        return None
    return Stage(out, up, down)


def _inputs_of(e: Element, ts: list[Transistor]) -> set[int]:
    """Nodos de los que depende un elemento: sus compuertas y la entrada de un pase."""
    gates = {ts[i].gate.id for i in e.transistors}
    return gates | ({e.left} if isinstance(e, PassGate) else set())


def _outputs_of(e: Element, ts: list[Transistor], rails: set[int]) -> set[int]:
    if isinstance(e, Stage):
        return {e.output}
    if isinstance(e, PassGate):
        return {e.right}
    return {n.id for i in e.indices for n in (ts[i].source, ts[i].drain)} - rails


def _signal_order(elements: list[Element], ts: list[Transistor], rails: set[int]) -> list[Element]:
    """Orden topológico por dependencia de señal (los lazos se cortan en profundidad)."""
    driver: dict[int, int] = {}
    for k, e in enumerate(elements):
        for n in _outputs_of(e, ts, rails):
            driver.setdefault(n, k)
    order: list[int] = []
    state: dict[int, int] = {}

    def visit(k: int) -> None:
        state[k] = 1
        for n in sorted(_inputs_of(elements[k], ts)):
            d = driver.get(n)
            if d is not None and d != k and state.get(d, 0) == 0:
                visit(d)
        state[k] = 2
        order.append(k)

    for k in range(len(elements)):
        if state.get(k, 0) == 0:
            visit(k)
    return [elements[k] for k in order]


def _orient_pass_gates(
    elements: list[Element], ts: list[Transistor], inputs: set[int], rails: set[int]
) -> list[Element]:
    """Pone a la izquierda de cada transmission gate el extremo que viene de antes:
    una entrada de la celda o la salida de una etapa."""
    driven = {n for e in elements if isinstance(e, Stage) for n in _outputs_of(e, ts, rails)}
    out: list[Element] = []
    for e in elements:
        if isinstance(e, PassGate) and e.left not in driven | inputs and e.right in driven | inputs:
            e = PassGate(e.n, e.p, e.right, e.left)
        out.append(e)
    return out


def analyze(netlist: Netlist) -> CellCircuit:
    """Analiza una celda primitiva (sin sub-instancias) para dibujarla."""
    return _analyze(netlist)


@cache
def _analyze(netlist: Netlist) -> CellCircuit:
    ts = list(netlist.transistors)
    vdd, gnd = netlist.vdd.id, netlist.gnd.id
    rails = {vdd, gnd}
    circuit = CellCircuit(
        name=netlist.name,
        transistors=ts,
        nodes={n.id: n for n in netlist.nodes},
        inputs={p: n.id for p, n in netlist.inputs.items()},
        outputs={p: n.id for p, n in netlist.outputs.items()},
        gate_nets={t.gate.id for t in ts},
    )
    gates, used = _pass_gates(ts, rails)
    rest = [t for t in ts if t.id not in used]
    elements: list[Element] = list(gates)
    keep = circuit.gate_nets | set(circuit.inputs.values()) | set(circuit.outputs.values())
    keep |= {e.left for e in gates} | {e.right for e in gates}
    for group in _components(rest, rails):
        stage = _stage(group, vdd, gnd, keep)
        elements.append(stage if stage is not None else Loose(tuple(t.id for t in group)))
    elements = _orient_pass_gates(elements, ts, set(circuit.inputs.values()), rails)
    circuit.elements = _signal_order(elements, ts, rails)
    return circuit


# ------------------------------------------------------------- estado en vivo
@dataclass(frozen=True, slots=True)
class Binding:
    """Une una definición de celda con sus nodos reales en un netlist.

    ``nodes[i]`` es el nodo real del nodo ``i`` de la definición; ``transistors[k]`` el
    transistor real del transistor ``k``. Para una celda dibujada sola, son los mismos.
    """

    circuit: CellCircuit
    netlist: Netlist
    nodes: dict[int, Node]
    transistors: list[Transistor]
    path: str = ""

    def value(self, values: ValueReader, node: int) -> Logic:
        return values.value(self.nodes[node])

    def state(self, values: ValueReader) -> list[Conduction]:
        return [values.conduction(t) for t in self.transistors]


class ValueReader(Protocol):
    """Lo que las vistas leen del motor: el valor de un nodo y el estado de un canal."""

    def value(self, node: Node) -> Logic: ...

    def conduction(self, transistor: Transistor) -> Conduction: ...


def bind_cell(netlist: Netlist) -> Binding:
    """Una celda de la biblioteca dibujada sola."""
    nodes = {n.id: n for n in netlist.nodes}
    return Binding(analyze(netlist), netlist, nodes, list(netlist.transistors))


def bind_instance(inst: Instance) -> Binding:
    """Una celda instanciada dentro de una unidad."""
    circuit = analyze(inst.definition)
    nodes: dict[int, Node] = {}
    for d, real in zip(inst.definition.transistors, inst.transistors, strict=True):
        for a, b in ((d.gate, real.gate), (d.source, real.source), (d.drain, real.drain)):
            nodes[a.id] = b
    return Binding(circuit, inst.definition, nodes, list(inst.transistors), inst.path)


__all__ = [
    "Binding",
    "CellCircuit",
    "Element",
    "Leaf",
    "Loose",
    "Parallel",
    "PassGate",
    "Series",
    "Stage",
    "Tree",
    "ValueReader",
    "active_path",
    "analyze",
    "bind_cell",
    "bind_instance",
    "conducts",
    "flip",
    "leaves",
    "reduce_sp",
]
