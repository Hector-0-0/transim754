"""Decodificador de instrucciones con compuertas de L1 (responsable: Héctor). ADR-0006."""

from __future__ import annotations

from transim.core.netlist import Netlist


def instruction_decoder() -> Netlist:
    """Decodifica una palabra T754 con compuertas de la biblioteca.

    Puertos: bus ``ir[WORD_BITS]``; una salida one-hot por opcode con el nombre en
    minúsculas (``nop``, ``li``, ``mov``, ``fadd``, ``fsub``, ``fmul``, ``fdiv``, ``add``,
    ``sub``, ``out``, ``clrf``, ``halt``); ``illegal`` (opcode no definido o bits
    reservados distintos de cero); buses ``rd[3]``, ``rs1[3]``, ``rs2[3]`` (copias
    restauradas por buffers) y las señales de control ``reg_write``, ``fpu_op[2]``
    (0 FADD, 1 FSUB, 2 FMUL, 3 FDIV), ``use_fpu``, ``use_alu``. Nombre ``"DECODER"``.
    """
    raise NotImplementedError("pendiente: #30")
