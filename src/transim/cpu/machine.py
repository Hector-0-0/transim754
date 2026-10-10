"""Máquina T754 con datapath de transistores. ADR-0006, ADR-0010.

Integra memoria de programa (Python), ``ControlFSM``, decodificador de compuertas,
banco de registros de flip-flops, ``IntALU`` y las unidades de la FPU. Para cualquier
programa debe producir el mismo :class:`MachineState` que ``reference.machine.run``.
"""

from __future__ import annotations

from collections.abc import Sequence

from transim.alu.int_alu import OP_ADD, OP_SUB, IntALU
from transim.core.unit import EngineName, HardwareUnit, make_engine
from transim.cpu import isa
from transim.cpu.control import ControlFSM, Phase
from transim.cpu.decoder import instruction_decoder
from transim.cpu.registers import register_file
from transim.fpu.add_sub import FPAddSub
from transim.fpu.div import FPDiv
from transim.fpu.format import BINARY32, FloatFormat, FPResult, UndefinedOutputError
from transim.fpu.mul import FPMul
from transim.reference.machine import DEFAULT_MAX_STEPS, MachineError, MachineState

FPU_ADD, FPU_SUB, FPU_MUL, FPU_DIV = range(4)
"""Valores de la señal ``fpu_op`` del decodificador."""


class Machine:
    """Procesador T754 simulado.

    Args:
        program: palabras de 32 bits (salida del ensamblador).
        fmt: formato de punto flotante (binary32).
        engine: motor de simulación para el datapath.
    """

    def __init__(
        self,
        program: Sequence[int],
        fmt: FloatFormat = BINARY32,
        engine: EngineName = "cached",
    ) -> None:
        self.program = list(program)
        self.fmt = fmt
        self.engine: EngineName = engine
        self.fsm = ControlFSM()
        self.decoder = HardwareUnit(instruction_decoder(), engine)
        self.regs = make_engine(register_file(), engine)
        self.alu = IntALU(engine=engine)
        self._addsub: FPAddSub | None = None
        self._mul: FPMul | None = None
        self._div: FPDiv | None = None
        self.fsr = 0
        self.pc = 0
        self.outputs: list[int] = []
        self.steps = 0
        # Reinicio: los flip-flops arrancan sin valor; se escribe 0 en F0–F7.
        self.regs.set_inputs({"clk": 0, "we": 0, "ra1": 0, "ra2": 0, "wa": 0, "wd": 0})
        for r in range(isa.N_REGS):
            self._write(r, 0)

    # ------------------------------------------------------------------ registros
    def _write(self, reg: int, value: int) -> None:
        """Escribe ``value`` en ``reg`` con un pulso de reloj."""
        self.regs.set_inputs({"wa": reg, "wd": value, "we": 1})
        self.regs.set_inputs({"clk": 1})
        self.regs.set_inputs({"clk": 0})
        self.regs.set_inputs({"we": 0})

    def _read(self, ra1: int, ra2: int = 0) -> tuple[int, int]:
        """Lee dos registros por los puertos de lectura."""
        self.regs.set_inputs({"ra1": ra1, "ra2": ra2})
        values = self.regs.read_int("rd1"), self.regs.read_int("rd2")
        if None in values:
            raise UndefinedOutputError(f"lectura indefinida de F{ra1}/F{ra2}")
        return int(values[0] or 0), int(values[1] or 0)

    # ------------------------------------------------------------------ unidades
    def _fpu(self, fpu_op: int, a: int, b: int) -> FPResult:
        if fpu_op in (FPU_ADD, FPU_SUB):
            self._addsub = self._addsub or FPAddSub(self.fmt, self.engine)
            return self._addsub.add(a, b) if fpu_op == FPU_ADD else self._addsub.sub(a, b)
        if fpu_op == FPU_MUL:
            self._mul = self._mul or FPMul(self.fmt, self.engine)
            return self._mul.mul(a, b)
        self._div = self._div or FPDiv(self.fmt, self.engine)
        return self._div.div(a, b)

    # ------------------------------------------------------------------ ejecución
    @property
    def halted(self) -> bool:
        """True si se ejecutó HALT."""
        return self.fsm.phase is Phase.HALTED

    @property
    def state(self) -> MachineState:
        """Estado arquitectónico actual."""
        regs = [self._read(r)[0] for r in range(isa.N_REGS)]
        return MachineState(
            regs=regs,
            fsr=self.fsr,
            pc=self.pc,
            halted=self.halted,
            outputs=list(self.outputs),
            steps=self.steps,
        )

    def step(self) -> None:
        """Ejecuta una instrucción completa (las cuatro fases).

        Raises:
            MachineError: si el PC sale del programa o falta el literal de LI.
            isa.IllegalInstructionError: si el decodificador marca la palabra como ilegal.
        """
        if self.halted:
            return
        # FETCH
        if not 0 <= self.pc < len(self.program):
            raise MachineError(f"PC={self.pc} fuera del programa (sin HALT)")
        word = self.program[self.pc]
        # DECODE
        self.fsm.advance()
        d = self.decoder.evaluate({"ir": word})
        if d["illegal"]:
            raise isa.IllegalInstructionError(f"PC={self.pc}: palabra ilegal {word:#010x}")
        if d["halt"]:
            self.fsm.advance(halt=True)
            self.steps += 1
            return
        words = 1
        rd, rs1, rs2 = int(d["rd"] or 0), int(d["rs1"] or 0), int(d["rs2"] or 0)
        # EXECUTE
        self.fsm.advance()
        a, b = self._read(rs1, rs2)
        result: int | None = None
        if d["li"]:
            if self.pc + 1 >= len(self.program):
                raise MachineError(f"PC={self.pc}: LI sin literal")
            result, words = self.program[self.pc + 1], 2
        elif d["mov"]:
            result = a
        elif d["use_fpu"]:
            r = self._fpu(int(d["fpu_op"] or 0), a, b)
            result = r.bits
            self.fsr |= r.flags.to_bits()
        elif d["use_alu"]:
            res = self.alu.execute(OP_ADD if d["add"] else OP_SUB, a, b)
            result = res.value
            cvzn = (
                int(res.c) << isa.FSR_C
                | int(res.v) << isa.FSR_V
                | int(res.z) << isa.FSR_Z
                | int(res.n) << isa.FSR_N
            )
            self.fsr = (self.fsr & ~isa.FSR_INT_MASK) | cvzn
        elif d["out"]:
            self.outputs.append(a)
        elif d["clrf"]:
            self.fsr = 0
        # WRITEBACK
        self.fsm.advance()
        if d["reg_write"] and result is not None:
            self._write(rd, result)
        self.fsm.advance()
        self.pc += words
        self.steps += 1

    def run(self, max_steps: int = DEFAULT_MAX_STEPS) -> MachineState:
        """Ejecuta hasta HALT y devuelve el estado final.

        Raises:
            MachineError: si se supera ``max_steps`` o el programa termina sin HALT.
        """
        while not self.halted:
            if self.steps >= max_steps:
                raise MachineError(f"se superaron {max_steps} pasos sin HALT")
            self.step()
        return self.state
