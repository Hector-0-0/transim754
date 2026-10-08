"""Modelos de referencia de celdas, bloques y ALU entera."""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from transim.reference import blocks, cells
from transim.reference.integer import int_add, int_sub, to_signed

W = 32
palabras = st.integers(0, 2**W - 1)


def test_celdas_combinacionales_tablas() -> None:
    for a, b, c in itertools.product((0, 1), repeat=3):
        assert cells.xor2(a, b) == (a + b) % 2
        assert cells.mux2(a, b, c) == (b if c else a)
        assert cells.full_adder(a, b, c) == ((a + b + c) % 2, (a + b + c) // 2)
        assert cells.half_adder(a, b) == ((a + b) % 2, a * b)
    assert set(cells.COMBINATIONAL) >= {"INV", "AND2", "XOR2", "MUX2", "FA"}


def test_latch_y_flip_flop() -> None:
    lat, ff = cells.DLatch(), cells.DFlipFlop()
    assert lat.update(1, 0) is None
    assert lat.update(1, 1) == 1
    assert lat.update(0, 0) == 1
    assert ff.update(1, 0) is None
    assert ff.update(1, 1) == 1  # flanco de subida
    assert ff.update(0, 1) == 1  # sin flanco
    assert ff.update(0, 0) == 1
    assert ff.update(0, 1) == 0


@given(palabras, palabras)
def test_alu_entera_contra_aritmetica_con_signo(a: int, b: int) -> None:
    s = int_add(a, b, W)
    assert s.value == (a + b) % 2**W
    assert s.c == (a + b >= 2**W)
    assert s.v == (not -(2**31) <= to_signed(a, W) + to_signed(b, W) < 2**31)
    d = int_sub(a, b, W)
    assert d.value == (a - b) % 2**W
    assert d.c == (a >= b)  # C = 1 ⇔ no hubo préstamo
    assert d.v == (not -(2**31) <= to_signed(a, W) - to_signed(b, W) < 2**31)
    assert d.z == (a == b)
    assert d.n == bool(d.value >> 31)


@pytest.mark.parametrize(
    ("a", "b", "c", "v"),
    [
        (0x7FFFFFFF, 1, False, True),
        (0xFFFFFFFF, 1, True, False),
        (0x80000000, 0x80000000, True, True),
    ],
)
def test_alu_casos_borde_suma(a: int, b: int, c: bool, v: bool) -> None:
    r = int_add(a, b, W)
    assert (r.c, r.v) == (c, v)


@given(st.integers(0, 2**12 - 1), st.integers(0, 15))
def test_desplazamientos_y_sticky(a: int, k: int) -> None:
    y, sticky = blocks.shift_right_sticky(a, k, 12)
    assert y == a >> k
    assert sticky == (a % (1 << k) != 0)
    assert blocks.shift_left(a, k, 12) == (a << k) % 2**12


def test_lzc_y_comparador() -> None:
    assert blocks.leading_zeros(0, 8) == 8
    assert blocks.leading_zeros(1, 8) == 7
    assert blocks.leading_zeros(0x80, 8) == 0
    assert blocks.compare(3, 5) == (True, False, False)


@given(st.integers(2**10, 2**11 - 1), st.integers(2**10, 2**11 - 1))
def test_divisor_de_mantisas(a: int, b: int) -> None:
    q, sticky = blocks.divide_mantissas(a, b, 14)
    assert 2**12 <= q < 2**14
    assert q == (a << 13) // b
    assert sticky == ((a << 13) % b != 0)
