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


# ----------------------------------------------------------------------------
# Celdas pendientes (responsable: Jairo). Las firmas, los nombres de celda y los
# puertos son la interfaz acordada: no se cambian sin ADR.
# ----------------------------------------------------------------------------
@cache
def and2() -> Netlist:
    """AND2: y = a·b. 6 transistores (NAND2 + INV). Nombre de celda ``"AND2"``.

    Una etapa CMOS estática solo produce funciones invertidas, así que la AND se arma
    con una NAND2 (``u_nand``) cuya salida ``ny`` = ¬(a·b) maneja un INV (``u_inv``).
    Las entradas solo llegan a compuertas de la NAND2 y la salida la restaura el INV.
    """
    nl = Netlist("AND2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    ny = nl.node("ny")
    nl.instantiate(nand2(), "u_nand", {"a": a, "b": b, "y": ny})
    nl.instantiate(inv(), "u_inv", {"a": ny, "y": y})
    return nl


@cache
def or2() -> Netlist:
    """OR2: y = a + b. 6 transistores (NOR2 + INV). Nombre de celda ``"OR2"``.

    Misma idea que AND2: una NOR2 (``u_nor``) produce ``ny`` = ¬(a + b) y un INV
    (``u_inv``) la invierte y restaura.
    """
    nl = Netlist("OR2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    ny = nl.node("ny")
    nl.instantiate(nor2(), "u_nor", {"a": a, "b": b, "y": ny})
    nl.instantiate(inv(), "u_inv", {"a": ny, "y": y})
    return nl


def _inversores_de_entrada(nl: Netlist, a: Node, b: Node) -> tuple[Node, Node]:
    """Coloca dos inversores (4 T) que generan ``an`` = ¬a y ``bn`` = ¬b dentro de ``nl``.

    Se colocan como transistores, no como instancias, para que la celda que los usa
    siga siendo primitiva y el motor cached la tabule entera.
    """
    an, bn = nl.node("an"), nl.node("bn")
    nl.pmos(a, nl.vdd, an, "pia")
    nl.nmos(a, an, nl.gnd, "nia")
    nl.pmos(b, nl.vdd, bn, "pib")
    nl.nmos(b, bn, nl.gnd, "nib")
    return an, bn


@cache
def xor2() -> Netlist:
    """XOR2: y = a ⊕ b. 12 transistores: CMOS complementario de 8 T con ā y b̄
    generados por dos inversores internos. Nombre de celda ``"XOR2"``.

    Celda primitiva (transistores colocados directamente):

    - Inversores de entrada (4 T): ``an`` = ¬a, ``bn`` = ¬b.
    - Pull-down (4 nMOS), conduce cuando y = 0, es decir con a·b + ā·b̄:
      (``na`` serie ``nb``) ∥ (``nan`` serie ``nbn``), nodos intermedios ``n1``, ``n2``.
    - Pull-up (4 pMOS), la dual: (``pa`` ∥ ``pb``) serie (``pan`` ∥ ``pbn``), nodo
      intermedio ``p1``; conduce con (ā + b̄)·(a + b) = a ⊕ b.
    """
    nl = Netlist("XOR2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    an, bn = _inversores_de_entrada(nl, a, b)
    p1 = nl.node("p1")
    nl.pmos(a, nl.vdd, p1, "pa")
    nl.pmos(b, nl.vdd, p1, "pb")
    nl.pmos(an, p1, y, "pan")
    nl.pmos(bn, p1, y, "pbn")
    n1, n2 = nl.node("n1"), nl.node("n2")
    nl.nmos(a, y, n1, "na")
    nl.nmos(b, n1, nl.gnd, "nb")
    nl.nmos(an, y, n2, "nan")
    nl.nmos(bn, n2, nl.gnd, "nbn")
    return nl


@cache
def xnor2() -> Netlist:
    """XNOR2: y = ¬(a ⊕ b). 12 transistores, misma estructura que XOR2.
    Nombre de celda ``"XNOR2"``.

    Igual que XOR2 pero con los complementos cruzados en cada rama:

    - Pull-down, conduce cuando y = 0, es decir con a·b̄ + ā·b:
      (``na`` serie ``nbn``) ∥ (``nan`` serie ``nb``).
    - Pull-up: (``pa`` ∥ ``pbn``) serie (``pan`` ∥ ``pb``); conduce con
      (ā + b)·(a + b̄) = ¬(a ⊕ b).
    """
    nl = Netlist("XNOR2")
    a, b, y = nl.input("a"), nl.input("b"), nl.output("y")
    an, bn = _inversores_de_entrada(nl, a, b)
    p1 = nl.node("p1")
    nl.pmos(a, nl.vdd, p1, "pa")
    nl.pmos(bn, nl.vdd, p1, "pbn")
    nl.pmos(an, p1, y, "pan")
    nl.pmos(b, p1, y, "pb")
    n1, n2 = nl.node("n1"), nl.node("n2")
    nl.nmos(a, y, n1, "na")
    nl.nmos(bn, n1, nl.gnd, "nbn")
    nl.nmos(an, y, n2, "nan")
    nl.nmos(b, n2, nl.gnd, "nb")
    return nl


@cache
def mux2() -> Netlist:
    """MUX2 restaurador: y = a si s = 0, y = b si s = 1. 12 transistores.

    Estructura (ADR-0008, regla de biblioteca): un INV en cada entrada de datos, dos
    transmission gates controladas por s y s̄ (s̄ generado por un INV interno) y un INV
    de salida. Las entradas solo llegan a compuertas y la salida es restaurada.
    Puertos: entradas ``a``, ``b``, ``s``; salida ``y``. Nombre de celda ``"MUX2"``.

    Celda primitiva, en cuatro partes:

    - INV de datos (4 T): ``an`` = ¬a, ``bn`` = ¬b. Aíslan a ``a`` y ``b`` del canal de
      las TG (regla 1).
    - INV de selección (2 T): ``sn`` = ¬s.
    - TG (4 T): ``tg0`` une ``an`` con ``m`` cuando s = 0 (nMOS con ``sn``, pMOS con
      ``s``); ``tg1`` une ``bn`` con ``m`` cuando s = 1. Siempre conduce exactamente una.
    - INV de salida (2 T): y = ¬m. Deshace la inversión de los datos y restaura el nivel
      (regla 2), de modo que encadenar MUX2 no acumula TG en serie.
    """
    nl = Netlist("MUX2")
    a, b, s = nl.input("a"), nl.input("b"), nl.input("s")
    y = nl.output("y")
    an, bn = _inversores_de_entrada(nl, a, b)
    sn = nl.node("sn")
    nl.pmos(s, nl.vdd, sn, "pis")
    nl.nmos(s, sn, nl.gnd, "nis")
    m = nl.node("m")
    nl.transmission_gate(an, m, enable=sn, enable_n=s, name="tg0")
    nl.transmission_gate(bn, m, enable=s, enable_n=sn, name="tg1")
    nl.pmos(m, nl.vdd, y, "po")
    nl.nmos(m, y, nl.gnd, "no")
    return nl


@cache
def half_adder() -> Netlist:
    """Medio sumador: s = a ⊕ b, cout = a·b. 18 transistores (XOR2 + AND2).

    Puertos: entradas ``a``, ``b``; salidas ``s``, ``cout``. Nombre de celda ``"HA"``.

    Se compone instanciando las celdas ya probadas: ``u_xor`` (XOR2) produce la suma y
    ``u_and`` (AND2) el acarreo. Ambas reciben ``a`` y ``b`` solo en compuertas.
    """
    nl = Netlist("HA")
    a, b = nl.input("a"), nl.input("b")
    s, cout = nl.output("s"), nl.output("cout")
    nl.instantiate(xor2(), "u_xor", {"a": a, "b": b, "y": s})
    nl.instantiate(and2(), "u_and", {"a": a, "b": b, "y": cout})
    return nl


@cache
def full_adder() -> Netlist:
    """Sumador completo espejo (mirror adder) de 28 transistores (Weste y Harris, 2011).

    Etapa de acarreo espejo (10 T) que produce c̄out, etapa de suma espejo (14 T) que
    produce s̄, y dos inversores de salida (4 T). Celda primitiva: transistores
    colocados directamente, sin sub-instancias, para que el motor cached la tabule.
    Puertos: entradas ``a``, ``b``, ``cin``; salidas ``s``, ``cout``.
    Nombre de celda ``"FA"``.

    - Acarreo (10 T), nodo ``cout_n`` = ¬(a·b + cin·(a + b)). Pull-down:
      (``na1`` serie ``nb1``) ∥ (``nc1`` serie (``na2`` ∥ ``nb2``)); pull-up con la misma
      topología (``pa1``…``pb2``). Sirve la misma topología arriba y abajo porque la
      mayoría es autodual: ¬M(a, b, c) = M(ā, b̄, c̄).
    - Suma (14 T), nodo ``s_n`` = ¬(a·b·cin + cout_n·(a + b + cin)). Pull-down:
      (``na3`` serie ``nb3`` serie ``nc3``) ∥ (``nco`` serie (``na4`` ∥ ``nb4`` ∥ ``nc4``));
      pull-up espejo. ``cout_n`` vale 1 justo cuando hay a lo sumo un 1 en las entradas,
      así que el segundo término cubre el caso "exactamente un 1" y el primero "tres 1".
    - Inversores de salida (4 T): s = ¬s_n, cout = ¬cout_n.
    """
    nl = Netlist("FA")
    a, b, c = nl.input("a"), nl.input("b"), nl.input("cin")
    s, cout = nl.output("s"), nl.output("cout")
    vdd, gnd = nl.vdd, nl.gnd

    # Etapa de acarreo espejo -> cout_n
    cout_n = nl.node("cout_n")
    x1, x2 = nl.node("x1"), nl.node("x2")
    nl.nmos(a, cout_n, x1, "na1")
    nl.nmos(b, x1, gnd, "nb1")
    nl.nmos(c, cout_n, x2, "nc1")
    nl.nmos(a, x2, gnd, "na2")
    nl.nmos(b, x2, gnd, "nb2")
    y1, y2 = nl.node("y1"), nl.node("y2")
    nl.pmos(a, cout_n, y1, "pa1")
    nl.pmos(b, y1, vdd, "pb1")
    nl.pmos(c, cout_n, y2, "pc1")
    nl.pmos(a, y2, vdd, "pa2")
    nl.pmos(b, y2, vdd, "pb2")

    # Etapa de suma espejo -> s_n
    s_n = nl.node("s_n")
    x3, x4, x5 = nl.node("x3"), nl.node("x4"), nl.node("x5")
    nl.nmos(a, s_n, x3, "na3")
    nl.nmos(b, x3, x4, "nb3")
    nl.nmos(c, x4, gnd, "nc3")
    nl.nmos(cout_n, s_n, x5, "nco")
    nl.nmos(a, x5, gnd, "na4")
    nl.nmos(b, x5, gnd, "nb4")
    nl.nmos(c, x5, gnd, "nc4")
    y3, y4, y5 = nl.node("y3"), nl.node("y4"), nl.node("y5")
    nl.pmos(a, s_n, y3, "pa3")
    nl.pmos(b, y3, y4, "pb3")
    nl.pmos(c, y4, vdd, "pc3")
    nl.pmos(cout_n, s_n, y5, "pco")
    nl.pmos(a, y5, vdd, "pa4")
    nl.pmos(b, y5, vdd, "pb4")
    nl.pmos(c, y5, vdd, "pc4")

    # Inversores de salida
    nl.pmos(s_n, vdd, s, "ps")
    nl.nmos(s_n, s, gnd, "ns")
    nl.pmos(cout_n, vdd, cout, "pcout")
    nl.nmos(cout_n, cout, gnd, "ncout")
    return nl
