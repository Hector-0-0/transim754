"""FADD/FSUB a nivel de transistor. ADR-0002 a ADR-0005, ADR-0009.

Datapath: desempaquetar → clasificar → restar exponentes → intercambiar si |b| > |a|
→ alinear (barrel shifter a la derecha con sticky) → sumar/restar mantisas de p + 3
bits → normalizar (LZC + desplazador a la izquierda) → ``round_and_pack`` → elegir
entre el resultado numérico y el especial.
"""

from __future__ import annotations

from functools import cache

from transim.blocks.comparator import magnitude_comparator
from transim.blocks.lzc import count_bits_for, leading_zero_counter
from transim.blocks.shifter import barrel_shifter, shift_bits_for
from transim.blocks.subtractor import adder_subtractor
from transim.blocks.wiring import Wiring, ripple_add
from transim.core.netlist import Netlist
from transim.core.unit import EngineName, HardwareUnit
from transim.fpu.codec import unpack_into
from transim.fpu.format import FloatFormat, FPResult
from transim.fpu.rounding import exponent_width, round_into
from transim.fpu.special import classify_into, select_result, special_into

GUARD_BITS = 3
"""Bits extra a la derecha de la mantisa alineada: G, R y S (ADR-0002)."""


@cache
def fp_add_sub(fmt: FloatFormat) -> Netlist:
    """Sumador/restador de punto flotante.

    Puertos: buses ``a[fmt.width]``, ``b[fmt.width]``, entrada ``sub`` (0 = a + b,
    1 = a − b); bus ``y[fmt.width]``; salidas ``invalid``, ``overflow``, ``underflow``,
    ``inexact``. Opcionalmente, buses de depuración con prefijo ``dbg_`` (por ejemplo
    ``dbg_exp_diff``, ``dbg_aligned``, ``dbg_sum``) que el CLI muestra con ``--trace``.
    Nombre ``f"FADDSUB_{fmt.name}"``.
    """
    p, eb, ew = fmt.precision, fmt.exp_bits, exponent_width(fmt)
    nl = Netlist(f"FADDSUB_{fmt.name}")
    a, b = nl.input_bus("a", fmt.width), nl.input_bus("b", fmt.width)
    sub = nl.input("sub")
    y = nl.output_bus("y", fmt.width)
    flags = {f: nl.output(f) for f in ("invalid", "overflow", "underflow", "inexact")}
    w = Wiring(nl)
    gnd, vdd = nl.gnd, nl.vdd

    # 1. Desempaquetar; el signo efectivo de b incluye la operación.
    sa, ea, ma = unpack_into(nl, fmt, a, "unpack_a")
    sb_raw, eb_, mb = unpack_into(nl, fmt, b, "unpack_b")
    sb = w.xor2(sb_raw, sub)

    # 2. Ordenar por magnitud: X = mayor, Y = menor.
    swap = nl.node("swap")
    nl.instantiate(magnitude_comparator(eb + p), "order", {"a": ma + ea, "b": mb + eb_, "lt": swap})
    ex = [w.mux2(ea[i], eb_[i], swap) for i in range(eb)]
    ey = [w.mux2(eb_[i], ea[i], swap) for i in range(eb)]
    mx = [w.mux2(ma[i], mb[i], swap) for i in range(p)]
    my = [w.mux2(mb[i], ma[i], swap) for i in range(p)]
    sx, sy = w.mux2(sa, sb, swap), w.mux2(sb, sa, swap)

    # 3. d = ex − ey ≥ 0.
    d = nl.mark_output_bus("dbg_exp_diff", [nl.node(f"d{i}") for i in range(eb)])
    nl.instantiate(adder_subtractor(eb), "exp_diff", {"a": ex, "b": ey, "sub": vdd, "s": d})

    # 4. Alinear Y (p + 3 bits) d posiciones a la derecha, saturando si d no cabe.
    width = p + GUARD_BITS
    sh_bits = shift_bits_for(width)
    saturate = w.or_tree(d[sh_bits:]) if eb > sh_bits else gnd
    sh = [w.or2(d[i], saturate) if i < eb else saturate for i in range(sh_bits)]
    aligned = [nl.node(f"al{i}") for i in range(width)]
    lost = nl.node("al_sticky")
    nl.instantiate(
        barrel_shifter(width, "right"),
        "align",
        {"a": [gnd] * GUARD_BITS + my, "sh": sh, "y": aligned, "sticky": lost},
    )
    y_al = [w.or2(aligned[0], lost), *aligned[1:]]
    nl.mark_output_bus("dbg_aligned", y_al)

    # 5. X ± Y en p + 4 bits (uno extra para el acarreo).
    eop = w.xor2(sx, sy)
    total = nl.mark_output_bus("dbg_sum", [nl.node(f"sum{i}") for i in range(width + 1)])
    nl.instantiate(
        adder_subtractor(width + 1),
        "mant_addsub",
        {"a": [gnd] * GUARD_BITS + mx + [gnd], "b": [*y_al, gnd], "sub": eop, "s": total},
    )

    # 6. Signo: el de X, salvo resultado exactamente cero (sa · sb, ADR-0003).
    is_zero = w.inv(w.or_tree(total))
    sign = w.mux2(sx, w.and2(sa, sb), is_zero)

    # 7. Normalizar: contar ceros en p + 4 bits y desplazar a la izquierda.
    lz_bits = count_bits_for(width + 1)
    lz = nl.mark_output_bus("dbg_lz", [nl.node(f"lz{i}") for i in range(lz_bits)])
    nl.instantiate(leading_zero_counter(width + 1), "lzc", {"a": total, "count": lz})
    norm = [nl.node(f"norm{i}") for i in range(width + 1)]
    nl.instantiate(
        barrel_shifter(width + 1, "left"), "normalize", {"a": total, "sh": lz, "y": norm}
    )
    m, g, r = norm[GUARD_BITS + 1 :], norm[GUARD_BITS], norm[GUARD_BITS - 1]
    s = w.or_tree(norm[: GUARD_BITS - 1])

    # Exponente sesgado del bit más significativo: ex + 1 − lz (e + 2 bits, C2).
    ex_ext = ex + [gnd] * (ew - eb)
    not_lz = [w.inv(bit) for bit in lz + [gnd] * (ew - lz_bits)]
    diff, _ = ripple_add(w, ex_ext, not_lz, vdd)  # ex − lz
    e_lead, _ = ripple_add(w, diff, [gnd] * ew, vdd)

    # 8. Redondear y empaquetar.
    y_num, ovf, unf, inx = round_into(nl, fmt, sign, e_lead, m, g, r, s)

    # 9. Casos especiales (NaN e ∞) y selección del resultado.
    ca = classify_into(nl, fmt, a, "class_a")
    cb = classify_into(nl, fmt, b, "class_b")
    special, y_sp, invalid, _ = special_into(nl, fmt, "add", ca, cb, sa, sb)
    w.buf(invalid, flags["invalid"])
    select_result(
        w,
        special,
        y_sp,
        y_num,
        y,
        {ovf: flags["overflow"], unf: flags["underflow"], inx: flags["inexact"]},
    )
    return nl


class FPAddSub(HardwareUnit):
    """FADD/FSUB simuladas en transistores."""

    def __init__(self, fmt: FloatFormat, engine: EngineName = "cached") -> None:
        self.fmt = fmt
        super().__init__(fp_add_sub(fmt), engine)

    def add(self, a: int, b: int) -> FPResult:
        """a + b (patrones de bits)."""
        return FPResult.from_outputs(self.evaluate({"a": a, "b": b, "sub": 0}))

    def sub(self, a: int, b: int) -> FPResult:
        """a − b (patrones de bits)."""
        return FPResult.from_outputs(self.evaluate({"a": a, "b": b, "sub": 1}))
