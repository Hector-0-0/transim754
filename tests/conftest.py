"""Configuración común de pytest.

Marcadores:
- ``slow``: pruebas lentas (exhaustivas o de miles de casos). Se excluyen con
  ``-m "not slow"`` en ``make test`` y en la integración continua.
- ``switch``: pruebas que usan el motor exacto transistor por transistor.
- ``cached``: pruebas que usan el motor con tablas extraídas de las celdas.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: prueba lenta; se excluye con -m 'not slow'")
    config.addinivalue_line("markers", "switch: usa el motor switch-level exacto")
    config.addinivalue_line("markers", "cached: usa el motor con tablas de verdad cacheadas")
