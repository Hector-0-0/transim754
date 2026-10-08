"""Generadores de operandos: casos borde y aleatorios con distribución dirigida."""

from __future__ import annotations

import itertools
import random

from transim.fpu.format import FloatFormat


def edge_values(fmt: FloatFormat) -> list[int]:
    """Valores borde positivos y negativos: ceros, subnormales extremos, normales
    extremos, alrededor de 1, ∞, qNaN y sNaN."""
    one = fmt.compose(0, fmt.bias, 0)
    positivos = [
        fmt.zero(0),
        1,  # menor subnormal
        2,
        fmt.frac_mask >> 1,
        fmt.frac_mask,  # mayor subnormal
        fmt.compose(0, 1, 0),  # menor normal
        fmt.compose(0, 1, 1),
        fmt.compose(0, 1, fmt.frac_mask),
        fmt.compose(0, 2, 0),
        one,
        one + 1,  # 1 + ulp
        fmt.compose(0, fmt.bias - 1, 0),  # 0.5
        fmt.compose(0, fmt.bias + 1, 0),  # 2
        fmt.compose(0, fmt.bias + 1, fmt.quiet_bit),  # 3
        fmt.compose(0, fmt.bias - 1, fmt.frac_mask),
        fmt.compose(0, fmt.bias + fmt.frac_bits, 0),  # 2^(p−1): ulp = 1
        fmt.compose(0, fmt.bias + fmt.precision, 0),  # 2^p: ulp = 2
        fmt.compose(0, fmt.exp_max_field - 1, 0),
        fmt.max_finite(0) - 1,
        fmt.max_finite(0),
        fmt.inf(0),
        fmt.canonical_nan,
        fmt.compose(0, fmt.exp_max_field, 1),  # sNaN
    ]
    return positivos + [x | fmt.sign_mask for x in positivos]


def edge_pairs(fmt: FloatFormat) -> list[tuple[int, int]]:
    """Todos los pares de :func:`edge_values` (≈ 2100 pares)."""
    return list(itertools.product(edge_values(fmt), repeat=2))


def random_pairs(fmt: FloatFormat, n: int, seed: int = 754) -> list[tuple[int, int]]:
    """``n`` pares aleatorios reproducibles con tres distribuciones mezcladas:

    - 50 %: patrones de bits uniformes (todas las clases);
    - 25 %: operandos de exponente cercano (cancelación, empates de redondeo);
    - 25 %: operandos en la región subnormal y de normales pequeños (underflow).
    """
    rng = random.Random(seed)
    pairs: list[tuple[int, int]] = []
    for i in range(n):
        kind = i % 4
        if kind in (0, 1):
            pairs.append((rng.getrandbits(fmt.width), rng.getrandbits(fmt.width)))
        elif kind == 2:
            e = rng.randrange(1, fmt.exp_max_field)
            e2 = min(fmt.exp_max_field - 1, max(1, e + rng.randrange(-2, 3)))
            pairs.append(
                (
                    fmt.compose(rng.getrandbits(1), e, rng.getrandbits(fmt.frac_bits)),
                    fmt.compose(rng.getrandbits(1), e2, rng.getrandbits(fmt.frac_bits)),
                )
            )
        else:
            low = max(2, fmt.precision // 2)
            pairs.append(
                (
                    fmt.compose(
                        rng.getrandbits(1), rng.randrange(0, low), rng.getrandbits(fmt.frac_bits)
                    ),
                    fmt.compose(
                        rng.getrandbits(1),
                        rng.randrange(0, fmt.bias + 2),
                        rng.getrandbits(fmt.frac_bits),
                    ),
                )
            )
    return pairs
