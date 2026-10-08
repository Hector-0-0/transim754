"""Clasificación de operandos y resultados especiales (responsable: Daniel). ADR-0003."""

from __future__ import annotations

from typing import Literal

from transim.core.netlist import Netlist
from transim.fpu.format import FloatFormat

SpecialOp = Literal["add", "mul", "div"]


def classifier(fmt: FloatFormat) -> Netlist:
    """Clasifica un operando con compuertas (árboles AND/OR sobre exponente y fracción).

    Puertos: bus ``x[fmt.width]``; salidas one-hot ``zero``, ``subnormal``, ``normal``,
    ``inf``, ``qnan``, ``snan``. Nombre ``f"CLASS_{fmt.name}"``.
    """
    raise NotImplementedError("pendiente: #15")


def special_cases(fmt: FloatFormat, op: SpecialOp) -> Netlist:
    """Resultado de los casos especiales de la tabla de docs/03 §6 para ``op``.

    Entradas por operando ``a`` y ``b``: ``a_zero``, ``a_inf``, ``a_qnan``, ``a_snan``,
    ``a_sign`` (ídem con ``b_``). Para la resta, ``b_sign`` llega ya invertido.

    Salidas: ``special`` (1 si el resultado lo decide este bloque y no el datapath
    numérico), bus ``y[fmt.width]`` con el resultado especial (NaN canónico, ±∞ o ±0),
    ``invalid`` y ``div_by_zero``. Nombre ``f"SPECIAL_{op}_{fmt.name}"``.

    Nota: en ``add`` los casos "operando cero" no son especiales (los resuelve el
    datapath); solo NaN e ∞. En ``mul`` y ``div`` sí lo son.
    """
    raise NotImplementedError("pendiente: #15")
