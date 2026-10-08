"""Barrel shifter con sticky (responsable: Ronald). Issue #11."""

from __future__ import annotations

import itertools
import random

import pytest

from pendientes import pendiente
from transim.blocks.shifter import barrel_shifter, shift_bits_for
from transim.core import HardwareUnit
from transim.reference.blocks import shift_left, shift_right_sticky


def test_bits_de_desplazamiento() -> None:
    assert shift_bits_for(27) == 5
    assert shift_bits_for(8) == 4


@pendiente(11)
@pytest.mark.switch
def test_derecha_exhaustivo_6_bits() -> None:
    u = HardwareUnit(barrel_shifter(6, "right"), "switch")
    for a, sh in itertools.product(range(64), range(2 ** shift_bits_for(6))):
        out = u.evaluate({"a": a, "sh": sh})
        y, sticky = shift_right_sticky(a, sh, 6)
        assert (out["y"], out["sticky"]) == (y, int(sticky)), (a, sh)


@pendiente(11)
@pytest.mark.switch
def test_izquierda_exhaustivo_6_bits() -> None:
    nl = barrel_shifter(6, "left")
    assert "sticky" not in nl.outputs
    u = HardwareUnit(nl, "switch")
    for a, sh in itertools.product(range(64), range(2 ** shift_bits_for(6))):
        assert u.evaluate({"a": a, "sh": sh})["y"] == shift_left(a, sh, 6), (a, sh)


@pendiente(11)
@pytest.mark.cached
@pytest.mark.parametrize("direccion", ["left", "right"])
def test_ancho_de_alineacion_binary32(direccion: str) -> None:
    ancho = 27  # p + 3 de binary32
    u = HardwareUnit(barrel_shifter(ancho, direccion), "cached")  # type: ignore[arg-type]
    rng = random.Random(27)
    for _ in range(200):
        a, sh = rng.getrandbits(ancho), rng.randrange(2 ** shift_bits_for(ancho))
        out = u.evaluate({"a": a, "sh": sh})
        if direccion == "right":
            y, sticky = shift_right_sticky(a, sh, ancho)
            assert (out["y"], out["sticky"]) == (y, int(sticky))
        else:
            assert out["y"] == shift_left(a, sh, ancho)
