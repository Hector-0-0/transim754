"""Clasificación de operandos y resultados especiales. ADR-0003."""

from __future__ import annotations

from functools import cache
from typing import Literal

from transim.blocks.wiring import Wiring
from transim.core.netlist import Netlist
from transim.core.node import Node
from transim.fpu.format import FloatFormat

SpecialOp = Literal["add", "mul", "div"]


@cache
def classifier(fmt: FloatFormat) -> Netlist:
    """Clasifica un operando con compuertas (árboles AND/OR sobre exponente y fracción).

    Puertos: bus ``x[fmt.width]``; salidas one-hot ``zero``, ``subnormal``, ``normal``,
    ``inf``, ``qnan``, ``snan``. Nombre ``f"CLASS_{fmt.name}"``.
    """
    nl = Netlist(f"CLASS_{fmt.name}")
    x = nl.input_bus("x", fmt.width)
    names = ["zero", "subnormal", "normal", "inf", "qnan", "snan"]
    out = {n: nl.output(n) for n in names}
    w = Wiring(nl)
    field = x[fmt.frac_bits : fmt.frac_bits + fmt.exp_bits]
    frac = x[: fmt.frac_bits]
    e_nonzero = w.or_tree(field)
    e_ones = w.and_tree(field)
    f_nonzero = w.or_tree(frac)
    quiet = frac[fmt.frac_bits - 1]
    w.nor2(e_nonzero, f_nonzero, out["zero"])
    w.and2(w.inv(e_nonzero), f_nonzero, out["subnormal"])
    w.nor2(w.inv(e_nonzero), e_ones, out["normal"])
    w.and2(e_ones, w.inv(f_nonzero), out["inf"])
    w.and2(e_ones, quiet, out["qnan"])
    w.and2(w.and2(e_ones, f_nonzero), w.inv(quiet), out["snan"])
    return nl


@cache
def special_cases(fmt: FloatFormat, op: SpecialOp) -> Netlist:
    """Resultado de los casos especiales de la tabla de docs/03 §6 para ``op``.

    Entradas por operando ``a`` y ``b``: ``a_zero``, ``a_inf``, ``a_qnan``, ``a_snan``,
    ``a_sign`` (ídem con ``b_``). Para la resta, ``b_sign`` llega ya invertido.

    Salidas: ``special`` (1 si el resultado lo decide este bloque y no el datapath
    numérico), bus ``y[fmt.width]`` con el resultado especial (NaN canónico, ±∞ o ±0),
    ``invalid`` y ``div_by_zero``. Nombre ``f"SPECIAL_{op}_{fmt.name}"``.

    Nota: en ``add`` los casos "operando cero" no son especiales (los resuelve el
    datapath); solo NaN e ∞. En ``mul`` y ``div`` sí lo son.
    """
    nl = Netlist(f"SPECIAL_{op}_{fmt.name}")
    fields = ("zero", "inf", "qnan", "snan", "sign")
    a = {f: nl.input(f"a_{f}") for f in fields}
    b = {f: nl.input(f"b_{f}") for f in fields}
    special, invalid, dz = nl.output("special"), nl.output("invalid"), nl.output("div_by_zero")
    y = nl.output_bus("y", fmt.width)
    w = Wiring(nl)

    nan_in = w.or_tree([a["qnan"], a["snan"], b["qnan"], b["snan"]])
    snan_in = w.or2(a["snan"], b["snan"])
    any_inf = w.or2(a["inf"], b["inf"])
    if op == "add":
        inv_op = w.and2(w.and2(a["inf"], b["inf"]), w.xor2(a["sign"], b["sign"]))
        w.or2(nan_in, any_inf, special)
        is_inf = any_inf
        sign = w.mux2(b["sign"], a["sign"], a["inf"])
        w.const(0, dz)
    else:
        any_zero = w.or2(a["zero"], b["zero"])
        sign = w.xor2(a["sign"], b["sign"])
        w.or2(w.or2(nan_in, any_inf), any_zero, special)
        if op == "mul":
            inv_op = w.or2(w.and2(a["inf"], b["zero"]), w.and2(a["zero"], b["inf"]))
            is_inf = any_inf
            w.const(0, dz)
        else:
            inv_op = w.or2(w.and2(a["inf"], b["inf"]), w.and2(a["zero"], b["zero"]))
            is_inf = w.or2(a["inf"], b["zero"])
            # División por cero: x / 0 con x finito y distinto de cero, sin NaN.
            finite_nonzero_a = w.nor2(a["zero"], a["inf"])
            w.and2(w.and2(b["zero"], finite_nonzero_a), w.inv(nan_in), dz)
    is_nan = w.or2(nan_in, inv_op)
    w.or2(snan_in, inv_op, invalid)
    exp_ones = w.or2(is_nan, is_inf)
    # NaN canónico: signo 0, exponente en unos y solo el bit quiet en la fracción.
    w.and2(sign, w.inv(is_nan), y[fmt.width - 1])
    for i in range(fmt.frac_bits, fmt.frac_bits + fmt.exp_bits):
        w.buf(exp_ones, y[i])
    w.buf(is_nan, y[fmt.frac_bits - 1])
    for i in range(fmt.frac_bits - 1):
        w.const(0, y[i])
    return nl


CLASSES = ("zero", "subnormal", "normal", "inf", "qnan", "snan")
"""Salidas one-hot de :func:`classifier`."""


def classify_into(nl: Netlist, fmt: FloatFormat, x: list[Node], name: str) -> dict[str, Node]:
    """Instancia :func:`classifier` en ``nl`` sobre el bus ``x``; devuelve sus salidas."""
    out = {c: nl.node(f"{name}_{c}") for c in CLASSES}
    nl.instantiate(classifier(fmt), name, {"x": x, **out})
    return out


def special_into(
    nl: Netlist,
    fmt: FloatFormat,
    op: SpecialOp,
    a: dict[str, Node],
    b: dict[str, Node],
    a_sign: Node,
    b_sign: Node,
) -> tuple[Node, list[Node], Node, Node]:
    """Instancia :func:`special_cases` con las clases de ``a`` y ``b``.

    Returns:
        (special, y especial, invalid, div_by_zero).
    """
    special, invalid, dz = nl.node("sp_special"), nl.node("sp_invalid"), nl.node("sp_dz")
    y = [nl.node(f"sp_y{i}") for i in range(fmt.width)]
    conn: dict[str, Node | list[Node]] = {"special": special, "y": y}
    conn |= {"invalid": invalid, "div_by_zero": dz, "a_sign": a_sign, "b_sign": b_sign}
    for f in ("zero", "inf", "qnan", "snan"):
        conn[f"a_{f}"], conn[f"b_{f}"] = a[f], b[f]
    nl.instantiate(special_cases(fmt, op), "special", conn)
    return special, y, invalid, dz


def select_result(
    w: Wiring,
    special: Node,
    y_special: list[Node],
    y_numeric: list[Node],
    y: list[Node],
    numeric_flags: dict[Node, Node],
) -> None:
    """Salida final: el resultado especial si ``special`` = 1, si no el numérico.

    ``numeric_flags`` asocia cada flag del datapath numérico a su salida; se anulan
    cuando el resultado es especial.
    """
    for i in range(len(y)):
        w.mux2(y_numeric[i], y_special[i], special, y[i])
    not_special = w.inv(special)
    for flag, out in numeric_flags.items():
        w.and2(flag, not_special, out)
