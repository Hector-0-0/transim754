"""Banco de registros F0–F7 de flip-flops. ADR-0006, ADR-0010."""

from __future__ import annotations

from functools import cache

from transim.blocks.mux import mux_n
from transim.blocks.wiring import Wiring
from transim.cells.sequential import register
from transim.core.netlist import Netlist
from transim.cpu.isa import N_REGS, REG_BITS, WORD_BITS


@cache
def register_file(n_regs: int = N_REGS, width: int = WORD_BITS) -> Netlist:
    """Banco de ``n_regs`` registros (celda REG de L1) con un puerto de escritura y dos
    de lectura (``mux_n`` de L2).

    Puertos: bus ``wd[width]``, bus ``wa[REG_BITS]``, entradas ``we`` y ``clk``; buses
    ``ra1[REG_BITS]``, ``ra2[REG_BITS]``; buses de salida ``rd1[width]`` y ``rd2[width]``.
    Escribe ``wd`` en el registro ``wa`` en el flanco de subida de ``clk`` si ``we`` = 1.
    Netlist secuencial. Nombre ``f"REGFILE{n_regs}x{width}"``.
    """
    sel_bits = (n_regs - 1).bit_length()
    nl = Netlist(f"REGFILE{n_regs}x{width}", sequential=True)
    wd = nl.input_bus("wd", width)
    wa = nl.input_bus("wa", REG_BITS)
    we, clk = nl.input("we"), nl.input("clk")
    ra1, ra2 = nl.input_bus("ra1", REG_BITS), nl.input_bus("ra2", REG_BITS)
    rd1, rd2 = nl.output_bus("rd1", width), nl.output_bus("rd2", width)
    w = Wiring(nl)
    wa_n = [w.inv(bit) for bit in wa[:sel_bits]]

    q = []
    for r in range(n_regs):
        match = [wa[i] if (r >> i) & 1 else wa_n[i] for i in range(sel_bits)]
        enable = w.and_tree([we, *match])
        out = [nl.node(f"f{r}_{i}") for i in range(width)]
        nl.instantiate(register(width), f"f{r}", {"d": wd, "clk": clk, "en": enable, "q": out})
        q.append(out)

    for name, sel, rd in (("read1", ra1, rd1), ("read2", ra2, rd2)):
        ports = {f"in{r}": q[r] for r in range(n_regs)}
        nl.instantiate(mux_n(width, n_regs), name, {**ports, "sel": sel[:sel_bits], "y": rd})
    return nl


__all__ = ["REG_BITS", "register_file"]
