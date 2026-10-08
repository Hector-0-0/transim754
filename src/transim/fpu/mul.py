"""FMUL a nivel de transistor (responsable: Fabricio). ADR-0002 a ADR-0005, ADR-0009."""

from __future__ import annotations

from transim.core.netlist import Netlist
from transim.core.unit import EngineName, HardwareUnit
from transim.fpu.format import FloatFormat, FPResult


def array_multiplier(width: int) -> Netlist:
    """Multiplicador en arreglo sin signo: ``width``² compuertas AND2 para los productos
    parciales y filas de sumadores (HA/FA) que los acumulan.

    Puertos: buses ``a[width]``, ``b[width]``; bus ``p[2·width]`` = a · b.
    Nombre ``f"ARRMUL{width}"``.
    """
    raise NotImplementedError("pendiente: #18")


def fp_multiplier(fmt: FloatFormat) -> Netlist:
    """Multiplicador de punto flotante.

    Datapath: desempaquetar → clasificar → signo = XOR → exponente = ea + eb − sesgo
    (sumador de L2 con ``exponent_width(fmt)`` bits) → producto de mantisas (p × p) →
    normalizar (LZC si hay subnormales) → G, R, S del producto → ``round_and_pack`` →
    elegir entre el resultado numérico y el especial.

    Puertos: buses ``a[fmt.width]``, ``b[fmt.width]``; bus ``y[fmt.width]``; salidas
    ``invalid``, ``overflow``, ``underflow``, ``inexact``. Nombre ``f"FMUL_{fmt.name}"``.
    """
    raise NotImplementedError("pendiente: #19")


class FPMul(HardwareUnit):
    """FMUL simulada en transistores."""

    def __init__(self, fmt: FloatFormat, engine: EngineName = "cached") -> None:
        self.fmt = fmt
        super().__init__(fp_multiplier(fmt), engine)

    def mul(self, a: int, b: int) -> FPResult:
        """a × b (patrones de bits)."""
        return FPResult.from_outputs(self.evaluate({"a": a, "b": b}))
