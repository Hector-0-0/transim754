"""Validación del modelo de referencia de la FPU contra numpy (binary32 y binary16)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from oracle.cases import edge_pairs, random_pairs
from oracle.numpy_oracle import expected, numpy_op
from transim.fpu.format import BINARY16, BINARY32, Flags, FloatFormat, FPResult
from transim.reference import fpu as ref

FORMATOS = [BINARY32, BINARY16]
OPS = ["+", "-", "*", "/"]


@pytest.mark.parametrize("op", OPS)
@pytest.mark.parametrize("fmt", FORMATOS, ids=lambda f: f.name)
def test_casos_borde_todos_los_pares(fmt: FloatFormat, op: str) -> None:
    for a, b in edge_pairs(fmt):
        expected(fmt, op, a, b)  # lanza OracleDisagreementError si discrepan


@pytest.mark.parametrize("op", OPS)
@pytest.mark.parametrize("fmt", FORMATOS, ids=lambda f: f.name)
def test_aleatorios_rapidos(fmt: FloatFormat, op: str) -> None:
    for a, b in random_pairs(fmt, 1000, seed=OPS.index(op)):
        expected(fmt, op, a, b)


@pytest.mark.slow
@pytest.mark.parametrize("op", OPS)
@pytest.mark.parametrize("fmt", FORMATOS, ids=lambda f: f.name)
def test_aleatorios_10000(fmt: FloatFormat, op: str) -> None:
    for a, b in random_pairs(fmt, 10_000, seed=12):
        expected(fmt, op, a, b)


def test_binary16_tininess_antes_y_despues_del_redondeo() -> None:
    """(1 − 2⁻¹⁰)·2⁻¹⁴ × (1 + 2⁻¹⁰) = (1 − 2⁻²⁰)·2⁻¹⁴ redondea a 2⁻¹⁴ (menor normal).

    Antes de redondear es diminuto; después, no. ADR-0004 detecta después → sin
    underflow. La conversión a float16 de numpy detecta antes → underflow. Por eso el
    oráculo no usa el underflow de numpy en binary16. En binary32 (hardware x86, que
    detecta después) el caso análogo no levanta underflow, igual que la referencia.
    """
    r16 = ref.fmul(BINARY16, 0x03FF, 0x3C01)
    assert r16 == FPResult(0x0400, Flags(inexact=True))
    assert "underflow" in numpy_op(BINARY16, "*", 0x03FF, 0x3C01)[1]

    r32 = ref.fmul(BINARY32, 0x007FFFFF, 0x3F800001)
    assert r32 == FPResult(0x00800000, Flags(inexact=True))
    assert "underflow" not in numpy_op(BINARY32, "*", 0x007FFFFF, 0x3F800001)[1]


@pytest.mark.parametrize(
    ("op", "a", "b", "bits", "flags"),
    [
        ("-", 0x3FC00000, 0x3FC00000, 0x00000000, Flags()),  # x − x = +0
        ("+", 0x80000000, 0x80000000, 0x80000000, Flags()),  # (−0) + (−0) = −0
        ("+", 0x00000000, 0x80000000, 0x00000000, Flags()),  # (+0) + (−0) = +0
        ("-", 0x7F800000, 0x7F800000, 0x7FC00000, Flags(invalid=True)),  # ∞ − ∞
        ("*", 0x00000000, 0xFF800000, 0x7FC00000, Flags(invalid=True)),  # 0 × ∞
        ("/", 0x00000000, 0x80000000, 0x7FC00000, Flags(invalid=True)),  # 0 / 0
        ("/", 0x7F800000, 0xFF800000, 0x7FC00000, Flags(invalid=True)),  # ∞ / ∞
        ("/", 0xBF800000, 0x00000000, 0xFF800000, Flags(div_by_zero=True)),  # −1 / +0
        ("/", 0x3F800000, 0x80000000, 0xFF800000, Flags(div_by_zero=True)),  # 1 / −0
        ("+", 0x7FC00001, 0x3F800000, 0x7FC00000, Flags()),  # qNaN: canónico, sin NV
        ("+", 0x7F800001, 0x3F800000, 0x7FC00000, Flags(invalid=True)),  # sNaN → NV
        ("*", 0xFFC00000, 0x7FC12345, 0x7FC00000, Flags()),  # signo y carga se pierden
    ],
)
def test_reglas_obligatorias_de_adr_0003(op: str, a: int, b: int, bits: int, flags: Flags) -> None:
    assert ref.OPERATIONS[op](BINARY32, a, b) == FPResult(bits, flags)


def test_round_and_pack_es_coherente_con_round_exact() -> None:
    f = BINARY32
    one = 1 << (f.precision - 1)
    assert ref.round_and_pack(f, 0, f.bias, one, 0, 0, 0).bits == 0x3F800000
    assert ref.round_and_pack(f, 1, f.bias + 1, one | 1, 0, 0, 0).bits == 0xC0000001
    # empate a par hacia abajo y hacia arriba
    assert ref.round_and_pack(f, 0, f.bias, one, 1, 0, 0) == FPResult(
        0x3F800000, Flags(inexact=True)
    )
    assert ref.round_and_pack(f, 0, f.bias, one | 1, 1, 0, 0).bits == 0x3F800002
    # subnormal (ejemplo 4 de docs/03) y desbordamiento
    assert ref.round_and_pack(f, 0, 0, one | 1, 0, 0, 0) == FPResult(
        0x00400000, Flags(underflow=True, inexact=True)
    )
    assert ref.round_and_pack(f, 0, 255, one, 0, 0, 0) == FPResult(
        0x7F800000, Flags(overflow=True, inexact=True)
    )
    # muy por debajo del menor subnormal: redondea a cero con underflow
    assert ref.round_and_pack(f, 1, -200, one, 0, 0, 0) == FPResult(
        0x80000000, Flags(underflow=True, inexact=True)
    )
    with pytest.raises(ValueError, match="bit"):
        ref.round_and_pack(f, 0, 1, 3, 0, 0, 0)


@pytest.mark.parametrize(
    ("texto", "bits"),
    [
        ("1.5", 0x3FC00000),
        ("-6.25", 0xC0C80000),
        ("0.1", 0x3DCCCCCD),
        ("-0", 0x80000000),
        ("inf", 0x7F800000),
        ("-inf", 0xFF800000),
        ("nan", 0x7FC00000),
        ("3.4028235e38", 0x7F7FFFFF),
        ("1e-45", 0x00000001),
        ("1e39", 0x7F800000),
    ],
)
def test_from_decimal(texto: str, bits: int) -> None:
    assert ref.from_decimal(BINARY32, texto).bits == bits


def test_from_decimal_sin_doble_redondeo() -> None:
    """Un decimal en el punto medio exacto entre dos binary32: la conversión directa
    redondea a par; pasar por binary64 podría desempatar mal."""
    texto = "1.000000059604644775390625"  # 1 + 2^−24 exacto: empate entre 1 y 1 + 2^−23
    assert Fraction(texto) == 1 + Fraction(1, 2**24)
    assert ref.from_decimal(BINARY32, texto).bits == 0x3F800000


def test_to_float_y_to_fraction() -> None:
    assert ref.to_float(BINARY32, 0x40700000) == 3.75
    assert ref.to_fraction(BINARY16, 0x0001) == Fraction(1, 2**24)
