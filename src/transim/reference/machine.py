"""Simulador de referencia de la ISA T754 (comportamiento puro, ADR-0010).

Ejecuta un programa ya ensamblado (lista de palabras de 32 bits) con la FPU y la ALU
de referencia. La máquina de transistores (``cpu/machine.py``) debe producir el mismo
estado final, las mismas salidas y el mismo FSR para cualquier programa.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from transim.cpu import isa
from transim.cpu.isa import Opcode
from transim.fpu.format import BINARY32, FloatFormat
from transim.reference import fpu as ref_fpu
from transim.reference.integer import int_add, int_sub

DEFAULT_MAX_STEPS = 100_000


class MachineError(RuntimeError):
    """Error de ejecución: PC fuera del programa, LI sin literal o límite de pasos."""


@dataclass
class MachineState:
    """Estado arquitectónico de T754."""

    regs: list[int] = field(default_factory=lambda: [0] * isa.N_REGS)
    fsr: int = 0
    pc: int = 0
    halted: bool = False
    outputs: list[int] = field(default_factory=list)
    steps: int = 0


_FP = {
    Opcode.FADD: ref_fpu.fadd,
    Opcode.FSUB: ref_fpu.fsub,
    Opcode.FMUL: ref_fpu.fmul,
    Opcode.FDIV: ref_fpu.fdiv,
}


def step(state: MachineState, program: Sequence[int], fmt: FloatFormat = BINARY32) -> None:
    """Ejecuta una instrucción (FETCH, DECODE, EXECUTE, WRITEBACK).

    Raises:
        MachineError: si el PC sale del programa o falta el literal de LI.
        isa.IllegalInstructionError: si la palabra no es una instrucción válida.
    """
    if state.halted:
        return
    if not 0 <= state.pc < len(program):
        raise MachineError(f"PC={state.pc} fuera del programa (sin HALT)")
    instr = isa.decode(program[state.pc])
    op, r = instr.opcode, state.regs
    if op is Opcode.LI:
        if state.pc + 1 >= len(program):
            raise MachineError(f"PC={state.pc}: LI sin literal")
        r[instr.rd] = program[state.pc + 1]
    elif op is Opcode.MOV:
        r[instr.rd] = r[instr.rs1]
    elif op in _FP:
        result = _FP[op](fmt, r[instr.rs1], r[instr.rs2])
        r[instr.rd] = result.bits
        state.fsr |= result.flags.to_bits()
    elif op in isa.INT_OPS:
        fn = int_add if op is Opcode.ADD else int_sub
        res = fn(r[instr.rs1], r[instr.rs2], isa.WORD_BITS)
        r[instr.rd] = res.value
        cvzn = (
            int(res.c) << isa.FSR_C
            | int(res.v) << isa.FSR_V
            | int(res.z) << isa.FSR_Z
            | int(res.n) << isa.FSR_N
        )
        state.fsr = (state.fsr & ~isa.FSR_INT_MASK) | cvzn
    elif op is Opcode.OUT:
        state.outputs.append(r[instr.rs1])
    elif op is Opcode.CLRF:
        state.fsr = 0
    elif op is Opcode.HALT:
        state.halted = True
    state.pc += instr.words if not state.halted else 0
    state.steps += 1


def run(
    program: Sequence[int],
    fmt: FloatFormat = BINARY32,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> MachineState:
    """Ejecuta ``program`` desde PC = 0 hasta HALT.

    Raises:
        MachineError: si se supera ``max_steps`` o el programa termina sin HALT.
    """
    state = MachineState()
    while not state.halted:
        if state.steps >= max_steps:
            raise MachineError(f"se superaron {max_steps} pasos sin HALT")
        step(state, program, fmt)
    return state
