"""Marcador de pruebas escritas por adelantado para módulos aún no implementados.

``@pendiente(7)`` equivale a ``xfail(strict=True, raises=NotImplementedError)`` con
``reason="pendiente: #7"``:

- mientras el módulo sea un stub (``NotImplementedError``), la prueba cuenta como
  fallo esperado;
- si el módulo está implementado pero la prueba falla por otra razón (resultado
  incorrecto), la prueba **falla de verdad**: no se ocultan errores;
- si la prueba pasa, ``strict=True`` la convierte en fallo (XPASS) para obligar al
  responsable a quitar el marcador. ``make validar`` exige que no quede ninguno.
"""

from __future__ import annotations

import pytest


def pendiente(issue: int) -> pytest.MarkDecorator:
    """Marca una prueba como pendiente del issue ``#issue``."""
    return pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=f"pendiente: #{issue}")
