"""Simulador de referencia de T754 con programas codificados a mano."""

from __future__ import annotations

import pytest

from transim.cpu import isa
from transim.cpu.isa import Instruction, Opcode
from transim.reference.machine import MachineError, run

Ins = Instruction


def prog(*items: Instruction | int) -> list[int]:
    return [isa.encode(x) if isinstance(x, Instruction) else x for x in items]


def test_horner_de_docs_04() -> None:
    p = prog(
        Ins(Opcode.LI, rd=1), 0x3FC00000,  # x = 1.5
        Ins(Opcode.LI, rd=2), 0x40000000,  # 2
        Ins(Opcode.LI, rd=3), 0x40400000,  # 3
        Ins(Opcode.LI, rd=4), 0x3F800000,  # 1
        Ins(Opcode.FMUL, rd=5, rs1=2, rs2=1),
        Ins(Opcode.FSUB, rd=5, rs1=5, rs2=3),
        Ins(Opcode.FMUL, rd=5, rs1=5, rs2=1),
        Ins(Opcode.FADD, rd=5, rs1=5, rs2=4),
        Ins(Opcode.OUT, rs1=5),
        Ins(Opcode.HALT),
    )  # fmt: skip
    s = run(p)
    assert s.outputs == [0x3F800000]
    assert s.fsr == 0
    assert s.halted
    assert s.pc == len(p) - 1


def test_flags_acumulativos_y_clrf() -> None:
    p = prog(
        Ins(Opcode.LI, rd=1), 0x3F800000,
        Ins(Opcode.FDIV, rd=2, rs1=1, rs2=0),  # 1/0 → DZ
        Ins(Opcode.LI, rd=3), 0x40400000,
        Ins(Opcode.FDIV, rd=4, rs1=1, rs2=3),  # 1/3 → NX
        Ins(Opcode.OUT, rs1=2),
        Ins(Opcode.HALT),
    )  # fmt: skip
    s = run(p)
    assert s.outputs == [0x7F800000]
    assert s.fsr == 0b01001  # DZ | NX
    s2 = run(p[:-1] + prog(Ins(Opcode.CLRF), Ins(Opcode.HALT)))
    assert s2.fsr == 0


def test_alu_entera_escribe_cvzn_sin_tocar_flags_fp() -> None:
    p = prog(
        Ins(Opcode.LI, rd=1), 5,
        Ins(Opcode.LI, rd=2), 7,
        Ins(Opcode.FDIV, rd=0, rs1=1, rs2=0),  # 5 (subnormal) / 0 → DZ
        Ins(Opcode.SUB, rd=3, rs1=1, rs2=2),  # 5 − 7: préstamo (C=0), N=1
        Ins(Opcode.OUT, rs1=3),
        Ins(Opcode.HALT),
    )  # fmt: skip
    s = run(p)
    assert s.outputs == [0xFFFFFFFE]
    assert s.fsr == (1 << isa.FSR_N) | 0b01000


def test_errores_de_ejecucion() -> None:
    with pytest.raises(MachineError, match="sin HALT"):
        run(prog(Ins(Opcode.NOP)))
    with pytest.raises(MachineError, match="literal"):
        run(prog(Ins(Opcode.LI, rd=1)))
    with pytest.raises(isa.IllegalInstructionError):
        run([0x05000000])
