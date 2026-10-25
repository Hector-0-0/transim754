"""Etapas del camino crítico, ciclos estimados y actividad por etapa (ADR-0014)."""

from __future__ import annotations

import pytest

from transim.alu.int_alu import int_alu
from transim.cells.combinational import inv
from transim.core import Netlist, SwitchEngine
from transim.fpu.add_sub import FPAddSub
from transim.fpu.format import BINARY16
from transim.metrics.critical_path import cell_depth
from transim.metrics.stages import (
    GLUE,
    Stage,
    activity_by_stage,
    critical_stages,
    reference_period,
    schedule,
)


def cadena(n: int, nombre: str = "cadena") -> Netlist:
    nl = Netlist(f"{nombre}{n}")
    x = nl.input("a")
    for i in range(n):
        x = nl.instantiate(inv(), f"i{i}", {"a": x})["y"]
    nl.mark_output("y", x)
    return nl


def test_celdas_sueltas_son_enlace() -> None:
    assert critical_stages(cadena(4)) == (Stage(GLUE, 4),)


def test_etapas_por_bloque_de_primer_nivel() -> None:
    sub = cadena(3, "sub")
    top = Netlist("top")
    x = top.instantiate(sub, "u0", {"a": top.input("a")})["y"]
    x = top.instantiate(inv(), "suelta", {"a": x})["y"]
    top.instantiate(sub, "u1", {"a": x, "y": top.output("y")})
    assert critical_stages(top) == (Stage("u0", 3), Stage(GLUE, 1), Stage("u1", 3))


def test_reparto_en_ciclos() -> None:
    etapas = (Stage("u0", 3), Stage(GLUE, 1), Stage("u1", 3))
    ciclos = schedule(etapas, 4)
    assert [(c.first_cell, c.last_cell) for c in ciclos] == [(1, 4), (5, 7)]
    assert ciclos[0].stages == ("u0", "selección y enlace")
    assert ciclos[1].stages == ("u1",)
    with pytest.raises(ValueError, match="periodo"):
        schedule(etapas, 0)


def test_periodo_de_referencia_es_la_alu() -> None:
    assert reference_period() == cell_depth(int_alu())


@pytest.mark.cached
def test_actividad_por_etapa_suma_el_total() -> None:
    u = FPAddSub(BINARY16)
    u.add(0x3C00, 0x4000)
    u.engine.reset_counters()
    u.add(0x3E00, 0x4080)  # 1.5 + 2.25
    por_etapa = activity_by_stage(u.engine)
    assert sum(por_etapa.values()) == u.engine.stats().node_toggles
    assert por_etapa["align"] > 0
    assert por_etapa["round"] > 0


def test_actividad_en_motor_exacto() -> None:
    nl = cadena(3)
    motor = SwitchEngine(nl)
    motor.set_inputs({"a": 0})
    motor.reset_counters()
    motor.set_inputs({"a": 1})
    assert activity_by_stage(motor) == {"(entradas)": 1, GLUE: 3}
