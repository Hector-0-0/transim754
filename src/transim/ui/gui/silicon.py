"""Layout físico ilustrativo de una celda: cómo se vería en el silicio, visto desde arriba.

Se genera a partir del netlist con las reglas de una celda estándar CMOS (Weste y
Harris, 2011, cap. 1.5):

- La celda tiene una altura fija, el riel VDD (metal 1) arriba y GND abajo; así las
  celdas se pueden poner una al lado de otra en filas, como en un chip.
- Los pMOS van en una franja de difusión p+ dentro del pozo n (arriba) y los nMOS en
  una franja de difusión n+ sobre el sustrato p (abajo). Un pMOS y un nMOS con la misma
  compuerta comparten una columna de polisilicio, que cruza las dos franjas.
- Las columnas se ordenan para que transistores vecinos **compartan difusión** (el
  nodo entre dos transistores en serie no necesita contacto), como en el método de
  caminos de Euler.
- Las conexiones usan contactos, metal 1 (vertical) y metal 2 (horizontal, en pistas
  entre las dos franjas) con vías.

Es un layout **ilustrativo**: respeta la conectividad del netlist (lo verifica
:func:`check`, una comparación layout-netlist simplificada) pero no las reglas de diseño
de un proceso real ni sus medidas. No cambia la simulación, que es de nivel de
interruptor (ADR-0007). Unidades: píxeles a zoom 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

from transim.core.netlist import Netlist
from transim.core.node import NodeKind
from transim.core.transistor import TransistorType
from transim.ui.gui.circuit import CellCircuit, PassGate, analyze

# Medidas (px a zoom 1)
POLY_W = 6.0
CONTACT = 6.0
ENCLOSE = 5.0  # difusión alrededor de un contacto
SHARED = 9.0  # difusión compartida sin contacto entre dos compuertas
WITH_CONTACT = ENCLOSE + CONTACT + ENCLOSE  # difusión con contacto
DIFF_SPACE = 12.0  # separación entre dos franjas de difusión
ENDCAP = 6.0  # polisilicio que sobresale de la difusión
METAL_W = 9.0
PAD = 10.0  # cuadrado de metal 1 sobre un contacto de polisilicio
PITCH = 13.0  # separación de pistas de metal 2
RAIL_H = 12.0
P_TOP = 24.0  # borde superior de la difusión p
P_H = 27.0  # ancho de los pMOS (más anchos que los nMOS)
N_H = 16.0
CHANNEL_MARGIN = 13.0
EDGE = 7.0  # margen lateral de la celda

LAYERS = ("nwell", "pdiff", "ndiff", "poly", "channel", "contact", "metal1", "via", "metal2")
"""Capas, en el orden en que se pintan."""

CONDUCTING = ("pdiff", "ndiff", "poly", "metal1", "metal2")


@dataclass(frozen=True, slots=True)
class Shape:
    """Un rectángulo de una capa.

    ``node`` es el nodo de la definición al que pertenece (None para el pozo).
    ``transistor`` es el índice del transistor en la capa ``channel``.
    """

    layer: str
    x0: float
    y0: float
    x1: float
    y1: float
    node: int | None = None
    transistor: int | None = None

    def overlaps(self, other: Shape) -> bool:
        return (
            self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1
        )

    def touches(self, other: Shape) -> bool:
        return (
            self.x0 <= other.x1
            and other.x0 <= self.x1
            and self.y0 <= other.y1
            and other.y0 <= self.y1
        )


@dataclass(frozen=True, slots=True)
class Pin:
    """Nombre de un puerto sobre su metal."""

    text: str
    x: float
    y: float
    node: int


@dataclass
class Layout:
    """Layout de una celda."""

    circuit: CellCircuit
    width: float
    height: float
    shapes: list[Shape] = field(default_factory=list)
    pins: list[Pin] = field(default_factory=list)
    columns: list[tuple[int | None, int | None]] = field(default_factory=list)
    """(pMOS, nMOS) de cada columna de polisilicio, de izquierda a derecha."""
    well_bottom: float = 0.0
    tracks: int = 0
    """Pistas de metal 2 del canal central."""

    def layer(self, name: str) -> list[Shape]:
        return [s for s in self.shapes if s.layer == name]


# ------------------------------------------------------------ columnas
@dataclass(frozen=True, slots=True)
class _Column:
    p: int | None
    n: int | None
    element: int


def _pairs(c: CellCircuit) -> list[_Column]:
    """Columnas de polisilicio: un pMOS y un nMOS de la misma etapa con la misma compuerta."""
    cols: list[_Column] = []
    ts = c.transistors
    for k, e in enumerate(c.elements):
        if isinstance(e, PassGate):
            cols.append(_Column(e.p, e.n, k))
            continue
        idx = e.transistors
        ps = [i for i in idx if ts[i].kind is TransistorType.PMOS]
        ns = [i for i in idx if ts[i].kind is TransistorType.NMOS]
        free = list(ns)
        for p in ps:
            match = next((n for n in free if ts[n].gate.id == ts[p].gate.id), None)
            if match is None and free:
                match = free[0]
            if match is not None:
                free.remove(match)
            cols.append(_Column(p, match, k))
        cols.extend(_Column(None, n, k) for n in free)
    return cols


@dataclass(frozen=True, slots=True)
class _Placed:
    col: _Column
    p_ends: tuple[int, int] | None  # (izquierda, derecha) de la difusión p
    n_ends: tuple[int, int] | None


def _ends(c: CellCircuit, index: int | None, flip: bool) -> tuple[int, int] | None:
    if index is None:
        return None
    t = c.transistors[index]
    a, b = t.source.id, t.drain.id
    return (b, a) if flip else (a, b)


def _order(c: CellCircuit, cols: list[_Column], beam: int = 80) -> list[_Placed]:
    """Ordena y orienta las columnas para compartir la mayor cantidad de difusión."""
    rails = {n for n, node in c.nodes.items() if node.kind in (NodeKind.VDD, NodeKind.GND)}

    def options(col: _Column) -> list[_Placed]:
        out = []
        for fp in (False, True) if col.p is not None else (False,):
            for fn in (False, True) if col.n is not None else (False,):
                out.append(_Placed(col, _ends(c, col.p, fp), _ends(c, col.n, fn)))
        return out

    def gain(prev: _Placed | None, nxt: _Placed) -> float:
        score = 0.0
        if prev is None:
            for ends in (nxt.p_ends, nxt.n_ends):
                if ends is not None and ends[0] in rails:
                    score += 0.5  # la franja empieza en un riel
            return score
        for a, b in ((prev.p_ends, nxt.p_ends), (prev.n_ends, nxt.n_ends)):
            if a is not None and b is not None and a[1] == b[0]:
                score += 10.0
        if prev.col.element == nxt.col.element:
            score += 1.0
        return score

    states: list[tuple[float, tuple[_Placed, ...], frozenset[int]]] = [(0.0, (), frozenset())]
    for _ in cols:
        nxt_states: dict[tuple[frozenset[int], object, object], tuple[float, tuple[_Placed, ...]]]
        nxt_states = {}
        for score, seq, used in states:
            last = seq[-1] if seq else None
            for k, col in enumerate(cols):
                if k in used:
                    continue
                for placed in options(col):
                    s = score + gain(last, placed)
                    key = (
                        used | {k},
                        placed.p_ends[1] if placed.p_ends else None,
                        placed.n_ends[1] if placed.n_ends else None,
                    )
                    if key not in nxt_states or nxt_states[key][0] < s:
                        nxt_states[key] = (s, (*seq, placed))
        ranked = sorted(nxt_states.items(), key=lambda kv: -kv[1][0])[:beam]
        states = [(s, seq, key[0]) for key, (s, seq) in ranked]
    return list(states[0][1]) if states else []


# ------------------------------------------------------------ generador
@dataclass
class _Row:
    """Una franja (p o n) de una columna: el transistor y sus nodos izquierdo y derecho."""

    index: int | None
    left: int | None
    right: int | None


def _needs_contact(c: CellCircuit, node: int, regions: dict[int, int]) -> bool:
    """Un nodo entre dos transistores en serie, que no sale de esa difusión, no necesita
    contacto: queda conectado por la propia difusión compartida."""
    if c.is_rail(node) or c.is_port(node) or node in c.gate_nets:
        return True
    return regions.get(node, 0) > 1


def build(netlist: Netlist, tracks: int | None = None) -> Layout:
    """Layout de una celda primitiva. ``tracks`` fija el número de pistas de metal 2 (por
    defecto, el máximo de la biblioteca, para que todas las celdas tengan la misma altura)."""
    return _build(netlist, standard_tracks() if tracks is None else tracks)


@cache
def standard_tracks() -> int:
    """Pistas necesarias por la celda más exigente de la biblioteca."""
    from transim.cells.library import CELLS

    leaves = [b() for b in CELLS.values() if not b().instances]
    return max(_natural_tracks(nl) for nl in leaves)


@cache
def _natural_tracks(netlist: Netlist) -> int:
    return _build(netlist, 0).tracks


Region = tuple[int | None, int | None, int]
"""Región de difusión: (columna a su izquierda, columna a su derecha, nodo); None en los
extremos de una franja."""


def _row_regions(order: list[_Placed], row: str) -> list[Region]:
    """Regiones de difusión de una fila, de izquierda a derecha."""
    out: list[Region] = []
    prev: tuple[int, int] | None = None
    for k, pl in enumerate(order):
        ends = pl.p_ends if row == "p" else pl.n_ends
        if ends is None:
            if prev is not None:
                out.append((k - 1, None, prev[1]))
            prev = None
            continue
        if prev is not None and prev[1] == ends[0]:
            out.append((k - 1, k, ends[0]))
        else:
            if prev is not None:
                out.append((k - 1, None, prev[1]))
            out.append((None, k, ends[0]))
        prev = ends
    if prev is not None:
        out.append((len(order) - 1, None, prev[1]))
    return out


@cache
def _plan(netlist: Netlist) -> tuple[list[_Placed], dict[str, list[Region]], list[float], set[int]]:
    """Orden de las columnas, regiones de cada fila, x de cada columna y nodos con contacto."""
    c = analyze(netlist)
    order = _order(c, _pairs(c))
    regions = {row: _row_regions(order, row) for row in ("p", "n")}
    count: dict[int, int] = {}
    for rs in regions.values():
        for _, _, node in rs:
            count[node] = count.get(node, 0) + 1
    contacts = {n for n in count if _needs_contact(c, n, count)}

    def width(node: int) -> float:
        return WITH_CONTACT if node in contacts else SHARED

    xs: list[float] = []
    x = EDGE
    for k in range(len(order)):
        gap = SHARED
        for rs in regions.values():
            need = 0.0
            for left, right, node in rs:
                if right == k and left == k - 1 and left is not None:
                    need = width(node)  # compartida
                elif right == k and left is None:
                    need += width(node)  # comienzo de franja
                elif left == k - 1 and right is None and k > 0:
                    need += width(node) + DIFF_SPACE  # fin de la franja anterior
            gap = max(gap, need)
        x += gap
        xs.append(x)
        x += POLY_W
    return order, regions, xs, contacts


UP = ("p", "gp")
"""Pines que llegan al canal de pistas desde arriba (difusión p o polisilicio superior)."""


def _subnets(
    pins: dict[int, list[tuple[float, str]]],
) -> tuple[dict[tuple[int, int], list[tuple[float, str]]], dict[tuple[int, int], int], set[int]]:
    """Asigna pistas de metal 2 (algoritmo del borde izquierdo con restricciones
    verticales). Si las restricciones forman un ciclo (dos transmission gates con las
    compuertas cruzadas, como en un MUX), el nodo se parte en dos pistas unidas por un
    tramo vertical al costado de la celda (un *dogleg*).

    Returns:
        (pines de cada subred, pista de cada subred, nodos partidos).
    """
    split: set[int] = set()
    while True:
        subs: dict[tuple[int, int], list[tuple[float, str]]] = {}
        for node, ps in pins.items():
            if node in split:
                subs[(node, 1)] = [p for p in ps if p[1] in UP]
                subs[(node, 2)] = [p for p in ps if p[1] not in UP]
            else:
                subs[(node, 0)] = ps
        tracks, stuck = _left_edge(subs, split)
        if not stuck:
            return subs, tracks, split
        candidates = [
            k[0]
            for k in stuck
            if k[1] == 0
            and any(p[1] in UP for p in subs[k])
            and any(p[1] not in UP for p in subs[k])
        ]
        if not candidates:
            return subs, tracks, split
        split.add(candidates[0])


def _left_edge(
    subs: dict[tuple[int, int], list[tuple[float, str]]], split: set[int]
) -> tuple[dict[tuple[int, int], int], list[tuple[int, int]]]:
    above: dict[tuple[int, int], set[tuple[int, int]]] = {k: set() for k in subs}
    for a, pa in subs.items():
        for b, pb in subs.items():
            if a[0] == b[0]:
                continue
            if any(
                abs(xa - xb) < METAL_W and ka in UP and kb not in UP and kb != "g"
                for xa, ka in pa
                for xb, kb in pb
            ):
                above[b].add(a)
    for node in split:  # la parte superior va arriba de la inferior
        above[(node, 2)].add((node, 1))
    reach = max((x for ps in subs.values() for x, _ in ps), default=0.0) + 100.0
    span = {}
    for k, ps in subs.items():
        lo, hi = min(x for x, _ in ps), max(x for x, _ in ps)
        if k[0] in split:
            hi = reach
        span[k] = (lo - METAL_W, hi + METAL_W)
    track: dict[tuple[int, int], int] = {}
    level = 0
    while len(track) < len(subs):
        ready = [k for k in subs if k not in track and above[k] <= set(track)]
        if not ready:
            return track, [k for k in subs if k not in track]
        ready.sort(key=lambda k: span[k][0])
        end = float("-inf")
        for k in ready:
            if span[k][0] > end and all(track[a] < level for a in above[k]):
                track[k] = level
                end = span[k][1]
        level += 1
    return track, []


@cache
def _build(netlist: Netlist, tracks: int) -> Layout:
    c = analyze(netlist)
    order, regions, xs, contacts = _plan(netlist)

    def width(node: int) -> float:
        return WITH_CONTACT if node in contacts else SHARED

    # ---------------------------------------------- regiones con su x
    diff: list[tuple[str, float, float, int]] = []
    for row, rs in regions.items():
        for left, right, node in rs:
            if left is None:
                assert right is not None
                x0, x1 = xs[right] - width(node), xs[right]
            elif right is None:
                x0, x1 = xs[left] + POLY_W, xs[left] + POLY_W + width(node)
            else:
                x0, x1 = xs[left] + POLY_W, xs[right]
            diff.append((row, x0, x1, node))

    # ---------------------------------------------- pines por nodo
    # (x, tipo): "p"/"n" contacto en difusión p/n; "g" polisilicio de columna completa;
    # "gp"/"gn" polisilicio solo arriba / solo abajo.
    pins: dict[int, list[tuple[float, str]]] = {}
    for row, x0, x1, node in diff:
        if node in contacts and not c.is_rail(node):
            pins.setdefault(node, []).append(((x0 + x1) / 2, row))
    gates: list[tuple[int | None, int | None]] = []
    for k, pl in enumerate(order):
        cx = xs[k] + POLY_W / 2
        gp = c.transistors[pl.col.p].gate.id if pl.col.p is not None else None
        gn = c.transistors[pl.col.n].gate.id if pl.col.n is not None else None
        gates.append((gp, gn))
        if gp is not None and gp == gn:
            pins.setdefault(gp, []).append((cx, "g"))
        else:
            if gp is not None:
                pins.setdefault(gp, []).append((cx, "gp"))
            if gn is not None:
                pins.setdefault(gn, []).append((cx, "gn"))
    routed = {n: ps for n, ps in pins.items() if len({round(x, 2) for x, _ in ps}) > 1}
    subs, track_of, split = _subnets(routed)
    used = max(track_of.values(), default=-1) + 1
    tracks = max(tracks, used)

    def sub_of(node: int, kind: str) -> tuple[int, int] | None:
        if node not in routed:
            return None
        if node in split:
            return (node, 1) if kind in UP else (node, 2)
        return (node, 0)

    # ---------------------------------------------- medidas verticales
    p0, p1 = P_TOP, P_TOP + P_H
    ch0 = p1 + CHANNEL_MARGIN
    ch1 = ch0 + max(tracks, 1) * PITCH
    n0 = ch1 + CHANNEL_MARGIN
    n1 = n0 + N_H
    height = n1 + P_TOP
    x_end = max([x1 for _, _, x1, _ in diff] + [EDGE])
    jogs = {
        node: x_end + 7 + METAL_W / 2 + k * (METAL_W + 7) for k, node in enumerate(sorted(split))
    }
    width_cell = (max(jogs.values()) + METAL_W / 2 if jogs else x_end) + EDGE
    mid = (ch0 + ch1) / 2
    vdd, gnd = _rail(c, NodeKind.VDD), _rail(c, NodeKind.GND)

    def ty(key: tuple[int, int]) -> float:
        return ch0 + PITCH / 2 + track_of[key] * PITCH

    out = Layout(
        c, width_cell, height, columns=[(pl.col.p, pl.col.n) for pl in order], tracks=tracks
    )
    out.well_bottom = (p1 + n0) / 2
    add = out.shapes.append
    add(Shape("nwell", 0.0, 0.0, width_cell, out.well_bottom))
    add(Shape("metal1", 0.0, 0.0, width_cell, RAIL_H, vdd))
    add(Shape("metal1", 0.0, height - RAIL_H, width_cell, height, gnd))
    half = METAL_W / 2

    # Difusión, contactos y su metal 1
    for row, x0, x1, node in diff:
        y0, y1 = (p0, p1) if row == "p" else (n0, n1)
        add(Shape("pdiff" if row == "p" else "ndiff", x0, y0, x1, y1, node))
        if node not in contacts:
            continue
        cx = (x0 + x1) / 2
        n_contacts = 2 if row == "p" else 1
        cys = [y0 + ENCLOSE + k * (CONTACT + 4) for k in range(n_contacts)]
        for cy in cys:
            add(Shape("contact", cx - CONTACT / 2, cy, cx + CONTACT / 2, cy + CONTACT, node))
        top, bottom = cys[0] - 1, cys[-1] + CONTACT + 1
        key = sub_of(node, row)
        if node == vdd:
            add(Shape("metal1", cx - half, RAIL_H - 1, cx + half, bottom, node))
        elif node == gnd:
            add(Shape("metal1", cx - half, top, cx + half, height - RAIL_H + 1, node))
        elif key is not None:
            y = ty(key)
            if row == "p":
                add(Shape("metal1", cx - half, top, cx + half, y + half, node))
            else:
                add(Shape("metal1", cx - half, y - half, cx + half, bottom, node))
            _via(out, cx, y, node)
        else:
            add(Shape("metal1", cx - half, top, cx + half, bottom, node))

    # Nodos locales: un tramo vertical une sus contactos p y n (la salida de un INV).
    for node, ps in pins.items():
        if node in routed or c.is_rail(node):
            continue
        kinds = {kind for _, kind in ps}
        cx = ps[0][0]
        if "p" in kinds and "n" in kinds:
            add(Shape("metal1", cx - half, p0 + 2, cx + half, n1 - 2, node))
            if c.is_port(node):
                out.pins.append(Pin(c.label(node), cx, mid, node))
        elif kinds <= {"p", "n"} and c.is_port(node):
            out.pins.append(
                Pin(c.label(node), cx, (p0 + p1) / 2 if "p" in kinds else (n0 + n1) / 2, node)
            )

    # Polisilicio, contactos de compuerta y canales
    for k, (gp, gn) in enumerate(gates):
        x0, x1 = xs[k], xs[k] + POLY_W
        cx = (x0 + x1) / 2
        if gp is not None and gp == gn:
            add(Shape("poly", x0, p0 - ENDCAP, x1, n1 + ENDCAP, gp))
            key = sub_of(gp, "g")
            y = ty(key) if key is not None else mid
            _poly_contact(out, cx, y, gp, key is not None)
            if key is None and c.is_port(gp):
                out.pins.append(Pin(c.label(gp), cx, y, gp))
        else:
            if gp is not None:
                key = sub_of(gp, "gp")
                y = ty(key) if key is not None else p1 + CHANNEL_MARGIN / 2
                add(Shape("poly", x0, p0 - ENDCAP, x1, y + PAD / 2, gp))
                _poly_contact(out, cx, y, gp, key is not None)
                if key is None and c.is_port(gp):
                    out.pins.append(Pin(c.label(gp), cx, y, gp))
            if gn is not None:
                key = sub_of(gn, "gn")
                y = ty(key) if key is not None else n0 - CHANNEL_MARGIN / 2
                add(Shape("poly", x0, y - PAD / 2, x1, n1 + ENDCAP, gn))
                _poly_contact(out, cx, y, gn, key is not None)
                if key is None and c.is_port(gn):
                    out.pins.append(Pin(c.label(gn), cx, y, gn))
        p_index, n_index = out.columns[k]
        if p_index is not None:
            add(Shape("channel", x0, p0, x1, p1, gp, p_index))
        if n_index is not None:
            add(Shape("channel", x0, n0, x1, n1, gn, n_index))

    # Pistas de metal 2 y doglegs
    for key, ps in subs.items():
        node = key[0]
        y = ty(key)
        xs_net = [x for x, _ in ps]
        if node in split:
            xs_net.append(jogs[node])
        add(Shape("metal2", min(xs_net) - half, y - half, max(xs_net) + half, y + half, node))
        if c.is_port(node) and key[1] != 2:
            out.pins.append(Pin(c.label(node), (min(xs_net) + max(xs_net)) / 2, y, node))
    for node, jx in jogs.items():
        y_up, y_low = ty((node, 1)), ty((node, 2))
        add(Shape("metal1", jx - half, y_up - half, jx + half, y_low + half, node))
        _via(out, jx, y_up, node)
        _via(out, jx, y_low, node)
    return out


def _rail(c: CellCircuit, kind: NodeKind) -> int:
    return next(n for n, node in c.nodes.items() if node.kind is kind)


def _via(out: Layout, x: float, y: float, node: int) -> None:
    out.shapes.append(
        Shape("via", x - CONTACT / 2, y - CONTACT / 2, x + CONTACT / 2, y + CONTACT / 2, node)
    )


def _poly_contact(out: Layout, x: float, y: float, node: int, to_metal2: bool) -> None:
    """Contacto de polisilicio a metal 1 (y vía a metal 2 si el nodo tiene pista)."""
    out.shapes.append(Shape("metal1", x - PAD / 2, y - PAD / 2, x + PAD / 2, y + PAD / 2, node))
    out.shapes.append(
        Shape("contact", x - CONTACT / 2, y - CONTACT / 2, x + CONTACT / 2, y + CONTACT / 2, node)
    )
    if to_metal2:
        _via(out, x, y, node)


# ------------------------------------------------------------ verificación
def check(layout: Layout) -> list[str]:
    """Compara el layout con el netlist (verificación simplificada tipo LVS).

    Comprueba que no haya cortocircuitos (formas de nodos distintos que se solapan en una
    misma capa conductora), que cada nodo quede conectado en una sola pieza (contactos y
    vías unen capas) y que cada canal tenga la compuerta y los extremos de su transistor.

    Returns:
        Lista de problemas (vacía si el layout es correcto).
    """
    problems: list[str] = []
    c = layout.circuit
    shapes = [s for s in layout.shapes if s.node is not None]
    for layer in CONDUCTING:
        on = [s for s in shapes if s.layer == layer]
        for i, a in enumerate(on):
            for b in on[i + 1 :]:
                if a.node != b.node and a.overlaps(b):
                    problems.append(
                        f"cortocircuito en {layer}: {c.label(a.node)} con {c.label(b.node)}"  # type: ignore[arg-type]
                    )
    # Conectividad por nodo
    parent = list(range(len(shapes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    joins = {
        ("contact", "pdiff"),
        ("contact", "ndiff"),
        ("contact", "poly"),
        ("contact", "metal1"),
        ("via", "metal1"),
        ("via", "metal2"),
    }
    for i, a in enumerate(shapes):
        for j in range(i + 1, len(shapes)):
            b = shapes[j]
            if a.node != b.node or a.layer == "channel" or b.layer == "channel":
                continue
            same = a.layer == b.layer and a.touches(b)
            linked = ((a.layer, b.layer) in joins or (b.layer, a.layer) in joins) and a.overlaps(b)
            if same or linked:
                parent[find(i)] = find(j)
    by_node: dict[int, set[int]] = {}
    for i, s in enumerate(shapes):
        if s.layer != "channel":
            by_node.setdefault(s.node, set()).add(find(i))  # type: ignore[arg-type]
    for node, groups in by_node.items():
        if len(groups) > 1:
            problems.append(f"nodo abierto: {c.label(node)} quedó en {len(groups)} piezas")
    # Cada canal: compuerta y extremos correctos
    for ch in layout.layer("channel"):
        assert ch.transistor is not None
        t = c.transistors[ch.transistor]
        diff_layer = "pdiff" if t.kind is TransistorType.PMOS else "ndiff"
        sides = {
            s.node
            for s in layout.layer(diff_layer)
            if abs(s.x1 - ch.x0) < 0.01 or abs(s.x0 - ch.x1) < 0.01
            if s.y0 < ch.y1 and ch.y0 < s.y1
        }
        if sides != {t.source.id, t.drain.id}:
            problems.append(f"{t.name}: extremos del canal distintos del netlist")
        polys = [
            s for s in layout.layer("poly") if s.touches(ch) and s.x0 <= ch.x0 and ch.x1 <= s.x1
        ]
        if not polys or any(s.node != t.gate.id for s in polys):
            problems.append(f"{t.name}: compuerta distinta del netlist")
    return problems


__all__ = ["LAYERS", "Layout", "Pin", "Shape", "build", "check", "standard_tracks"]
