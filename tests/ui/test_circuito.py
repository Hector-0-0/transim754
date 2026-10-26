"""Análisis de celdas, esquema y layout de la pestaña de transistores (sin Qt).

El dibujo se genera a partir del netlist; estas pruebas comprueban que lo dibujado es
fiel al circuito: las redes serie-paralelo reproducen lo que calcula el simulador, el
esquema tiene cada transistor una vez y el layout no tiene cortocircuitos ni nodos
abiertos (verificación tipo LVS).
"""

from __future__ import annotations

import itertools

import pytest

from transim.cells.library import CELLS
from transim.core.engine_switch import SwitchEngine
from transim.core.signals import Logic
from transim.core.transistor import Conduction
from transim.ui.gui import schematic, silicon
from transim.ui.gui.circuit import Loose, PassGate, Stage, analyze, conducts

HOJAS = [nombre for nombre, f in CELLS.items() if not f().instances]


@pytest.mark.parametrize("nombre", HOJAS)
def test_cada_transistor_en_un_solo_elemento(nombre: str) -> None:
    celda = CELLS[nombre]()
    c = analyze(celda)
    usados = [i for e in c.elements for i in e.transistors]
    assert sorted(usados) == list(range(len(celda.transistors)))
    assert not any(isinstance(e, Loose) for e in c.elements), "la biblioteca es CMOS estática"


def test_redes_reconocidas() -> None:
    nand = analyze(CELLS["NAND2"]())
    (etapa,) = nand.elements
    assert isinstance(etapa, Stage)
    assert type(etapa.pull_up).__name__ == "Parallel"
    assert type(etapa.pull_down).__name__ == "Series"
    mux = analyze(CELLS["MUX2"]())
    assert sum(isinstance(e, PassGate) for e in mux.elements) == 2


@pytest.mark.parametrize("nombre", HOJAS)
def test_las_redes_reproducen_la_simulacion(nombre: str) -> None:
    """Para cada combinación de entradas, la salida de cada etapa vale 1 si conduce su
    pull-up, 0 si conduce su pull-down, y nunca conducen las dos a la vez."""
    celda = CELLS[nombre]()
    c = analyze(celda)
    motor = SwitchEngine(celda)
    puertos = list(celda.inputs)
    for valores in itertools.product((0, 1), repeat=len(puertos)):
        motor.set_inputs(dict(zip(puertos, valores, strict=True)))
        estado = [motor.conduction(t) for t in celda.transistors]
        for e in c.elements:
            if not isinstance(e, Stage):
                continue
            arriba, abajo = conducts(e.pull_up, estado), conducts(e.pull_down, estado)
            assert not (arriba is Conduction.ON and abajo is Conduction.ON)
            salida = motor.value(celda.nodes[e.output])
            if arriba is Conduction.ON:
                assert salida is Logic.ONE
            if abajo is Conduction.ON:
                assert salida is Logic.ZERO


@pytest.mark.parametrize("nombre", HOJAS)
def test_esquema_dibuja_cada_transistor_sin_solaparse(nombre: str) -> None:
    celda = CELLS[nombre]()
    esq = schematic.build(celda)
    assert sorted(d.index for d in esq.devices) == list(range(len(celda.transistors)))
    cajas = [d.bounds() for d in esq.devices]
    for (a0, a1, a2, a3), (b0, b1, b2, b3) in itertools.combinations(cajas, 2):
        assert not (a0 < b2 - 1 and b0 < a2 - 1 and a1 < b3 - 1 and b1 < a3 - 1)
    for d in esq.devices:
        x0, y0, x1, y1 = d.bounds()
        assert x0 >= 0
        assert y0 >= 0
        assert x1 <= esq.width
        assert y1 <= esq.height
    etiquetas = {t.text for t in esq.texts}
    assert set(celda.inputs) <= etiquetas
    assert set(celda.outputs) <= etiquetas


@pytest.mark.parametrize("nombre", HOJAS)
def test_layout_sin_cortocircuitos_ni_nodos_abiertos(nombre: str) -> None:
    lay = silicon.build(CELLS[nombre]())
    assert silicon.check(lay) == []
    canales = [s.transistor for s in lay.layer("channel")]
    assert sorted(canales) == list(range(len(CELLS[nombre]().transistors)))


def test_layout_de_altura_estandar() -> None:
    """Todas las celdas tienen la misma altura: se pueden poner en filas, como en un chip."""
    alturas = {silicon.build(CELLS[n]()).height for n in HOJAS}
    assert len(alturas) == 1


def test_difusion_compartida_en_serie() -> None:
    """En la NAND2 el nodo entre los dos nMOS en serie no lleva contacto: lo une la
    misma franja de difusión."""
    celda = CELLS["NAND2"]()
    lay = silicon.build(celda)
    n1 = celda.find("n1").id
    assert any(s.node == n1 for s in lay.layer("ndiff"))
    assert not any(s.node == n1 for s in lay.layer("contact"))


def test_la_verificacion_detecta_un_corto() -> None:
    lay = silicon.build(CELLS["INV"]())
    rail = next(s for s in lay.layer("metal1") if s.y0 == 0)
    otro = next(s for s in lay.layer("metal1") if s.node != rail.node and s.node is not None)
    lay.shapes.append(silicon.Shape("metal1", otro.x0, otro.y0, otro.x1, otro.y1, rail.node))
    assert any("cortocircuito" in p for p in silicon.check(lay))
