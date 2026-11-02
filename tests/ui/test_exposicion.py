"""Modo exposición de la GUI (ADR-0019): qué se oculta, qué sigue igual y el texto.

En modo exposición (el de ``transim gui``) no hay menús, atajos de teclado, pestaña
Programa, historial ni panel de detalle de Transistores; nada se elimina: con
``full=True`` (``transim gui --completo``) todo vuelve.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPointF, Qt, QThreadPool  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QLabel,
    QListWidget,
    QTabWidget,
    QTreeWidget,
    QWidget,
)

SEPARADOR = " · "
"""El punto medio entre palabras que la interfaz ya no usa."""


def esperar(app: object, condicion: Callable[[], bool], segundos: float = 20.0) -> None:
    fin = time.monotonic() + segundos
    while not condicion():
        QThreadPool.globalInstance().waitForDone(20)
        app.processEvents()  # type: ignore[attr-defined]
        assert time.monotonic() < fin, "la interfaz no respondió a tiempo"
    app.processEvents()  # type: ignore[attr-defined]


def abrir(qapp: object, full: bool) -> Iterator[object]:
    from transim.ui.gui.app import create_window

    v = create_window(full=full)
    v.resize(1440, 900)
    v.show()
    qapp.processEvents()  # type: ignore[attr-defined]
    yield v
    QThreadPool.globalInstance().waitForDone(5000)
    v.close()
    v.deleteLater()


@pytest.fixture
def expo(qapp: object) -> Iterator[object]:
    yield from abrir(qapp, full=False)


@pytest.fixture
def completa(qapp: object) -> Iterator[object]:
    yield from abrir(qapp, full=True)


def calcular(app: object, v: object) -> None:
    """Calcula −1.5 + 2.25. Las unidades se comparten entre pruebas: con otra operación
    que la de los demás archivos, la siguiente prueba sí tiene conmutaciones."""
    op = v.operation  # type: ignore[attr-defined]
    op.a.set_text("-1.5")
    op.run()
    esperar(app, lambda: op.last is not None and not op._busy)


def textos_visibles(raiz: QWidget) -> list[str]:
    """Texto de etiquetas, botones, pestañas, listas y árboles visibles bajo ``raiz``."""
    out: list[str] = []
    for w in raiz.findChildren(QWidget):
        if not w.isVisible():
            continue
        if isinstance(w, QLabel | QAbstractButton):
            out.append(w.text())
        elif isinstance(w, QTabWidget):
            out += [w.tabText(k) for k in range(w.count()) if w.isTabVisible(k)]
        elif isinstance(w, QListWidget):
            out += [w.item(k).text() for k in range(w.count())]
        elif isinstance(w, QTreeWidget):
            for k in range(w.topLevelItemCount()):
                item = w.topLevelItem(k)
                out.append(item.text(0))
                out += [item.child(j).text(0) for j in range(item.childCount())]
    return out


# ------------------------------------------------------------------ oculto
def test_sin_menus_ni_programa_ni_guia(expo: object) -> None:
    assert not expo.menuBar().isVisible()  # type: ignore[attr-defined]
    tabs = expo.tabs  # type: ignore[attr-defined]
    visibles = [tabs.tabText(k) for k in range(tabs.count()) if tabs.isTabVisible(k)]
    assert visibles == ["Operación", "Recorrido", "Transistores"]
    assert expo.program is not None  # type: ignore[attr-defined]  # existe, solo oculta
    barra = [w.text() for w in expo.statusBar().findChildren(QLabel)]  # type: ignore[attr-defined]
    assert not any("F1" in t for t in barra)


def test_modo_completo_muestra_todo(completa: object) -> None:
    assert completa.menuBar().isVisible()  # type: ignore[attr-defined]
    tabs = completa.tabs  # type: ignore[attr-defined]
    assert all(tabs.isTabVisible(k) for k in range(tabs.count()))
    op = completa.operation  # type: ignore[attr-defined]
    assert op.details.isTabVisible(op.details.indexOf(op.history_list))
    assert not completa.transistors.inspector.isHidden()  # type: ignore[attr-defined]


def test_sin_atajos_de_teclado(expo: object, completa: object) -> None:
    acciones = [a for m in expo.menuBar().findChildren(QtWidgets.QMenu) for a in m.actions()]  # type: ignore[attr-defined]
    assert acciones
    assert all(a.shortcut().isEmpty() for a in acciones)
    assert not any(sc.isEnabled() for sc in expo.transistors.shortcuts)  # type: ignore[attr-defined]
    assert not any(sc.isEnabled() for sc in expo.operation.shortcuts)  # type: ignore[attr-defined]
    # En el modo completo siguen.
    menus = completa.menuBar().findChildren(QtWidgets.QMenu)  # type: ignore[attr-defined]
    assert any(not a.shortcut().isEmpty() for m in menus for a in m.actions())
    assert all(sc.isEnabled() for sc in completa.transistors.shortcuts)  # type: ignore[attr-defined]


def test_alt_s_no_cambia_de_vista(expo: object) -> None:
    tr = expo.transistors  # type: ignore[attr-defined]
    expo.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    tr.library.select("NAND2")
    tr.mode.set_value("gates", emit=True)
    QTest.keyClick(tr.view, Qt.Key.Key_S, Qt.KeyboardModifier.AltModifier)
    assert tr.mode.value() == "gates"


def test_siempre_oscuro(expo: object) -> None:
    assert expo.theme_choice == "oscuro"  # type: ignore[attr-defined]
    expo._system_theme_changed()  # type: ignore[attr-defined]  # el sistema cambia: nada
    assert expo.theme_choice == "oscuro"  # type: ignore[attr-defined]


def test_sin_historial_ni_detalle(expo: object, qapp: object) -> None:
    calcular(qapp, expo)
    op = expo.operation  # type: ignore[attr-defined]
    assert not op.details.isTabVisible(op.details.indexOf(op.history_list))
    assert op.tiles["eventos"].isHidden()
    assert op.history  # el historial se sigue guardando
    tr = expo.transistors  # type: ignore[attr-defined]
    expo.tabs.setCurrentWidget(tr)  # type: ignore[attr-defined]
    qapp.processEvents()  # type: ignore[attr-defined]
    assert tr.inspector.isHidden()
    assert tr.info.isHidden()
    tr.library.select("XOR2")
    tr.mode.set_value("silicon", emit=True)
    assert not tr.layer_row.isVisible()
    rec = expo.walkthrough  # type: ignore[attr-defined]
    expo.tabs.setCurrentWidget(rec)  # type: ignore[attr-defined]
    qapp.processEvents()  # type: ignore[attr-defined]
    assert rec.keys.isHidden()
    assert rec.p_links.isHidden()


# ------------------------------------------------------------------ texto
def test_ningun_texto_visible_usa_el_punto_medio(expo: object, qapp: object) -> None:
    calcular(qapp, expo)
    vistos: list[str] = []
    tabs = expo.tabs  # type: ignore[attr-defined]
    tr = expo.transistors  # type: ignore[attr-defined]
    for k in range(tabs.count()):
        if not tabs.isTabVisible(k):
            continue
        tabs.setCurrentIndex(k)
        qapp.processEvents()  # type: ignore[attr-defined]
        vistos += textos_visibles(expo)  # type: ignore[arg-type]
    tabs.setCurrentWidget(tr)
    for objetivo in ("unit", "mant_addsub", "order"):
        tr.reveal(objetivo)
        for modo in ("gates", "schematic", "silicon"):
            if tr.mode.buttons[modo].isEnabled():
                tr.mode.set_value(modo, emit=True)
                qapp.processEvents()  # type: ignore[attr-defined]
                vistos += textos_visibles(expo)  # type: ignore[arg-type]
    con_punto = sorted({t for t in vistos if SEPARADOR in t})
    assert not con_punto, con_punto


def test_nombres_naturales_de_las_unidades() -> None:
    from transim.ui.gui.model import unit_title

    assert unit_title("FADDSUB_binary32") == "Suma y resta en binary32"
    assert unit_title("FMUL_binary16") == "Multiplicación en binary16"
    assert unit_title("FDIV_binary32") == "División en binary32"
    assert unit_title("ALU32") == "ALU32"


# ------------------------------------------------------------------ recorrido
def pastilla(rec: object, titulo: str) -> object:
    escena = rec.diagram.scene()  # type: ignore[attr-defined]
    return next(i for i in escena.items() if type(i).__name__ == "PillItem" and i.title == titulo)


def test_clic_en_entradas_y_resultado(expo: object, qapp: object) -> None:
    """Un clic en las entradas vuelve al paso 1; en el resultado, muestra todo. Las dos
    cajas siguen en el diagrama después del clic."""
    calcular(qapp, expo)
    rec = expo.walkthrough  # type: ignore[attr-defined]
    expo.tabs.setCurrentWidget(rec)  # type: ignore[attr-defined]
    qapp.processEvents()  # type: ignore[attr-defined]
    rec.go(3)
    vista = rec.diagram
    for titulo, paso in (("resultado", rec.count - 1), ("entradas", 0)):
        centro: QPointF = pastilla(rec, titulo).sceneBoundingRect().center()  # type: ignore[attr-defined]
        QTest.mouseClick(
            vista.viewport(), Qt.MouseButton.LeftButton, pos=vista.mapFromScene(centro)
        )
        qapp.processEvents()  # type: ignore[attr-defined]
        assert rec.index == paso
        for nombre in ("entradas", "resultado"):
            item = pastilla(rec, nombre)
            assert item.isVisible()  # type: ignore[attr-defined]
    assert pastilla(rec, "entradas").lit  # type: ignore[attr-defined]


# ------------------------------------------------------------------ CLI
def test_la_opcion_completo_esta_en_la_ayuda() -> None:
    from typer.testing import CliRunner

    from transim.ui.cli import app

    salida = CliRunner().invoke(app, ["gui", "--help"]).output
    assert "--completo" in salida
