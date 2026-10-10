"""Sumador/restador en complemento a 2 (capa L2). ADR-0009."""

from __future__ import annotations

from transim.blocks.wiring import Wiring, ripple_chain
from transim.core.netlist import Netlist


def adder_subtractor(width: int) -> Netlist:
    """Sumador/restador: ``sub`` = 0 → s = a + b; ``sub`` = 1 → s = a + ¬b + 1.

    Cada bit de ``b`` pasa por un XOR2 con ``sub`` y ``sub`` entra como acarreo inicial
    del sumador ripple-carry.

    Puertos: buses ``a[width]``, ``b[width]``, entrada ``sub``; bus ``s[width]``,
    salidas ``cout`` (acarreo de salida; en la resta, 1 = sin préstamo) y ``ovf``
    (desbordamiento con signo = acarreo hacia el bit de signo ⊕ acarreo de salida).
    Nombre del netlist ``f"ADDSUB{width}"``.
    """
    nl = Netlist(f"ADDSUB{width}")
    a, b = nl.input_bus("a", width), nl.input_bus("b", width)
    sub = nl.input("sub")
    s = nl.output_bus("s", width)
    cout, ovf = nl.output("cout"), nl.output("ovf")
    w = Wiring(nl)
    bx = [w.xor2(b[i], sub) for i in range(width)]
    carries = ripple_chain(w, a, bx, sub, s)
    w.inv(w.inv(carries[width]), cout)
    w.xor2(carries[width - 1], carries[width], ovf)
    return nl
