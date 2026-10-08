"""Contador de ceros a la izquierda (capa L2, responsable: Ronald). ADR-0009."""

from __future__ import annotations

from transim.core.netlist import Netlist


def count_bits_for(width: int) -> int:
    """Bits del resultado: los necesarios para representar ``width`` (caso a = 0)."""
    return width.bit_length()


def leading_zero_counter(width: int) -> Netlist:
    """LZC combinacional: ``count`` = número de ceros antes del primer 1 empezando por
    el bit más significativo; ``count`` = ``width`` si a = 0.

    Puertos: bus ``a[width]``; bus ``count[count_bits_for(width)]``.
    Nombre del netlist ``f"LZC{width}"``.
    """
    raise NotImplementedError("pendiente: #12")
