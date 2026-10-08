"""Interfaz de línea de comandos `transim` (capa L5).

Los subcomandos `calc`, `run`, `asm`, `metrics` y `gui` se incorporan a medida que
se implementan las capas inferiores (ver docs/04_isa_t754.md y docs/05_metricas.md).
"""

from __future__ import annotations

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


if __name__ == "__main__":
    app()
