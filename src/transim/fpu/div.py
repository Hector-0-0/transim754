"""FDIV a nivel de transistor. ADR-0002 a ADR-0005, ADR-0009."""

from __future__ import annotations

from functools import cache

from transim.blocks.lzc import count_bits_for, leading_zero_counter
from transim.blocks.shifter import barrel_shifter
from transim.blocks.wiring import Wiring, constant_bus, ripple_add
from transim.core.netlist import Netlist
from transim.core.node import Node
from transim.core.unit import EngineName, HardwareUnit
from transim.fpu.codec import unpack_into
from transim.fpu.format import FloatFormat, FPResult
from transim.fpu.rounding import exponent_width, round_into
from transim.fpu.special import classify_into, select_result, special_into


def quotient_bits(fmt: FloatFormat) -> int:
    """Bits de cociente que genera el divisor: p + 3 (p de mantisa, G, R y uno extra
    porque el cociente de dos mantisas normalizadas está en (1/2, 2))."""
    return fmt.precision + 3


@cache
def nonrestoring_divider(width: int, q_bits: int) -> Netlist:
    """Divisor combinacional no restaurador de mantisas normalizadas.

    ``q_bits`` filas de celdas de suma/resta controlada (XOR2 + FA); cada fila suma o
    resta el divisor según el signo del resto parcial anterior. Al final, el resto se
    corrige y ``sticky`` = resto ≠ 0.

    Puertos: buses ``a[width]``, ``b[width]`` (ambos con el bit más alto en 1); bus
    ``q[q_bits]`` = ⌊a · 2^(q_bits − 1) / b⌋; salida ``sticky``.
    Nombre ``f"NRDIV{width}x{q_bits}"``.

    El resto parcial R cumple −b ≤ R < b, así que basta con ``width + 2`` bits en
    complemento a 2. Fila 0: R = a − b; fila k: R = 2R − b si el R anterior es ≥ 0, o
    2R + b si es negativo. El bit de cociente de cada fila es 1 si el nuevo R es ≥ 0.
    """
    nl = Netlist(f"NRDIV{width}x{q_bits}")
    a, b = nl.input_bus("a", width), nl.input_bus("b", width)
    q = nl.output_bus("q", q_bits)
    sticky = nl.output("sticky")
    w = Wiring(nl)
    rw = width + 2
    b_ext = [*b, nl.gnd, nl.gnd]
    rem: list[Node] = [*a, nl.gnd, nl.gnd]
    subtract: Node = nl.vdd
    for k in range(q_bits):
        shifted = rem if k == 0 else [nl.gnd, *rem[: rw - 1]]
        operand = [w.xor2(bit, subtract) for bit in b_ext]
        rem, _ = ripple_add(w, shifted, operand, subtract)
        subtract = w.inv(rem[rw - 1], q[q_bits - 1 - k])  # 1 si R ≥ 0
    # Corrección final: si R < 0, el resto verdadero es R + b.
    negative = rem[rw - 1]
    fix = [w.and2(bit, negative) for bit in b_ext]
    corrected, _ = ripple_add(w, rem, fix, nl.gnd)
    w.buf(w.or_tree(corrected), sticky)
    return nl


@cache
def fp_divider(fmt: FloatFormat) -> Netlist:
    """Divisor de punto flotante.

    Datapath: desempaquetar → clasificar → signo = XOR → normalizar subnormales (LZC +
    desplazador) → exponente = ea − eb + sesgo → cociente de mantisas con
    ``quotient_bits(fmt)`` bits → normalizar (1 bit) → G, R, S → ``round_and_pack`` →
    elegir entre el resultado numérico y el especial.

    Puertos: buses ``a[fmt.width]``, ``b[fmt.width]``; bus ``y[fmt.width]``; salidas
    ``invalid``, ``div_by_zero``, ``overflow``, ``underflow``, ``inexact``.
    Nombre ``f"FDIV_{fmt.name}"``.
    """
    p, ew, qb = fmt.precision, exponent_width(fmt), quotient_bits(fmt)
    nl = Netlist(f"FDIV_{fmt.name}")
    a, b = nl.input_bus("a", fmt.width), nl.input_bus("b", fmt.width)
    y = nl.output_bus("y", fmt.width)
    names = ("invalid", "div_by_zero", "overflow", "underflow", "inexact")
    flags = {f: nl.output(f) for f in names}
    w = Wiring(nl)
    vdd = nl.vdd

    sa, ea, ma = unpack_into(nl, fmt, a, "unpack_a")
    sb, eb, mb = unpack_into(nl, fmt, b, "unpack_b")
    sign = w.xor2(sa, sb)

    # Normalizar cada mantisa (subnormales) y ajustar su exponente: e' = e − lz.
    na, ea_n = _normalize(nl, w, fmt, ma, ea, "a")
    nb, eb_n = _normalize(nl, w, fmt, mb, eb, "b")

    # Cociente de p + 3 bits con sticky.
    q = nl.mark_output_bus("dbg_quotient", [nl.node(f"q{i}") for i in range(qb)])
    rest = nl.node("div_sticky")
    nl.instantiate(
        nonrestoring_divider(p, qb), "mant_div", {"a": na, "b": nb, "q": q, "sticky": rest}
    )
    top = q[qb - 1]
    # Si el bit alto es 1 se toman los p bits superiores; si no, desde el siguiente.
    m = [w.mux2(q[i + 2], q[i + 3], top) for i in range(p)]
    g = w.mux2(q[1], q[2], top)
    r = w.mux2(q[0], q[1], top)
    s = w.or2(rest, w.and2(q[0], top))

    # e = ea' − eb' + sesgo − 1 + (bit alto del cociente).
    not_eb = [w.inv(bit) for bit in eb_n]
    diff, _ = ripple_add(w, ea_n, not_eb, vdd)
    e_lead, _ = ripple_add(w, diff, constant_bus(nl, fmt.bias - 1, ew), top)
    nl.mark_output_bus("dbg_exp", e_lead)

    y_num, ovf, unf, inx = round_into(nl, fmt, sign, e_lead, m, g, r, s)

    ca = classify_into(nl, fmt, a, "class_a")
    cb = classify_into(nl, fmt, b, "class_b")
    special, y_sp, invalid, dz = special_into(nl, fmt, "div", ca, cb, sa, sb)
    w.buf(invalid, flags["invalid"])
    w.buf(dz, flags["div_by_zero"])
    select_result(
        w,
        special,
        y_sp,
        y_num,
        y,
        {ovf: flags["overflow"], unf: flags["underflow"], inx: flags["inexact"]},
    )
    return nl


def _normalize(
    nl: Netlist, w: Wiring, fmt: FloatFormat, mant: list[Node], exp: list[Node], tag: str
) -> tuple[list[Node], list[Node]]:
    """Desplaza ``mant`` hasta que su bit alto sea 1 y devuelve (mantisa, exp − lz) con
    el exponente en ``exponent_width(fmt)`` bits."""
    p, ew = fmt.precision, exponent_width(fmt)
    lz_bits = count_bits_for(p)
    lz = [nl.node(f"lz_{tag}{i}") for i in range(lz_bits)]
    nl.instantiate(leading_zero_counter(p), f"lzc_{tag}", {"a": mant, "count": lz})
    norm = [nl.node(f"norm_{tag}{i}") for i in range(p)]
    nl.instantiate(barrel_shifter(p, "left"), f"normalize_{tag}", {"a": mant, "sh": lz, "y": norm})
    not_lz = [w.inv(bit) for bit in lz + [nl.gnd] * (ew - lz_bits)]
    exp_n, _ = ripple_add(w, exp + [nl.gnd] * (ew - fmt.exp_bits), not_lz, nl.vdd)
    return norm, exp_n


class FPDiv(HardwareUnit):
    """FDIV simulada en transistores."""

    def __init__(self, fmt: FloatFormat, engine: EngineName = "cached") -> None:
        self.fmt = fmt
        super().__init__(fp_divider(fmt), engine)

    def div(self, a: int, b: int) -> FPResult:
        """a / b (patrones de bits)."""
        return FPResult.from_outputs(self.evaluate({"a": a, "b": b}))
