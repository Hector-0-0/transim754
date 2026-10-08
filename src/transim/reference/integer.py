"""Modelo de referencia de la ALU entera en complemento a 2 (ADR-0005)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IntResult:
    """Resultado de la ALU entera.

    Attributes:
        value: resultado módulo 2^width, como entero sin signo.
        c: acarreo de salida (en la resta, 1 = no hubo préstamo).
        v: desbordamiento con signo.
        z: el resultado es cero.
        n: bit de signo del resultado.
    """

    value: int
    c: bool
    v: bool
    z: bool
    n: bool


def add_with_carry(a: int, b: int, cin: int, width: int) -> tuple[int, int, bool]:
    """a + b + cin en ``width`` bits: (suma, acarreo de salida, desbordamiento con signo)."""
    mask = (1 << width) - 1
    raw = (a & mask) + (b & mask) + cin
    s = raw & mask
    sign = 1 << (width - 1)
    overflow = bool(~(a ^ b) & (a ^ s) & sign)
    return s, raw >> width, overflow


def _result(s: int, c: int, v: bool, width: int) -> IntResult:
    return IntResult(value=s, c=bool(c), v=v, z=s == 0, n=bool(s >> (width - 1)))


def int_add(a: int, b: int, width: int) -> IntResult:
    """ADD: a + b con indicadores C, V, Z, N."""
    return _result(*add_with_carry(a, b, 0, width), width)


def int_sub(a: int, b: int, width: int) -> IntResult:
    """SUB: a − b = a + ¬b + 1 con indicadores C, V, Z, N."""
    mask = (1 << width) - 1
    return _result(*add_with_carry(a, ~b & mask, 1, width), width)


def to_signed(value: int, width: int) -> int:
    """Interpreta ``value`` (sin signo) como entero en complemento a 2."""
    return value - (1 << width) if value >> (width - 1) else value
