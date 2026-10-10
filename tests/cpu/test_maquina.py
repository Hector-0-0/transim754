"""Decodificador, banco de registros, control y máquina T754 (responsable: Héctor). Issue #30."""

from __future__ import annotations

import pytest

from cpu.programas import PROGRAMAS
from transim.core import HardwareUnit, SwitchEngine
from transim.cpu import isa
from transim.cpu.control import ControlFSM, Phase
from transim.cpu.decoder import instruction_decoder
from transim.cpu.isa import Instruction, Opcode
from transim.cpu.machine import Machine
from transim.cpu.registers import register_file
from transim.reference.machine import run

SALIDAS_OPCODE = [op.name.lower() for op in Opcode]


@pytest.mark.cached
def test_decodificador_one_hot_y_campos() -> None:
    u = HardwareUnit(instruction_decoder(), "cached")
    for op in Opcode:
        campos = {c: 5 for c in ("rd", "rs1", "rs2") if c in isa.OPERANDS[op]}
        instr = Instruction(op, **campos)
        out = u.evaluate({"ir": isa.encode(instr)})
        assert {k: out[k] for k in SALIDAS_OPCODE} == {
            k: int(k == op.name.lower()) for k in SALIDAS_OPCODE
        }
        assert out["illegal"] == 0
        assert (out["rd"], out["rs1"], out["rs2"]) == (instr.rd, instr.rs1, instr.rs2)


@pytest.mark.cached
@pytest.mark.parametrize("palabra", [0x05000000, 0x10650001, 0x22000000])
def test_decodificador_detecta_ilegales(palabra: int) -> None:
    out = HardwareUnit(instruction_decoder(), "cached").evaluate({"ir": palabra})
    assert out["illegal"] == 1


@pytest.mark.switch
def test_banco_de_registros_escribe_y_lee() -> None:
    sim = SwitchEngine(register_file(n_regs=4, width=4))
    sim.set_inputs({"clk": 0, "we": 1})
    for r in range(4):
        sim.set_inputs({"wa": r, "wd": r + 9})
        sim.set_inputs({"clk": 1})
        sim.set_inputs({"clk": 0})
    sim.set_inputs({"we": 0, "wd": 0, "wa": 2})
    sim.set_inputs({"clk": 1})  # we = 0: no escribe
    sim.set_inputs({"ra1": 2, "ra2": 3})
    assert (sim.read_int("rd1"), sim.read_int("rd2")) == (11, 12)


def test_fsm_recorre_las_cuatro_fases() -> None:
    fsm = ControlFSM()
    assert fsm.phase is Phase.FETCH
    assert [fsm.advance() for _ in range(4)] == [
        Phase.DECODE,
        Phase.EXECUTE,
        Phase.WRITEBACK,
        Phase.FETCH,
    ]
    fsm.advance()
    assert fsm.advance(halt=True) is Phase.HALTED


@pytest.mark.cached
@pytest.mark.parametrize("nombre", sorted(PROGRAMAS))
def test_maquina_igual_a_la_referencia(nombre: str) -> None:
    palabras, salidas, fsr = PROGRAMAS[nombre]
    estado = Machine(palabras).run()
    esperado = run(palabras)
    assert estado.outputs == salidas == esperado.outputs
    assert estado.fsr == fsr == esperado.fsr
    assert estado.regs == esperado.regs
    assert (estado.pc, estado.halted) == (esperado.pc, True)
