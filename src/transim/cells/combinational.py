"""Celdas combinacionales CMOS estáticas (capa L1).

Convenciones de toda la biblioteca:

- Entradas ``a``, ``b``, ``c`` (o ``s`` para selección, ``cin`` para acarreo); salida
  ``y`` (o ``s``/``cout`` en sumadores).
- **Entradas de alta impedancia:** cada entrada solo llega a compuertas de transistores
  (nunca a un canal). **Salidas restauradas:** cada salida la maneja una red CMOS hacia
  los rieles. Estas dos reglas hacen a la celda componible y tabulable por el motor
  ``cached`` (ADR-0008).
- Cada constructor devuelve **siempre el mismo objeto** :class:`Netlist` (se construye
  una vez); no debe modificarse. Para usarlo se instancia con ``Netlist.instantiate``.
"""

from __future__ import annotations

from functools import cache

from transim.core.netlist import Netlist
from transim.core.node import Node


@cache
def inv() -> Netlist:
    """Inversor CMOS: y = ¬a. 2 transistores (1 pMOS + 1 nMOS)."""
    nl = Netlist("INV")
    a, y = nl.input("a"), nl.output("y")
    nl.pmos(a, nl.vdd, y, "p")
    nl.nmos(a, y, nl.gnd, "n")
    return nl


@cache
def nand2() -> Netlist:
    """NAND de dos entradas: y = ¬(a·b). 4 transistores.

    Red pull-up: dos pMOS en paralelo. Red pull-down: dos nMOS en serie con el nodo
    intermedio ``n1``.
    """
    nl = Netlist("NAND2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    nl.pmos(a, nl.vdd, y, "pa")
    nl.pmos(b, nl.vdd, y, "pb")
    n1 = nl.node("n1")
    nl.nmos(a, y, n1, "na")
    nl.nmos(b, n1, nl.gnd, "nb")
    return nl


@cache
def nor2() -> Netlist:
    """NOR de dos entradas: y = ¬(a + b). 4 transistores.

    Red pull-up: dos pMOS en serie con el nodo intermedio ``p1``. Red pull-down: dos
    nMOS en paralelo.
    """
    nl = Netlist("NOR2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    p1 = nl.node("p1")
    nl.pmos(a, nl.vdd, p1, "pa")
    nl.pmos(b, p1, y, "pb")
    nl.nmos(a, y, nl.gnd, "na")
    nl.nmos(b, y, nl.gnd, "nb")
    return nl


@cache
def and2() -> Netlist:
    """AND2: y = a·b. 6 transistores (NAND2 + INV). Nombre de celda ``"AND2"``.

    Se colocan los transistores directamente (sin sub-instancias): el nodo ``yn`` es la
    salida de la NAND interna.
    """
    nl = Netlist("AND2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    yn, n1 = nl.node("yn"), nl.node("n1")
    nl.pmos(a, nl.vdd, yn, "pa")
    nl.pmos(b, nl.vdd, yn, "pb")
    nl.nmos(a, yn, n1, "na")
    nl.nmos(b, n1, nl.gnd, "nb")
    _inverter(nl, yn, y, "inv")
    return nl


@cache
def or2() -> Netlist:
    """OR2: y = a + b. 6 transistores (NOR2 + INV). Nombre de celda ``"OR2"``."""
    nl = Netlist("OR2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    yn, p1 = nl.node("yn"), nl.node("p1")
    nl.pmos(a, nl.vdd, p1, "pa")
    nl.pmos(b, p1, yn, "pb")
    nl.nmos(a, yn, nl.gnd, "na")
    nl.nmos(b, yn, nl.gnd, "nb")
    _inverter(nl, yn, y, "inv")
    return nl


@cache
def xor2() -> Netlist:
    """XOR2: y = a ⊕ b. 12 transistores: CMOS complementario de 8 T con ā y b̄
    generados por dos inversores internos. Nombre de celda ``"XOR2"``.

    Pull-down (y = 0 si a = b): ramas en serie (a, b) y (ā, b̄). Pull-up (y = 1 si
    a ≠ b): ramas en serie (ā, b) y (a, b̄) con pMOS.
    """
    return _xor_like("XOR2", invert=False)


@cache
def xnor2() -> Netlist:
    """XNOR2: y = ¬(a ⊕ b). 12 transistores, misma estructura que XOR2.
    Nombre de celda ``"XNOR2"``."""
    return _xor_like("XNOR2", invert=True)


@cache
def mux2() -> Netlist:
    """MUX2 restaurador: y = a si s = 0, y = b si s = 1. 12 transistores.

    Estructura (ADR-0008, regla de biblioteca): un INV en cada entrada de datos, dos
    transmission gates controladas por s y s̄ (s̄ generado por un INV interno) y un INV
    de salida. Las entradas solo llegan a compuertas y la salida es restaurada.
    Puertos: entradas ``a``, ``b``, ``s``; salida ``y``. Nombre de celda ``"MUX2"``.
    """
    nl = Netlist("MUX2")
    a, b, s, y = nl.input("a"), nl.input("b"), nl.input("s"), nl.output("y")
    an, bn, sn, m = nl.node("an"), nl.node("bn"), nl.node("sn"), nl.node("m")
    _inverter(nl, a, an, "inv_a")
    _inverter(nl, b, bn, "inv_b")
    _inverter(nl, s, sn, "inv_s")
    nl.transmission_gate(an, m, sn, s, "tg_a")
    nl.transmission_gate(bn, m, s, sn, "tg_b")
    _inverter(nl, m, y, "inv_y")
    return nl


@cache
def half_adder() -> Netlist:
    """Medio sumador: s = a ⊕ b, cout = a·b. 18 transistores (XOR2 + AND2).

    Puertos: entradas ``a``, ``b``; salidas ``s``, ``cout``. Nombre de celda ``"HA"``.
    """
    nl = Netlist("HA")
    a, b = nl.input("a"), nl.input("b")
    s, cout = nl.output("s"), nl.output("cout")
    nl.instantiate(xor2(), "xor", {"a": a, "b": b, "y": s})
    nl.instantiate(and2(), "and", {"a": a, "b": b, "y": cout})
    return nl


@cache
def full_adder() -> Netlist:
    """Sumador completo espejo (mirror adder) de 28 transistores (Weste y Harris, 2011).

    Etapa de acarreo espejo (10 T) que produce c̄out, etapa de suma espejo (14 T) que
    produce s̄, y dos inversores de salida (4 T). Celda primitiva: transistores
    colocados directamente, sin sub-instancias, para que el motor cached la tabule.
    Puertos: entradas ``a``, ``b``, ``cin``; salidas ``s``, ``cout``.
    Nombre de celda ``"FA"``.
    """
    nl = Netlist("FA")
    a, b, cin = nl.input("a"), nl.input("b"), nl.input("cin")
    s, cout = nl.output("s"), nl.output("cout")
    coutn, sn = nl.node("coutn"), nl.node("sn")

    # Acarreo: c̄out = ¬(a·b + cin·(a + b)); la red pull-up es el espejo de la pull-down.
    n1, n2 = nl.node("cn1"), nl.node("cn2")
    nl.nmos(a, coutn, n1, "c_na1")
    nl.nmos(b, n1, nl.gnd, "c_nb1")
    nl.nmos(cin, coutn, n2, "c_nc")
    nl.nmos(a, n2, nl.gnd, "c_na2")
    nl.nmos(b, n2, nl.gnd, "c_nb2")
    p1, p2 = nl.node("cp1"), nl.node("cp2")
    nl.pmos(a, nl.vdd, p1, "c_pa1")
    nl.pmos(b, p1, coutn, "c_pb1")
    nl.pmos(cin, coutn, p2, "c_pc")
    nl.pmos(a, p2, nl.vdd, "c_pa2")
    nl.pmos(b, p2, nl.vdd, "c_pb2")

    # Suma: s̄ = ¬(a·b·cin + c̄out·(a + b + cin)).
    n3, n4, n5 = nl.node("sn1"), nl.node("sn2"), nl.node("sn3")
    nl.nmos(coutn, sn, n3, "s_nco")
    for g, name in ((a, "s_na1"), (b, "s_nb1"), (cin, "s_nc1")):
        nl.nmos(g, n3, nl.gnd, name)
    nl.nmos(a, sn, n4, "s_na2")
    nl.nmos(b, n4, n5, "s_nb2")
    nl.nmos(cin, n5, nl.gnd, "s_nc2")
    p3, p4, p5 = nl.node("sp1"), nl.node("sp2"), nl.node("sp3")
    nl.pmos(coutn, p3, sn, "s_pco")
    for g, name in ((a, "s_pa1"), (b, "s_pb1"), (cin, "s_pc1")):
        nl.pmos(g, nl.vdd, p3, name)
    nl.pmos(a, nl.vdd, p4, "s_pa2")
    nl.pmos(b, p4, p5, "s_pb2")
    nl.pmos(cin, p5, sn, "s_pc2")

    _inverter(nl, coutn, cout, "inv_c")
    _inverter(nl, sn, s, "inv_s")
    return nl


def _inverter(nl: Netlist, a: Node, y: Node, name: str) -> None:
    """Coloca un inversor (2 T) de ``a`` a ``y`` dentro de ``nl``."""
    nl.pmos(a, nl.vdd, y, f"{name}.p")
    nl.nmos(a, y, nl.gnd, f"{name}.n")


def _xor_like(name: str, *, invert: bool) -> Netlist:
    """XOR2 (``invert=False``) o XNOR2 (``invert=True``) complementario de 12 T."""
    nl = Netlist(name)
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    an, bn = nl.node("an"), nl.node("bn")
    _inverter(nl, a, an, "inv_a")
    _inverter(nl, b, bn, "inv_b")
    # Pares de compuertas en serie: los de "iguales" (a = b) y los de "distintos".
    equal = ((a, b), (an, bn))
    different = ((a, bn), (an, b))
    pull_down = different if invert else equal
    # Un pMOS conduce con compuerta en 0: la rama (x̄, ȳ) del pull-up conduce si x = y = 1.
    pull_up = equal if invert else different
    for i, (g1, g2) in enumerate(pull_down):
        mid = nl.node(f"n{i}")
        nl.nmos(g1, y, mid, f"n{i}a")
        nl.nmos(g2, mid, nl.gnd, f"n{i}b")
    for i, (g1, g2) in enumerate(pull_up):
        mid = nl.node(f"p{i}")
        nl.pmos(g1, nl.vdd, mid, f"p{i}a")
        nl.pmos(g2, mid, y, f"p{i}b")
    return nl
