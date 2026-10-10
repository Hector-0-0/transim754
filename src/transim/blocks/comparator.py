"""Comparador de magnitud sin signo (capa L2). ADR-0009."""

from __future__ import annotations

from transim.blocks.subtractor import adder_subtractor
from transim.blocks.wiring import Wiring
from transim.core.netlist import Netlist


def magnitude_comparator(width: int) -> Netlist:
    """Compara ``a`` y ``b`` sin signo usando el restador: a − b.

    lt = ¬cout (hubo préstamo); eq = todos los bits de la diferencia en 0 (árbol NOR);
    gt = ¬lt · ¬eq.

    Puertos: buses ``a[width]``, ``b[width]``; salidas ``lt``, ``eq``, ``gt``.
    Nombre del netlist ``f"CMP{width}"``.
    """
    nl = Netlist(f"CMP{width}")
    a, b = nl.input_bus("a", width), nl.input_bus("b", width)
    lt, eq, gt = nl.output("lt"), nl.output("eq"), nl.output("gt")
    diff = [nl.node(f"d{i}") for i in range(width)]
    no_borrow = nl.node("no_borrow")
    nl.instantiate(
        adder_subtractor(width),
        "sub",
        {"a": a, "b": b, "sub": nl.vdd, "s": diff, "cout": no_borrow},
    )
    w = Wiring(nl)
    w.inv(no_borrow, lt)
    w.inv(w.or_tree(diff), eq)
    w.nor2(lt, eq, gt)
    return nl
