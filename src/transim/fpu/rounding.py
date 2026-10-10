"""Redondeo roundTiesToEven y empaquetado (compartido). ADR-0002, ADR-0004.

Lo usan FADD/FSUB, FMUL y FDIV. El contrato exacto está en
:func:`transim.reference.fpu.round_and_pack`, que es su modelo de referencia.
"""

from __future__ import annotations

from functools import cache

from transim.blocks.shifter import barrel_shifter, shift_bits_for
from transim.blocks.wiring import Wiring, ripple_add
from transim.core.netlist import Netlist
from transim.core.node import Node
from transim.fpu.format import FloatFormat


def exponent_width(fmt: FloatFormat) -> int:
    """Ancho del exponente extendido con signo: e + 2 bits (complemento a 2)."""
    return fmt.exp_bits + 2


@cache
def round_and_pack(fmt: FloatFormat) -> Netlist:
    """Redondea con RNE, desnormaliza si hace falta y empaqueta, con flags.

    Entradas:
        - ``sign``;
        - bus ``e[exponent_width(fmt)]``: exponente **sesgado** del bit más
          significativo de ``m``, en complemento a 2 (puede ser ≤ 0 o > emax + sesgo);
        - bus ``m[fmt.precision]``: mantisa normalizada (m[p−1] = 1) o cero;
        - ``g``, ``r``, ``s``: guard, round y sticky.

    Salidas: bus ``y[fmt.width]``; ``overflow``, ``underflow``, ``inexact``.

    Comportamiento (ver la referencia): si e ≤ 0, desplazar m a la derecha 1 − e
    posiciones acumulando sticky (barrel shifter con sticky); incrementar el LSB si
    G·(R + S + LSB); si el incremento desborda la mantisa, ajustar el exponente; si el
    exponente supera emax + sesgo, ±∞ con overflow e inexact; underflow = diminuto
    después de redondear **e** inexacto. Nombre ``f"ROUND_{fmt.name}"``.
    """
    p, ew = fmt.precision, exponent_width(fmt)
    nl = Netlist(f"ROUND_{fmt.name}")
    sign = nl.input("sign")
    e = nl.input_bus("e", ew)
    m = nl.input_bus("m", p)
    g, r, s = nl.input("g"), nl.input("r"), nl.input("s")
    y = nl.output_bus("y", fmt.width)
    overflow, underflow, inexact = (
        nl.output("overflow"),
        nl.output("underflow"),
        nl.output("inexact"),
    )
    w = Wiring(nl)
    lead = m[p - 1]  # 0 solo si m = 0 (cero exacto)

    # 1. Desnormalización: si e ≤ 0, desplazar m:g:r a la derecha 1 − e posiciones.
    e_zero = w.inv(w.or_tree(e))
    denorm = w.or2(e[ew - 1], e_zero)
    not_e = [w.inv(bit) for bit in e]
    two = [w.nl.gnd, w.nl.vdd] + [w.nl.gnd] * (ew - 2)
    amount, _ = ripple_add(w, not_e, two, w.nl.gnd)  # 1 − e = ¬e + 2
    width = p + 2
    sh_bits = shift_bits_for(width)
    saturate = w.or_tree(amount[sh_bits:]) if ew > sh_bits else w.nl.gnd
    sh = [w.and2(denorm, w.or2(amount[i], saturate)) for i in range(sh_bits)]
    shifted = [nl.node(f"dn{i}") for i in range(width)]
    lost = nl.node("dn_sticky")
    nl.instantiate(
        barrel_shifter(width, "right"),
        "denorm",
        {"a": [r, g, *m], "sh": sh, "y": shifted, "sticky": lost},
    )
    r2, g2, m2 = shifted[0], shifted[1], shifted[2:]
    s2 = w.or2(s, lost)

    # 2. Redondeo RNE: incremento = G·(R + S + LSB).
    inc = w.and2(g2, w.or_tree([r2, s2, m2[0]]))
    rounded, carry = ripple_add(w, m2, [w.nl.gnd] * p, inc)
    exact = w.inv(w.or_tree([g2, r2, s2]))

    # 3. Exponente: e + acarreo (normal) o el bit implícito tras redondear (subnormal).
    e_next, _ = ripple_add(w, e, [w.nl.gnd] * ew, carry)
    field = [w.mux2(e_next[i], rounded[p - 1] if i == 0 else w.nl.gnd, denorm) for i in range(ew)]

    # 4. Desbordamiento: campo ≥ 2^e − 1 sin desnormalizar y con m ≠ 0.
    too_big = w.or2(w.or_tree(field[fmt.exp_bits :]), w.and_tree(field[: fmt.exp_bits]))
    ovf = w.and2(w.and2(too_big, w.inv(denorm)), lead, overflow)

    # 5. Diminuto después de redondear con exponente ilimitado: e ≤ 0, salvo e = 0
    #    con m = 1.1…1 y G = 1 (el redondeo lo lleva a 2^emin).
    rescued = w.and2(e_zero, w.and2(w.and_tree(m), g))
    tiny = w.and2(denorm, w.inv(rescued))
    w.or2(w.inv(exact), ovf, inexact)
    w.and2(tiny, w.inv(exact), underflow)

    # 6. Empaquetado.
    w.buf(sign, y[fmt.width - 1])
    for i in range(fmt.exp_bits):
        w.or2(w.and2(field[i], lead), ovf, y[fmt.frac_bits + i])
    not_ovf = w.inv(ovf)
    for i in range(fmt.frac_bits):
        w.and2(rounded[i], not_ovf, y[i])
    return nl


def round_into(
    nl: Netlist,
    fmt: FloatFormat,
    sign: Node,
    e: list[Node],
    m: list[Node],
    g: Node,
    r: Node,
    s: Node,
) -> tuple[list[Node], Node, Node, Node]:
    """Instancia :func:`round_and_pack` en ``nl``.

    Returns:
        (y numérico, overflow, underflow, inexact).
    """
    y = [nl.node(f"num{i}") for i in range(fmt.width)]
    ovf, unf, inx = nl.node("num_ovf"), nl.node("num_unf"), nl.node("num_inx")
    ports: dict[str, Node | list[Node]] = {"sign": sign, "e": e, "m": m, "g": g, "r": r}
    ports |= {"s": s, "y": y, "overflow": ovf, "underflow": unf, "inexact": inx}
    nl.instantiate(round_and_pack(fmt), "round", ports)
    return y, ovf, unf, inx
