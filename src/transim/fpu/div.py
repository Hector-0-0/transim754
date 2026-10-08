"""FDIV a nivel de transistor (responsable: Fabricio). ADR-0002 a ADR-0005, ADR-0009."""

from __future__ import annotations

from transim.core.netlist import Netlist
from transim.core.unit import EngineName, HardwareUnit
from transim.fpu.format import FloatFormat, FPResult


def quotient_bits(fmt: FloatFormat) -> int:
    """Bits de cociente que genera el divisor: p + 3 (p de mantisa, G, R y uno extra
    porque el cociente de dos mantisas normalizadas está en (1/2, 2))."""
    return fmt.precision + 3


def nonrestoring_divider(width: int, q_bits: int) -> Netlist:
    """Divisor combinacional no restaurador de mantisas normalizadas.

    ``q_bits`` filas de celdas de suma/resta controlada (XOR2 + FA); cada fila suma o
    resta el divisor según el signo del resto parcial anterior. Al final, el resto se
    corrige y ``sticky`` = resto ≠ 0.

    Puertos: buses ``a[width]``, ``b[width]`` (ambos con el bit más alto en 1); bus
    ``q[q_bits]`` = ⌊a · 2^(q_bits − 1) / b⌋; salida ``sticky``.
    Nombre ``f"NRDIV{width}x{q_bits}"``.
    """
    raise NotImplementedError("pendiente: #20")


def fp_divider(fmt: FloatFormat) -> Netlist:
    """Divisor de punto flotante.

    Datapath: desempaquetar → clasificar → signo = XOR → normalizar subnormales (LZC +
    desplazador) → exponente = ea − eb + sesgo → cociente de mantisas con
    ``quotient_bits(fmt)`` bits → normalizar (1 bit) → G, R, S → ``round_and_pack`` →
    elegir entre el resultado numérico y el especial.

    Puertos: buses ``a[fmt.width]``, ``b[fmt.width]``; bus ``y[fmt.width]``; salidas
    ``invalid``, ``div_by_zero``, ``overflow``, ``underflow``, ``inexact``.
    Nombre ``f"FDIV_{fmt.name}"``.
    """
    raise NotImplementedError("pendiente: #21")


class FPDiv(HardwareUnit):
    """FDIV simulada en transistores."""

    def __init__(self, fmt: FloatFormat, engine: EngineName = "cached") -> None:
        self.fmt = fmt
        super().__init__(fp_divider(fmt), engine)

    def div(self, a: int, b: int) -> FPResult:
        """a / b (patrones de bits)."""
        return FPResult.from_outputs(self.evaluate({"a": a, "b": b}))
