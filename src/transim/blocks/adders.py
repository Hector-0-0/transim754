"""Sumadores de N bits (capa L2). ADR-0009.

Interfaz común de todos los sumadores (puertos acordados, no cambiar sin ADR):

- buses de entrada ``a[width]`` y ``b[width]``, entrada ``cin``;
- bus de salida ``s[width]``, salida ``cout``.
"""

from __future__ import annotations

from collections.abc import Sequence

from transim.blocks.wiring import Wiring
from transim.cells.combinational import full_adder
from transim.core.netlist import Netlist
from transim.core.node import Node

GROUP = 4
"""Bits por grupo del carry-lookahead."""


def ripple_carry_adder(width: int) -> Netlist:
    """Sumador ripple-carry: ``width`` instancias de la celda ``FA`` encadenadas por el
    acarreo (``fa0`` … ``fa{width-1}``). Profundidad lógica lineal en ``width``.
    Nombre del netlist ``f"RCA{width}"``.
    """
    nl = Netlist(f"RCA{width}")
    a, b = nl.input_bus("a", width), nl.input_bus("b", width)
    carry = nl.input("cin")
    s = nl.output_bus("s", width)
    cout = nl.output("cout")
    for i in range(width):
        nxt = cout if i == width - 1 else nl.node(f"c{i + 1}")
        nl.instantiate(
            full_adder(), f"fa{i}", {"a": a[i], "b": b[i], "cin": carry, "s": s[i], "cout": nxt}
        )
        carry = nxt
    return nl


def carry_lookahead_adder(width: int) -> Netlist:
    """Sumador carry-lookahead (v1): señales g = a·b y p = a ⊕ b por bit, acarreos
    calculados en bloques de 4 bits con lookahead jerárquico. Mismos puertos que el RCA.
    Nombre del netlist ``f"CLA{width}"``.
    """
    nl = Netlist(f"CLA{width}")
    a, b = nl.input_bus("a", width), nl.input_bus("b", width)
    cin = nl.input("cin")
    s = nl.output_bus("s", width)
    cout = nl.output("cout")
    w = Wiring(nl)
    g = [w.and2(a[i], b[i]) for i in range(width)]
    p = [w.xor2(a[i], b[i]) for i in range(width)]
    carries = _lookahead(w, g, p, cin)
    for i in range(width):
        w.xor2(p[i], carries[i], s[i])
    # El acarreo final se copia a la salida con dos inversores (salida restaurada).
    w.inv(w.inv(carries[width]), cout)
    return nl


def _group_carries(w: Wiring, g: Sequence[Node], p: Sequence[Node], cin: Node) -> list[Node]:
    """Acarreos c1 … cn de un grupo, cada uno como suma de productos desde ``cin``:
    c_j = Σ_k g_k·p_{k+1}·…·p_{j-1} + p_0·…·p_{j-1}·cin."""
    out = []
    for j in range(1, len(g) + 1):
        terms = [w.and_tree([g[k], *p[k + 1 : j]]) for k in range(j)]
        terms.append(w.and_tree([*p[:j], cin]))
        out.append(w.or_tree(terms))
    return out


def _group_gp(w: Wiring, g: Sequence[Node], p: Sequence[Node]) -> tuple[Node, Node]:
    """Generación y propagación de grupo: G = Σ g_k·p_{k+1}…p_{n-1}, P = Π p_k."""
    n = len(g)
    big_g = w.or_tree([w.and_tree([g[k], *p[k + 1 : n]]) for k in range(n)])
    return big_g, w.and_tree(list(p))


def _lookahead(w: Wiring, g: Sequence[Node], p: Sequence[Node], cin: Node) -> list[Node]:
    """Acarreos c0 = cin … cn con lookahead jerárquico en grupos de :data:`GROUP`."""
    if len(g) <= GROUP:
        return [cin, *_group_carries(w, g, p, cin)]
    groups = [range(i, min(i + GROUP, len(g))) for i in range(0, len(g), GROUP)]
    gps = [_group_gp(w, [g[k] for k in r], [p[k] for k in r]) for r in groups]
    group_carries = _lookahead(w, [x[0] for x in gps], [x[1] for x in gps], cin)
    carries = [cin]
    for idx, r in enumerate(groups):
        inner = _group_carries(w, [g[k] for k in r], [p[k] for k in r], group_carries[idx])
        carries.extend(inner[:-1])
        carries.append(group_carries[idx + 1])
    return carries
