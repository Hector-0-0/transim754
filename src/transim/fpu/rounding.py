"""Redondeo roundTiesToEven y empaquetado (compartido; dueño: Daniel). ADR-0002, ADR-0004.

Lo usan FADD/FSUB, FMUL y FDIV. El contrato exacto está en
:func:`transim.reference.fpu.round_and_pack`, que es su modelo de referencia.
"""

from __future__ import annotations

from transim.core.netlist import Netlist
from transim.fpu.format import FloatFormat


def exponent_width(fmt: FloatFormat) -> int:
    """Ancho del exponente extendido con signo: e + 2 bits (complemento a 2)."""
    return fmt.exp_bits + 2


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
    raise NotImplementedError("pendiente: #16")
