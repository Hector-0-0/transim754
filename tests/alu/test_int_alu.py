"""ALU entera de 32 bits (responsable: Ronald). Issue #13."""

from __future__ import annotations

import random

import pytest

from pendientes import pendiente
from transim.alu.int_alu import OP_ADD, OP_SUB, IntALU, int_alu
from transim.reference.integer import int_add, int_sub

pytestmark = pendiente(13)

BORDE = [0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x80000001, 0x55555555]


@pytest.fixture(scope="module")
def alu() -> IntALU:
    return IntALU()


@pytest.mark.cached
def test_casos_borde(alu: IntALU) -> None:
    for a in BORDE:
        for b in BORDE:
            assert alu.execute(OP_ADD, a, b) == int_add(a, b, 32), (a, b)
            assert alu.execute(OP_SUB, a, b) == int_sub(a, b, 32), (a, b)


@pytest.mark.cached
def test_aleatorio(alu: IntALU) -> None:
    rng = random.Random(13)
    for _ in range(500):
        a, b = rng.getrandbits(32), rng.getrandbits(32)
        op = rng.choice([OP_ADD, OP_SUB])
        esperado = (int_add if op == OP_ADD else int_sub)(a, b, 32)
        assert alu.execute(op, a, b) == esperado, (op, a, b)


def test_puertos() -> None:
    nl = int_alu(8)
    assert nl.name == "ALU8"
    assert set(nl.outputs) >= {"c", "v", "z", "n"}
