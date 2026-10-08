"""FloatFormat, Flags y FPResult (entregados completos con la base)."""

from __future__ import annotations

import pytest

from transim.fpu.format import (
    BINARY16,
    BINARY32,
    Flags,
    FloatFormat,
    FPClass,
    FPResult,
    UndefinedOutputError,
)


def test_constantes_derivadas() -> None:
    f = BINARY32
    assert (f.width, f.precision, f.bias, f.emin, f.emax) == (32, 24, 127, -126, 127)
    h = BINARY16
    assert (h.width, h.precision, h.bias, h.emin, h.emax) == (16, 11, 15, -14, 15)
    assert f.canonical_nan == 0x7FC00000
    assert h.canonical_nan == 0x7E00
    assert f.max_finite() == 0x7F7FFFFF
    assert f.name == "binary32"
    assert FloatFormat(4, 3).name == "e4f3"


@pytest.mark.parametrize(
    ("bits", "clase"),
    [
        (0x00000000, FPClass.ZERO),
        (0x80000000, FPClass.ZERO),
        (0x00000001, FPClass.SUBNORMAL),
        (0x00800000, FPClass.NORMAL),
        (0x7F800000, FPClass.INF),
        (0x7FC00000, FPClass.QNAN),
        (0x7F800001, FPClass.SNAN),
    ],
)
def test_clasificacion(bits: int, clase: FPClass) -> None:
    assert BINARY32.classify(bits) is clase


def test_campos_ida_y_vuelta() -> None:
    assert BINARY32.fields(0xC0C80000) == (1, 0x81, 0x480000)
    assert BINARY32.compose(1, 0x81, 0x480000) == 0xC0C80000
    with pytest.raises(ValueError, match="no cabe"):
        BINARY32.fields(2**32)
    with pytest.raises(ValueError, match="fuera de rango"):
        BINARY32.compose(0, 256, 0)


def test_flags_en_fsr() -> None:
    f = Flags(invalid=True, inexact=True)
    assert f.to_bits() == 0b10001
    assert Flags.from_bits(0b10001) == f
    assert (Flags(overflow=True) | Flags(inexact=True)) == Flags(overflow=True, inexact=True)
    assert str(f) == "NV|NX"
    assert str(Flags()) == "—"


def test_fpresult_desde_salidas() -> None:
    r = FPResult.from_outputs({"y": 0x40700000, "inexact": 0, "overflow": 0})
    assert r == FPResult(0x40700000, Flags())
    with pytest.raises(UndefinedOutputError, match="y"):
        FPResult.from_outputs({"y": None})
