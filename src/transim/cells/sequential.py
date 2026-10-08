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
    """
    raise NotImplementedError("pendiente: #5")


@cache
def dff() -> Netlist:
    """Flip-flop D maestro-esclavo disparado por flanco de subida de ``clk``.

    Dos latches D con relojes complementarios: el maestro es transparente con
    ``clk`` = 0 y el esclavo con ``clk`` = 1.
    Puertos: entradas ``d``, ``clk``; salida ``q``. Nombre de celda ``"DFF"``.
    """
    raise NotImplementedError("pendiente: #5")


def register(width: int) -> Netlist:
    """Registro de ``width`` bits con habilitación de escritura.

    Cada bit es un DFF cuya entrada es ``en ? d[i] : q[i]`` (MUX2 de realimentación).
    Puertos: bus de entrada ``d[width]``, entradas ``clk`` y ``en``; bus de salida
    ``q[width]``. Nombre de celda ``f"REG{width}"``.
    """
    raise NotImplementedError("pendiente: #6")
