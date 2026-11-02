"""GUI de escritorio: la ventana y lo que hace cada clic. Issues #25 y #26.

Requiere ``make install-gui``. Las pruebas usan la ventana real sin pantalla
(``QT_QPA_PLATFORM=offscreen``) y simulan el ratón y el teclado con ``QTest``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPoint, QPointF, Qt, QThreadPool  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402


def esperar(app: object, condicion: Callable[[], bool], segundos: float = 20.0) -> None:
    """Procesa eventos hasta que se cumpla ``condicion`` (los cálculos van en otro hilo)."""
    fin = time.monotonic() + segundos
    while not condicion():
        QThreadPool.globalInstance().waitForDone(20)
        app.processEvents()  # type: ignore[attr-defined]
        assert time.monotonic() < fin, "la interfaz no respondió a tiempo"
    app.processEvents()  # type: ignore[attr-defined]


@pytest.fixture
def ventana(qapp: object) -> Iterator[object]:
    from transim.ui.gui.app import create_window

    v = create_window()
    v.resize(1440, 900)
    v.show()
    qapp.processEvents()  # type: ignore[attr-defined]
    yield v
    borrar(v)


def borrar(v: object) -> None:
    """Cierra la ventana. Qt la destruye al final de la sesión: forzar el borrado con
    ventanas que todavía tienen referencias de Python corrompe la memoria de PySide."""
    QThreadPool.globalInstance().waitForDone(5000)
    v.close()  # type: ignore[attr-defined]
    v.deleteLater()  # type: ignore[attr-defined]


def calcular(app: object, v: object) -> None:
    op = v.operation  # type: ignore[attr-defined]
    op.run()
    esperar(app, lambda: op.last is not None and not op._busy)


def clic_en(vista: object, punto: QPointF, doble: bool = False) -> None:
    pos = vista.mapFromScene(punto)  # type: ignore[attr-defined]
    puerto = vista.viewport()  # type: ignore[attr-defined]
    if doble:
        QTest.mouseDClick(puerto, Qt.MouseButton.LeftButton, pos=pos)
    else:
        QTest.mouseClick(puerto, Qt.MouseButton.LeftButton, pos=pos)


# ------------------------------------------------------------------ ventana
def test_ventana_principal(ventana: object) -> None:
    assert "TranSim754" in ventana.windowTitle()  # type: ignore[attr-defined]
    tabs = ventana.tabs  # type: ignore[attr-defined]
    nombres = [tabs.tabText(i) for i in range(tabs.count())]
    assert nombres == ["Operación", "Recorrido", "Transistores", "Programa"]
    menus = [a.text().replace("&", "") for a in ventana.menuBar().actions()]  # type: ignore[attr-defined]
    assert menus == ["Archivo", "Ver", "Ayuda"]


def test_cabe_en_un_proyector_de_1280x720(ventana: object) -> None:
    minimo = ventana.minimumSizeHint()  # type: ignore[attr-defined]
    assert minimo.width() <= 1280
    assert minimo.height() <= 720


def test_cambio_de_tema(ventana: object) -> None:
    from transim.ui.gui import theme

    ventana.set_theme("oscuro")  # type: ignore[attr-defined]
    assert theme.current().dark
    ventana.set_theme("claro")  # type: ignore[attr-defined]
    assert not theme.current().dark


def test_atajos_de_pestanas(ventana: object) -> None:
    QTest.keyClick(ventana, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)  # type: ignore[arg-type]
    assert ventana.tabs.currentIndex() == 1  # type: ignore[attr-defined]
    QTest.keyClick(ventana, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)  # type: ignore[arg-type]
    assert ventana.tabs.currentIndex() == 2  # type: ignore[attr-defined]
    QTest.keyClick(ventana, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)  # type: ignore[arg-type]
    assert ventana.tabs.currentIndex() == 3  # type: ignore[attr-defined]


# ---------------------------------------------------------------- operación
def test_operacion_verificada_y_metricas(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    op = ventana.operation  # type: ignore[attr-defined]
    assert op.last.result.bits == 0x40700000
    assert op.last.matches
    assert op.expr.text() == "1.5 + 2.25 = 3.75"
    assert "Coincide" in op.verify.text()
    assert op.tiles["ciclos"].value.text() == "5"
    assert op.history_list.count() == 1
    assert op.activity.bars, "la actividad por etapa tiene barras"


def test_operando_invalido_deshabilita_el_calculo(ventana: object) -> None:
    op = ventana.operation  # type: ignore[attr-defined]
    op.a.set_text("uno coma cinco")
    assert not op.run_button.isEnabled()
    assert op.a.info.objectName() == "error"
    op.a.set_text("1.5")
    assert op.run_button.isEnabled()


def test_clic_en_un_bit_lo_invierte_y_recalcula(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    op = ventana.operation  # type: ignore[attr-defined]
    campo = op.bitfield
    bit = campo.fmt.width - 1  # el signo de a
    x = campo._x(bit) + campo._cell() / 2
    y = campo.TOP + campo._cell() / 2
    QTest.mouseClick(campo, Qt.MouseButton.LeftButton, pos=QPoint(int(x), int(y)))
    esperar(qapp, lambda: op.last is not None and op.last.a == 0xBFC00000 and not op._busy)
    assert op.a.text() == "0xBFC00000"
    assert op.last.result.bits == 0x3F400000  # −1.5 + 2.25 = 0.75


def test_ejemplos_y_cambio_de_formato(ventana: object, qapp: object) -> None:
    from transim.ui.gui.model import EXAMPLES

    op = ventana.operation  # type: ignore[attr-defined]
    division = next(e for e in EXAMPLES if e.title == "1 ÷ 0")
    op.load_example(division)
    esperar(qapp, lambda: op.last is not None and op.last.op == "div" and not op._busy)
    assert op.flags.active == {"DZ"}
    op.a.set_text("0x3FC00000")
    op.fmt.set_value("binary16", emit=True)
    assert op.a.text() == "1.5"  # el hex pasó a decimal para seguir valiendo lo mismo
    assert op.a.bits == 0x3E00


def test_historial_repite_una_operacion(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    op = ventana.operation  # type: ignore[attr-defined]
    op.a.set_text("7")
    op.run()
    esperar(qapp, lambda: op.history_list.count() == 2 and not op._busy)
    op._restore(op.history_list.item(1))
    esperar(qapp, lambda: op.history_list.count() == 3 and not op._busy)
    assert op.last.a == 0x3FC00000


def test_actividad_abre_la_etapa_en_transistores(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    op = ventana.operation  # type: ignore[attr-defined]
    op.open_stage.emit("align")
    tr = ventana.transistors  # type: ignore[attr-defined]
    assert ventana.tabs.currentWidget() is tr  # type: ignore[attr-defined]
    assert tr._target == ("instance", "align")


# -------------------------------------------------------------- transistores
def test_biblioteca_clic_en_una_entrada_del_dibujo(ventana: object, qapp: object) -> None:
    from transim.ui.gui.canvas import _aligned, measure

    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.library.select("NAND2")
    tr.mode.set_value("schematic", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    item = tr.scene.cells[0]
    texto = next(t for t in item.geo.texts if t.kind == "gate" and t.text == "a")
    x = _aligned(texto.x, measure(texto.text), texto.align) + 6
    clic_en(tr.view, item.mapToScene(QPointF(x, texto.y)))
    assert tr.library.inputs()["a"] == 1
    assert "de 4 transistores conducen" in tr.info.text()


def test_cambiar_una_entrada_anima_la_corriente(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.library.select("INV")
    tr.mode.set_value("schematic", emit=True)
    tr.library.toggle("a")  # la salida baja de 1 a 0: se descarga por el nMOS
    assert tr.scene.flows
    (transistores,) = tr.scene.flows.values()
    assert transistores == {1}  # el nMOS "n" es el transistor 1 del INV


def test_biblioteca_tabla_de_verdad_y_siguiente(ventana: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.library.select("FA")
    tr.library._row_clicked(7, 0)
    assert tr.library.inputs() == {"a": 1, "b": 1, "cin": 1}
    salidas = tr.library.outputs.text()
    assert "s = 1" in salidas
    assert "cout = 1" in salidas
    tr.library.next_combination()
    assert tr.library.inputs() == {"a": 0, "b": 0, "cin": 0}


def test_celdas_secuenciales_y_compuestas(ventana: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.library.select("DFF")
    assert len(tr.scene.cells) > 1  # se dibujan sus celdas internas
    tr.library.buttons["d"].setChecked(True)
    tr.library.next_combination()  # pulso de reloj
    assert "q = 1" in tr.library.outputs.text()
    tr.library.select("HA")
    assert len(tr.scene.cells) == 2


def test_clic_en_transistor_y_esc(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    tr.library.select("INV")
    tr.mode.set_value("schematic", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    item = tr.scene.cells[0]
    d = item.geo.devices[0]
    x0, y0, x1, y1 = d.bounds()
    clic_en(tr.view, item.mapToScene(QPointF((x0 + x1) / 2 + 8, (y0 + y1) / 2)))
    assert tr.scene.selected_transistor == d.index
    assert "MOS" in tr.inspector.title.text()
    assert tr.inspector.section.device is not None
    tr.view.setFocus()
    QTest.keyClick(tr.view, Qt.Key.Key_Escape)
    assert tr.scene.selected_transistor is None


def test_vista_de_silicio_y_corte(ventana: object, qapp: object) -> None:
    from transim.ui.gui.canvas import Hit, SiliconItem

    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    tr.library.select("NOR2")
    tr.mode.set_value("silicon", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    # Una celda en silicio se ve junto a su esquema.
    assert tr.scene.pair
    esquema, item = tr.scene.cells
    assert isinstance(item, SiliconItem)
    canal = item.lay.layer("channel")[0]
    centro = item.mapToScene(item.transistor_rect(canal.transistor).center())
    clic_en(tr.view, centro)
    assert tr.scene.selected_transistor == canal.transistor
    assert tr.inspector.section.device is not None
    # Pasar el ratón por un transistor del esquema lo resalta también en el silicio.
    d = esquema.geo.devices[0]
    hit = Hit(esquema, "transistor", transistor=d.index)
    tr.scene.set_hover(hit)
    assert item.linked(tr.scene.hover_item)
    assert tr.scene.hover_transistor == d.index
    tr.scene.set_hover(None)
    tr.mode.set_value("schematic", emit=True)


def test_ultima_operacion_chip_bloque_y_celda(ventana: object, qapp: object) -> None:
    from transim.ui.gui.canvas import SchematicItem

    calcular(qapp, ventana)
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    tr.reveal("unit")
    netlist = tr.unit.netlist
    assert tr._target == ("unit", "")
    # El chip es un plano: un rectángulo por bloque, sin dibujar las 1411 celdas.
    assert not tr.scene.cells
    bloques = [i for i in netlist.top_instances() if not i.is_leaf]
    assert len(tr.scene.blocks) == len(bloques) + 1  # más las celdas sueltas
    assert not tr.mode.buttons["schematic"].isEnabled()  # el chip entero no tiene esquema
    # Doble clic en un bloque lo abre.
    align = next(b for b in tr.scene.blocks if b.tile.key == "align")
    clic_en(tr.view, align.rect.center(), doble=True)
    assert tr._target == ("instance", "align")
    tr.reveal("unit")

    tr.reveal("unpack_a")
    tr.mode.set_value("schematic", emit=True)
    assert "bloque de 74 celdas" in tr.info.text()
    assert all(isinstance(i, SchematicItem) for i in tr.scene.cells)
    # Doble clic en una celda del bloque: se abre esa celda.
    item = tr.scene.cells[0]
    esquina = QPointF(item.geo.width - 6, item.geo.height - 6)
    clic_en(tr.view, item.mapToScene(esquina), doble=True)
    assert tr._target == ("instance", item.binding.path)
    assert len(tr.scene.cells) == 1
    # Retroceso sube al bloque; la ruta de navegación lleva a la unidad.
    tr.view.setFocus()
    QTest.keyClick(tr.view, Qt.Key.Key_Backspace)
    assert tr._target == ("instance", "unpack_a")
    tr._crumb("unit")
    assert tr._target == ("unit", "")


def test_bloque_grande_solo_en_silicio(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.mode.set_value("schematic", emit=True)
    tr.reveal("round")  # 3812 transistores
    assert tr.silicon
    assert "se muestra su plano" in tr.info.text()
    # Su plano: los sub-bloques uno por uno y las celdas sueltas agrupadas por tipo.
    assert sum(b.tile.weight for b in tr.scene.blocks) == len(tr._instances["round"].transistors)
    grupos = [b for b in tr.scene.blocks if " × " in b.tile.title]
    assert grupos
    primero = grupos[0]
    clic_en(tr.view, primero.rect.center(), doble=True)
    assert tr._target == ("instance", primero.tile.key)
    assert tr._instances[primero.tile.key].is_leaf


def test_buscador_y_mapa_de_actividad(ventana: object, qapp: object) -> None:
    ventana.operation.a.set_text("-3.75")  # type: ignore[attr-defined]
    calcular(qapp, ventana)
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.sources.setCurrentIndex(1)
    tr.hierarchy.search.setText("gor1")
    textos = [tr.tree.topLevelItem(i).text(0) for i in range(tr.tree.topLevelItemCount())]
    assert textos
    assert all("gor1" in t for t in textos)
    tr.hierarchy.search.clear()
    assert tr.tree.topLevelItem(0).text(0) == tr.unit.netlist.name
    tr.reveal("align")
    tr.heat.setChecked(True)
    assert tr.scene.show_heat
    assert max(i.heat for i in tr.scene.cells) == pytest.approx(1.0)


def test_paso_del_raton_resalta_el_nodo_en_otras_celdas(ventana: object, qapp: object) -> None:
    from transim.ui.gui.canvas import Hit

    calcular(qapp, ventana)
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.reveal("unpack_a")
    tr.mode.set_value("schematic", emit=True)
    item = tr.scene.cells[0]
    salida = item.binding.nodes[next(iter(item.binding.circuit.outputs.values()))]
    tr.scene.set_hover(Hit(item, "node", node=salida.id))
    assert len(tr.scene.items_with_node(salida.id)) >= 2  # la salida llega a otra celda
    assert "Nodo" in tr.inspector.title.text()
    tr.scene.set_hover(None)


def test_exportar_imagen(ventana: object, tmp_path: Path) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.library.select("XOR2")
    destino = tmp_path / "xor2.png"
    assert tr.export_image(str(destino))
    assert destino.stat().st_size > 1000


# ------------------------------------------------------------------ programa
def test_programa_paso_a_paso_y_hasta_halt(ventana: object, qapp: object) -> None:
    pg = ventana.program  # type: ignore[attr-defined]
    pg.load()
    esperar(qapp, lambda: pg.machine is not None)
    assert pg.source.pc_line == 2  # primera instrucción (después del comentario)
    pg.step()
    esperar(qapp, lambda: pg.machine.state.steps == 1 and pg.load_button.isEnabled())
    assert pg.source.pc_line == 3
    pg.run()
    esperar(qapp, lambda: pg.machine.halted and pg.load_button.isEnabled())
    assert pg.outputs.item(0).text().startswith("0x40700000")
    assert not pg.step_button.isEnabled()


def test_programa_error_de_ensamblado(ventana: object) -> None:
    pg = ventana.program  # type: ignore[attr-defined]
    pg.source.setPlainText("LI F1, 1.5\nFSQRT F2, F1\nHALT\n")
    pg.load()
    assert pg.source.error_line == 2
    assert pg.message.objectName() == "error"


def test_programa_compatible_con_la_maquina(ventana: object) -> None:
    from transim.cpu.assembler import assemble
    from transim.cpu.machine import Machine

    pg = ventana.program  # type: ignore[attr-defined]
    pg._loaded(Machine(assemble(pg.source.toPlainText())))
    pg.machine.run()
    pg.refresh()
    assert pg.outputs.item(0).text().startswith("0x40700000")


# -------------------------------------------------------------- consola
def test_consola_de_ciclos() -> None:
    from transim.fpu.add_sub import fp_add_sub
    from transim.fpu.format import BINARY32
    from transim.ui.gui.app import cycles_report

    texto = cycles_report(fp_add_sub(BINARY32), 39, {"round": 10, "align": 3})
    assert "camino crítico: 176 celdas" in texto
    assert "5 ciclos" in texto
    assert "Ciclo 1" in texto
    assert "redondear y empaquetar" in texto


# ------------------------------------------------------------ más interacción
def test_enter_en_un_operando_calcula(ventana: object, qapp: object) -> None:
    op = ventana.operation  # type: ignore[attr-defined]
    op.a.set_text("2.5")
    op.a.edit.setFocus()
    QTest.keyClick(op.a.edit, Qt.Key.Key_Return)
    esperar(qapp, lambda: op.last is not None and op.last.a == 0x40200000 and not op._busy)
    assert op.expr.text() == "2.5 + 2.25 = 4.75"


def test_menu_contextual_del_dibujo(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.reveal("unpack_a")
    item = tr.scene.cells[0]  # un recuadro de la rejilla de bits
    centro = item.mapToScene(item.boundingRect().center())
    textos = [a.text() for a in tr.context_menu(tr.view.mapFromScene(centro)).actions()]
    assert "Ajustar a la vista" in textos
    assert f"Abrir {item.binding.path}" in textos
    assert "Subir un nivel (Retroceso)" in textos
    assert "Exportar imagen…" in textos


def test_recuerda_tamano_pestana_y_tema(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtCore import QSettings

    from transim.ui.gui import theme
    from transim.ui.gui.app import MainWindow

    # Se prueba que se guarde la elección; repintar todas las ventanas abiertas de la
    # sesión de pruebas con el tema nuevo solo la haría lenta.
    monkeypatch.setattr(theme, "apply", lambda app, t: None)

    archivo = str(tmp_path / "transim.ini")
    original = MainWindow._settings
    MainWindow._settings = lambda self: QSettings(archivo, QSettings.Format.IniFormat)  # type: ignore[method-assign]
    try:
        v = MainWindow(persist=True)
        v.tabs.setCurrentIndex(3)
        v.set_theme("oscuro")
        borrar(v)
        w = MainWindow(persist=True)
        assert w.tabs.currentIndex() == 3
        assert w.theme_choice == "oscuro"
        w.set_theme("claro")
        borrar(w)
    finally:
        MainWindow._settings = original  # type: ignore[method-assign]


@pytest.mark.switch
def test_division_binary32_con_el_motor_exacto(ventana: object, qapp: object) -> None:
    """1 ÷ 3 con el motor switch: antes del arreglo del límite de eventos fallaba."""
    op = ventana.operation  # type: ignore[attr-defined]
    op.a.set_text("1")
    op.b.set_text("3")
    op.op.set_value("div")
    op.engine_box.setCurrentIndex(op.engine_box.findData("switch"))
    op.run()
    esperar(qapp, lambda: op.last is not None and op.last.engine == "switch" and not op._busy, 60)
    assert op.last.matches
    assert op.expr.text() == "1 ÷ 3 = 0.33333334"


def test_aviso_de_resultado_desactualizado(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    op = ventana.operation  # type: ignore[attr-defined]
    assert op.stale.isHidden()
    op.b.set_text("4")
    assert not op.stale.isHidden()
    op.run()
    esperar(qapp, lambda: not op._busy and op.last.b == 0x40800000)
    assert op.stale.isHidden()


def test_transistores_se_cargan_al_mostrarse(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentIndex(0)  # type: ignore[attr-defined]
    op = ventana.operation  # type: ignore[attr-defined]
    op.a.set_text("9.5")
    calcular(qapp, ventana)
    assert tr._pending is op.last  # no se dibujó con la pestaña oculta
    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    assert tr._pending is None
    assert tr.calc is op.last


def test_atajos_de_programa_y_de_vista(ventana: object, qapp: object) -> None:
    pg = ventana.program  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(ventana.program)  # type: ignore[attr-defined]
    pg.source.setFocus()
    QTest.keyClick(pg.source, Qt.Key.Key_F5)
    esperar(qapp, lambda: pg.machine is not None and pg.load_button.isEnabled())
    QTest.keyClick(pg.source, Qt.Key.Key_F10)
    esperar(qapp, lambda: pg.machine.state.steps == 1 and pg.load_button.isEnabled())
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    tr.view.setFocus()
    QTest.keyClick(tr.view, Qt.Key.Key_S, Qt.KeyboardModifier.AltModifier)
    assert tr.silicon
    QTest.keyClick(tr.view, Qt.Key.Key_E, Qt.KeyboardModifier.AltModifier)
    assert not tr.silicon


def test_capas_del_silicio_se_ocultan_con_sus_casillas(ventana: object, qapp: object) -> None:
    from transim.ui.gui import theme as th
    from transim.ui.gui.canvas import LAYER_COLOR, TOGGLE_LAYERS

    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    tr.library.select("NOR2")
    tr.mode.set_value("silicon", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    assert not tr.layer_row.isHidden()
    assert set(tr.scene.visible_layers) == set(TOGGLE_LAYERS)
    tr.layer_boxes["metal1"].setChecked(False)
    assert "metal1" not in tr.scene.visible_layers
    tr.layer_boxes["metal1"].setChecked(True)
    assert "metal1" in tr.scene.visible_layers
    # Los colores de las capas no coinciden con los de los valores lógicos.
    t = th.current()
    assert LAYER_COLOR["poly"] not in (t.one, t.zero)
    assert LAYER_COLOR["metal1"] not in (t.one, t.zero)
    tr.mode.set_value("schematic", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    assert not tr.layer_row.isVisible()


# ------------------------------------------------------- paso a paso y flujo
def test_paso_a_paso_resalta_y_atenua(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    tr.library.select("XOR2")
    tr.mode.set_value("schematic", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    assert not tr.step_row.isHidden()
    assert tr.scene.step_filter is None
    tr.step_next.click()
    filtro = tr.scene.step_filter
    assert filtro is not None
    transistores, _nodos = filtro
    assert transistores == tr.steps[0].transistors
    assert tr.step_pos == 0
    assert "Etapa 1 de 3" in tr.step_text.text()
    assert "an = ¬a" in tr.step_text.text()
    tr.step_all.click()
    assert tr.scene.step_filter is None


def test_paso_a_paso_no_aparece_en_silicio(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(ventana.transistors)  # type: ignore[attr-defined]
    tr.library.select("NAND2")
    tr.mode.set_value("silicon", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    assert tr.step_row.isHidden()
    assert tr.scene.step_filter is None


def test_recorrido_vacio_lleva_a_operacion(ventana: object, qapp: object) -> None:
    rec = ventana.walkthrough  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(rec)  # type: ignore[attr-defined]
    assert rec.stack.currentIndex() == 0
    boton = next(b for b in rec.findChildren(QPushButton) if b.text() == "Ir a Operación")
    boton.click()
    assert ventana.tabs.currentWidget() is ventana.operation  # type: ignore[attr-defined]


def test_recorrido_paso_a_paso(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    rec = ventana.walkthrough  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(rec)  # type: ignore[attr-defined]
    qapp.processEvents()  # type: ignore[attr-defined]
    assert rec.stack.currentIndex() == 1
    assert rec.expression.text() == "1.5 + 2.25 = 3.75"
    assert rec.count == 9
    assert rec.index == 0
    assert rec.counter.text() == "Paso 1 de 9"
    assert "Desempaquetar" in rec.p_title.text()
    assert not rec.prev.isEnabled()
    # Teclado: → avanza, ← retrocede, Fin muestra todo, Inicio vuelve.
    QTest.keyClick(rec.diagram, Qt.Key.Key_Right)
    QTest.keyClick(rec.diagram, Qt.Key.Key_Right)
    assert rec.index == 2
    assert "128 − 127 = 1" in rec.p_detail.text()
    QTest.keyClick(rec.diagram, Qt.Key.Key_Left)
    assert rec.index == 1
    QTest.keyClick(rec.diagram, Qt.Key.Key_End)
    assert rec.index == 8
    assert not rec.next.isEnabled()
    assert "0x40700000" in rec.p_detail.text()
    QTest.keyClick(rec.diagram, Qt.Key.Key_Right)  # en el último paso no pasa nada
    assert rec.index == 8
    QTest.keyClick(rec.diagram, Qt.Key.Key_Home)
    assert rec.index == 0
    # Las cajas que faltan no muestran su resultado.
    assert [b.state for b in rec.diagram.boxes[:2]] == ["now", "todo"]


def test_recorrido_clic_y_doble_clic(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    rec = ventana.walkthrough  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(rec)  # type: ignore[attr-defined]
    qapp.processEvents()  # type: ignore[attr-defined]
    vista = rec.diagram
    clic_en(vista, vista.item_center(3))
    assert rec.index == 3
    assert "Alinear mantisa" in rec.p_title.text()
    clic_en(vista, vista.item_center(4), doble=True)
    tr = ventana.transistors  # type: ignore[attr-defined]
    assert ventana.tabs.currentWidget() is tr  # type: ignore[attr-defined]
    assert tr.tree.currentItem().data(0, Qt.ItemDataRole.UserRole).path == "mant_addsub"


def test_recorrido_se_reproduce_solo(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    rec = ventana.walkthrough  # type: ignore[attr-defined]
    rec.toggle_play()
    assert rec.timer.isActive()
    assert rec.play.text().endswith("Pausa")
    for _ in range(rec.count):
        rec._tick()
    assert rec.index == rec.count - 1
    assert not rec.timer.isActive()


def test_recorrido_conserva_el_paso_al_recalcular(ventana: object, qapp: object) -> None:
    """Al invertir un bit en Operación se compara el mismo paso con el valor nuevo."""
    calcular(qapp, ventana)
    rec = ventana.walkthrough  # type: ignore[attr-defined]
    rec.go(2)
    op = ventana.operation  # type: ignore[attr-defined]
    op.b.set_text("4")
    calcular(qapp, ventana)
    assert rec.index == 2
    assert "129 − 127 = 2" in rec.p_detail.text()
    op.op.set_value("mul")
    calcular(qapp, ventana)
    assert rec.index == 0  # otra unidad: vuelve al inicio
    assert "FMUL" in rec.subtitle.text()
    assert "explicado paso a paso" in rec.subtitle.text()


# ---------------------------------------------------------------- compuertas
def test_compuertas_es_la_vista_inicial_de_una_celda(ventana: object, qapp: object) -> None:
    from transim.ui.gui.canvas import GateItem

    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.library.select("XOR2")
    qapp.processEvents()  # type: ignore[attr-defined]
    assert tr.mode.value() == "gates"
    (item,) = tr.scene.cells
    assert isinstance(item, GateItem)
    assert [g.title for g in item.gates] == ["INV", "INV", "AOI"]
    # «Qué está pasando» explica cada etapa con los valores de ahora.
    cuerpo = tr.inspector.body.text()
    assert "an = ¬a = ¬0 = 1" in cuerpo
    assert "y = ¬(a·b + an·bn)" in cuerpo


def test_compuertas_clic_en_una_entrada(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.library.select("NAND2")
    qapp.processEvents()  # type: ignore[attr-defined]
    item = tr.scene.cells[0]
    puerto = next(p for p in item.geo.ports if p.name == "b")
    clic_en(tr.view, item.mapToScene(QPointF(puerto.x - 14, puerto.y)))
    assert tr.library.inputs()["b"] == 1


def test_compuertas_inspector_y_doble_clic(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.library.select("FA")
    qapp.processEvents()  # type: ignore[attr-defined]
    item = tr.scene.cells[0]
    primera = item.gates[0]
    centro = item.gate_center(primera.element)
    hit = tr.view.hit_at(QPointF(tr.view.mapFromScene(centro)))
    assert hit is not None
    assert hit.kind == "gate"
    tr._hover(hit)
    assert "compuerta compleja" in tr.inspector.title.text()
    assert "coutn = ¬(a·b + cin·(a + b))" in tr.inspector.body.text()
    clic_en(tr.view, centro, doble=True)
    assert tr.mode.value() == "schematic"
    assert tr.scene.step_filter is not None
    assert tr.scene.step_filter[0] == frozenset(primera.transistors)


def test_paso_a_paso_tambien_en_compuertas(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.library.select("AND2")
    qapp.processEvents()  # type: ignore[attr-defined]
    assert not tr.step_row.isHidden()
    tr.step_next.click()
    tr.step_next.click()
    assert "y = ¬yn" in tr.step_text.text()
    assert "Etapa 2 de 2" in tr.step_text.text()


def test_atajos_de_vista_y_panel(ventana: object, qapp: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.library.select("INV")
    tr.view.setFocus()
    QTest.keyClick(tr.view, Qt.Key.Key_E, Qt.KeyboardModifier.AltModifier)
    assert tr.mode.value() == "schematic"
    QTest.keyClick(tr.view, Qt.Key.Key_C, Qt.KeyboardModifier.AltModifier)
    assert tr.mode.value() == "gates"
    # En la biblioteca el panel se ve; se puede ocultar con su botón.
    assert tr.sources.isVisible()
    tr.panel_button.click()
    assert not tr.sources.isVisible()
    QTest.keyClick(tr.view, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert tr.sources.isVisible()


def test_con_una_operacion_el_panel_se_oculta(ventana: object, qapp: object) -> None:
    calcular(qapp, ventana)
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.reveal("mant_addsub")
    qapp.processEvents()  # type: ignore[attr-defined]
    assert not tr.sources.isVisible()
    tr.open_search()
    assert tr.sources.isVisible()
    assert tr.hierarchy.search.hasFocus() or not tr.isActiveWindow()


def test_opciones_en_el_menu_ver(ventana: object) -> None:
    tr = ventana.transistors  # type: ignore[attr-defined]
    textos = [a.text() for a in tr.view_menu.actions() if a.text()]
    assert textos[:4] == ["Camino activo", "Conmutaciones", "Mapa de actividad", "Color por valor"]
    assert any(t.startswith("Exportar imagen") for t in textos)
    assert not tr.paths.isChecked()  # sin recuadros verdes salvo que se pidan


# -------------------------------------------------------------------- plano
def test_plano_inspector_y_actividad(ventana: object, qapp: object) -> None:
    from transim.ui.gui.canvas import BlockHit

    ventana.operation.a.set_text("9.25")  # type: ignore[attr-defined]
    calcular(qapp, ventana)  # distinta de la anterior: hay conmutaciones
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.reveal("unit")
    qapp.processEvents()  # type: ignore[attr-defined]
    total = len(tr.unit.netlist.transistors)
    assert sum(b.tile.weight for b in tr.scene.blocks) == total
    # El área sigue a los transistores: el bloque más grande tiene el rectángulo más grande.
    grande = max(tr.scene.blocks, key=lambda b: b.tile.weight)
    area = max(tr.scene.blocks, key=lambda b: b.rect.width() * b.rect.height())
    assert grande is area
    clic_en(tr.view, grande.rect.center())
    assert tr.scene.selected_block is grande
    assert "transistores" in tr.inspector.body.text()
    tr._hover(BlockHit(grande))
    assert grande.tile.title in tr.inspector.title.text()
    tr.heat.setChecked(True)
    assert max(b.heat for b in tr.scene.blocks) == pytest.approx(1.0)
    tr.heat.setChecked(False)
    assert not tr.layer_row.isVisible()  # las capas son de la vista de una celda


# ---------------------------------------------------------- rejilla y propagación
def test_rejilla_de_un_bloque_y_propagacion(ventana: object, qapp: object) -> None:
    from transim.ui.gui.canvas import TileItem

    ventana.operation.a.set_text("6.5")  # type: ignore[attr-defined]
    calcular(qapp, ventana)
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.reveal("mant_addsub")
    tr.mode.set_value("gates", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    assert all(isinstance(i, TileItem) for i in tr.scene.cells)
    assert not tr.time_row.isHidden()
    r = tr.replay
    assert r is not None
    assert r.valid
    # Al abrir se ve el estado final, que es el del motor.
    assert tr.time_t == r.length
    # En el instante 0 nada del bloque cambió todavía; luego algo cambia.
    tr.set_time(0)
    assert not tr.scene.flash_cells
    paths = frozenset(c.binding.path for c in tr.scene.cells)
    ultimo = r.last_change(paths)
    assert ultimo > 0
    tr.set_time(ultimo)
    assert tr.scene.flash_cells & paths
    assert f"t = {ultimo}" in tr.time_text.text()
    # Reproducir avanza solo hasta el final.
    tr.toggle_time()
    for _ in range(r.length + 1):
        tr._time_tick()
    assert tr.time_t == r.length
    # Doble clic en un recuadro abre esa celda.
    item = tr.scene.cells[0]
    clic_en(tr.view, item.mapToScene(item.boundingRect().center()), doble=True)
    assert tr._target == ("instance", item.binding.path)
    assert tr.time_row.isHidden()


def test_recorrido_abre_la_propagacion(ventana: object, qapp: object) -> None:
    ventana.operation.a.set_text("12.5")  # type: ignore[attr-defined]
    calcular(qapp, ventana)
    rec = ventana.walkthrough  # type: ignore[attr-defined]
    ventana.tabs.setCurrentWidget(rec)  # type: ignore[attr-defined]
    rec.go(4)  # sumar mantisas
    assert rec.p_wave.text() == "Ver el acarreo ▸"
    rec.p_wave.click()
    tr = ventana.transistors  # type: ignore[attr-defined]
    assert ventana.tabs.currentWidget() is tr  # type: ignore[attr-defined]
    assert tr._target == ("instance", "mant_addsub")
    assert tr.gates
    assert tr._time_timer.isActive()
    assert tr.time_t == 0
    tr.toggle_time()  # pausa
    assert not tr._time_timer.isActive()
