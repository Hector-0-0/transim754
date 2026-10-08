"""Pruebas del propio harness del oráculo."""

from __future__ import annotations

import pytest

from oracle.cases import edge_pairs, edge_values, random_pairs
from oracle.compare import assert_fp_equal, describe
from oracle.numpy_oracle import expected, numpy_op
from transim.fpu.format import BINARY16, BINARY32, Flags, FPResult


@pytest.mark.parametrize("fmt", [BINARY32, BINARY16])
def test_casos_borde_cubren_todas_las_clases(fmt) -> None:  # type: ignore[no-untyped-def]
    clases = {fmt.classify(x).name for x in edge_values(fmt)}
    assert clases == {"ZERO", "SUBNORMAL", "NORMAL", "INF", "QNAN", "SNAN"}
    assert len(edge_pairs(fmt)) == len(edge_values(fmt)) ** 2


def test_aleatorios_reproducibles() -> None:
    assert random_pairs(BINARY32, 50) == random_pairs(BINARY32, 50)
    assert random_pairs(BINARY32, 50, seed=1) != random_pairs(BINARY32, 50, seed=2)


def test_numpy_op_reporta_flags() -> None:
    bits, flags = numpy_op(BINARY32, "/", 0x3F800000, 0)
    assert bits == 0x7F800000
    assert flags == {"div_by_zero"}


def test_expected_ejemplo_fadd() -> None:
    assert expected(BINARY32, "+", 0x3FC00000, 0x40100000) == FPResult(0x40700000, Flags())


def test_expected_nan_canonico_aunque_numpy_de_otro_nan() -> None:
    r = expected(BINARY32, "-", 0x7F800000, 0x7F800000)  # ∞ − ∞
    assert r == FPResult(0x7FC00000, Flags(invalid=True))


def test_assert_fp_equal_muestra_campos() -> None:
    with pytest.raises(AssertionError, match=r"s=0 e=0x80 f=0x700000"):
        assert_fp_equal(BINARY32, FPResult(0, Flags()), FPResult(0x40700000, Flags()), "x")
    assert "normal" in describe(BINARY32, 0x40700000)
