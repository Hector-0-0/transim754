"""Una sola ``QApplication`` para todas las pruebas de la GUI.

Si cada prueba crea la aplicación en una variable local, Python puede destruirla antes
que los widgets de la prueba y el proceso termina con una violación de segmento al
salir. Aquí se crea una vez y vive hasta el final de la sesión.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp() -> Iterator[object]:
    widgets = pytest.importorskip("PySide6.QtWidgets")
    app = widgets.QApplication.instance() or widgets.QApplication([])
    yield app
    for widget in widgets.QApplication.topLevelWidgets():
        widget.close()
