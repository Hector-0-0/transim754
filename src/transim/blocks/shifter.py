"""Desplazador barrel logarítmico con sticky (capa L2). ADR-0009."""

from __future__ import annotations

from typing import Literal

from transim.blocks._wiring import Wiring
from transim.core.netlist import Netlist
from transim.core.node import Node


def shift_bits_for(width: int) -> int:
    """Bits del bus de desplazamiento: los necesarios para representar ``width``.

    Así un desplazamiento ≥ ``width`` (alineación saturada) también es representable.
    """
    return width.bit_length()


def barrel_shifter(width: int, direction: Literal["left", "right"]) -> Netlist:
    """Desplazador lógico de ``width`` bits en ``shift_bits_for(width)`` etapas de MUX2.

    La etapa i desplaza 2^i posiciones si ``sh[i]`` = 1. Los bits que entran son 0.
    En el desplazador a la derecha, la salida ``sticky`` es el OR de todos los bits que
    salieron por la derecha (se calcula etapa por etapa).

    Puertos: buses ``a[width]`` y ``sh[shift_bits_for(width)]``; bus ``y[width]``;
    salida ``sticky`` solo si ``direction == "right"``.
    Nombre del netlist ``f"SHL{width}"`` o ``f"SHR{width}"``.
    """
    right = direction == "right"
    stages = shift_bits_for(width)
    nl = Netlist(f"{'SHR' if right else 'SHL'}{width}")
    x: list[Node] = nl.input_bus("a", width)
    sh = nl.input_bus("sh", stages)
    y = nl.output_bus("y", width)
    sticky = nl.output("sticky") if right else None
    w = Wiring(nl)
    lost: list[Node] = []
    for stage in range(stages):
        k = 1 << stage
        if right:
            # Bits que salen en esta etapa si sh[stage] = 1: los k menos significativos.
            lost.append(w.and2(w.or_tree(x[: min(k, width)]), sh[stage]))
        nxt = []
        for j in range(width):
            src = j + k if right else j - k
            moved = x[src] if 0 <= src < width else nl.gnd
            out = y[j] if stage == stages - 1 else None
            nxt.append(w.mux2(x[j], moved, sh[stage], out))
        x = nxt
    if sticky is not None:
        w.inv(w.inv(w.or_tree(lost)), sticky)
    return nl
