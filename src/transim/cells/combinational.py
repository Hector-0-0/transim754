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
