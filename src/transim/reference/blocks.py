"""Modelos de referencia de los bloques de la capa L2 (sobre enteros sin signo)."""

from __future__ import annotations

from collections.abc import Sequence

from transim.reference.integer import add_with_carry


def adder(a: int, b: int, cin: int, width: int) -> tuple[int, int]:
    """Sumador de ``width`` bits (RCA o CLA): (suma, acarreo de salida)."""
    s, cout, _ = add_with_carry(a, b, cin, width)
    return s, cout


def add_sub(a: int, b: int, sub: int, width: int) -> tuple[int, int, bool]:
    """Sumador/restador: sub = 0 → a + b; sub = 1 → a + ¬b + 1.

    Returns:
        (resultado, acarreo de salida, desbordamiento con signo).
    """
    mask = (1 << width) - 1
    return add_with_carry(a, (~b & mask) if sub else b, sub, width)


def compare(a: int, b: int) -> tuple[bool, bool, bool]:
    """Comparador de magnitud sin signo: (a < b, a = b, a > b)."""
    return a < b, a == b, a > b


def shift_right_sticky(a: int, amount: int, width: int) -> tuple[int, bool]:
    """Desplazamiento lógico a la derecha con sticky (OR de los bits que salen)."""
    mask = (1 << width) - 1
    a &= mask
    if amount >= width:
        return 0, a != 0
    return a >> amount, (a & ((1 << amount) - 1)) != 0


def shift_left(a: int, amount: int, width: int) -> int:
    """Desplazamiento lógico a la izquierda; los bits que salen se pierden."""
    return (a << amount) & ((1 << width) - 1) if amount < width else 0


def leading_zeros(a: int, width: int) -> int:
    """Ceros a la izquierda de ``a`` en ``width`` bits (``width`` si a = 0)."""
    return width - (a & ((1 << width) - 1)).bit_length()


def mux(inputs: Sequence[int], select: int) -> int:
    """Multiplexor: devuelve ``inputs[select]``."""
    return inputs[select]


def multiply(a: int, b: int) -> int:
    """Multiplicador de mantisas: producto exacto (2p bits para operandos de p bits)."""
    return a * b


def divide_mantissas(a: int, b: int, q_bits: int) -> tuple[int, bool]:
    """Divisor de mantisas normalizadas (bit más alto en 1, mismo ancho p).

    Returns:
        (q, sticky) con q = ⌊a · 2^(q_bits − 1) / b⌋ (q tiene ``q_bits`` bits porque
        a/b ∈ (1/2, 2)) y sticky = resto ≠ 0.
    """
    if b == 0:
        raise ZeroDivisionError("divide_mantissas: divisor cero")
    q, r = divmod(a << (q_bits - 1), b)
    return q, r != 0
