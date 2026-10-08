"""Actividad y camino crítico (responsable: Yenny). Issues #22 y #23."""

from __future__ import annotations

import pytest

from pendientes import pendiente
from transim.cells.combinational import inv, nand2
from transim.core import Netlist, SwitchEngine
from transim.metrics.activity import measure_activity
from transim.metrics.critical_path import cell_depth, critical_path


def cadena_de_inversores(n: int) -> Netlist:
    nl = Netlist(f"cadena{n}")
    x = nl.input("a")
    for i in range(n):
        x = nl.instantiate(inv(), f"i{i}", {"a": x})["y"]
    nl.mark_output("y", x)
    return nl


@pendiente(22)
def test_actividad_de_una_cadena() -> None:
    nl = cadena_de_inversores(5)
    motor = SwitchEngine(nl)
    motor.set_inputs({"a": 0})
    reporte = measure_activity(motor, [{"a": 1}, {"a": 0}, {"a": 1}, {"a": 1}])
    assert reporte.operations == 4
    assert reporte.node_toggles == 3 * 6  # 3 cambios efectivos × (entrada + 5 salidas)
    assert reporte.transistor_events == 3 * 10
    assert reporte.nodes == 5
    assert reporte.alpha == pytest.approx(reporte.node_toggles / (5 * 4))
    assert reporte.seconds >= 0


@pendiente(22)
def test_actividad_sin_estimulos() -> None:
    with pytest.raises(ValueError, match="vac"):
        measure_activity(SwitchEngine(cadena_de_inversores(1)), [])


@pendiente(23)
@pytest.mark.parametrize("n", [1, 4, 9])
def test_profundidad_de_una_cadena(n: int) -> None:
    nl = cadena_de_inversores(n)
    assert cell_depth(nl) == n
    assert critical_path(nl) == [f"i{i}" for i in range(n)]


@pendiente(23)
def test_profundidad_toma_el_camino_mas_largo() -> None:
    nl = Netlist("ramas")
    a, b = nl.input("a"), nl.input("b")
    x = nl.instantiate(inv(), "corto", {"a": a})["y"]
    y = b
    for i in range(3):
        y = nl.instantiate(inv(), f"largo{i}", {"a": y})["y"]
    nl.instantiate(nand2(), "final", {"a": x, "b": y, "y": nl.output("y")})
    assert cell_depth(nl) == 4
    assert critical_path(nl)[-1] == "final"


@pendiente(23)
def test_profundidad_cuenta_celdas_primitivas_en_jerarquia() -> None:
    sub = cadena_de_inversores(3)
    top = Netlist("top")
    x = top.instantiate(sub, "u0", {"a": top.input("a")})["y"]
    top.instantiate(sub, "u1", {"a": x, "y": top.output("y")})
    assert cell_depth(top) == 6
    assert critical_path(top)[0] == "u0.i0"
