"""Desempaquetado de operandos en hardware (responsable: Daniel). ADR-0001, ADR-0003."""

from __future__ import annotations

from transim.core.netlist import Netlist
from transim.fpu.format import FloatFormat


def unpacker(fmt: FloatFormat) -> Netlist:
    """Separa un operando en signo, exponente efectivo y mantisa con bit implícito.

    - ``sign`` = x[width−1];
    - ``exp`` = campo de exponente E, salvo E = 0 (cero o subnormal), en cuyo caso vale
      1: así un subnormal queda con el exponente de emin (docs/03 §2);
    - ``mant`` = bit implícito (E ≠ 0, árbol OR) seguido de la fracción: p bits.

    Puertos: bus ``x[fmt.width]``; salida ``sign``; buses ``exp[fmt.exp_bits]`` y
    ``mant[fmt.precision]``. Nombre ``f"UNPACK_{fmt.name}"``.
    """
    raise NotImplementedError("pendiente: #15")
