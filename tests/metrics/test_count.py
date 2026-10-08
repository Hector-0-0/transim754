"""Conteo de transistores por circuito, instancia y tipo de celda."""

from __future__ import annotations

from transim.cells.combinational import inv, nand2, nor2
from transim.core import Netlist
from transim.metrics.count import UNOWNED, TransistorCount, count, count_by_cell, count_by_instance


def _circuito() -> Netlist:
    nl = Netlist("mixto")
    a, b = nl.input("a"), nl.input("b")
    u0 = nl.instantiate(nand2(), "u0", {"a": a, "b": b})
    u1 = nl.instantiate(nor2(), "u1", {"a": a, "b": b})
    u2 = nl.instantiate(inv(), "u2", {"a": u0["y"]})
    nl.instantiate(inv(), "u3", {"a": u1["y"]})
    nl.nmos(u2["y"], nl.output("y"), nl.gnd)  # transistor suelto
    return nl


def test_conteo_total() -> None:
    assert count(_circuito()) == TransistorCount(nmos=7, pmos=6)
    assert count(_circuito()).total == 13


def test_conteo_por_instancia_suma_el_total() -> None:
    nl = _circuito()
    por_instancia = count_by_instance(nl)
    assert por_instancia["u0"].total == 4
    assert por_instancia["u2"].total == 2
    assert por_instancia[UNOWNED] == TransistorCount(1, 0)
    total = sum((c for c in por_instancia.values()), TransistorCount(0, 0))
    assert total == count(nl)


def test_conteo_por_celda() -> None:
    por_celda = count_by_cell(_circuito())
    assert por_celda == {
        "INV": (2, TransistorCount(2, 2)),
        "NAND2": (1, TransistorCount(2, 2)),
        "NOR2": (1, TransistorCount(2, 2)),
    }
