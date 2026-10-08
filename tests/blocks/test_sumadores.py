"""Sumadores RCA y CLA (responsable: Ronald). Issues #7 y #14."""

from __future__ import annotations

import itertools
import random
from collections.abc import Callable

import pytest

from pendientes import pendiente
from transim.blocks.adders import carry_lookahead_adder, ripple_carry_adder
from transim.core import HardwareUnit, Netlist
from transim.metrics.count import count_by_cell
from transim.reference.blocks import adder

SUMADORES = [
    pytest.param(ripple_carry_adder, marks=pendiente(7), id="rca"),
    pytest.param(carry_lookahead_adder, marks=pendiente(14), id="cla"),
]


@pytest.mark.switch
@pytest.mark.parametrize("construir", SUMADORES)
@pytest.mark.parametrize("ancho", [1, 2, 3, 4])
def test_exhaustivo_anchos_pequenos(construir: Callable[[int], Netlist], ancho: int) -> None:
    u = HardwareUnit(construir(ancho), "switch")
    for a, b, cin in itertools.product(range(2**ancho), range(2**ancho), (0, 1)):
        out = u.evaluate({"a": a, "b": b, "cin": cin})
        assert (out["s"], out["cout"]) == adder(a, b, cin, ancho), (a, b, cin)


@pytest.mark.cached
@pytest.mark.parametrize("construir", SUMADORES)
@pytest.mark.parametrize("ancho", [8, 24, 32])
def test_aleatorio_anchos_grandes(construir: Callable[[int], Netlist], ancho: int) -> None:
    u = HardwareUnit(construir(ancho), "cached")
    rng = random.Random(ancho)
    casos = [(2**ancho - 1, 1, 0), (2**ancho - 1, 2**ancho - 1, 1), (0, 0, 0)]
    casos += [
        (rng.getrandbits(ancho), rng.getrandbits(ancho), rng.getrandbits(1)) for _ in range(300)
    ]
    for a, b, cin in casos:
        out = u.evaluate({"a": a, "b": b, "cin": cin})
        assert (out["s"], out["cout"]) == adder(a, b, cin, ancho), (a, b, cin)


@pendiente(7)
def test_rca_usa_un_sumador_completo_por_bit() -> None:
    nl = ripple_carry_adder(8)
    assert nl.name == "RCA8"
    assert count_by_cell(nl)["FA"][0] == 8
    assert nl.transistor_count()["total"] == 8 * 28


@pendiente(14)
def test_cla_mismos_puertos_que_rca() -> None:
    nl = carry_lookahead_adder(8)
    assert nl.name == "CLA8"
    assert set(nl.input_buses) == {"a", "b"}
    assert set(nl.inputs) >= {"cin"}
    assert set(nl.output_buses) == {"s"}
    assert "cout" in nl.outputs
