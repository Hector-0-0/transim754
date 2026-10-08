"""Verifica contra numpy los seis ejemplos resueltos a mano en docs/03_ieee754.md.

Si uno de estos valores cambia, el documento está mal: se corrige el documento,
no la prueba. La exactitud (flag inexact) se decide con aritmética racional exacta.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

import numpy as np
import pytest

f32 = np.float32


def _de_bits(h: int) -> np.float32:
    return np.array(h, dtype=np.uint32).view(np.float32)[()]


def _bits(x: np.float32) -> int:
    return int(np.array(x, dtype=np.float32).view(np.uint32))


def _con_flags(fn: Callable[[], np.float32]) -> tuple[np.float32, set[str]]:
    """Ejecuta `fn` y devuelve el resultado y los flags que numpy reporta."""
    vistos: set[str] = set()
    anterior = np.seterrcall(lambda tipo, _flag: vistos.add(tipo))
    try:
        with np.errstate(all="call"):
            r = fn()
    finally:
        np.seterrcall(anterior)
    return r, vistos


def test_ejemplo_1_codificacion_menos_6_25() -> None:
    assert _bits(f32(-6.25)) == 0xC0C80000


def test_ejemplo_2_fadd_1_5_mas_2_25() -> None:
    r, flags = _con_flags(lambda: f32(1.5) + f32(2.25))
    assert _bits(r) == 0x40700000
    assert flags == set()
    assert Fraction(float(r)) == Fraction(15, 4)  # exacto: sin inexact


@pytest.mark.parametrize(
    ("a", "esperado", "exacto"),
    [
        (0x4B800000, 0x4B800000, 16777217),  # empate -> par hacia abajo
        (0x4B800001, 0x4B800002, 16777219),  # empate -> par hacia arriba
    ],
)
def test_ejemplo_3_empates_a_par(a: int, esperado: int, exacto: int) -> None:
    r, _ = _con_flags(lambda: _de_bits(a) + f32(1.0))
    assert _bits(r) == esperado
    assert Fraction(float(_de_bits(a))) + 1 == exacto
    assert Fraction(float(r)) != exacto  # inexact


def test_ejemplo_4_fmul_resultado_subnormal() -> None:
    a = _de_bits(0x00800001)
    r, flags = _con_flags(lambda: a * f32(0.5))
    assert _bits(r) == 0x00400000
    assert "underflow" in flags
    assert Fraction(float(a)) / 2 != Fraction(float(r))  # inexact
    assert Fraction(float(a)) / 2 == Fraction(1, 2**127) + Fraction(1, 2**150)


def test_ejemplo_5_fdiv_un_tercio() -> None:
    r, _ = _con_flags(lambda: f32(1.0) / f32(3.0))
    assert _bits(r) == 0x3EAAAAAB
    # Se redondeó hacia arriba: error = +1/(3·2^25), menor que medio ulp (2^-26).
    assert Fraction(float(r)) - Fraction(1, 3) == Fraction(1, 3 * 2**25)


def test_ejemplo_6_overflow() -> None:
    r, flags = _con_flags(lambda: _de_bits(0x7F7FFFFF) * f32(2.0))
    assert _bits(r) == 0x7F800000
    assert "overflow" in flags
