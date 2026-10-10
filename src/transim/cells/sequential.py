"""Celdas secuenciales con transmission gates (capa L1, responsable: Jairo).

Todas se marcan ``Netlist(..., sequential=True)``: el motor cached nunca las tabula
(ADR-0008). Las firmas, nombres y puertos son la interfaz acordada.

Disciplina de uso: los datos deben estar estables antes del flanco de reloj; el reloj
se cambia en una llamada a ``set_inputs`` distinta de la que cambia los datos.
"""

from __future__ import annotations

from functools import cache

from transim.core.netlist import Netlist


@cache
def d_latch() -> Netlist:
    """Latch D estático: transparente con ``clk`` = 1 y retiene con ``clk`` = 0.

    Estructura: transmission gate de entrada, dos inversores en lazo y transmission
    gate de realimentación; el complemento de ``clk`` se genera con un INV interno.
    Puertos: entradas ``d``, ``clk``; salida ``q``. Nombre de celda ``"DLATCH"``.

    12 transistores:

    - INV de entrada (``pid``/``nid``): ``dn`` = ¬d, para que ``d`` solo llegue a
      compuertas (regla 1).
    - INV de reloj (``pik``/``nik``): ``clkn`` = ¬clk.
    - ``tg_in`` une ``dn`` con el nodo de almacenamiento ``x`` cuando clk = 1.
    - INV de salida (``po``/``no``): q = ¬x = d. Es la salida restaurada (regla 2).
    - INV de realimentación (``pf``/``nf``): ``fb`` = ¬q, que vale lo mismo que ``x``.
    - ``tg_fb`` une ``fb`` con ``x`` cuando clk = 0 y cierra el lazo de dos inversores
      que retiene el dato de forma estática (no depende de carga retenida).
    """
    nl = Netlist("DLATCH", sequential=True)
    d, clk, q = nl.input("d"), nl.input("clk"), nl.output("q")
    vdd, gnd = nl.vdd, nl.gnd
    dn, clkn = nl.node("dn"), nl.node("clkn")
    nl.pmos(d, vdd, dn, "pid")
    nl.nmos(d, dn, gnd, "nid")
    nl.pmos(clk, vdd, clkn, "pik")
    nl.nmos(clk, clkn, gnd, "nik")
    x, fb = nl.node("x"), nl.node("fb")
    nl.transmission_gate(dn, x, enable=clk, enable_n=clkn, name="tg_in")
    nl.pmos(x, vdd, q, "po")
    nl.nmos(x, q, gnd, "no")
    nl.pmos(q, vdd, fb, "pf")
    nl.nmos(q, fb, gnd, "nf")
    nl.transmission_gate(fb, x, enable=clkn, enable_n=clk, name="tg_fb")
    return nl


@cache
def dff() -> Netlist:
    """Flip-flop D maestro-esclavo disparado por flanco de subida de ``clk``.

    Dos latches D con relojes complementarios: el maestro es transparente con
    ``clk`` = 0 y el esclavo con ``clk`` = 1.
    Puertos: entradas ``d``, ``clk``; salida ``q``. Nombre de celda ``"DFF"``.

    26 transistores: un INV (``pik``/``nik``) genera ``clkn``; el maestro ``u_m`` es
    un DLATCH con reloj ``clkn`` (transparente con clk = 0) y el esclavo ``u_s`` un
    DLATCH con reloj ``clk``. Nunca son transparentes a la vez, así que ``q`` solo
    cambia en el flanco de subida, cuando el esclavo copia lo que el maestro retuvo.
    """
    nl = Netlist("DFF", sequential=True)
    d, clk, q = nl.input("d"), nl.input("clk"), nl.output("q")
    clkn = nl.node("clkn")
    nl.pmos(clk, nl.vdd, clkn, "pik")
    nl.nmos(clk, clkn, nl.gnd, "nik")
    qm = nl.node("qm")
    nl.instantiate(d_latch(), "u_m", {"d": d, "clk": clkn, "q": qm})
    nl.instantiate(d_latch(), "u_s", {"d": qm, "clk": clk, "q": q})
    return nl


def register(width: int) -> Netlist:
    """Registro de ``width`` bits con habilitación de escritura.

    Cada bit es un DFF cuya entrada es ``en ? d[i] : q[i]`` (MUX2 de realimentación).
    Puertos: bus de entrada ``d[width]``, entradas ``clk`` y ``en``; bus de salida
    ``q[width]``. Nombre de celda ``f"REG{width}"``.
    """
    raise NotImplementedError("pendiente: #6")
