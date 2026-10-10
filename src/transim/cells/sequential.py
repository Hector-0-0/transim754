"""Celdas secuenciales con transmission gates (capa L1).

Todas se marcan ``Netlist(..., sequential=True)``: el motor cached nunca las tabula
(ADR-0008). Las firmas, nombres y puertos son la interfaz acordada.

Disciplina de uso: los datos deben estar estables antes del flanco de reloj; el reloj
se cambia en una llamada a ``set_inputs`` distinta de la que cambia los datos.
"""

from __future__ import annotations

from functools import cache

from transim.cells.combinational import mux2
from transim.core.netlist import Netlist
from transim.core.node import Node


@cache
def d_latch() -> Netlist:
    """Latch D estático: transparente con ``clk`` = 1 y retiene con ``clk`` = 0.

    Estructura: transmission gate de entrada, dos inversores en lazo y transmission
    gate de realimentación; el complemento de ``clk`` se genera con un INV interno.
    Puertos: entradas ``d``, ``clk``; salida ``q``. Nombre de celda ``"DLATCH"``.
    10 transistores.
    """
    nl = Netlist("DLATCH", sequential=True)
    d, clk, q = nl.input("d"), nl.input("clk"), nl.output("q")
    clkn, x, xn = nl.node("clkn"), nl.node("x"), nl.node("xn")
    _inverter(nl, clk, clkn, "inv_clk")
    nl.transmission_gate(d, x, clk, clkn, "tg_in")
    _inverter(nl, x, xn, "inv1")
    _inverter(nl, xn, q, "inv2")
    nl.transmission_gate(q, x, clkn, clk, "tg_fb")
    return nl


@cache
def dff() -> Netlist:
    """Flip-flop D maestro-esclavo disparado por flanco de subida de ``clk``.

    Dos latches D con relojes complementarios: el maestro es transparente con
    ``clk`` = 0 y el esclavo con ``clk`` = 1.
    Puertos: entradas ``d``, ``clk``; salida ``q``. Nombre de celda ``"DFF"``.
    """
    nl = Netlist("DFF", sequential=True)
    d, clk, q = nl.input("d"), nl.input("clk"), nl.output("q")
    clkn, m = nl.node("clkn"), nl.node("m")
    _inverter(nl, clk, clkn, "inv_clk")
    nl.instantiate(d_latch(), "master", {"d": d, "clk": clkn, "q": m})
    nl.instantiate(d_latch(), "slave", {"d": m, "clk": clk, "q": q})
    return nl


def register(width: int) -> Netlist:
    """Registro de ``width`` bits con habilitación de escritura.

    Cada bit es un DFF cuya entrada es ``en ? d[i] : q[i]`` (MUX2 de realimentación).
    Puertos: bus de entrada ``d[width]``, entradas ``clk`` y ``en``; bus de salida
    ``q[width]``. Nombre de celda ``f"REG{width}"``.
    """
    nl = Netlist(f"REG{width}", sequential=True)
    d = nl.input_bus("d", width)
    clk, en = nl.input("clk"), nl.input("en")
    q = nl.output_bus("q", width)
    for i in range(width):
        nxt = nl.node(f"next{i}")
        nl.instantiate(mux2(), f"mux{i}", {"a": q[i], "b": d[i], "s": en, "y": nxt})
        nl.instantiate(dff(), f"ff{i}", {"d": nxt, "clk": clk, "q": q[i]})
    return nl


def _inverter(nl: Netlist, a: Node, y: Node, name: str) -> None:
    """Coloca un inversor (2 T) de ``a`` a ``y`` dentro de ``nl``."""
    nl.pmos(a, nl.vdd, y, f"{name}.p")
    nl.nmos(a, y, nl.gnd, f"{name}.n")
