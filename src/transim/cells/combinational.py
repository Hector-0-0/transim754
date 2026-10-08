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


# ----------------------------------------------------------------------------
# Celdas pendientes (responsable: Jairo). Las firmas, los nombres de celda y los
# puertos son la interfaz acordada: no se cambian sin ADR.
# ----------------------------------------------------------------------------
@cache
def and2() -> Netlist:
    """AND2: y = a·b. 6 transistores (NAND2 + INV). Nombre de celda ``"AND2"``."""
    raise NotImplementedError("pendiente: #1")


@cache
def or2() -> Netlist:
    """OR2: y = a + b. 6 transistores (NOR2 + INV). Nombre de celda ``"OR2"``."""
    raise NotImplementedError("pendiente: #1")


@cache
def xor2() -> Netlist:
    """XOR2: y = a ⊕ b. 12 transistores: CMOS complementario de 8 T con ā y b̄
    generados por dos inversores internos. Nombre de celda ``"XOR2"``."""
    raise NotImplementedError("pendiente: #2")


@cache
def xnor2() -> Netlist:
    """XNOR2: y = ¬(a ⊕ b). 12 transistores, misma estructura que XOR2.
    Nombre de celda ``"XNOR2"``."""
    raise NotImplementedError("pendiente: #2")


@cache
def mux2() -> Netlist:
    """MUX2 restaurador: y = a si s = 0, y = b si s = 1. 12 transistores.

    Estructura (ADR-0008, regla de biblioteca): un INV en cada entrada de datos, dos
    transmission gates controladas por s y s̄ (s̄ generado por un INV interno) y un INV
    de salida. Las entradas solo llegan a compuertas y la salida es restaurada.
    Puertos: entradas ``a``, ``b``, ``s``; salida ``y``. Nombre de celda ``"MUX2"``.
    """
    raise NotImplementedError("pendiente: #3")


@cache
def half_adder() -> Netlist:
    """Medio sumador: s = a ⊕ b, cout = a·b. 18 transistores (XOR2 + AND2).

    Puertos: entradas ``a``, ``b``; salidas ``s``, ``cout``. Nombre de celda ``"HA"``.
    """
    raise NotImplementedError("pendiente: #4")


@cache
def full_adder() -> Netlist:
    """Sumador completo espejo (mirror adder) de 28 transistores (Weste y Harris, 2011).

    Etapa de acarreo espejo (10 T) que produce c̄out, etapa de suma espejo (14 T) que
    produce s̄, y dos inversores de salida (4 T). Celda primitiva: transistores
    colocados directamente, sin sub-instancias, para que el motor cached la tabule.
    Puertos: entradas ``a``, ``b``, ``cin``; salidas ``s``, ``cout``.
    Nombre de celda ``"FA"``.
    """
    raise NotImplementedError("pendiente: #4")
