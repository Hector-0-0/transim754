"""Lo que la interfaz calcula sin Qt: operaciones, textos de valores, ciclos y ejemplos.

Los resultados los calcula la FPU de transistores (``FPAddSub``, ``FPMul``, ``FPDiv``).
El modelo de referencia (``transim.reference.fpu``) solo convierte el texto escrito a
bits, igual que el CLI, y verifica el resultado: la interfaz muestra si el hardware
coincide con él.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from transim.core.engine_switch import SwitchEngine
from transim.core.netlist import Instance, Netlist
from transim.core.unit import EngineName, HardwareUnit
from transim.cpu import isa
from transim.fpu.format import FloatFormat, FPClass, FPResult
from transim.metrics.stages import activity_by_stage, critical_stages, schedule
from transim.reference import fpu as ref

MINUS = "−"

OPS: dict[str, tuple[str, str, str]] = {
    "add": ("+", "suma", "FADD"),
    "sub": (MINUS, "resta", "FSUB"),
    "mul": ("×", "multiplicación", "FMUL"),
    "div": ("÷", "división", "FDIV"),
}
"""Operación → (símbolo, nombre, instrucción de T754)."""

_REFERENCE = {"add": ref.fadd, "sub": ref.fsub, "mul": ref.fmul, "div": ref.fdiv}


# ---------------------------------------------------------------- textos
def value_text(fmt: FloatFormat, bits: int) -> str:
    """Valor en decimal con los dígitos justos para identificar el número en el formato.

    Por ejemplo, ``0x3DCCCCCD`` en binary32 se muestra como ``0.1`` y no como
    ``0.100000001``.
    """
    cls = fmt.classify(bits)
    sign = MINUS if bits >> (fmt.width - 1) else ""
    if cls.is_nan:
        return "NaN"
    if cls is FPClass.INF:
        return f"{sign or '+'}∞"
    if cls is FPClass.ZERO:
        return f"{sign}0"
    x = abs(ref.to_float(fmt, bits))
    if x.is_integer() and x < 1e9:
        return sign + str(int(x))
    for digits in range(1, 18):
        text = f"{x:.{digits}g}"
        if ref.from_decimal(fmt, text).bits == bits & ~fmt.sign_mask:
            break
    return sign + text.replace("e-", "e" + MINUS)


def exact_text(fmt: FloatFormat, bits: int) -> str:
    """Valor exacto que representan los bits (sin redondeo decimal)."""
    cls = fmt.classify(bits)
    if cls.is_nan or cls in (FPClass.INF, FPClass.ZERO):
        return value_text(fmt, bits)
    frac = ref.to_fraction(fmt, bits)
    if frac.denominator == 1:
        return str(frac.numerator).replace("-", MINUS)
    sign = MINUS if frac < 0 else ""
    frac = abs(frac)
    whole, rest = divmod(frac.numerator, frac.denominator)
    digits: list[str] = []
    while rest and len(digits) < 160:
        rest *= 10
        d, rest = divmod(rest, frac.denominator)
        digits.append(str(d))
    return f"{sign}{whole}." + "".join(digits) + ("…" if rest else "")


CLASS_NAMES = {
    FPClass.ZERO: "cero",
    FPClass.SUBNORMAL: "subnormal",
    FPClass.NORMAL: "normal",
    FPClass.INF: "infinito",
    FPClass.QNAN: "NaN silencioso",
    FPClass.SNAN: "NaN señalizador",
}


def decode_text(fmt: FloatFormat, bits: int) -> str:
    """Cómo se lee el número a partir de sus campos (ADR-0003)."""
    s, e, f = fmt.fields(bits)
    cls = fmt.classify(bits)
    sign = MINUS if s else "+"
    if cls is FPClass.ZERO:
        return f"exponente y fracción en 0: cero con signo {sign}"
    if cls is FPClass.INF:
        return f"exponente todo en 1 y fracción 0: infinito {sign}"
    if cls.is_nan:
        return "exponente todo en 1 y fracción ≠ 0: no es un número (NaN)"
    if cls is FPClass.SUBNORMAL:
        m = Fraction(f, 1 << fmt.frac_bits)
        return f"subnormal: ({sign}1) × 0.{f:0{fmt.frac_bits}b}₂ × 2^{1 - fmt.bias}".replace(
            "-", MINUS
        ) + f" (significando {float(m):.9g})".replace("-", MINUS)
    m = 1 + Fraction(f, 1 << fmt.frac_bits)
    exp = str(e - fmt.bias).replace("-", MINUS)
    return f"({sign}1) × {float(m):.9g} × 2^{exp}   (exponente {e} {MINUS} {fmt.bias} = {exp})"


def hex_text(fmt: FloatFormat, bits: int) -> str:
    return f"0x{bits:0{fmt.width // 4}X}"


def parse_operand(text: str, fmt: FloatFormat) -> int:
    """Bits del operando escrito en decimal (``1.5``, ``-2e-3``, ``1/3``, ``inf``,
    ``nan``) o en hexadecimal ``0x…``.

    Raises:
        ValueError: si el texto no es un número válido o no cabe en el formato.
    """
    text = text.strip().replace(MINUS, "-").replace("∞", "inf").replace(",", ".")
    if not text:
        raise ValueError("escriba un número")
    if text.lower().startswith(("0x", "-0x")):
        if text.startswith("-"):
            raise ValueError("en hexadecimal escriba los bits, sin signo")
        try:
            bits = int(text, 16)
        except ValueError:
            raise ValueError(f"{text!r} no es un hexadecimal válido") from None
        if bits >> fmt.width:
            raise ValueError(f"{text} no cabe en {fmt.width} bits")
        return bits
    try:
        return ref.from_decimal(fmt, text).bits
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"{text!r} no es un número válido") from None


# ---------------------------------------------------------------- cálculo
@dataclass
class Calculation:
    """Resultado de una operación en la FPU de transistores."""

    fmt: FloatFormat
    a: int
    b: int
    result: FPResult
    stages: dict[str, int | None]
    transistors: int
    toggles: int
    events: int
    seconds: float
    unit: HardwareUnit
    stage_toggles: dict[str, int]
    op: str = "add"
    engine: str = "cached"
    reference: FPResult | None = None

    @property
    def matches(self) -> bool:
        """True si el hardware dio los mismos bits y flags que el modelo de referencia."""
        return self.reference is not None and self.reference == self.result

    @property
    def symbol(self) -> str:
        return OPS[self.op][0]

    @property
    def expression(self) -> str:
        """``1.5 + 2.25 = 3.75``."""
        f = self.fmt
        return (
            f"{value_text(f, self.a)} {self.symbol} {value_text(f, self.b)} = "
            f"{value_text(f, self.result.bits)}"
        )


_UNITS: dict[tuple[str, str, str], HardwareUnit] = {}


def unit_for(fmt: FloatFormat, op: str, engine: EngineName) -> HardwareUnit:
    """Unidad de hardware para ``op`` (se construye una vez por formato y motor)."""
    from transim.fpu.add_sub import FPAddSub
    from transim.fpu.div import FPDiv
    from transim.fpu.mul import FPMul

    kind = "addsub" if op in ("add", "sub") else op
    key = (fmt.name, kind, engine)
    if key not in _UNITS:
        cls = {"addsub": FPAddSub, "mul": FPMul, "div": FPDiv}[kind]
        unit = cls(fmt, engine)
        # Estado de partida definido (0 op 0) para que la primera medición sea comparable.
        unit.evaluate({"a": 0, "b": 0, "sub": 0} if kind == "addsub" else {"a": 0, "b": 0})
        _UNITS[key] = unit
    return _UNITS[key]


def is_built(fmt: FloatFormat, op: str, engine: str) -> bool:
    """True si la unidad ya está construida (la primera vez tarda más)."""
    kind = "addsub" if op in ("add", "sub") else op
    return (fmt.name, kind, engine) in _UNITS


def calculate(fmt: FloatFormat, op: str, a: int, b: int, engine: EngineName) -> Calculation:
    """Calcula ``a op b`` en la unidad de transistores y mide su actividad.

    Las conmutaciones se cuentan respecto de la operación anterior de la misma unidad
    (para la primera, respecto de 0 op 0).
    """
    unit = unit_for(fmt, op, engine)
    inputs: dict[str, int] = {"a": a, "b": b}
    if op in ("add", "sub"):
        inputs["sub"] = int(op == "sub")
    unit.engine.reset_counters()
    start = time.perf_counter()
    outputs = unit.evaluate(inputs)
    seconds = time.perf_counter() - start
    stats = unit.engine.stats()
    stages = {k: v for k, v in outputs.items() if k.startswith("dbg_")}
    return Calculation(
        fmt=fmt,
        a=a,
        b=b,
        result=FPResult.from_outputs({k: v for k, v in outputs.items() if k not in stages}),
        stages=stages,
        transistors=unit.transistor_count(),
        toggles=stats.node_toggles,
        events=stats.transistor_events,
        seconds=seconds,
        unit=unit,
        stage_toggles=activity_by_stage(unit.engine),
        op=op,
        engine=engine,
        reference=_REFERENCE[op](fmt, a, b),
    )


def cycle_groups(netlist: Netlist, period: int) -> tuple[int, list[tuple[str, str, str]]]:
    """Ciclos de ADR-0014 agrupados cuando ocupan las mismas etapas.

    Returns:
        (celdas del camino crítico, filas ``(ciclos, celdas, etapas)``).
    """
    stages = critical_stages(netlist)
    cycles = schedule(stages, period)
    rows = []
    i = 0
    while i < len(cycles):
        j = i
        while j + 1 < len(cycles) and cycles[j + 1].stages == cycles[i].stages:
            j += 1
        first, last = cycles[i], cycles[j]
        which = str(first.index) if i == j else f"{first.index}–{last.index}"
        rows.append((which, f"{first.first_cell}–{last.last_cell}", " · ".join(first.stages)))
        i = j + 1
    return sum(st.cells for st in stages), rows


def cycles_report(netlist: Netlist, period: int, stage_toggles: dict[str, int]) -> str:
    """Texto de la consola de ciclos (ADR-0014): el camino crítico repartido en ciclos de
    ``period`` celdas y las conmutaciones de cada etapa en la última operación."""
    from transim.metrics.stages import STAGE_NAMES

    total, groups = cycle_groups(netlist, period)
    n_cycles = len(schedule(critical_stages(netlist), period))
    lines = [
        f"{netlist.name} · camino crítico: {total} celdas",
        f"Periodo de reloj: {period} celdas → {n_cycles} ciclos (estimado, ADR-0014)",
        "",
    ]
    for which, cells, stages in groups:
        label = f"Ciclo {which}" if "–" not in which else f"Ciclos {which}"
        lines.append(f"{label:<14} celdas {cells:<11} {stages}")
    if stage_toggles:
        lines += ["", "Conmutaciones por etapa en esta operación:"]
        for name, n in sorted(stage_toggles.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {STAGE_NAMES.get(name, name):<28} {n:>7}")
    return "\n".join(lines)


def instance_toggles(engine: SwitchEngine, inst: Instance) -> int:
    """Conmutaciones de los nodos que manejan los canales de ``inst`` (contadores actuales)."""
    nodes = {n.id for t in inst.transistors for n in (t.source, t.drain) if not n.is_source}
    return sum(engine.node_toggles[i] for i in nodes)


# ---------------------------------------------------------------- ejemplos
Operand = str | Callable[[FloatFormat], str]


@dataclass(frozen=True)
class Example:
    """Un caso para mostrar en la exposición."""

    title: str
    a: Operand
    op: str
    b: Operand
    note: str

    def operands(self, fmt: FloatFormat) -> tuple[str, str]:
        return _operand(self.a, fmt), _operand(self.b, fmt)


def _operand(spec: Operand, fmt: FloatFormat) -> str:
    return spec(fmt) if callable(spec) else spec


def _max(fmt: FloatFormat) -> str:
    return hex_text(fmt, fmt.max_finite())


def _min_tie(fmt: FloatFormat) -> str:
    """El menor normal más un ulp: al dividirlo entre 2 queda un empate en subnormal."""
    return hex_text(fmt, fmt.compose(0, 1, 1))


def _tiny(fmt: FloatFormat) -> str:
    return hex_text(fmt, fmt.compose(0, 0, 1))


EXAMPLES = [
    Example("1.5 + 2.25", "1.5", "add", "2.25", "suma exacta: sin flags"),
    Example("0.1 + 0.2", "0.1", "add", "0.2", "ni 0.1 ni 0.2 son exactos: inexacto (NX)"),
    Example("1 ÷ 3", "1", "div", "3", "el cociente se redondea al par más cercano (NX)"),
    Example("5 − 5", "5", "sub", "5", "resta exacta que da +0"),
    Example("(−0) + (−0)", "-0", "add", "-0", "el signo del cero se conserva: −0"),
    Example("1 ÷ 0", "1", "div", "0", "división por cero (DZ): +∞"),
    Example("0 ÷ 0", "0", "div", "0", "operación inválida (NV): NaN"),
    Example("∞ − ∞", "inf", "sub", "inf", "operación inválida (NV): NaN"),
    Example("máximo × 2", _max, "mul", "2", "desborda: overflow (OF) y +∞"),
    Example("menor normal × 0.5", _min_tie, "mul", "0.5", "resultado subnormal: underflow (UF)"),
    Example("menor subnormal + sí mismo", _tiny, "add", _tiny, "suma exacta entre subnormales"),
]


# ---------------------------------------------------------------- programa
def instruction_lines(source: str, words: list[int]) -> dict[int, int]:
    """Línea del código fuente (desde 1) de cada dirección de instrucción del programa."""
    from transim.cpu.assembler import _sin_comentario

    lines = [n for n, text in enumerate(source.splitlines(), 1) if _sin_comentario(text).strip()]
    out: dict[int, int] = {}
    pc = 0
    for line in lines:
        if pc >= len(words):
            break
        out[pc] = line
        pc += isa.decode(words[pc]).words
    return out


__all__ = [
    "EXAMPLES",
    "OPS",
    "Calculation",
    "Example",
    "calculate",
    "cycle_groups",
    "cycles_report",
    "decode_text",
    "exact_text",
    "hex_text",
    "instance_toggles",
    "instruction_lines",
    "is_built",
    "parse_operand",
    "unit_for",
    "value_text",
]
