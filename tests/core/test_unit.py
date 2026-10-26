"""Unidades de hardware: límite de eventos del motor (regresión)."""

from __future__ import annotations

import pytest

from transim.core.unit import EVENTS_PER_NODE, HardwareUnit, make_engine
from transim.fpu.div import fp_divider
from transim.fpu.format import BINARY32, FPResult
from transim.reference import fpu as ref


def test_presupuesto_proporcional_a_los_nodos() -> None:
    nl = fp_divider(BINARY32)
    assert make_engine(nl, "switch").max_events == EVENTS_PER_NODE * len(nl.nodes) + 1000


@pytest.mark.switch
def test_divisor_binary32_se_estabiliza_en_el_motor_exacto() -> None:
    """1 / 3 provoca unos 11 cambios por nodo: con 10 por nodo el motor se detenía."""
    unidad = HardwareUnit(fp_divider(BINARY32), "switch")
    a, b = 0x3F800000, 0x40400000
    salidas = unidad.evaluate({"a": a, "b": b})
    resultado = FPResult.from_outputs(
        {k: v for k, v in salidas.items() if not k.startswith("dbg_")}
    )
    assert resultado == ref.fdiv(BINARY32, a, b)
