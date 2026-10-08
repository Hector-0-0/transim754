"""Formatos binarios de IEEE 754-2019 y tipos compartidos de la FPU (ADR-0001, ADR-0004).

Este es el **único** módulo donde se escriben los parámetros de los formatos
(``BINARY32 = FloatFormat(8, 23)`` y ``BINARY16 = FloatFormat(5, 10)``). Todo lo demás
se deriva de :class:`FloatFormat`. Una prueba automática rechaza los literales 8, 23,
32 y 127 fuera de este archivo y de ``cpu/isa.py``.

Las funciones de este módulo manipulan patrones de bits como enteros de Python; son
utilidades de software (para pruebas, CLI y GUI), no hardware simulado.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class FPClass(Enum):
    """Clase de un valor de punto flotante (ADR-0003)."""

    ZERO = "zero"
    SUBNORMAL = "subnormal"
    NORMAL = "normal"
    INF = "inf"
    QNAN = "qnan"
    SNAN = "snan"

    @property
    def is_nan(self) -> bool:
        """True para qNaN y sNaN."""
        return self in (FPClass.QNAN, FPClass.SNAN)


@dataclass(frozen=True, slots=True)
class FloatFormat:
    """Formato binario de intercambio con ``exp_bits`` de exponente y ``frac_bits`` de fracción."""

    exp_bits: int
    frac_bits: int

    def __post_init__(self) -> None:
        if self.exp_bits < 2 or self.frac_bits < 1:
            raise ValueError("FloatFormat requiere exp_bits ≥ 2 y frac_bits ≥ 1")

    # ------------------------------------------------------------ derivadas
    @property
    def width(self) -> int:
        """Ancho total: 1 + exp_bits + frac_bits."""
        return 1 + self.exp_bits + self.frac_bits

    @property
    def precision(self) -> int:
        """Precisión p = frac_bits + 1 (incluye el bit implícito)."""
        return self.frac_bits + 1

    @property
    def bias(self) -> int:
        """Sesgo 2^(e−1) − 1."""
        return (1 << (self.exp_bits - 1)) - 1

    @property
    def emax(self) -> int:
        """Exponente máximo de los normales (= sesgo)."""
        return self.bias

    @property
    def emin(self) -> int:
        """Exponente mínimo de los normales (1 − sesgo)."""
        return 1 - self.bias

    @property
    def exp_max_field(self) -> int:
        """Valor del campo de exponente todo en unos (∞ y NaN)."""
        return (1 << self.exp_bits) - 1

    @property
    def frac_mask(self) -> int:
        """Máscara de los bits de fracción."""
        return (1 << self.frac_bits) - 1

    @property
    def sign_mask(self) -> int:
        """Máscara del bit de signo."""
        return 1 << (self.width - 1)

    @property
    def quiet_bit(self) -> int:
        """Bit más significativo de la fracción: distingue qNaN (1) de sNaN (0)."""
        return 1 << (self.frac_bits - 1)

    @property
    def canonical_nan(self) -> int:
        """NaN canónico del proyecto: signo 0, exponente todo unos, fracción 10…0."""
        return (self.exp_max_field << self.frac_bits) | self.quiet_bit

    @property
    def name(self) -> str:
        """Nombre IEEE (``binary32``…) o descripción ``e?f?`` si no es estándar."""
        return _NAMES.get((self.exp_bits, self.frac_bits), f"e{self.exp_bits}f{self.frac_bits}")

    # --------------------------------------------------------- utilidades
    def fields(self, bits: int) -> tuple[int, int, int]:
        """Separa ``bits`` en (signo, exponente almacenado, fracción)."""
        self._check(bits)
        return (
            bits >> (self.width - 1),
            (bits >> self.frac_bits) & self.exp_max_field,
            bits & self.frac_mask,
        )

    def compose(self, sign: int, exponent: int, fraction: int) -> int:
        """Une (signo, exponente almacenado, fracción) en un patrón de bits."""
        if sign not in (0, 1) or not 0 <= exponent <= self.exp_max_field:
            raise ValueError("signo o exponente fuera de rango")
        if not 0 <= fraction <= self.frac_mask:
            raise ValueError("fracción fuera de rango")
        return (sign << (self.width - 1)) | (exponent << self.frac_bits) | fraction

    def classify(self, bits: int) -> FPClass:
        """Clase del valor codificado en ``bits``."""
        _, e, f = self.fields(bits)
        if e == 0:
            return FPClass.ZERO if f == 0 else FPClass.SUBNORMAL
        if e == self.exp_max_field:
            if f == 0:
                return FPClass.INF
            return FPClass.QNAN if f & self.quiet_bit else FPClass.SNAN
        return FPClass.NORMAL

    def inf(self, sign: int = 0) -> int:
        """Patrón de ±∞."""
        return self.compose(sign, self.exp_max_field, 0)

    def zero(self, sign: int = 0) -> int:
        """Patrón de ±0."""
        return self.compose(sign, 0, 0)

    def max_finite(self, sign: int = 0) -> int:
        """Patrón del mayor finito con signo ``sign``."""
        return self.compose(sign, self.exp_max_field - 1, self.frac_mask)

    def _check(self, bits: int) -> None:
        if not 0 <= bits < (1 << self.width):
            raise ValueError(f"{bits:#x} no cabe en {self.width} bits")


BINARY32 = FloatFormat(8, 23)
"""IEEE 754-2019 binary32: formato oficial del proyecto."""

BINARY16 = FloatFormat(5, 10)
"""IEEE 754-2019 binary16: demostraciones y pruebas exhaustivas parciales."""

_NAMES = {(8, 23): "binary32", (5, 10): "binary16"}

FORMATS = {"binary32": BINARY32, "binary16": BINARY16}
"""Formatos por nombre (CLI y GUI)."""


@dataclass(frozen=True, slots=True)
class Flags:
    """Los cinco flags de IEEE 754-2019 §7 (ADR-0004)."""

    invalid: bool = False
    div_by_zero: bool = False
    overflow: bool = False
    underflow: bool = False
    inexact: bool = False

    def __or__(self, other: Flags) -> Flags:
        return Flags(
            self.invalid or other.invalid,
            self.div_by_zero or other.div_by_zero,
            self.overflow or other.overflow,
            self.underflow or other.underflow,
            self.inexact or other.inexact,
        )

    def to_bits(self) -> int:
        """Codificación en el FSR: bit 0 NX, 1 UF, 2 OF, 3 DZ, 4 NV."""
        return (
            int(self.inexact)
            | int(self.underflow) << 1
            | int(self.overflow) << 2
            | int(self.div_by_zero) << 3
            | int(self.invalid) << 4
        )

    @classmethod
    def from_bits(cls, bits: int) -> Flags:
        """Inversa de :meth:`to_bits` (ignora los bits superiores)."""
        return cls(
            invalid=bool(bits >> 4 & 1),
            div_by_zero=bool(bits >> 3 & 1),
            overflow=bool(bits >> 2 & 1),
            underflow=bool(bits >> 1 & 1),
            inexact=bool(bits & 1),
        )

    def __str__(self) -> str:
        names = [
            n
            for n, v in (
                ("NV", self.invalid),
                ("DZ", self.div_by_zero),
                ("OF", self.overflow),
                ("UF", self.underflow),
                ("NX", self.inexact),
            )
            if v
        ]
        return "|".join(names) if names else "—"


class UndefinedOutputError(RuntimeError):
    """Una salida del circuito quedó en X o Z: el hardware no produjo un valor definido."""


@dataclass(frozen=True, slots=True)
class FPResult:
    """Resultado de una operación de punto flotante: patrón de bits y flags."""

    bits: int
    flags: Flags

    @classmethod
    def from_outputs(cls, outputs: Mapping[str, int | None]) -> FPResult:
        """Construye el resultado a partir de las salidas de un netlist de la FPU.

        Lee el bus ``y`` y las salidas ``invalid``, ``div_by_zero``, ``overflow``,
        ``underflow`` e ``inexact`` (las que no existan valen 0).

        Raises:
            UndefinedOutputError: si alguna salida vale X o Z.
        """
        undefined = [k for k, v in outputs.items() if v is None]
        if undefined:
            raise UndefinedOutputError(f"salidas indefinidas (X/Z): {sorted(undefined)}")
        out = {k: v or 0 for k, v in outputs.items()}
        return cls(
            bits=out["y"],
            flags=Flags(
                invalid=bool(out.get("invalid", 0)),
                div_by_zero=bool(out.get("div_by_zero", 0)),
                overflow=bool(out.get("overflow", 0)),
                underflow=bool(out.get("underflow", 0)),
                inexact=bool(out.get("inexact", 0)),
            ),
        )
