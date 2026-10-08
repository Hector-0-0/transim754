"""Oráculo de punto flotante: modelo de referencia verificado contra numpy en cada uso.

:func:`expected` devuelve el resultado que debe producir el hardware. Antes de
devolverlo comprueba que el modelo de referencia y numpy coinciden:

- **valor:** bits exactos, salvo NaN (numpy en x86 devuelve 0xFFC00000; la referencia,
  el NaN canónico 0x7FC00000: basta con que ambos sean NaN);
- **flags en binary32:** invalid, divideByZero, overflow y underflow contra los flags
  del hardware x86 que reporta numpy (tininess después del redondeo, como ADR-0004);
- **inexact:** contra la aritmética racional exacta de ``fractions.Fraction``;
- **flags en binary16:** numpy no tiene binary16 en hardware y su conversión por
  software detecta la tininess *antes* del redondeo; por eso en binary16 se comparan
  invalid, divideByZero y overflow contra numpy, y underflow se toma de la referencia
  (caso documentado en ``tests/reference/test_ref_fpu.py``).

Si alguna comprobación falla se lanza :class:`OracleDisagreementError`: el error está en el
oráculo, no en el módulo que se prueba.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from fractions import Fraction

import numpy as np

from transim.fpu.format import BINARY16, BINARY32, FloatFormat, FPResult
from transim.reference import fpu as ref

_NUMPY_TYPES = {BINARY32: (np.float32, np.uint32), BINARY16: (np.float16, np.uint16)}
_NUMPY_OPS: dict[str, Callable[[np.ndarray, np.ndarray], np.ndarray]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
}
_EXACT_OPS: dict[str, Callable[[Fraction, Fraction], Fraction]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
}
_NUMPY_FLAG = {
    "invalid value": "invalid",
    "divide by zero": "div_by_zero",
    "overflow": "overflow",
    "underflow": "underflow",
}


class OracleDisagreementError(AssertionError):
    """La referencia y numpy no coinciden: hay un error en el oráculo."""


def numpy_op(fmt: FloatFormat, op: str, a: int, b: int) -> tuple[int, set[str]]:
    """Ejecuta ``a op b`` en numpy y devuelve (bits, nombres de flags de ADR-0004)."""
    ftype, utype = _NUMPY_TYPES[fmt]
    x = np.array([a], dtype=utype).view(ftype)
    y = np.array([b], dtype=utype).view(ftype)
    seen: set[str] = set()
    previous = np.seterrcall(lambda kind, _flag: seen.add(_NUMPY_FLAG[kind]))
    try:
        with np.errstate(all="call"):
            r = _NUMPY_OPS[op](x, y)
    finally:
        np.seterrcall(previous)
    return int(r.view(utype)[0]), seen


def expected(fmt: FloatFormat, op: str, a: int, b: int) -> FPResult:
    """Resultado esperado de ``a op b`` (op ∈ ``+ - * /``) en ``fmt``, verificado.

    Raises:
        OracleDisagreementError: si la referencia y numpy discrepan.
    """
    result = ref.OPERATIONS[op](fmt, a, b)
    np_bits, np_flags = numpy_op(fmt, op, a, b)
    ctx = f"{fmt.name} {a:#x} {op} {b:#x}: referencia {result.bits:#x} {result.flags}"

    if fmt.classify(np_bits).is_nan:
        if result.bits != fmt.canonical_nan:
            raise OracleDisagreementError(f"{ctx}; numpy da NaN")
    elif result.bits != np_bits:
        raise OracleDisagreementError(f"{ctx}; numpy {np_bits:#x}")

    checked = ("invalid", "div_by_zero", "overflow", "underflow")
    if fmt is not BINARY32:
        checked = ("invalid", "div_by_zero", "overflow")
    for name in checked:
        if (name in np_flags) != getattr(result.flags, name):
            raise OracleDisagreementError(f"{ctx}; flags de numpy {sorted(np_flags)}")

    ca, cb, cr = fmt.classify(a), fmt.classify(b), fmt.classify(result.bits)
    finite_inputs = not (ca.is_nan or cb.is_nan or "INF" in (ca.name, cb.name))
    if finite_inputs and not cr.is_nan and not (op == "/" and cb.name == "ZERO"):
        exact = _EXACT_OPS[op](ref.to_fraction(fmt, a), ref.to_fraction(fmt, b))
        inexact = cr.name == "INF" or exact != ref.to_fraction(fmt, result.bits)
        if inexact != result.flags.inexact:
            raise OracleDisagreementError(f"{ctx}; inexact exacto = {inexact}")
    return result
