"""Pruebas de humo del paquete y del CLI."""

from __future__ import annotations

from typer.testing import CliRunner

import transim
from transim.ui.cli import app


def test_paquete_expone_version() -> None:
    assert transim.__version__.count(".") == 2


def test_cli_version() -> None:
    resultado = CliRunner().invoke(app, ["version"])
    assert resultado.exit_code == 0
    assert transim.__version__ in resultado.output
