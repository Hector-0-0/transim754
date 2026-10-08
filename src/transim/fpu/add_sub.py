"""FADD/FSUB a nivel de transistor (responsable: Daniel). ADR-0002 a ADR-0005, ADR-0009.

Datapath: desempaquetar → clasificar → restar exponentes → intercambiar si |b| > |a|
→ alinear (barrel shifter a la derecha con sticky) → sumar/restar mantisas de p + 3
bits → normalizar (LZC + desplazador a la izquierda) → ``round_and_pack`` → elegir
entre el resultado numérico y el especial.
"""

from __future__ import annotations

from transim.core.netlist import Netlist
from transim.core.unit import EngineName, HardwareUnit
from transim.fpu.format import FloatFormat, FPResult


def fp_add_sub(fmt: FloatFormat) -> Netlist:
    """Sumador/restador de punto flotante.

    Puertos: buses ``a[fmt.width]``, ``b[fmt.width]``, entrada ``sub`` (0 = a + b,
    1 = a − b); bus ``y[fmt.width]``; salidas ``invalid``, ``overflow``, ``underflow``,
    ``inexact``. Opcionalmente, buses de depuración con prefijo ``dbg_`` (por ejemplo
    ``dbg_exp_diff``, ``dbg_aligned``, ``dbg_sum``) que el CLI muestra con ``--trace``.
    Nombre ``f"FADDSUB_{fmt.name}"``.
    """
    raise NotImplementedError("pendiente: #17")


class FPAddSub(HardwareUnit):
    """FADD/FSUB simuladas en transistores."""

    def __init__(self, fmt: FloatFormat, engine: EngineName = "cached") -> None:
        self.fmt = fmt
        super().__init__(fp_add_sub(fmt), engine)

    def add(self, a: int, b: int) -> FPResult:
        """a + b (patrones de bits)."""
        return FPResult.from_outputs(self.evaluate({"a": a, "b": b, "sub": 0}))

    def sub(self, a: int, b: int) -> FPResult:
        """a − b (patrones de bits)."""
        return FPResult.from_outputs(self.evaluate({"a": a, "b": b, "sub": 1}))
