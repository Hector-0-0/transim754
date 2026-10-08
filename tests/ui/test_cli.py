"""CLI ``transim`` (responsable: Héctor). Issues #31 y #24."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from cpu.programas import EJEMPLOS
from pendientes import pendiente
from transim.ui.cli import app

runner = CliRunner()


def invocar(*args: str) -> Result:
    """Ejecuta el CLI y re-lanza la excepción interna (para que xfail la reconozca)."""
    resultado = runner.invoke(app, list(args))
    if resultado.exception is not None and not isinstance(resultado.exception, SystemExit):
        raise resultado.exception
    return resultado


def test_calc_binary32() -> None:
    r = invocar("calc", "1.5", "+", "2.25", "--format", "binary32")
    assert r.exit_code == 0
    assert "0x40700000" in r.output
    assert "3.75" in r.output


def test_calc_con_traza_y_flags() -> None:
    r = invocar("calc", "1", "/", "0", "--trace")
    assert "0x7F800000" in r.output
    assert "DZ" in r.output


def test_calc_operador_invalido() -> None:
    r = invocar("calc", "1", "%", "2")
    assert r.exit_code != 0


def test_asm_y_run(tmp_path: Path) -> None:
    salida = tmp_path / "suma.bin"
    r = invocar("asm", str(EJEMPLOS / "suma_simple.t754"), "-o", str(salida))
    assert r.exit_code == 0
    assert salida.read_bytes()[:4] == bytes([0x01, 0x20, 0x00, 0x00])
    r = invocar("run", str(EJEMPLOS / "suma_simple.t754"))
    assert "0x40700000" in r.output


@pendiente(24)
def test_metrics(tmp_path: Path) -> None:
    r = invocar("metrics", "--out", str(tmp_path))
    assert r.exit_code == 0
    assert (tmp_path / "transistores.md").is_file()


@pytest.mark.parametrize("comando", ["calc", "asm", "run", "metrics", "gui", "version"])
def test_comandos_registrados(comando: str) -> None:
    assert runner.invoke(app, [comando, "--help"]).exit_code == 0
