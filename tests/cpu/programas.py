"""Programas de ejemplo: código máquina codificado a mano y resultados esperados.

Las palabras se escriben con ``isa.encode`` (no con el ensamblador) para que las
pruebas de la máquina no dependan del ensamblador, y viceversa.
"""

from __future__ import annotations

from pathlib import Path

from transim.cpu import isa
from transim.cpu.isa import Instruction as I  # noqa: N817
from transim.cpu.isa import Opcode as O  # noqa: N817

EJEMPLOS = Path(__file__).resolve().parent.parent.parent / "examples"


def _p(*items: I | int) -> list[int]:
    return [isa.encode(x) if isinstance(x, I) else x for x in items]


PROGRAMAS: dict[str, tuple[list[int], list[int], int]] = {
    # nombre: (palabras, salidas esperadas, FSR esperado)
    "suma_simple": (
        _p(I(O.LI, rd=1), 0x3FC00000, I(O.LI, rd=2), 0x40100000,
           I(O.FADD, rd=3, rs1=1, rs2=2), I(O.OUT, rs1=3), I(O.HALT)),
        [0x40700000], 0,
    ),
    "horner": (
        _p(I(O.LI, rd=1), 0x3FC00000, I(O.LI, rd=2), 0x40000000,
           I(O.LI, rd=3), 0x40400000, I(O.LI, rd=4), 0x3F800000,
           I(O.FMUL, rd=5, rs1=2, rs2=1), I(O.FSUB, rd=5, rs1=5, rs2=3),
           I(O.FMUL, rd=5, rs1=5, rs2=1), I(O.FADD, rd=5, rs1=5, rs2=4),
           I(O.OUT, rs1=5), I(O.HALT)),
        [0x3F800000], 0,
    ),
    "casos_especiales": (
        _p(I(O.LI, rd=0), 0x00000000, I(O.LI, rd=1), 0x3F800000,
           I(O.LI, rd=2), 0x7F800000, I(O.LI, rd=3), 0x80000000,
           I(O.FDIV, rd=4, rs1=1, rs2=0), I(O.OUT, rs1=4),
           I(O.FDIV, rd=5, rs1=0, rs2=0), I(O.OUT, rs1=5),
           I(O.FSUB, rd=6, rs1=2, rs2=2), I(O.OUT, rs1=6),
           I(O.FADD, rd=7, rs1=3, rs2=3), I(O.OUT, rs1=7), I(O.HALT)),
        [0x7F800000, 0x7FC00000, 0x7FC00000, 0x80000000], 0x18,
    ),
    "subnormales": (
        _p(I(O.LI, rd=1), 0x00800001, I(O.LI, rd=2), 0x3F000000,
           I(O.FMUL, rd=3, rs1=1, rs2=2), I(O.OUT, rs1=3),
           I(O.LI, rd=4), 0x00000001, I(O.FADD, rd=5, rs1=4, rs2=4),
           I(O.OUT, rs1=5), I(O.HALT)),
        [0x00400000, 0x00000002], 0x03,
    ),
}  # fmt: skip
