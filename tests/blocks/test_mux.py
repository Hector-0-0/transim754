"""Multiplexores de bus (responsable: Ronald). Issue #10."""

from __future__ import annotations

import random

import pytest

from pendientes import pendiente
from transim.blocks.mux import mux2_bus, mux_n
from transim.core import HardwareUnit
from transim.metrics.count import count_by_cell

pytestmark = pendiente(10)


def test_mux2_bus() -> None:
    u = HardwareUnit(mux2_bus(8), "switch")
    for a, b, s in [(0x12, 0xAB, 0), (0x12, 0xAB, 1), (0xFF, 0, 1), (0, 0xFF, 0)]:
        assert u.evaluate({"a": a, "b": b, "s": s})["y"] == (b if s else a)
    assert count_by_cell(mux2_bus(8))["MUX2"][0] == 8


@pytest.mark.parametrize("n", [2, 4, 8])
def test_mux_n(n: int) -> None:
    nl = mux_n(6, n)
    assert nl.name == f"MUX{n}x6"
    u = HardwareUnit(nl, "cached")
    rng = random.Random(n)
    valores = [rng.getrandbits(6) for _ in range(n)]
    entradas = {f"in{i}": v for i, v in enumerate(valores)}
    for sel in range(n):
        assert u.evaluate(entradas | {"sel": sel})["y"] == valores[sel]


def test_mux_n_rechaza_n_que_no_es_potencia_de_2() -> None:
    with pytest.raises(ValueError, match="potencia"):
        mux_n(4, 3)
