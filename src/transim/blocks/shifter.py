"""Desplazador barrel logarítmico con sticky (capa L2, responsable: Ronald). ADR-0009."""

from __future__ import annotations

from typing import Literal

from transim.core.netlist import Netlist


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
    raise NotImplementedError("pendiente: #11")
