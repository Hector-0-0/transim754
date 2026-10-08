"""GUI de escritorio (responsable: Yenny). Issues #25 y #26. Requiere ``make install-gui``."""

from __future__ import annotations

import os

import pytest

from pendientes import pendiente

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pendiente(25)
def test_ventana_principal() -> None:
    from transim.ui.gui.app import create_window

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ventana = create_window()
    assert "TranSim754" in ventana.windowTitle()
    assert app is not None
