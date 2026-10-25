"""GUI de escritorio. Issues #25 y #26. Requiere ``make install-gui``."""

from __future__ import annotations

import os

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_ventana_principal() -> None:
    from transim.ui.gui.app import create_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ventana = create_window()
    assert "TranSim754" in ventana.windowTitle()
    assert app is not None


def test_operacion_y_programa_en_transistores() -> None:
    from transim.fpu.format import BINARY32
    from transim.ui.gui.app import ProgramTab, calculate, create_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calc = calculate(BINARY32, "add", 0x3FC00000, 0x40100000, "cached")
    assert calc.result.bits == 0x40700000
    assert calc.transistors > 0
    assert calc.toggles > 0
    assert "dbg_exp_diff" in calc.stages

    ventana = create_window()
    pestana = ventana.centralWidget().widget(2)
    assert isinstance(pestana, ProgramTab)
    from transim.cpu.assembler import assemble
    from transim.cpu.machine import Machine

    pestana._loaded(Machine(assemble(pestana.source.toPlainText())))
    pestana.machine.run()
    pestana.refresh()
    assert pestana.outputs.item(0).text().startswith("0x40700000")
    assert app is not None


def test_consola_de_ciclos() -> None:
    from transim.fpu.add_sub import fp_add_sub
    from transim.fpu.format import BINARY32
    from transim.ui.gui.app import cycles_report

    texto = cycles_report(fp_add_sub(BINARY32), 39, {"round": 10, "align": 3})
    assert "camino crítico: 176 celdas" in texto
    assert "5 ciclos" in texto
    assert "Ciclo 1" in texto
    assert "redondear y empaquetar" in texto


def test_pestana_de_transistores() -> None:
    from transim.core.transistor import Conduction
    from transim.fpu.format import BINARY16
    from transim.ui.gui.app import TransistorTab, calculate

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    pestana = TransistorTab()
    pestana.cell_box.setCurrentText("INV")
    assert pestana.scene.flowing == 1  # entrada 0: conduce el pMOS
    pestana.checks["a"].setChecked(True)
    assert pestana.engine.conduction(pestana.cell.transistors[1]) is Conduction.ON
    assert pestana.outputs.text() == "y = 0"
    pestana.cell_box.setCurrentText("FA")
    assert len(pestana.cell.transistors) == 28

    calc = calculate(BINARY16, "add", 0x3E00, 0x4080, "cached")
    pestana.show_calculation(calc)
    raiz = pestana.tree.topLevelItem(0)
    assert raiz.childCount() > 0
    bloque = next(
        raiz.child(i) for i in range(raiz.childCount()) if raiz.child(i).text(0).startswith("align")
    )
    assert any(raiz.child(i).text(0).startswith("selección") for i in range(raiz.childCount()))
    pestana._expand(bloque)
    hoja = bloque.child(0)
    while hoja.childCount():
        pestana._expand(hoja)
        hoja = hoja.child(0)
    pestana._select(hoja)
    assert "conducen" in pestana.info.text()
    assert app is not None
