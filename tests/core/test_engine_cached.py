"""Motor cached: extracción de tablas, criterios de tabulación y equivalencia exacta
con el motor switch (ADR-0008)."""

from __future__ import annotations

import itertools
import random
from collections.abc import Mapping, Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from transim.cells.combinational import inv, nand2, nor2
from transim.core import (
    CachedEngine,
    Logic,
    Netlist,
    NotCombinationalError,
    Strength,
    SwitchEngine,
    table_for,
)
from transim.core.engine_cached import CellTable, tabulable_definition
from transim.core.engine_switch import InputValue

pytestmark = pytest.mark.cached


# ------------------------------------------------------------------ circuitos
def sumador_completo_nand() -> Netlist:
    """Sumador completo de 9 NAND2 (jerárquico: hojas = NAND2)."""
    nl = Netlist("FA_NAND")
    a, b, cin = nl.input("a"), nl.input("b"), nl.input("cin")
    s, cout = nl.output("s"), nl.output("cout")

    def g(nombre: str, x: object, y: object, out: object = None) -> object:
        conn = {"a": x, "b": y}
        if out is not None:
            conn["y"] = out
        return nl.instantiate(nand2(), nombre, conn)["y"]  # type: ignore[arg-type]

    n1 = g("g1", a, b)
    n2 = g("g2", a, n1)
    n3 = g("g3", b, n1)
    x = g("g4", n2, n3)
    n5 = g("g5", x, cin)
    n6 = g("g6", x, n5)
    n7 = g("g7", cin, n5)
    g("g8", n6, n7, s)
    g("g9", n1, n5, cout)
    return nl


def sumador_ripple(ancho: int) -> Netlist:
    nl = Netlist(f"RCA{ancho}")
    a, b = nl.input_bus("a", ancho), nl.input_bus("b", ancho)
    s = nl.output_bus("s", ancho)
    carry = nl.input("cin")
    fa = sumador_completo_nand()
    for i in range(ancho):
        out = nl.output("cout") if i == ancho - 1 else None
        conn = {"a": a[i], "b": b[i], "cin": carry, "s": s[i]}
        if out is not None:
            conn["cout"] = out
        carry = nl.instantiate(fa, f"fa{i}", conn)["cout"]
    return nl


def latch_estatico() -> Netlist:
    """Latch D estático con transmission gates (secuencial: no se tabula)."""
    nl = Netlist("DLATCH", sequential=True)
    d, clk, clk_n = nl.input("d"), nl.input("clk"), nl.input("clk_n")
    q = nl.output("q")
    m, qn = nl.node("m"), nl.node("qn")
    nl.transmission_gate(d, m, clk, clk_n, "tg_in")
    nl.pmos(m, nl.vdd, qn)
    nl.nmos(m, qn, nl.gnd)
    nl.pmos(qn, nl.vdd, q)
    nl.nmos(qn, q, nl.gnd)
    nl.transmission_gate(q, m, clk_n, clk, "tg_fb")
    return nl


def mux_tg_sin_buffer() -> Netlist:
    """MUX2 de transmission gates sin buffers: sus entradas tocan canales."""
    nl = Netlist("MUX_TG")
    a, b, s = nl.input("a"), nl.input("b"), nl.input("s")
    y, s_n = nl.output("y"), nl.node("s_n")
    nl.pmos(s, nl.vdd, s_n)
    nl.nmos(s, s_n, nl.gnd)
    nl.transmission_gate(a, y, s_n, s)
    nl.transmission_gate(b, y, s, s_n)
    return nl


def circuito_mixto() -> Netlist:
    """Celdas tabulables, una celda secuencial, una no tabulable y transistores sueltos."""
    nl = Netlist("mixto")
    a, b, en, en_n = nl.input("a"), nl.input("b"), nl.input("en"), nl.input("en_n")
    x = nl.instantiate(nand2(), "u_nand", {"a": a, "b": b})["y"]
    xn = nl.instantiate(inv(), "u_inv", {"a": x})["y"]
    # salida de NOR conectada a un canal externo: no tabulable
    z = nl.instantiate(nor2(), "u_nor", {"a": a, "b": xn})["y"]
    w = nl.output("w")
    nl.transmission_gate(z, w, en, en_n)
    lat = nl.instantiate(latch_estatico(), "u_lat", {"d": xn, "clk": en, "clk_n": en_n})
    nl.instantiate(
        mux_tg_sin_buffer(), "u_mux", {"a": lat["q"], "b": a, "s": b, "y": nl.output("y")}
    )
    return nl


# ----------------------------------------------------------------- utilidades
def estado_observable(motor: SwitchEngine) -> dict[str, Logic]:
    """Nodos con valor conocido impuesto con fuerza ≥ DRIVEN, y su valor.

    Excluye la carga retenida y las X: en un modelo de retardo cero dependen del orden
    de los eventos intermedios y no son reproducibles (ADR-0008, precisiones).
    """
    valores, fuerzas = motor.values(), motor.strengths()
    return {
        n.name: valores[n.id]
        for n in motor.netlist.nodes
        if valores[n.id].is_known and fuerzas[n.id] >= Strength.DRIVEN
    }


def assert_equivalentes(
    nl: Netlist, pasos: Sequence[Mapping[str, InputValue]]
) -> tuple[SwitchEngine, CachedEngine]:
    """Aplica la misma secuencia a ambos motores y exige estados y conteos idénticos."""
    sw, ca = SwitchEngine(nl, max_events=10**6), CachedEngine(nl, max_events=10**6)
    for paso in [{}, *pasos]:
        if paso:
            sw.set_inputs(paso)
            ca.set_inputs(paso)
        assert estado_observable(sw) == estado_observable(ca), paso
        assert sw.node_toggles == ca.node_toggles, paso
        assert sw.transistor_events == ca.transistor_events, paso
    return sw, ca


# ---------------------------------------------------------- tablas de celdas
@pytest.mark.parametrize(
    ("celda", "esperada"),
    [
        (inv, {(0,): (1,), (1,): (0,)}),
        (nand2, {(0, 0): (1,), (0, 1): (1,), (1, 0): (1,), (1, 1): (0,)}),
        (nor2, {(0, 0): (1,), (0, 1): (0,), (1, 0): (0,), (1, 1): (0,)}),
    ],
)
def test_extraccion_automatica_de_la_tabla_de_verdad(
    celda: object, esperada: dict[tuple[int, ...], tuple[int, ...]]
) -> None:
    tabla = table_for(celda())  # type: ignore[operator]
    assert {k: tuple(int(v) for v in vs) for k, vs in tabla.truth_table.items()} == esperada


def test_la_tabla_se_construye_una_vez_por_tipo() -> None:
    assert table_for(nand2()) is table_for(nand2())


def test_tabla_con_estado_interno() -> None:
    """El nodo n1 de NAND2 retiene carga: la tabla depende del estado previo."""
    tabla = table_for(nand2())
    pos_n1 = tabla.state_ids.index(nand2().find("n1").id)
    pos_y = tabla.state_ids.index(nand2().outputs["y"].id)
    entradas = (Logic.ZERO, Logic.ZERO)  # ambos nMOS cortados: n1 aislado
    for retenido in (Logic.ZERO, Logic.ONE):
        estado = [Logic.X] * len(tabla.state_ids)
        estado[pos_n1] = retenido
        valores, fuerzas = tabla.step(entradas, tuple(estado))
        assert valores[pos_n1] is retenido
        assert fuerzas[pos_n1] is Strength.CHARGE
        assert valores[pos_y] is Logic.ONE


def test_celda_no_combinacional_se_rechaza() -> None:
    nl = Netlist("SOLO_PULLDOWN")
    a, y = nl.input("a"), nl.output("y")
    nl.nmos(a, y, nl.gnd)  # con a = 0, y queda flotando
    with pytest.raises(NotCombinationalError, match="indefinida"):
        CellTable(nl)


@pytest.mark.parametrize(
    ("definicion", "motivo"),
    [
        (latch_estatico(), "secuencial"),
        (mux_tg_sin_buffer(), "toca un canal"),
        (sumador_completo_nand(), "sub-instancias"),
    ],
)
def test_criterios_de_tabulacion(definicion: Netlist, motivo: str) -> None:
    razon = tabulable_definition(definicion)
    assert razon is not None
    assert motivo in razon


def test_particion_del_circuito_mixto() -> None:
    motor = CachedEngine(circuito_mixto())
    assert motor.cached_instances == ["u_nand"]
    # la salida del INV llega a la entrada d del latch, que es el canal de una TG
    assert "canales fuera" in motor.switch_instances["u_inv"]
    assert "canales fuera" in motor.switch_instances["u_nor"]
    assert "secuencial" in motor.switch_instances["u_lat"]
    assert "toca un canal" in motor.switch_instances["u_mux"]


def test_memoizacion_reutiliza_resultados() -> None:
    motor = CachedEngine(sumador_ripple(4))
    for a, b in itertools.product(range(4), repeat=2):
        motor.set_inputs({"a": a, "b": b, "cin": 0})
    hits, misses = motor.table_stats()["NAND2"]
    assert hits > misses


# ------------------------------------------------------------- equivalencia
def test_sumador_ripple_correcto_en_ambos_motores() -> None:
    nl = sumador_ripple(4)
    pasos: list[Mapping[str, InputValue]] = [
        {"a": a, "b": b, "cin": c} for a, b, c in itertools.product(range(16), range(16), range(2))
    ]
    _sw, ca = assert_equivalentes(nl, pasos[:40])
    for paso in pasos:
        ca.set_inputs(paso)
        total = paso["a"] + paso["b"] + paso["cin"]  # type: ignore[operator]
        assert ca.read_int("s") == total & 0xF
        assert ca.read("cout") is Logic(total >> 4)


def test_equivalencia_en_circuito_mixto() -> None:
    rng = random.Random(754)
    niveles = [0, 1, "X"]
    pasos: list[Mapping[str, InputValue]] = []
    for _ in range(200):
        en = rng.choice([0, 1])
        pasos.append({"a": rng.choice(niveles), "b": rng.choice(niveles), "en": en, "en_n": 1 - en})
    assert_equivalentes(circuito_mixto(), pasos)


def test_equivalencia_celda_por_celda_con_x_y_z() -> None:
    for celda in (inv, nand2, nor2):
        top = Netlist("top")
        conn = {n: top.input(n) for n in celda().inputs}
        top.instantiate(celda(), "u", conn | {"y": top.output("y")})
        rng = random.Random(celda().name)
        pasos = [{n: rng.choice([0, 1, "X", "Z"]) for n in conn} for _ in range(100)]
        assert_equivalentes(top, pasos)


@st.composite
def circuito_aleatorio(draw: st.DrawFn) -> tuple[Netlist, list[dict[str, int]]]:
    """DAG aleatorio de INV/NAND2/NOR2 con 3 entradas y una secuencia de estímulos."""
    nl = Netlist("aleatorio")
    senales = [nl.input(n) for n in ("a", "b", "c")]
    n_compuertas = draw(st.integers(1, 25))
    for i in range(n_compuertas):
        tipo = draw(st.sampled_from(["INV", "NAND2", "NOR2"]))
        x = senales[draw(st.integers(0, len(senales) - 1))]
        if tipo == "INV":
            senales.append(nl.instantiate(inv(), f"g{i}", {"a": x})["y"])
        else:
            y = senales[draw(st.integers(0, len(senales) - 1))]
            celda = nand2() if tipo == "NAND2" else nor2()
            senales.append(nl.instantiate(celda, f"g{i}", {"a": x, "b": y})["y"])
    if not senales[-1].is_source:
        nl.mark_output("y", senales[-1])
    pasos = draw(
        st.lists(
            st.fixed_dictionaries({n: st.integers(0, 1) for n in ("a", "b", "c")}),
            min_size=1,
            max_size=12,
        )
    )
    return nl, pasos


@settings(max_examples=60, deadline=None)
@given(circuito_aleatorio())
def test_equivalencia_en_circuitos_aleatorios(caso: tuple[Netlist, list[dict[str, int]]]) -> None:
    nl, pasos = caso
    assert_equivalentes(nl, pasos)


def test_mismo_conteo_de_transistores() -> None:
    nl = sumador_ripple(8)
    sw, ca = SwitchEngine(nl), CachedEngine(nl)
    assert sw.netlist.transistor_count() == ca.netlist.transistor_count()
    assert len(sw.transistor_events) == len(ca.transistor_events) == 8 * 9 * 4


# ------------------------------------------------- regresiones (validación F4)
def test_cambio_solo_de_fuerza_actualiza_el_contador() -> None:
    """Un nodo que pasa de carga retenida a valor manejado sin cambiar de valor debe
    compararse con su último valor manejado (ADR-0007, punto 9)."""
    nl = Netlist("tg")
    d, en, en_n, q = nl.input("d"), nl.input("en"), nl.input("en_n"), nl.output("q")
    nl.transmission_gate(d, q, en, en_n)
    sim = SwitchEngine(nl)
    sim.set_inputs({"d": 1, "en": 1, "en_n": 0})  # q manejado a 1
    sim.set_inputs({"en": 0, "en_n": 1})  # q aislado
    valores = sim.values()
    valores[q.id] = Logic.ZERO  # carga distinta del último valor manejado
    sim.load_state(valores)
    sim.set_inputs({"d": 0})
    sim.set_inputs({"en": 1, "en_n": 0})  # q manejado a 0: mismo valor, otra fuerza
    assert sim.node_toggles[q.id] == 1


def test_solapamiento_transitorio_no_es_cortocircuito() -> None:
    """Al cambiar la selección, las dos TG conducen un instante (retardo cero): no se
    reporta; solo se reportan cortocircuitos que persisten en el estado estable."""
    import warnings

    nl = Netlist("selector")
    a, b, s, m = nl.input("a"), nl.input("b"), nl.input("s"), nl.output("m")
    s_n = nl.instantiate(inv(), "is", {"a": s})["y"]
    a_n = nl.instantiate(inv(), "ia", {"a": a})["y"]
    b_n = nl.instantiate(inv(), "ib", {"a": b})["y"]
    nl.transmission_gate(a_n, m, s_n, s)
    nl.transmission_gate(b_n, m, s, s_n)
    for motor in (SwitchEngine(nl), CachedEngine(nl)):
        motor.set_inputs({"a": 0, "b": 1, "s": 0})
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            for k in range(10):
                motor.set_inputs({"s": k % 2})
                assert motor.read("m") is Logic(1 - k % 2)
        assert motor.short_circuits == []


@settings(max_examples=40, deadline=None)
@given(circuito_aleatorio(), st.randoms(use_true_random=False))
def test_equivalencia_aleatoria_con_entradas_x(
    caso: tuple[Netlist, list[dict[str, int]]], rng: random.Random
) -> None:
    nl, pasos = caso
    con_x: list[Mapping[str, InputValue]] = [
        {k: (rng.choice([0, 1, "X"])) for k in p} for p in pasos * 3
    ]
    assert_equivalentes(nl, con_x)
