"""Conjunto de instrucciones T754: opcodes, campos y codificación (ADR-0010).

Formato de palabra (32 bits)::

    [31:24] opcode  [23:21] rd  [20:18] rs1  [17:15] rs2  [14:0] reservado (0)

``LI`` ocupa dos palabras: la instrucción y el literal de 32 bits. Este módulo es la
especificación ejecutable de la ISA; lo usan el ensamblador, el decodificador, la
máquina y el modelo de referencia.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

WORD_BITS = 32
"""Ancho de palabra de la máquina y de los registros F0–F7."""

WORD_BYTES = WORD_BITS // 8
"""Bytes por palabra en el binario ensamblado."""

N_REGS = 8
"""Número de registros F0–F7."""

REG_BITS = 3
OPCODE_SHIFT, RD_SHIFT, RS1_SHIFT, RS2_SHIFT = 24, 21, 18, 15
OPCODE_MASK = 0xFF
REG_MASK = 0b111
RESERVED_MASK = (1 << RS2_SHIFT) - 1
WORD_MASK = (1 << WORD_BITS) - 1

# Bits del registro de estado FSR (ADR-0004).
FSR_FLAGS_MASK = 0b11111  # bits 0–4: NX, UF, OF, DZ, NV (acumulativos)
FSR_C, FSR_V, FSR_Z, FSR_N = 8, 9, 10, 11  # indicadores enteros (no acumulativos)
FSR_INT_MASK = 0b1111 << FSR_C


class Opcode(IntEnum):
    """Códigos de operación de T754."""

    NOP = 0x00
    LI = 0x01
    MOV = 0x02
    FADD = 0x10
    FSUB = 0x11
    FMUL = 0x12
    FDIV = 0x13
    ADD = 0x20
    SUB = 0x21
    OUT = 0x30
    CLRF = 0x31
    HALT = 0xFF


OPERANDS: dict[Opcode, tuple[str, ...]] = {
    Opcode.NOP: (),
    Opcode.LI: ("rd", "lit"),
    Opcode.MOV: ("rd", "rs1"),
    Opcode.FADD: ("rd", "rs1", "rs2"),
    Opcode.FSUB: ("rd", "rs1", "rs2"),
    Opcode.FMUL: ("rd", "rs1", "rs2"),
    Opcode.FDIV: ("rd", "rs1", "rs2"),
    Opcode.ADD: ("rd", "rs1", "rs2"),
    Opcode.SUB: ("rd", "rs1", "rs2"),
    Opcode.OUT: ("rs1",),
    Opcode.CLRF: (),
    Opcode.HALT: (),
}
"""Operandos de cada instrucción, en el orden en que se escriben en ensamblador."""

FP_OPS = frozenset({Opcode.FADD, Opcode.FSUB, Opcode.FMUL, Opcode.FDIV})
INT_OPS = frozenset({Opcode.ADD, Opcode.SUB})


class IllegalInstructionError(ValueError):
    """Palabra que no codifica una instrucción válida de T754."""


@dataclass(frozen=True, slots=True)
class Instruction:
    """Instrucción decodificada. Los campos no usados valen 0."""

    opcode: Opcode
    rd: int = 0
    rs1: int = 0
    rs2: int = 0

    @property
    def words(self) -> int:
        """Palabras que ocupa en memoria (2 para LI, 1 para el resto)."""
        return 2 if self.opcode is Opcode.LI else 1

    def __str__(self) -> str:
        regs = {"rd": self.rd, "rs1": self.rs1, "rs2": self.rs2}
        ops = [f"F{regs[o]}" for o in OPERANDS[self.opcode] if o in regs]
        return f"{self.opcode.name} {', '.join(ops)}".strip()


def encode(instr: Instruction) -> int:
    """Codifica ``instr`` en una palabra de 32 bits (sin el literal de LI).

    Raises:
        ValueError: si un registro está fuera de F0–F7 o se usa un campo no permitido.
    """
    used = OPERANDS[instr.opcode]
    for field_name in ("rd", "rs1", "rs2"):
        value = getattr(instr, field_name)
        if not 0 <= value < N_REGS:
            raise ValueError(f"{field_name}={value} fuera de F0–F{N_REGS - 1}")
        if value and field_name not in used:
            raise ValueError(f"{instr.opcode.name} no usa el campo {field_name}")
    return (
        (int(instr.opcode) << OPCODE_SHIFT)
        | (instr.rd << RD_SHIFT)
        | (instr.rs1 << RS1_SHIFT)
        | (instr.rs2 << RS2_SHIFT)
    )


def decode(word: int) -> Instruction:
    """Decodifica una palabra.

    Raises:
        IllegalInstructionError: opcode no definido, bits reservados distintos de cero o
            campo de registro no usado distinto de cero.
    """
    if not 0 <= word <= WORD_MASK:
        raise IllegalInstructionError(f"{word:#x} no es una palabra de {WORD_BITS} bits")
    raw = (word >> OPCODE_SHIFT) & OPCODE_MASK
    try:
        opcode = Opcode(raw)
    except ValueError:
        raise IllegalInstructionError(f"opcode no definido {raw:#04x}") from None
    if word & RESERVED_MASK:
        raise IllegalInstructionError(f"{word:#010x}: bits reservados [14:0] distintos de cero")
    fields = {
        "rd": (word >> RD_SHIFT) & REG_MASK,
        "rs1": (word >> RS1_SHIFT) & REG_MASK,
        "rs2": (word >> RS2_SHIFT) & REG_MASK,
    }
    for name, value in fields.items():
        if value and name not in OPERANDS[opcode]:
            raise IllegalInstructionError(f"{word:#010x}: {opcode.name} no usa {name}")
    return Instruction(opcode, **fields)
