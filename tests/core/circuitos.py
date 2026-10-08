"""Circuitos de prueba del núcleo L0 construidos directamente con transistores.

Son independientes de la biblioteca de celdas (L1): las pruebas del núcleo no deben
depender de capas superiores.
"""

from __future__ import annotations

from transim.core.netlist import Netlist


def inversor() -> Netlist:
    """INV: a → y (2 transistores)."""
    nl = Netlist("inv")
    a, y = nl.input("a"), nl.output("y")
    nl.pmos(a, nl.vdd, y)
    nl.nmos(a, y, nl.gnd)
    return nl


def nand2() -> Netlist:
    """NAND2: pMOS en paralelo, nMOS en serie (4 transistores)."""
    nl = Netlist("nand2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    nl.pmos(a, nl.vdd, y)
    nl.pmos(b, nl.vdd, y)
    n1 = nl.node("n1")
    nl.nmos(a, y, n1)
    nl.nmos(b, n1, nl.gnd)
    return nl


def nor2() -> Netlist:
    """NOR2: pMOS en serie, nMOS en paralelo (4 transistores)."""
    nl = Netlist("nor2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    p1 = nl.node("p1")
    nl.pmos(a, nl.vdd, p1)
    nl.pmos(b, p1, y)
    nl.nmos(a, y, nl.gnd)
    nl.nmos(b, y, nl.gnd)
    return nl


def compuerta_de_transmision() -> Netlist:
    """Transmission gate de d a q, con habilitación en y su complemento en_n.

    q no tiene otra fuente: cuando la TG se abre, q retiene su carga.
    """
    nl = Netlist("tg")
    d, en, en_n = nl.input("d"), nl.input("en"), nl.input("en_n")
    q = nl.output("q")
    nl.transmission_gate(d, q, en, en_n)
    return nl


def and2_jerarquico() -> Netlist:
    """AND2 = NAND2 + INV, construido instanciando subcircuitos (6 transistores)."""
    nl = Netlist("and2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    u_nand = nl.instantiate(nand2(), "nand", {"a": a, "b": b})
    nl.instantiate(inversor(), "inv", {"a": u_nand["y"], "y": y})
    return nl


def anillo_oscilador() -> Netlist:
    """Anillo NAND2 + 2 INV: estable con en = 0; oscila con en = 1."""
    nl = Netlist("anillo")
    en = nl.input("en")
    x0, x1, x2 = nl.node("x0"), nl.node("x1"), nl.node("x2")
    nl.instantiate(nand2(), "g0", {"a": en, "b": x2, "y": x0})
    nl.instantiate(inversor(), "g1", {"a": x0, "y": x1})
    nl.instantiate(inversor(), "g2", {"a": x1, "y": x2})
    return nl


def inversores_en_conflicto() -> Netlist:
    """Dos inversores con la salida unida: con entradas distintas hay cortocircuito."""
    nl = Netlist("conflicto")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    nl.instantiate(inversor(), "i0", {"a": a, "y": y})
    nl.instantiate(inversor(), "i1", {"a": b, "y": y})
    return nl


def inversor_de_bus(ancho: int) -> Netlist:
    """Inversor bit a bit de un bus: y[i] = ¬a[i]."""
    nl = Netlist(f"inv_bus{ancho}")
    a = nl.input_bus("a", ancho)
    y = nl.output_bus("y", ancho)
    for i in range(ancho):
        nl.instantiate(inversor(), f"u{i}", {"a": a[i], "y": y[i]})
    return nl
