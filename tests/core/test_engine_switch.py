"""Pruebas del motor switch-level exacto (ADR-0007)."""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.circuitos import (
    and2_jerarquico,
    anillo_oscilador,
    compuerta_de_transmision,
    inversor,
    inversor_de_bus,
    inversores_en_conflicto,
    nand2,
    nor2,
)
from transim.core import (
    Conduction,
    Logic,
    Netlist,
    OscillationError,
    ShortCircuitWarning,
    Strength,
    SwitchEngine,
)

pytestmark = pytest.mark.switch

L0, L1, X, Z = Logic.ZERO, Logic.ONE, Logic.X, Logic.Z


# ------------------------------------------------------------ tablas de verdad
def test_estado_inicial_es_x() -> None:
    sim = SwitchEngine(inversor())
    assert sim.read("a") is X
    assert sim.read("y") is X


@pytest.mark.parametrize(("a", "y"), [(0, L1), (1, L0)])
def test_inversor(a: int, y: Logic) -> None:
    sim = SwitchEngine(inversor())
    sim.set_inputs({"a": a})
    assert sim.read("y") is y
    assert sim.strength(sim.netlist.outputs["y"]) is Strength.SUPPLY


@pytest.mark.parametrize(
    ("construir", "funcion"),
    [
        (nand2, lambda a, b: 1 - (a & b)),
        (nor2, lambda a, b: 1 - (a | b)),
        (and2_jerarquico, lambda a, b: a & b),
    ],
    ids=["nand2", "nor2", "and2-jerarquico"],
)
def test_tabla_de_verdad_exhaustiva(construir: object, funcion: object) -> None:
    sim = SwitchEngine(construir())  # type: ignore[operator]
    for a, b in itertools.product((0, 1), repeat=2):
        sim.set_inputs({"a": a, "b": b})
        assert sim.read("y") is Logic(funcion(a, b)), (a, b)  # type: ignore[operator]


def test_bus_entero() -> None:
    sim = SwitchEngine(inversor_de_bus(4))
    for valor in range(16):
        sim.set_inputs({"a": valor})
        assert sim.read_int("y") == (~valor) & 0xF
    assert sim.read_int("a") == 15
    sim.set_inputs({"a": [1, 0, "X", 1]})
    assert sim.read_bus("y") == [L0, L1, X, L0]
    assert sim.read_int("y") is None


# ------------------------------------------------------- transmission gate
def test_transmission_gate_transmite_0_y_1() -> None:
    sim = SwitchEngine(compuerta_de_transmision())
    for d in (0, 1):
        sim.set_inputs({"d": d, "en": 1, "en_n": 0})
        assert sim.read("q") is Logic(d)
        assert sim.strength(sim.netlist.outputs["q"]) is Strength.DRIVEN


def test_transmission_gate_media_conduce() -> None:
    """Solo el nMOS (o solo el pMOS) encendido también conecta: interruptor ideal."""
    sim = SwitchEngine(compuerta_de_transmision())
    sim.set_inputs({"d": 1, "en": 1, "en_n": 1})
    assert sim.read("q") is L1
    sim.set_inputs({"d": 0, "en": 0, "en_n": 0})
    assert sim.read("q") is L0


# ------------------------------------------------------ almacenamiento de carga
def test_nodo_flotante_retiene_carga() -> None:
    sim = SwitchEngine(compuerta_de_transmision())
    sim.set_inputs({"d": 1, "en": 1, "en_n": 0})
    sim.set_inputs({"en": 0, "en_n": 1})  # se abre la TG: q queda aislado
    sim.set_inputs({"d": 0})
    assert sim.read("q") is L1
    assert sim.strength(sim.netlist.outputs["q"]) is Strength.CHARGE
    sim.set_inputs({"en": 1, "en_n": 0})  # al cerrarla, la entrada vuelve a mandar
    assert sim.read("q") is L0


def test_nodo_interno_de_la_pila_retiene_carga() -> None:
    sim = SwitchEngine(nand2())
    sim.set_inputs({"a": 0, "b": 1})  # n1 conectado a GND
    assert sim.read("n1") is L0
    sim.set_inputs({"b": 0})  # n1 aislado (ambos nMOS cortados)
    assert sim.read("n1") is L0
    assert sim.strength(sim.netlist.find("n1")) is Strength.CHARGE
    sim.set_inputs({"a": 1})  # n1 conectado a Y = 1
    assert sim.read("n1") is L1


def test_reparto_de_carga_distinta_da_x() -> None:
    nl = Netlist("reparto")
    d0, d1, en, en_n, s, s_n = (nl.input(n) for n in ("d0", "d1", "en", "en_n", "s", "s_n"))
    q0, q1 = nl.output("q0"), nl.output("q1")
    nl.transmission_gate(d0, q0, en, en_n)
    nl.transmission_gate(d1, q1, en, en_n)
    nl.transmission_gate(q0, q1, s, s_n)
    sim = SwitchEngine(nl)
    sim.set_inputs({"d0": 0, "d1": 1, "en": 1, "en_n": 0, "s": 0, "s_n": 1})
    sim.set_inputs({"en": 0, "en_n": 1})  # q0 = 0 y q1 = 1 retenidos
    assert (sim.read("q0"), sim.read("q1")) == (L0, L1)
    sim.set_inputs({"s": 1, "s_n": 0})  # se unen dos cargas distintas
    assert (sim.read("q0"), sim.read("q1")) == (X, X)


def test_nodo_sin_conexiones_queda_en_x() -> None:
    nl = Netlist("suelto")
    nl.input("a")
    nl.output("y")
    sim = SwitchEngine(nl)
    sim.set_inputs({"a": 1})
    assert sim.read("y") is X


# -------------------------------------------------------------- cortocircuito
def test_cortocircuito_produce_x_y_advertencia() -> None:
    sim = SwitchEngine(inversores_en_conflicto())
    sim.set_inputs({"a": 0, "b": 0})
    assert sim.read("y") is L1
    with pytest.warns(ShortCircuitWarning, match="y"):
        sim.set_inputs({"b": 1})
    assert sim.read("y") is X
    assert sim.short_circuits
    assert "y" in sim.short_circuits[-1]


# ----------------------------------------------------------------- oscilación
def test_anillo_estable_con_enable_en_cero() -> None:
    sim = SwitchEngine(anillo_oscilador())
    sim.set_inputs({"en": 0})
    assert (sim.read("x0"), sim.read("x1"), sim.read("x2")) == (L1, L0, L1)


def test_anillo_de_tres_inversores_lanza_oscillation_error() -> None:
    sim = SwitchEngine(anillo_oscilador(), max_events=500)
    sim.set_inputs({"en": 0})
    with pytest.raises(OscillationError, match="500 eventos"):
        sim.set_inputs({"en": 1})


# ------------------------------------------------------------ propagación de X
@pytest.mark.parametrize(
    ("construir", "a", "b", "esperado"),
    [
        (nand2, 0, "X", L1),  # el 0 decide: la X no se propaga
        (nand2, 1, "X", X),
        (nor2, 1, "X", L0),
        (nor2, 0, "X", X),
        (and2_jerarquico, 0, "X", L0),
        (and2_jerarquico, 1, "X", X),
    ],
)
def test_propagacion_de_x(construir: object, a: int, b: str, esperado: Logic) -> None:
    sim = SwitchEngine(construir())  # type: ignore[operator]
    sim.set_inputs({"a": a, "b": b})
    assert sim.read("y") is esperado


def test_inversor_con_entrada_x_o_z() -> None:
    sim = SwitchEngine(inversor())
    sim.set_inputs({"a": 1})
    for valor in ("X", "Z"):
        sim.set_inputs({"a": valor})
        assert sim.read("y") is X
        assert all(sim.conduction(t) is Conduction.UNKNOWN for t in sim.netlist.transistors)


# -------------------------------------------------------------- actividad
def test_conteo_de_conmutaciones_y_eventos() -> None:
    sim = SwitchEngine(inversor())
    y = sim.netlist.outputs["y"].id
    sim.set_inputs({"a": 0})  # primera definición desde X: no es conmutación
    assert sim.node_toggles[y] == 0
    assert sim.transistor_events == [0, 0]
    sim.set_inputs({"a": 1})
    sim.set_inputs({"a": 0})
    sim.set_inputs({"a": 0})  # sin cambio: no cuenta
    assert sim.node_toggles[y] == 2
    assert sim.transistor_events == [2, 2]
    stats = sim.stats()
    assert stats.node_toggles == 4  # 2 de la entrada a + 2 de la salida y
    assert stats.transistor_events == 4
    sim.reset_counters()
    assert sim.stats().node_toggles == 0
    assert sim.read("y") is L1  # el estado no se altera


def test_paso_por_x_cuenta_una_conmutacion() -> None:
    sim = SwitchEngine(inversor())
    y = sim.netlist.outputs["y"].id
    sim.set_inputs({"a": 0})
    sim.set_inputs({"a": "X"})
    sim.set_inputs({"a": 1})  # 1 → X → 0 en y: una conmutación
    assert sim.node_toggles[y] == 1


def test_nodo_interno_conmuta() -> None:
    sim = SwitchEngine(nand2())
    n1 = sim.netlist.find("n1").id
    sim.set_inputs({"a": 0, "b": 1})
    sim.set_inputs({"a": 1})
    assert sim.node_toggles[n1] == 0  # n1 sigue en 0 (conectado a GND por b)
    sim.set_inputs({"b": 0})
    assert sim.node_toggles[n1] == 1  # n1 sube a 1 a través del nMOS de a


# ------------------------------------------------------------ errores de uso
def test_errores_en_set_inputs() -> None:
    sim = SwitchEngine(inversor_de_bus(4))
    with pytest.raises(KeyError):
        sim.set_inputs({"q": 1})
    with pytest.raises(ValueError, match="no cabe"):
        sim.set_inputs({"a": 16})
    with pytest.raises(ValueError, match="4 bits"):
        sim.set_inputs({"a": [0, 1]})
    with pytest.raises(KeyError):
        sim.read_bus("q")


# ------------------------------------------------- propiedades (hypothesis)
@given(st.lists(st.tuples(st.integers(0, 1), st.integers(0, 1)), min_size=1, max_size=30))
def test_secuencias_aleatorias_nand_y_nor(secuencia: list[tuple[int, int]]) -> None:
    s_nand, s_nor = SwitchEngine(nand2()), SwitchEngine(nor2())
    esperadas = 0
    anterior: int | None = None
    for a, b in secuencia:
        s_nand.set_inputs({"a": a, "b": b})
        s_nor.set_inputs({"a": a, "b": b})
        y = 1 - (a & b)
        assert s_nand.read("y") is Logic(y)
        assert s_nor.read("y") is Logic(1 - (a | b))
        if anterior is not None and y != anterior:
            esperadas += 1
        anterior = y
    assert s_nand.node_toggles[s_nand.netlist.outputs["y"].id] == esperadas
