"""Comparación bit a bit de resultados de punto flotante con mensajes legibles."""

from __future__ import annotations

from transim.fpu.format import FloatFormat, FPResult


def describe(fmt: FloatFormat, bits: int) -> str:
    """``0x40700000 (s=0 e=0x80 f=0x700000, normal)``."""
    s, e, f = fmt.fields(bits)
    width = (fmt.width + 3) // 4
    return f"{bits:#0{width + 2}x} (s={s} e={e:#x} f={f:#x}, {fmt.classify(bits).value})"


def assert_fp_equal(fmt: FloatFormat, got: FPResult, want: FPResult, context: str = "") -> None:
    """Exige bits y flags idénticos. Un NaN debe ser exactamente el NaN canónico."""
    if got.bits != want.bits or got.flags != want.flags:
        raise AssertionError(
            f"{context}\n  obtenido: {describe(fmt, got.bits)} flags {got.flags}"
            f"\n  esperado: {describe(fmt, want.bits)} flags {want.flags}"
        )
