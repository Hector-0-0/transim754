"""ALU entera de 32 bits en complemento a 2 (responsable: Ronald). ADR-0005."""

from __future__ import annotations

from transim.core.netlist import Netlist
from transim.core.unit import EngineName, HardwareUnit
from transim.cpu.isa import WORD_BITS
from transim.reference.integer import IntResult

OP_ADD, OP_SUB = 0, 1


def int_alu(width: int = WORD_BITS) -> Netlist:
    """ALU ADD/SUB con indicadores, sobre el sumador/restador de L2.

    Puertos: buses ``a[width]``, ``b[width]``, entrada ``op`` (0 = ADD, 1 = SUB); bus
    ``y[width]``; salidas ``c`` (acarreo de salida), ``v`` (desbordamiento con signo),
    ``z`` (y = 0, árbol NOR) y ``n`` (bit de signo de y). Nombre ``f"ALU{width}"``.
    """
    raise NotImplementedError("pendiente: #13")


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
        """Ejecuta ``op`` (``OP_ADD`` u ``OP_SUB``) sobre ``a`` y ``b`` sin signo."""
        raise NotImplementedError("pendiente: #13")
