"""Decodificador de instrucciones con compuertas de L1. ADR-0006."""

from __future__ import annotations

from functools import cache

from transim.blocks.wiring import Wiring
from transim.core.netlist import Netlist
from transim.core.node import Node
from transim.cpu import isa
from transim.cpu.isa import Opcode

OPCODE_BITS = isa.WORD_BITS - isa.OPCODE_SHIFT
"""Bits del campo de opcode."""

FIELDS = {"rd": isa.RD_SHIFT, "rs1": isa.RS1_SHIFT, "rs2": isa.RS2_SHIFT}
"""Campo de registro → bit menos significativo en la palabra."""


@cache
def instruction_decoder() -> Netlist:
    """Decodifica una palabra T754 con compuertas de la biblioteca.

    Puertos: bus ``ir[WORD_BITS]``; una salida one-hot por opcode con el nombre en
    minúsculas (``nop``, ``li``, ``mov``, ``fadd``, ``fsub``, ``fmul``, ``fdiv``, ``add``,
    ``sub``, ``out``, ``clrf``, ``halt``); ``illegal`` (opcode no definido, bits
    reservados distintos de cero o un campo de registro que el opcode no usa distinto
    de cero, igual que :func:`transim.cpu.isa.decode`); buses ``rd[3]``, ``rs1[3]``,
    ``rs2[3]`` (copias restauradas por buffers) y las señales de control ``reg_write``,
    ``fpu_op[2]`` (0 FADD, 1 FSUB, 2 FMUL, 3 FDIV), ``use_fpu``, ``use_alu``.
    Nombre ``"DECODER"``.
    """
    nl = Netlist("DECODER")
    ir = nl.input_bus("ir", isa.WORD_BITS)
    w = Wiring(nl)
    opcode = ir[isa.OPCODE_SHIFT :]
    inverted = [w.inv(bit) for bit in opcode]

    hot: dict[Opcode, Node] = {}
    for op in Opcode:
        literals = [opcode[i] if (op >> i) & 1 else inverted[i] for i in range(OPCODE_BITS)]
        hot[op] = w.and_tree(literals, nl.output(op.name.lower()))

    for name, shift in FIELDS.items():
        bits = ir[shift : shift + isa.REG_BITS]
        for bit, out in zip(bits, nl.output_bus(name, isa.REG_BITS), strict=True):
            w.buf(bit, out)

    # Ilegal: ningún opcode, bits reservados o campos no usados distintos de cero.
    causes = [w.inv(w.or_tree(list(hot.values()))), w.or_tree(ir[: isa.RS2_SHIFT])]
    for name in FIELDS:
        unused = [hot[op] for op in Opcode if name not in isa.OPERANDS[op]]
        causes.append(
            w.and2(w.or_tree(unused), w.or_tree(ir[FIELDS[name] : FIELDS[name] + isa.REG_BITS]))
        )
    w.or_tree(causes, nl.output("illegal"))

    writers = [op for op in Opcode if "rd" in isa.OPERANDS[op]]
    w.or_tree([hot[op] for op in writers], nl.output("reg_write"))
    fpu_op = nl.output_bus("fpu_op", 2)
    w.buf(opcode[0], fpu_op[0])
    w.buf(opcode[1], fpu_op[1])
    w.or_tree([hot[op] for op in sorted(isa.FP_OPS)], nl.output("use_fpu"))
    w.or_tree([hot[op] for op in sorted(isa.INT_OPS)], nl.output("use_alu"))
    return nl
