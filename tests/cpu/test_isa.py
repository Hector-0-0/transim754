"""Codificación y decodificación de la ISA T754 (docs/04)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from transim.cpu import isa
from transim.cpu.isa import IllegalInstructionError, Instruction, Opcode


def test_ejemplo_de_docs_04() -> None:
    assert isa.encode(Instruction(Opcode.FADD, rd=3, rs1=1, rs2=2)) == 0x10650000
    assert isa.decode(0x10650000) == Instruction(Opcode.FADD, 3, 1, 2)
    assert str(Instruction(Opcode.FADD, 3, 1, 2)) == "FADD F3, F1, F2"


def test_opcodes_de_adr_0010() -> None:
    assert {op.name: op.value for op in Opcode} == {
        "NOP": 0x00, "LI": 0x01, "MOV": 0x02, "FADD": 0x10, "FSUB": 0x11, "FMUL": 0x12,
        "FDIV": 0x13, "ADD": 0x20, "SUB": 0x21, "OUT": 0x30, "CLRF": 0x31, "HALT": 0xFF,
    }  # fmt: skip


@st.composite
def instrucciones(draw: st.DrawFn) -> Instruction:
    op = draw(st.sampled_from(list(Opcode)))
    campos = {c: draw(st.integers(0, 7)) for c in ("rd", "rs1", "rs2") if c in isa.OPERANDS[op]}
    return Instruction(op, **campos)


@given(instrucciones())
def test_ida_y_vuelta(instr: Instruction) -> None:
    assert isa.decode(isa.encode(instr)) == instr


@pytest.mark.parametrize(
    ("palabra", "motivo"),
    [
        (0x05000000, "opcode no definido"),
        (0x10650001, "reservados"),
        (0xFF200000, "no usa rd"),
        (0x30200000, "no usa rd"),
        (2**32, "32 bits"),
    ],
)
def test_instrucciones_ilegales(palabra: int, motivo: str) -> None:
    with pytest.raises(IllegalInstructionError, match=motivo):
        isa.decode(palabra)


def test_encode_valida_campos() -> None:
    with pytest.raises(ValueError, match="fuera"):
        isa.encode(Instruction(Opcode.MOV, rd=8))
    with pytest.raises(ValueError, match="no usa"):
        isa.encode(Instruction(Opcode.HALT, rd=1))
    assert Instruction(Opcode.LI, rd=1).words == 2
