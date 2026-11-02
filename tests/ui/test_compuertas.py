"""Vista de compuertas (sin Qt): función de cada etapa contra la simulación y cableado."""

from __future__ import annotations

import itertools

import pytest

from transim.cells.library import CELLS
from transim.core.engine_switch import SwitchEngine
from transim.core.netlist import Netlist
from transim.core.signals import Logic
from transim.ui.gui import gates
from transim.ui.gui.circuit import analyze
from transim.ui.gui.schematic import approx_width

PRIMITIVAS = sorted(n for n, f in CELLS.items() if not f().instances)


def celda(nombre: str) -> Netlist:
    return CELLS[nombre]()


@pytest.mark.parametrize("nombre", PRIMITIVAS)
def test_cada_compuerta_calcula_lo_que_simula_el_motor(nombre: str) -> None:
    """Para toda combinación de entradas, la fórmula de cada etapa evaluada con los
    valores simulados de sus entradas da el valor simulado de su salida."""
    nl = celda(nombre)
    c = analyze(nl)
    engine = SwitchEngine(nl)
    entradas = list(nl.inputs)
    for combo in itertools.product((0, 1), repeat=len(entradas)):
        engine.set_inputs(dict(zip(entradas, combo, strict=True)))

        def valor(n: int) -> Logic:
            return engine.value(c.nodes[n])

        for g in gates.cell_gates(nl):
            esperado = gates.gate_value(g, nl, valor)
            if esperado in (Logic.ZERO, Logic.ONE):
                assert esperado == valor(g.output), (nombre, combo, g.expression)


def test_tipos_de_compuerta() -> None:
    assert [g.title for g in gates.cell_gates(celda("NAND2"))] == ["NAND2"]
    assert [g.title for g in gates.cell_gates(celda("NOR2"))] == ["NOR2"]
    assert [g.title for g in gates.cell_gates(celda("XOR2"))] == ["INV", "INV", "AOI"]
    assert [g.kind for g in gates.cell_gates(celda("FA"))] == [
        "COMPLEJA",
        "COMPLEJA",
        "INV",
        "INV",
    ]
    assert [g.kind for g in gates.cell_gates(celda("MUX2"))].count("TG") == 2


def test_formulas_y_explicacion() -> None:
    nl = celda("XOR2")
    c = analyze(nl)
    (_, _, aoi) = gates.cell_gates(nl)
    assert aoi.expression == "¬(a·b + an·bn)"
    valores = {"a": Logic.ONE, "b": Logic.ZERO, "an": Logic.ZERO, "bn": Logic.ONE}

    def valor(n: int) -> Logic:
        return valores.get(c.label(n), Logic.X)

    texto = gates.explain(aoi, nl, valor)
    assert texto == "y = ¬(a·b + an·bn) = ¬(1·0 + 0·1) = 1: conduce la red pull-up (pMOS)"


def _toca(d: gates.GateDiagram, x: float, y: float, nodo: int) -> bool:
    return any(
        w.node == nodo
        and min(w.x1, w.x2) - 0.01 <= x <= max(w.x1, w.x2) + 0.01
        and min(w.y1, w.y2) - 0.01 <= y <= max(w.y1, w.y2) + 0.01
        for w in d.wires
    )


@pytest.mark.parametrize("nombre", PRIMITIVAS)
def test_cada_pin_tiene_su_cable(nombre: str) -> None:
    nl = celda(nombre)
    d = gates.layout(nl, approx_width)
    for b in d.boxes:
        for k, n in enumerate(b.gate.inputs):
            assert _toca(d, *b.pin(k), n), (nombre, b.gate.expression, k)
        if b.gate.output >= 0:
            assert _toca(d, *b.out, b.gate.output), (nombre, "salida", b.gate.expression)
    for p in d.ports:
        assert _toca(d, p.x, p.y, p.node), (nombre, p.name)


@pytest.mark.parametrize("nombre", PRIMITIVAS)
def test_ningun_cable_atraviesa_una_compuerta(nombre: str) -> None:
    d = gates.layout(celda(nombre), approx_width)
    for b in d.boxes:
        x0, x1 = b.x, b.x + b.w + 2 * gates.BUBBLE
        y0, y1 = b.y, b.y + b.h
        for w in d.wires:
            if w.y1 == w.y2:  # horizontal
                cruza = y0 < w.y1 < y1 and min(w.x1, w.x2) < x1 and max(w.x1, w.x2) > x0
            else:  # vertical
                cruza = x0 < w.x1 < x1 and min(w.y1, w.y2) < y1 and max(w.y1, w.y2) > y0
            assert not cruza, (nombre, b.gate.expression, w)


def test_mux2_une_las_dos_transmission_gates() -> None:
    """Las dos transmission gates del MUX2 manejan el mismo nodo: ambas salidas tienen cable."""
    nl = celda("MUX2")
    d = gates.layout(nl, approx_width)
    tgs = [b for b in d.boxes if b.gate.kind == "TG"]
    assert len(tgs) == 2
    assert tgs[0].gate.output == tgs[1].gate.output
    for b in tgs:
        assert _toca(d, *b.out, b.gate.output)
