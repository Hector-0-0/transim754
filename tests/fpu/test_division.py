"""Divisor de mantisas y FDIV (responsable: Fabricio). Issues #20 y #21."""

from __future__ import annotations

import itertools
import random

import pytest

from fpu.comun import comparar, pares_aceptacion, pares_rapidos
from transim.core import HardwareUnit
from transim.fpu.div import FPDiv, nonrestoring_divider, quotient_bits
from transim.fpu.format import BINARY16, BINARY32, FloatFormat
from transim.reference.blocks import divide_mantissas

FORMATOS = pytest.mark.parametrize("fmt", [BINARY16, BINARY32], ids=lambda f: f.name)


def test_bits_de_cociente() -> None:
    assert quotient_bits(BINARY32) == 27
    assert quotient_bits(BINARY16) == 14


@pytest.mark.switch
@pytest.mark.parametrize("ancho", [2, 3, 4])
def test_divisor_exhaustivo(ancho: int) -> None:
    q_bits = ancho + 3
    u = HardwareUnit(nonrestoring_divider(ancho, q_bits), "switch")
    normalizados = range(1 << (ancho - 1), 1 << ancho)
    for a, b in itertools.product(normalizados, repeat=2):
        out = u.evaluate({"a": a, "b": b})
        assert (out["q"], out["sticky"]) == tuple(int(x) for x in divide_mantissas(a, b, q_bits))


@pytest.mark.cached
@pytest.mark.parametrize("fmt", [BINARY16, BINARY32], ids=lambda f: f.name)
def test_divisor_anchos_de_mantisa(fmt: FloatFormat) -> None:
    p, q_bits = fmt.precision, quotient_bits(fmt)
    u = HardwareUnit(nonrestoring_divider(p, q_bits), "cached")
    rng = random.Random(p)
    lo, hi = 1 << (p - 1), (1 << p) - 1
    for a, b in [(lo, hi), (hi, lo), (lo, lo)] + [
        (rng.randint(lo, hi), rng.randint(lo, hi)) for _ in range(60)
    ]:
        out = u.evaluate({"a": a, "b": b})
        assert (out["q"], out["sticky"]) == tuple(int(x) for x in divide_mantissas(a, b, q_bits))


@pytest.mark.cached
def test_ejemplo_5_de_docs_03() -> None:
    r = FPDiv(BINARY32).div(0x3F800000, 0x40400000)  # 1/3
    assert r.bits == 0x3EAAAAAB
    assert r.flags.inexact


@pytest.mark.cached
@FORMATOS
def test_rapido(fmt: FloatFormat) -> None:
    comparar(fmt, "/", FPDiv(fmt).div, pares_rapidos(fmt))


@pytest.mark.slow
@FORMATOS
def test_aceptacion(fmt: FloatFormat) -> None:
    assert comparar(fmt, "/", FPDiv(fmt).div, pares_aceptacion(fmt)) > 10_200
