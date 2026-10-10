"""Contador de ceros a la izquierda (capa L2). ADR-0009."""

from __future__ import annotations

from transim.blocks._wiring import Wiring
from transim.core.netlist import Netlist
from transim.core.node import Node


def count_bits_for(width: int) -> int:
    """Bits del resultado: los necesarios para representar ``width`` (caso a = 0)."""
    return width.bit_length()


def leading_zero_counter(width: int) -> Netlist:
    """LZC combinacional: ``count`` = número de ceros antes del primer 1 empezando por
    el bit más significativo; ``count`` = ``width`` si a = 0.

    Puertos: bus ``a[width]``; bus ``count[count_bits_for(width)]``.
    Nombre del netlist ``f"LZC{width}"``.

    Árbol binario: la entrada se completa por la derecha con unos hasta una potencia de
    2; cada nodo combina las mitades (todo-cero, cuenta) con un AND2 y MUX2.
    """
    nl = Netlist(f"LZC{width}")
    a = nl.input_bus("a", width)
    bits = count_bits_for(width)
    count = nl.output_bus("count", bits)
    w = Wiring(nl)
    size = 1
    while size < width:
        size *= 2
    # Orden del más significativo al menos significativo, con relleno de unos.
    msb_first = [a[i] for i in reversed(range(width))] + [nl.vdd] * (size - width)
    zero, cnt = _tree(w, msb_first)
    if size == width:
        # a = 0 → count = width = 2^k: bit alto = todo-cero, el resto se anula.
        nzero = w.inv(zero)
        for i, c in enumerate(cnt):
            w.and2(c, nzero, count[i])
        w.inv(nzero, count[bits - 1])
    else:
        for i, c in enumerate(cnt):
            w.inv(w.inv(c), count[i])
    return nl


def _tree(w: Wiring, bits: list[Node]) -> tuple[Node, list[Node]]:
    """(todo-cero, cuenta LSB primero) de ``bits`` (MSB primero, longitud 2^k)."""
    if len(bits) == 1:
        return w.inv(bits[0]), []
    half = len(bits) // 2
    zl, cl = _tree(w, bits[:half])
    zr, cr = _tree(w, bits[half:])
    cnt = [w.mux2(cl[i], cr[i], zl) for i in range(len(cl))]
    return w.and2(zl, zr), [*cnt, zl]
