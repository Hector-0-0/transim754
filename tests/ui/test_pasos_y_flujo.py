"""Pasos de una celda (esquema paso a paso) y diagrama de flujo de datos de una operación."""

from __future__ import annotations

from transim.cells.library import CELLS
from transim.fpu.format import BINARY32
from transim.ui.gui.flow import graph
from transim.ui.gui.model import unit_for
from transim.ui.gui.steps import cell_steps


def test_pasos_de_xor2_van_en_orden_de_dependencia() -> None:
    nl = CELLS["XOR2"]
    nl = nl() if callable(nl) else nl
    steps = cell_steps(nl)
    labels = [s.label for s in steps]
    # Las entradas invertidas (an, bn) se calculan antes de la salida y.
    assert labels.index("an") < labels.index("y")
    assert labels.index("bn") < labels.index("y")
    assert steps[-1].label == "y"
    # Cada transistor pertenece a exactamente un paso.
    todos = [t for s in steps for t in s.transistors]
    assert len(todos) == len(set(todos))


def test_inversor_tiene_un_solo_paso() -> None:
    nl = CELLS["INV"]
    nl = nl() if callable(nl) else nl
    assert [s.label for s in cell_steps(nl)] == ["y"]


def test_flujo_del_sumador_sigue_el_datapath() -> None:
    g = graph(unit_for(BINARY32, "add", "cached").netlist)
    nombres = {b.path: k for k, b in enumerate(g.blocks)}
    pares = {(g.blocks[link.src].path, g.blocks[link.dst].path) for link in g.links}
    assert ("unpack_a", "order") in pares
    assert ("order", "mant_addsub") in pares
    assert ("mant_addsub", "normalize") in pares
    # Las columnas siguen el sentido del flujo: cada destino está a la derecha de su origen.
    for link in g.links:
        assert g.ranks[link.dst] > g.ranks[link.src]
    assert g.ranks[nombres["order"]] > g.ranks[nombres["unpack_a"]]
