"""Propagación con retardo unitario y rejilla de bits (ADR-0018), sin Qt."""

from __future__ import annotations

import pytest

from transim.fpu.format import BINARY16, BINARY32, FloatFormat
from transim.metrics.critical_path import cell_depth
from transim.ui.gui import model
from transim.ui.gui.bitgrid import grid


def calculo(fmt: FloatFormat, op: str, a: str, b: str) -> model.Calculation:
    return model.calculate(
        fmt, op, model.parse_operand(a, fmt), model.parse_operand(b, fmt), "cached"
    )


@pytest.mark.parametrize("fmt", [BINARY32, BINARY16])
@pytest.mark.parametrize("ejemplo", model.EXAMPLES, ids=lambda e: e.title)
def test_la_reproduccion_termina_en_el_estado_del_motor(
    fmt: FloatFormat, ejemplo: model.Example
) -> None:
    """Para cada ejemplo, la reproducción por rondas llega nodo por nodo al estado estable
    que calculó el motor, y no tarda más rondas que el camino más largo de la unidad."""
    a, b = ejemplo.operands(fmt)
    calc = calculo(fmt, ejemplo.op, a, b)
    r = calc.propagation()
    assert r.valid, r.reason
    assert r.length <= cell_depth(calc.unit.netlist)
    final = r.values_at(r.length)
    for cambios in r.rounds:
        for n in cambios:
            assert final[n] == calc.after[n]


def test_instante_cero_y_rondas() -> None:
    calculo(BINARY32, "add", "1", "1")
    calc = calculo(BINARY32, "add", "1.5", "2.25")
    r = calc.propagation()
    assert r.values_at(0) == list(r.start)
    assert r.length == len(r.rounds) == len(r.cells_changed)
    assert all(r.rounds)  # cada ronda cambia algo
    assert calc.propagation() is r  # se calcula una sola vez


def test_operacion_repetida_no_propaga_nada() -> None:
    calculo(BINARY32, "add", "1.5", "2.25")
    r = calculo(BINARY32, "add", "1.5", "2.25").propagation()
    assert r.valid
    assert r.length == 0


def test_rejilla_del_sumador_es_una_escalera() -> None:
    netlist = model.unit_for(BINARY32, "add", "cached").netlist
    g = grid(netlist, "mant_addsub")
    celdas = [i for i in netlist.leaf_instances() if i.path.startswith("mant_addsub.")]
    assert len(g.slots) == len(celdas)
    fas = sorted((s.column, s.row) for s in g.slots if s.inst.definition.name == "FA")
    assert [c for c, _ in fas] == list(range(len(fas)))  # un FA por bit
    filas = [r for _, r in fas]
    assert filas == sorted(filas)  # el acarreo baja un nivel por bit
    assert len(set(filas)) == len(filas)
    assert {s.row for s in g.slots if s.inst.definition.name == "XOR2" and s.column > 0} == {0}


def test_rejilla_del_desplazador_tiene_sus_cinco_niveles() -> None:
    netlist = model.unit_for(BINARY32, "add", "cached").netlist
    g = grid(netlist, "normalize")  # 140 MUX2 en 5 niveles
    filas = {s.row for s in g.slots}
    assert len(filas) == 5
    assert g.columns > 20  # los bits se reparten en columnas, no en una sola
