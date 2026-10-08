"""Multiplicador de mantisas y FMUL (responsable: Fabricio). Issues #18 y #19."""

from __future__ import annotations

import itertools
import random

import pytest

from fpu.comun import comparar, pares_aceptacion, pares_rapidos
from pendientes import pendiente
from transim.core import HardwareUnit
from transim.fpu.format import BINARY16, BINARY32, FloatFormat
from transim.fpu.mul import FPMul, array_multiplier
from transim.metrics.count import count_by_cell

FORMATOS = pytest.mark.parametrize("fmt", [BINARY16, BINARY32], ids=lambda f: f.name)


@pendiente(18)
@pytest.mark.switch
@pytest.mark.parametrize("ancho", [1, 2, 3, 4])
def test_arreglo_exhaustivo(ancho: int) -> None:
    u = HardwareUnit(array_multiplier(ancho), "switch")
    for a, b in itertools.product(range(2**ancho), repeat=2):
        assert u.evaluate({"a": a, "b": b})["p"] == a * b, (a, b)


@pendiente(18)
@pytest.mark.cached
@pytest.mark.parametrize("ancho", [11, 24])
def test_arreglo_anchos_de_mantisa(ancho: int) -> None:
    nl = array_multiplier(ancho)
    assert nl.name == f"ARRMUL{ancho}"
    assert count_by_cell(nl)["AND2"][0] == ancho * ancho
    u = HardwareUnit(nl, "cached")
    rng = random.Random(ancho)
    tope = (1 << ancho) - 1
    for a, b in [(tope, tope), (1 << (ancho - 1), 1 << (ancho - 1))] + [
        (rng.getrandbits(ancho), rng.getrandbits(ancho)) for _ in range(100)
    ]:
        assert u.evaluate({"a": a, "b": b})["p"] == a * b


@pendiente(19)
@pytest.mark.cached
def test_ejemplos_de_docs_03() -> None:
    u = FPMul(BINARY32)
    r = u.mul(0x00800001, 0x3F000000)  # ejemplo 4: resultado subnormal
    assert r.bits == 0x00400000
    assert (r.flags.underflow, r.flags.inexact) == (True, True)
    r = u.mul(0x7F7FFFFF, 0x40000000)  # ejemplo 6: overflow
    assert r.bits == 0x7F800000
    assert r.flags.overflow


@pendiente(19)
@pytest.mark.cached
@FORMATOS
def test_rapido(fmt: FloatFormat) -> None:
    comparar(fmt, "*", FPMul(fmt).mul, pares_rapidos(fmt))


@pendiente(19)
@pytest.mark.slow
@FORMATOS
def test_aceptacion(fmt: FloatFormat) -> None:
    assert comparar(fmt, "*", FPMul(fmt).mul, pares_aceptacion(fmt)) > 10_200
