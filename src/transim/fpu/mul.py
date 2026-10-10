"""FMUL a nivel de transistor. ADR-0002 a ADR-0005, ADR-0009."""

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


@cache
def array_multiplier(width: int) -> Netlist:
    """Multiplicador en arreglo sin signo: ``width``² compuertas AND2 para los productos
    parciales y filas de sumadores (HA/FA) que los acumulan.

    Puertos: buses ``a[width]``, ``b[width]``; bus ``p[2·width]`` = a · b.
    Nombre ``f"ARRMUL{width}"``.

    Fila j: suma ripple-carry de la acumulación (posiciones j … j + width − 1) con el
    producto parcial a · b_j; el bit más bajo de cada suma es un bit final del producto.
    """
    nl = Netlist(f"ARRMUL{width}")
    a, b = nl.input_bus("a", width), nl.input_bus("b", width)
    p = nl.output_bus("p", 2 * width)
    w = Wiring(nl)
    w.and2(a[0], b[0], p[0])
    acc: list[Node] = [w.and2(a[i], b[0]) for i in range(1, width)] + [nl.gnd]
    for j in range(1, width):
        row = [w.and2(a[i], b[j]) for i in range(width)]
        carry: Node = nl.gnd
        sums: list[Node] = []
        for i in range(width):
            target = p[j] if i == 0 else None
            node = target if target is not None else nl.node(f"r{j}_{i}")
            carry = w.full_adder(acc[i], row[i], carry, node)
            sums.append(node)
        acc = [*sums[1:], carry]
    for i in range(width):
        if acc[i] is nl.gnd:
            w.const(0, p[width + i])
        else:
            w.buf(acc[i], p[width + i])
    return nl


@cache
def fp_multiplier(fmt: FloatFormat) -> Netlist:
    """Multiplicador de punto flotante.

    Datapath: desempaquetar → clasificar → signo = XOR → exponente = ea + eb − sesgo
    (sumador de L2 con ``exponent_width(fmt)`` bits) → producto de mantisas (p × p) →
    normalizar (LZC si hay subnormales) → G, R, S del producto → ``round_and_pack`` →
    elegir entre el resultado numérico y el especial.

    Puertos: buses ``a[fmt.width]``, ``b[fmt.width]``; bus ``y[fmt.width]``; salidas
    ``invalid``, ``overflow``, ``underflow``, ``inexact``. Nombre ``f"FMUL_{fmt.name}"``.
    """
    p, ew = fmt.precision, exponent_width(fmt)
    nl = Netlist(f"FMUL_{fmt.name}")
    a, b = nl.input_bus("a", fmt.width), nl.input_bus("b", fmt.width)
    y = nl.output_bus("y", fmt.width)
    flags = {f: nl.output(f) for f in ("invalid", "overflow", "underflow", "inexact")}
    w = Wiring(nl)
    gnd, vdd = nl.gnd, nl.vdd

    sa, ea, ma = unpack_into(nl, fmt, a, "unpack_a")
    sb, eb, mb = unpack_into(nl, fmt, b, "unpack_b")
    sign = w.xor2(sa, sb)

    # Producto de mantisas (2p bits) y normalización con LZC (cubre subnormales).
    prod = nl.mark_output_bus("dbg_product", [nl.node(f"prod{i}") for i in range(2 * p)])
    nl.instantiate(array_multiplier(p), "mant_mul", {"a": ma, "b": mb, "p": prod})
    lz_bits = count_bits_for(2 * p)
    lz = nl.mark_output_bus("dbg_lz", [nl.node(f"lz{i}") for i in range(lz_bits)])
    nl.instantiate(leading_zero_counter(2 * p), "lzc", {"a": prod, "count": lz})
    norm = [nl.node(f"norm{i}") for i in range(2 * p)]
    nl.instantiate(barrel_shifter(2 * p, "left"), "normalize", {"a": prod, "sh": lz, "y": norm})
    m, g, r = norm[p:], norm[p - 1], norm[p - 2]
    s = w.or_tree(norm[: p - 2])

    # Exponente sesgado del bit más significativo: ea + eb − sesgo + 1 − lz.
    zeros = [gnd] * (ew - fmt.exp_bits)
    total, _ = ripple_add(w, ea + zeros, eb + zeros, gnd)
    offset = constant_bus(nl, 1 - fmt.bias, ew)
    biased, _ = ripple_add(w, total, offset, gnd)
    not_lz = [w.inv(bit) for bit in lz + [gnd] * (ew - lz_bits)]
    e_lead, _ = ripple_add(w, biased, not_lz, vdd)
    nl.mark_output_bus("dbg_exp", e_lead)

    y_num, ovf, unf, inx = round_into(nl, fmt, sign, e_lead, m, g, r, s)

    ca = classify_into(nl, fmt, a, "class_a")
    cb = classify_into(nl, fmt, b, "class_b")
    special, y_sp, invalid, _ = special_into(nl, fmt, "mul", ca, cb, sa, sb)
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


class FPMul(HardwareUnit):
    """FMUL simulada en transistores."""

    def __init__(self, fmt: FloatFormat, engine: EngineName = "cached") -> None:
        self.fmt = fmt
        super().__init__(fp_multiplier(fmt), engine)

    def mul(self, a: int, b: int) -> FPResult:
        """a × b (patrones de bits)."""
        return FPResult.from_outputs(self.evaluate({"a": a, "b": b}))
