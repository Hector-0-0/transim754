"""Desempaquetado, clasificación y casos especiales (responsable: Daniel). Issue #15."""

from __future__ import annotations

import itertools

import pytest

from oracle.cases import edge_values
from transim.core import HardwareUnit
from transim.fpu.codec import unpacker
from transim.fpu.format import BINARY16, BINARY32, FloatFormat, FPClass
from transim.fpu.special import classifier, special_cases
from transim.reference import fpu as ref

FORMATOS = pytest.mark.parametrize("fmt", [BINARY16, BINARY32], ids=lambda f: f.name)
SALIDAS_CLASE = ["zero", "subnormal", "normal", "inf", "qnan", "snan"]


@FORMATOS
def test_desempaquetado(fmt: FloatFormat) -> None:
    u = HardwareUnit(unpacker(fmt), "cached")
    for x in edge_values(fmt):
        s, e, f = fmt.fields(x)
        out = u.evaluate({"x": x})
        assert out["sign"] == s
        assert out["exp"] == (e if e else 1)
        assert out["mant"] == (f | (1 << fmt.frac_bits) if e else f), hex(x)


@FORMATOS
def test_clasificador_one_hot(fmt: FloatFormat) -> None:
    u = HardwareUnit(classifier(fmt), "cached")
    for x in edge_values(fmt):
        out = u.evaluate({"x": x})
        clase = fmt.classify(x).value
        assert {k: out[k] for k in SALIDAS_CLASE} == {k: int(k == clase) for k in SALIDAS_CLASE}


@pytest.mark.slow
def test_clasificador_exhaustivo_binary16() -> None:
    u = HardwareUnit(classifier(BINARY16), "cached")
    for x in range(2**16):
        out = u.evaluate({"x": x})
        assert out[BINARY16.classify(x).value] == 1, hex(x)


def _entradas_especiales(fmt: FloatFormat, a: int, b: int) -> dict[str, int]:
    entradas: dict[str, int] = {}
    for nombre, x in (("a", a), ("b", b)):
        clase = fmt.classify(x)
        entradas |= {
            f"{nombre}_zero": int(clase is FPClass.ZERO),
            f"{nombre}_inf": int(clase is FPClass.INF),
            f"{nombre}_qnan": int(clase is FPClass.QNAN),
            f"{nombre}_snan": int(clase is FPClass.SNAN),
            f"{nombre}_sign": x >> (fmt.width - 1),
        }
    return entradas


@pytest.mark.parametrize(("op", "fn"), [("add", ref.fadd), ("mul", ref.fmul), ("div", ref.fdiv)])
def test_casos_especiales_contra_referencia(op: str, fn) -> None:  # type: ignore[no-untyped-def]
    """Para cada par de clases, si la referencia da un resultado especial (NaN, ∞, o
    ±0 en mul/div), el bloque debe activar ``special`` y entregar ese resultado."""
    fmt = BINARY32
    u = HardwareUnit(special_cases(fmt, op), "cached")  # type: ignore[arg-type]
    representantes = [
        0,
        0x80000000,
        0x3F800000,
        0xBF800000,
        0x7F800000,
        0xFF800000,
        0x7FC00000,
        0x7F800001,
    ]
    for a, b in itertools.product(representantes, repeat=2):
        out = u.evaluate(_entradas_especiales(fmt, a, b))
        ca, cb = fmt.classify(a), fmt.classify(b)
        hay_especial = ca.is_nan or cb.is_nan or FPClass.INF in (ca, cb)
        if op != "add":
            hay_especial = hay_especial or FPClass.ZERO in (ca, cb)
        assert out["special"] == int(hay_especial), (hex(a), hex(b))
        if hay_especial:
            r = fn(fmt, a, b)
            assert out["y"] == r.bits, (hex(a), hex(b))
            assert out["invalid"] == int(r.flags.invalid)
            assert out["div_by_zero"] == int(r.flags.div_by_zero)
