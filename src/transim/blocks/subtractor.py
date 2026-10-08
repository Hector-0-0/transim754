"""Sumador/restador en complemento a 2 (capa L2, responsable: Ronald). ADR-0009."""

from __future__ import annotations

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
    raise NotImplementedError("pendiente: #8")
