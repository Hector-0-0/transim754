"""Bloque compartido round_and_pack (dueño: Daniel). Issue #16.

Contrato: ``transim.reference.fpu.round_and_pack``.
"""

from __future__ import annotations

import random

import pytest

from oracle.compare import assert_fp_equal
from transim.core import HardwareUnit
from transim.fpu.format import BINARY16, BINARY32, FloatFormat, FPResult
from transim.fpu.rounding import exponent_width, round_and_pack
from transim.reference import fpu as ref

FORMATOS = pytest.mark.parametrize("fmt", [BINARY16, BINARY32], ids=lambda f: f.name)


def test_ancho_de_exponente() -> None:
    assert exponent_width(BINARY32) == 10
    assert exponent_width(BINARY16) == 7


def _casos(fmt: FloatFormat, n: int, seed: int) -> list[tuple[int, int, int, int, int, int]]:
    rng = random.Random(seed)
    p = fmt.precision
    tope = 1 << p
    casos = []
    for i in range(n):
        region = i % 4
        if region == 0:  # normales
            e = rng.randrange(1, fmt.exp_max_field)
        elif region == 1:  # diminutos (subnormal o cero tras redondear)
            e = rng.randrange(-p - 2, 1)
        elif region == 2:  # alrededor del desbordamiento
            e = rng.randrange(fmt.exp_max_field - 2, fmt.exp_max_field + 2)
        else:  # bordes del rango normal
            e = rng.choice([1, 2, 0, fmt.exp_max_field - 1])
        m = rng.choice([tope - 1, tope >> 1, (tope >> 1) | 1, rng.randrange(tope >> 1, tope)])
        casos.append(
            (rng.getrandbits(1), e, m, rng.getrandbits(1), rng.getrandbits(1), rng.getrandbits(1))
        )
    casos.append((0, 5, 0, 0, 0, 0))  # cero exacto
    casos.append((1, 5, 0, 0, 0, 0))
    return casos


def _verificar(fmt: FloatFormat, u: HardwareUnit, casos) -> None:  # type: ignore[no-untyped-def]
    mask = (1 << exponent_width(fmt)) - 1
    for sign, e, m, g, r, s in casos:
        out = u.evaluate({"sign": sign, "e": e & mask, "m": m, "g": g, "r": r, "s": s})
        esperado = ref.round_and_pack(fmt, sign, e, m, g, r, s)
        assert_fp_equal(fmt, FPResult.from_outputs(out), esperado, f"{(sign, e, m, g, r, s)}")


@pytest.mark.cached
@FORMATOS
def test_contra_la_referencia(fmt: FloatFormat) -> None:
    _verificar(fmt, HardwareUnit(round_and_pack(fmt), "cached"), _casos(fmt, 300, 16))


@pytest.mark.slow
@FORMATOS
def test_contra_la_referencia_10000(fmt: FloatFormat) -> None:
    _verificar(fmt, HardwareUnit(round_and_pack(fmt), "cached"), _casos(fmt, 10_000, 17))
