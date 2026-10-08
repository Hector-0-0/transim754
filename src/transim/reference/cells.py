"""Modelos de referencia de las celdas de la capa L1 (funciones sobre bits 0/1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


def inv(a: int) -> int:
    return 1 - a


def nand2(a: int, b: int) -> int:
    return 1 - (a & b)


def nor2(a: int, b: int) -> int:
    return 1 - (a | b)


def and2(a: int, b: int) -> int:
    return a & b


def or2(a: int, b: int) -> int:
    return a | b


def xor2(a: int, b: int) -> int:
    return a ^ b


def xnor2(a: int, b: int) -> int:
    return 1 - (a ^ b)


def mux2(a: int, b: int, s: int) -> int:
    """y = a si s = 0; y = b si s = 1."""
    return b if s else a


def half_adder(a: int, b: int) -> tuple[int, int]:
    """(suma, acarreo)."""
    return a ^ b, a & b


def full_adder(a: int, b: int, cin: int) -> tuple[int, int]:
    """(suma, acarreo de salida)."""
    total = a + b + cin
    return total & 1, total >> 1


COMBINATIONAL: dict[str, Callable[..., int | tuple[int, int]]] = {
    "INV": inv,
    "NAND2": nand2,
    "NOR2": nor2,
    "AND2": and2,
    "OR2": or2,
    "XOR2": xor2,
    "XNOR2": xnor2,
    "MUX2": mux2,
    "HA": half_adder,
    "FA": full_adder,
}
"""Nombre de celda → función de referencia."""


@dataclass
class DLatch:
    """Latch D transparente con clk = 1; retiene con clk = 0. Estado inicial desconocido."""

    q: int | None = None

    def update(self, d: int, clk: int) -> int | None:
        if clk:
            self.q = d
        return self.q


@dataclass
class DFlipFlop:
    """Flip-flop D disparado por flanco de subida de clk."""

    q: int | None = None
    _clk: int = 0

    def update(self, d: int, clk: int) -> int | None:
        if clk and not self._clk:
            self.q = d
        self._clk = clk
        return self.q
