"""Modelo de referencia de la FPU: especificación ejecutable de IEEE 754-2019.

Calcula el resultado **exacto** de cada operación con enteros de Python (sin límite de
tamaño) y lo redondea con roundTiesToEven al formato pedido, con subnormales, valores
especiales, NaN canónico y los cinco flags (ADR-0001 a ADR-0005). No usa ningún tipo
de punto flotante de la plataforma; numpy solo se usa en las pruebas para validarlo.

Todo valor finito se representa como ``(-1)^s · M · 2^E`` con M y E enteros.
"""

from __future__ import annotations

from fractions import Fraction

from transim.fpu.format import Flags, FloatFormat, FPClass, FPResult

_NO_FLAGS = Flags()


# ------------------------------------------------------------------ utilidades
def decompose(fmt: FloatFormat, bits: int) -> tuple[int, int, int]:
    """(signo, M, E) de un valor finito: valor = (-1)^signo · M · 2^E.

    Raises:
        ValueError: si ``bits`` codifica ∞ o NaN.
    """
    s, e, f = fmt.fields(bits)
    if e == fmt.exp_max_field:
        raise ValueError("decompose: valor no finito")
    if e == 0:
        return s, f, fmt.emin - fmt.frac_bits
    return s, f | (1 << fmt.frac_bits), e - fmt.bias - fmt.frac_bits


def to_fraction(fmt: FloatFormat, bits: int) -> Fraction:
    """Valor exacto de un patrón finito como fracción (±0 → 0)."""
    s, m, e = decompose(fmt, bits)
    value = Fraction(m) * (Fraction(2) ** e)
    return -value if s else value


def to_float(fmt: FloatFormat, bits: int) -> float:
    """Valor como ``float`` de Python (para mostrar; exacto en binary16 y binary32)."""
    cls = fmt.classify(bits)
    sign = -1.0 if bits & fmt.sign_mask else 1.0
    if cls is FPClass.INF:
        return sign * float("inf")
    if cls.is_nan:
        return float("nan")
    if cls is FPClass.ZERO:
        return sign * 0.0
    return float(to_fraction(fmt, bits))


def _rne(m: int, shift: int, sticky: bool) -> tuple[int, bool]:
    """Descarta ``shift`` bits de ``m`` con roundTiesToEven.

    ``sticky`` indica que, por debajo de los bits de ``m``, el valor exacto tiene más
    bits distintos de cero (por ejemplo, el resto de una división).

    Returns:
        (m redondeado, inexacto).
    """
    if shift <= 0:
        if sticky:
            raise ValueError("_rne: hay sticky pero no bits que descartar")
        return m << -shift, False
    kept = m >> shift
    rest = m & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    inexact = rest != 0 or sticky
    if rest > half or (rest == half and sticky) or (rest == half and kept & 1):
        kept += 1
    return kept, inexact


def round_exact(fmt: FloatFormat, sign: int, m: int, e: int, *, sticky: bool = False) -> FPResult:
    """Redondea el valor exacto ``(-1)^sign · (m + δ) · 2^e`` al formato ``fmt``.

    ``0 ≤ δ < 1`` es una cola desconocida que solo se sabe si es cero (``sticky`` =
    False) o no. Aplica RNE, underflow gradual, overflow a ±∞ y los flags de ADR-0004
    (tininess **después** del redondeo).
    """
    if m < 0:
        raise ValueError("round_exact: m debe ser no negativo")
    if m == 0:
        if sticky:
            raise ValueError("round_exact: m = 0 con sticky no está soportado")
        return FPResult(fmt.zero(sign), _NO_FLAGS)
    p = fmt.precision
    e_lead = e + m.bit_length() - 1  # exponente del bit más significativo

    # Tininess después del redondeo: redondear a p bits con exponente ilimitado.
    m_unbounded, _ = _rne(m, e_lead - (p - 1) - e, sticky)
    tiny = e_lead + (m_unbounded >> p) < fmt.emin

    # Redondeo real: el LSB no puede quedar por debajo de emin − (p − 1).
    lsb = max(e_lead, fmt.emin) - (p - 1)
    m_r, inexact = _rne(m, lsb - e, sticky)
    if m_r >> p:  # 1.11…1 + ulp = 10.00…0
        m_r >>= 1
        lsb += 1

    if m_r >> (p - 1):  # normal
        exponent = lsb + p - 1
        if exponent > fmt.emax:
            return FPResult(fmt.inf(sign), Flags(overflow=True, inexact=True))
        bits = fmt.compose(sign, exponent + fmt.bias, m_r & fmt.frac_mask)
    else:  # subnormal o cero
        bits = fmt.compose(sign, 0, m_r)
    return FPResult(bits, Flags(underflow=tiny and inexact, inexact=inexact))


def _nan_result(fmt: FloatFormat, *operands: int) -> FPResult | None:
    """NaN canónico si algún operando es NaN (invalid solo con sNaN); si no, None."""
    classes = [fmt.classify(x) for x in operands]
    if not any(c.is_nan for c in classes):
        return None
    return FPResult(fmt.canonical_nan, Flags(invalid=FPClass.SNAN in classes))


def _invalid(fmt: FloatFormat) -> FPResult:
    return FPResult(fmt.canonical_nan, Flags(invalid=True))


# ------------------------------------------------------------------ operaciones
def fadd(fmt: FloatFormat, a: int, b: int) -> FPResult:
    """a + b en el formato ``fmt``."""
    nan = _nan_result(fmt, a, b)
    if nan is not None:
        return nan
    ca, cb = fmt.classify(a), fmt.classify(b)
    sa, sb = a >> (fmt.width - 1), b >> (fmt.width - 1)
    if ca is FPClass.INF or cb is FPClass.INF:
        if ca is FPClass.INF and cb is FPClass.INF and sa != sb:
            return _invalid(fmt)  # ∞ − ∞
        return FPResult(fmt.inf(sa if ca is FPClass.INF else sb), _NO_FLAGS)
    if ca is FPClass.ZERO and cb is FPClass.ZERO:
        return FPResult(fmt.zero(sa & sb), _NO_FLAGS)  # −0 solo si ambos son −0
    _, ma, ea = decompose(fmt, a)
    _, mb, eb = decompose(fmt, b)
    e = min(ea, eb)
    total = (-1) ** sa * (ma << (ea - e)) + (-1) ** sb * (mb << (eb - e))
    if total == 0:
        return FPResult(fmt.zero(0), _NO_FLAGS)  # x − x = +0 en RNE
    return round_exact(fmt, int(total < 0), abs(total), e)


def fsub(fmt: FloatFormat, a: int, b: int) -> FPResult:
    """a − b = a + (−b) en el formato ``fmt``."""
    return fadd(fmt, a, b ^ fmt.sign_mask)


def fmul(fmt: FloatFormat, a: int, b: int) -> FPResult:
    """a × b en el formato ``fmt``."""
    nan = _nan_result(fmt, a, b)
    if nan is not None:
        return nan
    ca, cb = fmt.classify(a), fmt.classify(b)
    sign = (a ^ b) >> (fmt.width - 1)
    if FPClass.INF in (ca, cb):
        if FPClass.ZERO in (ca, cb):
            return _invalid(fmt)  # 0 × ∞
        return FPResult(fmt.inf(sign), _NO_FLAGS)
    if FPClass.ZERO in (ca, cb):
        return FPResult(fmt.zero(sign), _NO_FLAGS)
    _, ma, ea = decompose(fmt, a)
    _, mb, eb = decompose(fmt, b)
    return round_exact(fmt, sign, ma * mb, ea + eb)


def _round_quotient(fmt: FloatFormat, sign: int, num: int, den: int, exponent: int) -> FPResult:
    """Redondea (num/den)·2^exponent, con num, den > 0."""
    k = max(0, fmt.precision + 3 + den.bit_length() - num.bit_length() + 1)
    q, r = divmod(num << k, den)
    return round_exact(fmt, sign, q, exponent - k, sticky=r != 0)


def fdiv(fmt: FloatFormat, a: int, b: int) -> FPResult:
    """a / b en el formato ``fmt``."""
    nan = _nan_result(fmt, a, b)
    if nan is not None:
        return nan
    ca, cb = fmt.classify(a), fmt.classify(b)
    sign = (a ^ b) >> (fmt.width - 1)
    if ca is FPClass.INF:
        if cb is FPClass.INF:
            return _invalid(fmt)  # ∞ / ∞
        return FPResult(fmt.inf(sign), _NO_FLAGS)
    if cb is FPClass.INF:
        return FPResult(fmt.zero(sign), _NO_FLAGS)
    if cb is FPClass.ZERO:
        if ca is FPClass.ZERO:
            return _invalid(fmt)  # 0 / 0
        return FPResult(fmt.inf(sign), Flags(div_by_zero=True))
    if ca is FPClass.ZERO:
        return FPResult(fmt.zero(sign), _NO_FLAGS)
    _, ma, ea = decompose(fmt, a)
    _, mb, eb = decompose(fmt, b)
    return _round_quotient(fmt, sign, ma, mb, ea - eb)


OPERATIONS = {"+": fadd, "-": fsub, "*": fmul, "/": fdiv}
"""Operador → función de referencia."""


# ------------------------------------------------------------ conversiones
def from_decimal(fmt: FloatFormat, text: str) -> FPResult:
    """Convierte un literal decimal (``"1.5"``, ``"-2e-3"``, ``"inf"``, ``"nan"``) con RNE.

    La conversión es exacta antes de redondear (sin pasar por binary64), por lo que no
    hay doble redondeo.

    Raises:
        ValueError: si el texto no es un número.
    """
    t = text.strip().lower()
    sign = 1 if t.startswith("-") else 0
    body = t.lstrip("+-")
    if body in ("inf", "infinity"):
        return FPResult(fmt.inf(sign), _NO_FLAGS)
    if body == "nan":
        return FPResult(fmt.canonical_nan, _NO_FLAGS)
    value = abs(Fraction(body))
    if value == 0:
        return FPResult(fmt.zero(sign), _NO_FLAGS)
    return _round_quotient(fmt, sign, value.numerator, value.denominator, 0)


def from_float(fmt: FloatFormat, x: float) -> FPResult:
    """Convierte un ``float`` de Python (binary64) al formato con RNE."""
    if x != x:
        return FPResult(fmt.canonical_nan, _NO_FLAGS)
    sign = 1 if str(x).startswith("-") else 0
    if x in (float("inf"), float("-inf")):
        return FPResult(fmt.inf(sign), _NO_FLAGS)
    value = abs(Fraction(x))
    if value == 0:
        return FPResult(fmt.zero(sign), _NO_FLAGS)
    return _round_quotient(fmt, sign, value.numerator, value.denominator, 0)


# ------------------------------------------------- contrato de round_and_pack
def round_and_pack(
    fmt: FloatFormat, sign: int, exponent: int, mantissa: int, g: int, r: int, s: int
) -> FPResult:
    """Referencia del bloque compartido ``fpu.rounding.round_and_pack`` (ADR-0002).

    Args:
        fmt: formato de salida.
        sign: signo del resultado.
        exponent: exponente **sesgado** del bit más significativo de ``mantissa``, como
            entero con signo (puede ser ≤ 0 si el resultado es diminuto o > emax + sesgo
            si desborda).
        mantissa: p bits con el bit p−1 en 1 (normalizada), o 0 para un cero exacto.
        g, r, s: bits guard, round y sticky que siguen al LSB de ``mantissa``.

    Returns:
        Resultado empaquetado con flags overflow, underflow e inexact. Si
        ``mantissa`` = 0, ``g``, ``r`` y ``s`` deben ser 0 y el resultado es ±0.
    """
    p = fmt.precision
    if mantissa == 0:
        if g or r or s:
            raise ValueError("round_and_pack: mantisa cero con bits G/R/S")
        return FPResult(fmt.zero(sign), _NO_FLAGS)
    if mantissa.bit_length() != p:
        raise ValueError(f"round_and_pack: la mantisa debe tener el bit {p - 1} en 1")
    m = (mantissa << 2) | (g << 1) | r
    return round_exact(fmt, sign, m, exponent - fmt.bias - (p - 1) - 2, sticky=bool(s))
