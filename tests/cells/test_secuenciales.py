"""Celdas secuenciales de L1 (responsable: Jairo). Issues #5 y #6."""

from __future__ import annotations

import pytest

from pendientes import pendiente
from transim.cells import sequential as seq
from transim.core import Logic, SwitchEngine

pytestmark = pytest.mark.switch
L0, L1 = Logic.ZERO, Logic.ONE


@pendiente(5)
def test_latch_transparente_y_retencion() -> None:
    nl = seq.d_latch()
    assert nl.sequential
    assert list(nl.inputs) == ["d", "clk"]
    assert list(nl.outputs) == ["q"]
    sim = SwitchEngine(nl)
    sim.set_inputs({"d": 1, "clk": 1})
    assert sim.read("q") is L1
    sim.set_inputs({"d": 0})
    assert sim.read("q") is L0  # transparente
    sim.set_inputs({"clk": 0})
    sim.set_inputs({"d": 1})
    assert sim.read("q") is L0  # retiene
    sim.set_inputs({"clk": 1})
    assert sim.read("q") is L1


@pendiente(5)
def test_flip_flop_captura_en_flanco_de_subida() -> None:
    nl = seq.dff()
    assert nl.sequential
    sim = SwitchEngine(nl)
    sim.set_inputs({"clk": 0, "d": 1})
    sim.set_inputs({"clk": 1})
    assert sim.read("q") is L1
    sim.set_inputs({"d": 0})
    assert sim.read("q") is L1  # con clk = 1 no cambia
    sim.set_inputs({"clk": 0})
    assert sim.read("q") is L1  # el flanco de bajada no captura
    sim.set_inputs({"clk": 1})
    assert sim.read("q") is L0


@pendiente(5)
def test_flip_flop_estable_ante_muchos_ciclos() -> None:
    sim = SwitchEngine(seq.dff())
    sim.set_inputs({"clk": 0, "d": 0})
    for i in range(40):
        bit = (i * 7) % 3 % 2
        sim.set_inputs({"d": bit})
        sim.set_inputs({"clk": 1})
        assert sim.read("q") is Logic(bit)
        sim.set_inputs({"clk": 0})


@pendiente(6)
@pytest.mark.parametrize("ancho", [1, 4, 8])
def test_registro_con_habilitacion(ancho: int) -> None:
    nl = seq.register(ancho)
    assert nl.sequential
    assert nl.name == f"REG{ancho}"
    sim = SwitchEngine(nl)
    mask = (1 << ancho) - 1
    sim.set_inputs({"clk": 0, "en": 1, "d": 0b1010 & mask})
    sim.set_inputs({"clk": 1})
    assert sim.read_int("q") == 0b1010 & mask
    sim.set_inputs({"clk": 0, "en": 0})
    sim.set_inputs({"d": mask})
    sim.set_inputs({"clk": 1})
    assert sim.read_int("q") == 0b1010 & mask  # en = 0: conserva
    sim.set_inputs({"clk": 0, "en": 1})
    sim.set_inputs({"clk": 1})
    assert sim.read_int("q") == mask
