"""Sumadores de N bits (capa L2, responsable: Ronald). ADR-0009.

Interfaz común de todos los sumadores (puertos acordados, no cambiar sin ADR):

- buses de entrada ``a[width]`` y ``b[width]``, entrada ``cin``;
- bus de salida ``s[width]``, salida ``cout``.
"""

from __future__ import annotations

from transim.core.netlist import Netlist


def ripple_carry_adder(width: int) -> Netlist:
    """Sumador ripple-carry: ``width`` instancias de la celda ``FA`` encadenadas por el
    acarreo (``fa0`` … ``fa{width-1}``). Profundidad lógica lineal en ``width``.
    Nombre del netlist ``f"RCA{width}"``.
    """
    raise NotImplementedError("pendiente: #7")


def carry_lookahead_adder(width: int) -> Netlist:
    """Sumador carry-lookahead (v1): señales g = a·b y p = a ⊕ b por bit, acarreos
    calculados en bloques de 4 bits con lookahead jerárquico. Mismos puertos que el RCA.
    Nombre del netlist ``f"CLA{width}"``.
    """
    raise NotImplementedError("pendiente: #14")
