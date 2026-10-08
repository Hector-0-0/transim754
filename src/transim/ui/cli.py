"""Interfaz de línea de comandos ``transim`` (capa L5).

Subcomandos (ver docs/04 y docs/05):

- ``transim calc 1.5 + 2.25 --format binary32 --trace``: una operación en la FPU de
  transistores, con los bits de operandos y resultado, flags y etapas.
- ``transim asm programa.t754 -o programa.bin``: ensambla.
- ``transim run programa.t754``: ensambla y ejecuta en la máquina T754.
- ``transim metrics --out docs/metricas``: genera las tablas de métricas.
- ``transim gui``: abre la interfaz gráfica.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transim import __version__

app = typer.Typer(
    name="transim",
    help="TranSim754: procesador con transistores simulados (IEEE 754).",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Punto de entrada del CLI."""


@app.command()
def version() -> None:
    """Muestra la versión instalada."""
    typer.echo(f"transim754 {__version__}")


@app.command()
def calc(
    a: Annotated[str, typer.Argument(help="Primer operando (decimal o 0x… en bits)")],
    op: Annotated[str, typer.Argument(help="Operación: + - * /")],
    b: Annotated[str, typer.Argument(help="Segundo operando (decimal o 0x… en bits)")],
    format: Annotated[str, typer.Option("--format", "-f", help="binary32 o binary16")] = "binary32",
    trace: Annotated[bool, typer.Option("--trace", help="Muestra las etapas")] = False,
    engine: Annotated[str, typer.Option(help="Motor: cached o switch")] = "cached",
) -> None:
    """Calcula ``a op b`` en la FPU de transistores."""
    raise NotImplementedError("pendiente: #31")


@app.command()
def asm(
    source: Annotated[Path, typer.Argument(help="Programa .t754")],
    output: Annotated[Path | None, typer.Option("-o", help="Archivo binario de salida")] = None,
) -> None:
    """Ensambla un programa .t754 (binario big-endian)."""
    raise NotImplementedError("pendiente: #31")


@app.command()
def run(
    source: Annotated[Path, typer.Argument(help="Programa .t754")],
    engine: Annotated[str, typer.Option(help="Motor: cached o switch")] = "cached",
) -> None:
    """Ensambla y ejecuta un programa en la máquina T754."""
    raise NotImplementedError("pendiente: #31")


@app.command()
def metrics(
    out: Annotated[Path, typer.Option(help="Directorio de salida")] = Path("docs/metricas"),
) -> None:
    """Genera las tablas de métricas en Markdown y CSV."""
    raise NotImplementedError("pendiente: #24")


@app.command()
def gui() -> None:
    """Abre la interfaz gráfica (requiere ``make install-gui``)."""
    raise NotImplementedError("pendiente: #25")


if __name__ == "__main__":
    app()
