"""FADD/FSUB en transistores (responsable: Daniel). Issue #17.

Criterio de aceptación: binary32 con todos los pares borde (> 200) y 10 000 pares
aleatorios, 0 discrepancias bit a bit (incluidos los flags) contra el oráculo.
"""

from __future__ import annotations

import pytest

from fpu.comun import comparar, pares_aceptacion, pares_rapidos
from pendientes import pendiente
from transim.fpu.add_sub import FPAddSub
from transim.fpu.format import BINARY16, BINARY32, FloatFormat

pytestmark = [pendiente(17), pytest.mark.cached]
FORMATOS = pytest.mark.parametrize("fmt", [BINARY16, BINARY32], ids=lambda f: f.name)


def test_ejemplos_de_docs_03() -> None:
    u = FPAddSub(BINARY32)
    assert u.add(0x3FC00000, 0x40100000).bits == 0x40700000  # ejemplo 2
    assert u.add(0x4B800000, 0x3F800000).bits == 0x4B800000  # ejemplo 3a
    assert u.add(0x4B800001, 0x3F800000).bits == 0x4B800002  # ejemplo 3b
    assert u.sub(0x3FC00000, 0x3FC00000).bits == 0x00000000  # x − x = +0


@FORMATOS
def test_rapido(fmt: FloatFormat) -> None:
    u = FPAddSub(fmt)
    comparar(fmt, "+", u.add, pares_rapidos(fmt))
    comparar(fmt, "-", u.sub, pares_rapidos(fmt))


@pytest.mark.slow
@FORMATOS
def test_aceptacion(fmt: FloatFormat) -> None:
    u = FPAddSub(fmt)
    assert comparar(fmt, "+", u.add, pares_aceptacion(fmt)) > 10_200
    comparar(fmt, "-", u.sub, pares_aceptacion(fmt))


def test_motor_switch_coincide_en_binary16() -> None:
    a, b = FPAddSub(BINARY16, "switch"), FPAddSub(BINARY16, "cached")
    for x, y in pares_rapidos(BINARY16, 20)[:40]:
        assert a.add(x, y) == b.add(x, y)
