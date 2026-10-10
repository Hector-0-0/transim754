"""ALU entera de 32 bits en complemento a 2 ADR-0005."""

from __future__ import annotations

from transim.blocks.subtractor import adder_subtractor
from transim.blocks.wiring import Wiring
from transim.core.netlist import Netlist
from transim.core.unit import EngineName, HardwareUnit
from transim.cpu.isa import WORD_BITS
from transim.fpu.format import UndefinedOutputError
from transim.reference.integer import IntResult

OP_ADD, OP_SUB = 0, 1


def int_alu(width: int = WORD_BITS) -> Netlist:
    """ALU ADD/SUB con indicadores, sobre el sumador/restador de L2.

    Puertos: buses ``a[width]``, ``b[width]``, entrada ``op`` (0 = ADD, 1 = SUB); bus
    ``y[width]``; salidas ``c`` (acarreo de salida), ``v`` (desbordamiento con signo),
    ``z`` (y = 0, árbol NOR) y ``n`` (bit de signo de y). Nombre ``f"ALU{width}"``.
    """
    nl = Netlist(f"ALU{width}")
    a, b = nl.input_bus("a", width), nl.input_bus("b", width)
    op = nl.input("op")
    y = nl.output_bus("y", width)
    c, v, z = nl.output("c"), nl.output("v"), nl.output("z")
    nl.instantiate(
        adder_subtractor(width), "addsub", {"a": a, "b": b, "sub": op, "s": y, "cout": c, "ovf": v}
    )
    w = Wiring(nl)
    w.inv(w.or_tree(y), z)
    nl.mark_output("n", y[width - 1])
    return nl


class IntALU(HardwareUnit):
    """ALU entera simulada en transistores.

    Ejemplo::

        alu = IntALU()
        r = alu.execute(OP_SUB, 5, 7)   # r.value == 0xFFFFFFFE, r.n is True
    """

    def __init__(self, width: int = WORD_BITS, engine: EngineName = "cached") -> None:
        self.width = width
        super().__init__(int_alu(width), engine)

    def execute(self, op: int, a: int, b: int) -> IntResult:
        """Ejecuta ``op`` (``OP_ADD`` u ``OP_SUB``) sobre ``a`` y ``b`` sin signo.

        Raises:
            UndefinedOutputError: si alguna salida no queda en 0 o 1.
        """
        out = self.evaluate({"a": a, "b": b, "op": op})
        if any(out[k] is None for k in ("y", "c", "v", "z", "n")):
            raise UndefinedOutputError(f"salida indefinida en la ALU: {out}")
        return IntResult(
            value=int(out["y"] or 0),
            c=bool(out["c"]),
            v=bool(out["v"]),
            z=bool(out["z"]),
            n=bool(out["n"]),
        )
