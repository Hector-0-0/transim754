"""Sumador/restador en complemento a 2 (responsable: Ronald). Issue #8."""

from __future__ import annotations

import itertools
import random

import pytest

from transim.blocks.subtractor import adder_subtractor
from transim.core import HardwareUnit
from transim.reference.blocks import add_sub


@pytest.mark.switch
@pytest.mark.parametrize("ancho", [1, 3, 4])
def test_exhaustivo(ancho: int) -> None:
    u = HardwareUnit(adder_subtractor(ancho), "switch")
    for a, b, sub in itertools.product(range(2**ancho), range(2**ancho), (0, 1)):
        out = u.evaluate({"a": a, "b": b, "sub": sub})
        s, cout, ovf = add_sub(a, b, sub, ancho)
        assert (out["s"], out["cout"], out["ovf"]) == (s, cout, int(ovf)), (a, b, sub)


@pytest.mark.cached
@pytest.mark.parametrize("ancho", [8, 32])
def test_aleatorio(ancho: int) -> None:
    u = HardwareUnit(adder_subtractor(ancho), "cached")
    rng = random.Random(ancho)
    for _ in range(300):
        a, b, sub = rng.getrandbits(ancho), rng.getrandbits(ancho), rng.getrandbits(1)
        s, cout, ovf = add_sub(a, b, sub, ancho)
        out = u.evaluate({"a": a, "b": b, "sub": sub})
        assert (out["s"], out["cout"], out["ovf"]) == (s, cout, int(ovf))


def test_nombre_y_puertos() -> None:
    nl = adder_subtractor(8)
    assert nl.name == "ADDSUB8"
    assert set(nl.outputs) >= {"cout", "ovf"}
