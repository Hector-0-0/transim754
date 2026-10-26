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
    assert nombres == ["Operación", "Transistores", "Programa"]
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

    ventana.tabs.setCurrentIndex(1)  # type: ignore[attr-defined]
    tr = ventana.transistors  # type: ignore[attr-defined]
    tr.library.select("NAND2")
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
    ventana.tabs.setCurrentIndex(1)  # type: ignore[attr-defined]
    tr.library.select("INV")
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
    from transim.ui.gui.canvas import SiliconItem

    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentIndex(1)  # type: ignore[attr-defined]
    tr.library.select("NOR2")
    tr.mode.set_value("silicon", emit=True)
    qapp.processEvents()  # type: ignore[attr-defined]
    item = tr.scene.cells[0]
    assert isinstance(item, SiliconItem)
    canal = item.lay.layer("channel")[0]
    centro = item.mapToScene(item.transistor_rect(canal.transistor).center())
    clic_en(tr.view, centro)
    assert tr.scene.selected_transistor == canal.transistor
    tr.mode.set_value("schematic", emit=True)


def test_ultima_operacion_chip_bloque_y_celda(ventana: object, qapp: object) -> None:
    from transim.ui.gui.canvas import SchematicItem, SiliconItem

    calcular(qapp, ventana)
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentIndex(1)  # type: ignore[attr-defined]
    tr.reveal("unit")
    netlist = tr.unit.netlist
    assert tr._target == ("unit", "")
    assert all(isinstance(i, SiliconItem) for i in tr.scene.cells)
    assert len(tr.scene.cells) == len(netlist.leaf_instances())
    assert not tr.mode.buttons["schematic"].isEnabled()  # el chip entero no tiene esquema

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
    assert "se muestra el silicio" in tr.info.text()


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
    item = tr.scene.cells[0]
    esquina = item.mapToScene(QPointF(item.geo.width - 6, item.geo.height - 6))
    textos = [a.text() for a in tr.context_menu(tr.view.mapFromScene(esquina)).actions()]
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
        v.tabs.setCurrentIndex(2)
        v.set_theme("oscuro")
        borrar(v)
        w = MainWindow(persist=True)
        assert w.tabs.currentIndex() == 2
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
    ventana.tabs.setCurrentIndex(1)  # type: ignore[attr-defined]
    assert tr._pending is None
    assert tr.calc is op.last


def test_atajos_de_programa_y_de_vista(ventana: object, qapp: object) -> None:
    pg = ventana.program  # type: ignore[attr-defined]
    ventana.tabs.setCurrentIndex(2)  # type: ignore[attr-defined]
    pg.source.setFocus()
    QTest.keyClick(pg.source, Qt.Key.Key_F5)
    esperar(qapp, lambda: pg.machine is not None and pg.load_button.isEnabled())
    QTest.keyClick(pg.source, Qt.Key.Key_F10)
    esperar(qapp, lambda: pg.machine.state.steps == 1 and pg.load_button.isEnabled())
    tr = ventana.transistors  # type: ignore[attr-defined]
    ventana.tabs.setCurrentIndex(1)  # type: ignore[attr-defined]
    tr.view.setFocus()
    QTest.keyClick(tr.view, Qt.Key.Key_S, Qt.KeyboardModifier.AltModifier)
    assert tr.silicon
    QTest.keyClick(tr.view, Qt.Key.Key_E, Qt.KeyboardModifier.AltModifier)
    assert not tr.silicon
