"""Desempaquetado de operandos en hardware. ADR-0001, ADR-0003."""

from __future__ import annotations

from functools import cache

from transim.blocks.wiring import Wiring
from transim.core.netlist import Netlist
from transim.core.node import Node
from transim.fpu.format import FloatFormat


@cache
def unpacker(fmt: FloatFormat) -> Netlist:
    """Separa un operando en signo, exponente efectivo y mantisa con bit implícito.

    - ``sign`` = x[width−1];
    - ``exp`` = campo de exponente E, salvo E = 0 (cero o subnormal), en cuyo caso vale
      1: así un subnormal queda con el exponente de emin (docs/03 §2);
    - ``mant`` = bit implícito (E ≠ 0, árbol OR) seguido de la fracción: p bits.

    Puertos: bus ``x[fmt.width]``; salida ``sign``; buses ``exp[fmt.exp_bits]`` y
    ``mant[fmt.precision]``. Nombre ``f"UNPACK_{fmt.name}"``.
    """
    nl = Netlist(f"UNPACK_{fmt.name}")
    x = nl.input_bus("x", fmt.width)
    sign = nl.output("sign")
    exp = nl.output_bus("exp", fmt.exp_bits)
    mant = nl.output_bus("mant", fmt.precision)
    w = Wiring(nl)
    field = x[fmt.frac_bits : fmt.frac_bits + fmt.exp_bits]
    nonzero = w.or_tree(field)
    w.buf(x[fmt.width - 1], sign)
    w.inv(w.and2(nonzero, w.inv(field[0])), exp[0])  # E[0] + (E = 0)
    for i in range(1, fmt.exp_bits):
        w.buf(field[i], exp[i])
    for i in range(fmt.frac_bits):
        w.buf(x[i], mant[i])
    w.buf(nonzero, mant[fmt.frac_bits])
    return nl


def unpack_into(
    nl: Netlist, fmt: FloatFormat, x: list[Node], name: str
) -> tuple[Node, list[Node], list[Node]]:
    """Instancia :func:`unpacker` en ``nl`` sobre el bus ``x``.

    Returns:
        (signo, exponente efectivo, mantisa), buses con el bit menos significativo primero.
    """
    sign = nl.node(f"{name}_sign")
    exp = [nl.node(f"{name}_exp{i}") for i in range(fmt.exp_bits)]
    mant = [nl.node(f"{name}_mant{i}") for i in range(fmt.precision)]
    nl.instantiate(unpacker(fmt), name, {"x": x, "sign": sign, "exp": exp, "mant": mant})
    return sign, exp, mant
