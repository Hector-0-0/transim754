"""Celdas semilla INV, NAND2 y NOR2: tablas de verdad exhaustivas y conteo."""

from __future__ import annotations

import itertools
from collections.abc import Callable

import pytest

from transim.cells import combinational, library
from transim.core import Logic, Netlist, SwitchEngine

pytestmark = pytest.mark.switch

CASOS: list[tuple[Callable[[], Netlist], int, Callable[..., int], int]] = [
    (combinational.inv, 1, lambda a: 1 - a, 2),
    (combinational.nand2, 2, lambda a, b: 1 - (a & b), 4),
    (combinational.nor2, 2, lambda a, b: 1 - (a | b), 4),
]


@pytest.mark.parametrize(("celda", "n", "funcion", "transistores"), CASOS)
def test_tabla_de_verdad_exhaustiva(
    celda: Callable[[], Netlist], n: int, funcion: Callable[..., int], transistores: int
) -> None:
    nl = celda()
    sim = SwitchEngine(nl)
    nombres = list(nl.inputs)
    assert len(nombres) == n
    for combo in itertools.product((0, 1), repeat=n):
        sim.set_inputs(dict(zip(nombres, combo, strict=True)))
        assert sim.read("y") is Logic(funcion(*combo)), combo


@pytest.mark.parametrize(("celda", "n", "funcion", "transistores"), CASOS)
def test_conteo_y_reglas_de_interfaz(
    celda: Callable[[], Netlist], n: int, funcion: Callable[..., int], transistores: int
) -> None:
    nl = celda()
    conteo = nl.transistor_count()
    assert conteo["total"] == transistores
    assert conteo["nmos"] == conteo["pmos"]  # CMOS complementario
    canales = {t.source.id for t in nl.transistors} | {t.drain.id for t in nl.transistors}
    assert all(n.id not in canales for n in nl.inputs.values())  # entradas solo a compuertas
    assert list(nl.outputs) == ["y"]


def test_constructores_devuelven_el_mismo_objeto() -> None:
    assert combinational.nand2() is combinational.nand2()


def test_registro_de_la_biblioteca() -> None:
    assert {"INV", "NAND2", "NOR2"} <= set(library.available())
    assert library.cell("NAND2") is combinational.nand2()
    with pytest.raises(KeyError, match="disponibles"):
        library.cell("NAND9")
