"""Utilidades comunes de las pruebas de la FPU."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable

from oracle.cases import edge_values, random_pairs
from oracle.compare import assert_fp_equal
from oracle.numpy_oracle import expected
from transim.fpu.format import FloatFormat, FPResult


def comparar(
    fmt: FloatFormat,
    op: str,
    operacion: Callable[[int, int], FPResult],
    pares: Iterable[tuple[int, int]],
) -> int:
    """Compara bit a bit (y flags) contra el oráculo. Devuelve los casos verificados."""
    n = 0
    for a, b in pares:
        assert_fp_equal(
            fmt, operacion(a, b), expected(fmt, op, a, b), f"{fmt.name}: {a:#x} {op} {b:#x}"
        )
        n += 1
    return n


def pares_rapidos(fmt: FloatFormat, n_aleatorios: int = 120) -> list[tuple[int, int]]:
    """≈ 200 pares: una muestra de casos borde combinados y aleatorios dirigidos."""
    borde = edge_values(fmt)[::3]
    return list(itertools.product(borde, repeat=2))[:100] + random_pairs(fmt, n_aleatorios, seed=1)


def pares_aceptacion(fmt: FloatFormat) -> list[tuple[int, int]]:
    """Criterio de aceptación: todos los pares borde (> 200) y 10 000 aleatorios."""
    return list(itertools.product(edge_values(fmt), repeat=2)) + random_pairs(fmt, 10_000, seed=2)
