"""Comparador de magnitud (responsable: Ronald). Issue #9."""

from __future__ import annotations

import itertools
import random

import pytest

from transim.blocks.comparator import magnitude_comparator
from transim.core import HardwareUnit
from transim.reference.blocks import compare


@pytest.mark.switch
def test_exhaustivo_4_bits() -> None:
    u = HardwareUnit(magnitude_comparator(4), "switch")
    for a, b in itertools.product(range(16), repeat=2):
        out = u.evaluate({"a": a, "b": b})
        assert (out["lt"], out["eq"], out["gt"]) == tuple(int(x) for x in compare(a, b))


@pytest.mark.cached
def test_aleatorio_10_bits() -> None:
    u = HardwareUnit(magnitude_comparator(10), "cached")
    rng = random.Random(9)
    for _ in range(300):
        a = rng.getrandbits(10)
        b = a if rng.random() < 0.2 else rng.getrandbits(10)
        out = u.evaluate({"a": a, "b": b})
        assert (out["lt"], out["eq"], out["gt"]) == tuple(int(x) for x in compare(a, b))
