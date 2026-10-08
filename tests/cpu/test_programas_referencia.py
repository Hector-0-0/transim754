"""Los programas de ejemplo en el simulador de referencia (comprueba las expectativas)."""

from __future__ import annotations

import pytest

from cpu.programas import EJEMPLOS, PROGRAMAS
from transim.reference.machine import run


@pytest.mark.parametrize("nombre", sorted(PROGRAMAS))
def test_salidas_esperadas(nombre: str) -> None:
    palabras, salidas, fsr = PROGRAMAS[nombre]
    estado = run(palabras)
    assert estado.outputs == salidas
    assert estado.fsr == fsr
    assert (EJEMPLOS / f"{nombre}.t754").is_file()
