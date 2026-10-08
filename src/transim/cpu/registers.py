"""Banco de registros F0–F7 de flip-flops (responsable: Héctor). ADR-0006, ADR-0010."""

from __future__ import annotations

from transim.core.netlist import Netlist
from transim.cpu.isa import N_REGS, REG_BITS, WORD_BITS


def register_file(n_regs: int = N_REGS, width: int = WORD_BITS) -> Netlist:
    """Banco de ``n_regs`` registros (celda REG de L1) con un puerto de escritura y dos
    de lectura (``mux_n`` de L2).

    Puertos: bus ``wd[width]``, bus ``wa[REG_BITS]``, entradas ``we`` y ``clk``; buses
    ``ra1[REG_BITS]``, ``ra2[REG_BITS]``; buses de salida ``rd1[width]`` y ``rd2[width]``.
    Escribe ``wd`` en el registro ``wa`` en el flanco de subida de ``clk`` si ``we`` = 1.
    Netlist secuencial. Nombre ``f"REGFILE{n_regs}x{width}"``.
    """
    raise NotImplementedError("pendiente: #30")


__all__ = ["REG_BITS", "register_file"]
