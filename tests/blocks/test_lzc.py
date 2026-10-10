"""Contador de ceros a la izquierda (responsable: Ronald). Issue #12."""

from __future__ import annotations

import random

import pytest

from transim.blocks.lzc import count_bits_for, leading_zero_counter
from transim.core import HardwareUnit
from transim.reference.blocks import leading_zeros


@pytest.mark.switch
@pytest.mark.parametrize("ancho", [1, 2, 5, 8])
def test_exhaustivo(ancho: int) -> None:
    u = HardwareUnit(leading_zero_counter(ancho), "switch")
    for a in range(2**ancho):
        assert u.evaluate({"a": a})["count"] == leading_zeros(a, ancho), a


@pytest.mark.cached
@pytest.mark.parametrize("ancho", [24, 27, 48])
def test_anchos_de_la_fpu(ancho: int) -> None:
    u = HardwareUnit(leading_zero_counter(ancho), "cached")
    assert len(u.netlist.output_buses["count"]) == count_bits_for(ancho)
    rng = random.Random(ancho)
    casos = [0, 1, 2 ** (ancho - 1)] + [
        rng.getrandbits(rng.randrange(1, ancho + 1)) for _ in range(150)
    ]
    for a in casos:
        assert u.evaluate({"a": a})["count"] == leading_zeros(a, ancho), a
