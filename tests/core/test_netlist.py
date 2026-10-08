"""Pruebas del netlist jerárquico: nodos, puertos, buses e instanciación."""

from __future__ import annotations

import pytest

from core.circuitos import and2_jerarquico, inversor, inversor_de_bus, nand2
from transim.core.netlist import Netlist, NetlistError
from transim.core.node import NodeKind
from transim.core.transistor import TransistorType


def test_rieles_y_tipos_de_nodo() -> None:
    nl = nand2()
    assert nl.vdd.kind is NodeKind.VDD
    assert nl.vdd.id == 0
    assert nl.gnd.kind is NodeKind.GND
    assert nl.gnd.id == 1
    assert nl.inputs["a"].kind is NodeKind.INPUT
    assert nl.outputs["y"].kind is NodeKind.INTERNAL
    assert nl.find("n1").kind is NodeKind.INTERNAL
    assert "n1" in nl
    assert "zz" not in nl


def test_conteo_de_transistores() -> None:
    assert nand2().transistor_count() == {"nmos": 2, "pmos": 2, "total": 4}
    assert inversor().transistor_count() == {"nmos": 1, "pmos": 1, "total": 2}


def test_nombres_automaticos_unicos() -> None:
    nl = Netlist("x")
    nombres = {nl.node().name for _ in range(5)}
    assert len(nombres) == 5


def test_instanciacion_aplana_y_conserva_jerarquia() -> None:
    nl = and2_jerarquico()
    assert nl.transistor_count()["total"] == 6
    assert [i.path for i in nl.instances] == ["nand", "inv"]
    nand_inst = nl.instances[0]
    assert len(nand_inst.transistors) == 4
    assert nand_inst.is_leaf
    assert nand_inst["a"] is nl.inputs["a"]
    # el nodo interno del NAND se renombra con el camino de la instancia
    assert "nand.n1" in nl
    assert all(t.name.startswith("nand.") for t in nand_inst.transistors)


def test_jerarquia_anidada() -> None:
    top = Netlist("top")
    a, b, c = top.input("a"), top.input("b"), top.input("c")
    u0 = top.instantiate(and2_jerarquico(), "u0", {"a": a, "b": b})
    top.instantiate(and2_jerarquico(), "u1", {"a": u0["y"], "b": c, "y": top.output("y")})
    caminos = {i.path: i.parent for i in top.instances}
    assert caminos == {
        "u0.nand": "u0",
        "u0.inv": "u0",
        "u0": None,
        "u1.nand": "u1",
        "u1.inv": "u1",
        "u1": None,
    }
    assert [i.path for i in top.top_instances()] == ["u0", "u1"]
    assert len(top.leaf_instances()) == 4
    assert len(top.instances[2].transistors) == 6  # u0 incluye sus sub-instancias
    assert top.transistor_count()["total"] == 12


def test_buses() -> None:
    nl = inversor_de_bus(4)
    assert [n.name for n in nl.input_buses["a"]] == ["a[0]", "a[1]", "a[2]", "a[3]"]
    assert len(nl.output_buses["y"]) == 4
    assert nl.transistor_count()["total"] == 8


def test_conexion_por_bus() -> None:
    top = Netlist("top")
    x = top.input_bus("x", 4)
    inst = top.instantiate(inversor_de_bus(4), "u", {"a": x})
    assert inst.bus("a") == x
    assert len(inst.bus("y")) == 4


def test_transmission_gate_agrega_n_y_p() -> None:
    nl = Netlist("t")
    a, b, en, en_n = nl.input("a"), nl.node("b"), nl.input("en"), nl.input("en_n")
    n, p = nl.transmission_gate(a, b, en, en_n)
    assert n.kind is TransistorType.NMOS
    assert p.kind is TransistorType.PMOS
    assert n.gate is en
    assert p.gate is en_n


@pytest.mark.parametrize(
    "construir",
    [
        lambda nl: nl.node("VDD"),  # nombre repetido
        lambda nl: nl.instantiate(nand2(), "u", {"a": nl.input("a")}),  # falta b
        lambda nl: nl.instantiate(nand2(), "u", {"a": nl.vdd, "b": nl.vdd, "q": nl.vdd}),
        lambda nl: nl.instantiate(inversor_de_bus(4), "u", {"a": [nl.vdd] * 3}),
        lambda nl: nl.instantiate(nl, "u", {}),
        lambda nl: nl.nmos(Netlist("otro").vdd, nl.vdd, nl.gnd),
        lambda nl: nl.instantiate(inversor(), "a.b", {"a": nl.vdd}),
    ],
    ids=[
        "repetido",
        "entrada-sin-conectar",
        "puerto-desconocido",
        "ancho-bus",
        "auto-instancia",
        "nodo-ajeno",
        "nombre-con-punto",
    ],
)
def test_errores_de_construccion(construir: object) -> None:
    nl = Netlist("top")
    with pytest.raises(NetlistError):
        construir(nl)  # type: ignore[operator]


def test_instancia_repetida() -> None:
    nl = Netlist("top")
    nl.instantiate(inversor(), "u", {"a": nl.vdd})
    with pytest.raises(NetlistError, match="repetido"):
        nl.instantiate(inversor(), "u", {"a": nl.vdd})
