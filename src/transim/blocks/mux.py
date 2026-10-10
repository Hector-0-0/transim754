"""Multiplexores de bus (capa L2)."""

from __future__ import annotations

from transim.cells.combinational import mux2
from transim.core.netlist import Netlist


def mux2_bus(width: int) -> Netlist:
    """``width`` celdas MUX2 con selección común: y = a si s = 0, y = b si s = 1.

    Puertos: buses ``a[width]``, ``b[width]``, entrada ``s``; bus ``y[width]``.
    Nombre del netlist ``f"MUX2x{width}"``.
    """
    nl = Netlist(f"MUX2x{width}")
    a, b = nl.input_bus("a", width), nl.input_bus("b", width)
    s = nl.input("s")
    y = nl.output_bus("y", width)
    for i in range(width):
        nl.instantiate(mux2(), f"m{i}", {"a": a[i], "b": b[i], "s": s, "y": y[i]})
    return nl


def mux_n(width: int, n_inputs: int) -> Netlist:
    """Multiplexor de ``n_inputs`` buses (potencia de 2) como árbol de MUX2.

    Puertos: buses ``in0[width]`` … ``in{n-1}[width]`` y ``sel[log2(n)]``; bus
    ``y[width]`` = ``in{sel}``. Nombre del netlist ``f"MUX{n_inputs}x{width}"``.

    Raises:
        ValueError: si ``n_inputs`` no es una potencia de 2 mayor o igual a 2.
    """
    if n_inputs < 2 or n_inputs & (n_inputs - 1):
        raise ValueError(f"n_inputs debe ser una potencia de 2 ≥ 2, no {n_inputs}")
    levels = n_inputs.bit_length() - 1
    nl = Netlist(f"MUX{n_inputs}x{width}")
    layer = [nl.input_bus(f"in{i}", width) for i in range(n_inputs)]
    sel = nl.input_bus("sel", levels)
    y = nl.output_bus("y", width)
    for level in range(levels):
        last = level == levels - 1
        nxt = []
        for k in range(0, len(layer), 2):
            out = y if last else [nl.node(f"l{level}_{k // 2}_{i}") for i in range(width)]
            nl.instantiate(
                mux2_bus(width),
                f"m{level}_{k // 2}",
                {"a": layer[k], "b": layer[k + 1], "s": sel[level], "y": out},
            )
            nxt.append(out)
        layer = nxt
    return nl
