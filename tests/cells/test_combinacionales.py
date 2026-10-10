"""Celdas combinacionales de L1 (responsable: Jairo). Issues #1–#4."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cells.comun import (
    entradas_solo_a_compuertas,
    equivalencia_motores,
    hojas_tabulables,
    tabla_exhaustiva,
)
from pendientes import pendiente
from transim.cells import combinational as c
from transim.core import Netlist
from transim.reference import cells as ref

# celda, issue, entradas, salidas, referencia, transistores
CELDAS: list[
    tuple[Callable[[], Netlist], int, list[str], list[str], Callable[..., object], int]
] = [
    (c.and2, 1, ["a", "b"], ["y"], ref.and2, 6),
    (c.or2, 1, ["a", "b"], ["y"], ref.or2, 6),
    (c.xor2, 2, ["a", "b"], ["y"], ref.xor2, 12),
    (c.xnor2, 2, ["a", "b"], ["y"], ref.xnor2, 12),
    (c.mux2, 3, ["a", "b", "s"], ["y"], ref.mux2, 12),
    (c.half_adder, 4, ["a", "b"], ["s", "cout"], ref.half_adder, 18),
    (c.full_adder, 4, ["a", "b", "cin"], ["s", "cout"], ref.full_adder, 28),
]


# Issues aún pendientes en esta tabla. Al terminar uno, quite su número del conjunto.
PENDIENTES: set[int] = {2, 3, 4}


def _parametros(celdas: list) -> list:  # type: ignore[type-arg]
    return [
        pytest.param(
            *fila, id=fila[0].__name__, marks=[pendiente(fila[1])] if fila[1] in PENDIENTES else []
        )
        for fila in celdas
    ]


@pytest.mark.switch
@pytest.mark.parametrize(("celda", "issue", "ent", "sal", "fn", "n"), _parametros(CELDAS))
def test_tabla_de_verdad_exhaustiva(celda, issue, ent, sal, fn, n) -> None:  # type: ignore[no-untyped-def]
    tabla_exhaustiva(celda(), ent, sal, fn)


@pytest.mark.parametrize(("celda", "issue", "ent", "sal", "fn", "n"), _parametros(CELDAS))
def test_puertos_y_conteo_de_transistores(celda, issue, ent, sal, fn, n) -> None:  # type: ignore[no-untyped-def]
    nl = celda()
    assert list(nl.inputs) == ent
    assert list(nl.outputs) == sal
    assert nl.transistor_count()["total"] == n
    assert nl.transistor_count()["nmos"] == nl.transistor_count()["pmos"]


@pytest.mark.parametrize(("celda", "issue", "ent", "sal", "fn", "n"), _parametros(CELDAS))
def test_reglas_de_biblioteca(celda, issue, ent, sal, fn, n) -> None:  # type: ignore[no-untyped-def]
    """Entradas solo a compuertas, salidas restauradas y celdas tabulables (ADR-0008)."""
    nl = celda()
    assert entradas_solo_a_compuertas(nl)
    hojas_tabulables(nl)
    assert celda() is nl  # el constructor devuelve siempre el mismo objeto


@pytest.mark.cached
@pytest.mark.parametrize(("celda", "issue", "ent", "sal", "fn", "n"), _parametros(CELDAS))
def test_equivalencia_switch_cached(celda, issue, ent, sal, fn, n) -> None:  # type: ignore[no-untyped-def]
    equivalencia_motores(celda(), ent)


@pendiente(4)
def test_sumador_completo_es_celda_primitiva() -> None:
    """El FA espejo se construye con transistores, no con sub-instancias, para que el
    motor cached lo tabule como una sola celda."""
    nl = c.full_adder()
    assert nl.name == "FA"
    assert not nl.instances


@pendiente(3)
def test_mux2_nombre() -> None:
    assert c.mux2().name == "MUX2"
