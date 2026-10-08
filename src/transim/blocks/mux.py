"""Multiplexores de bus (capa L2, responsable: Ronald)."""

from __future__ import annotations

from transim.core.netlist import Netlist


def mux2_bus(width: int) -> Netlist:
    """``width`` celdas MUX2 con selección común: y = a si s = 0, y = b si s = 1.

    Puertos: buses ``a[width]``, ``b[width]``, entrada ``s``; bus ``y[width]``.
    Nombre del netlist ``f"MUX2x{width}"``.
    """
    raise NotImplementedError("pendiente: #10")


def mux_n(width: int, n_inputs: int) -> Netlist:
    """Multiplexor de ``n_inputs`` buses (potencia de 2) como árbol de MUX2.

    Puertos: buses ``in0[width]`` … ``in{n-1}[width]`` y ``sel[log2(n)]``; bus
    ``y[width]`` = ``in{sel}``. Nombre del netlist ``f"MUX{n_inputs}x{width}"``.

    Raises:
        ValueError: si ``n_inputs`` no es una potencia de 2 mayor o igual a 2.
    """
    raise NotImplementedError("pendiente: #10")
