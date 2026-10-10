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
    pestana = ventana.centralWidget().widget(1)
    assert isinstance(pestana, ProgramTab)
    from transim.cpu.assembler import assemble
    from transim.cpu.machine import Machine

    pestana._loaded(Machine(assemble(pestana.source.toPlainText())))
    pestana.machine.run()
    pestana.refresh()
    assert pestana.outputs.item(0).text().startswith("0x40700000")
    assert app is not None
