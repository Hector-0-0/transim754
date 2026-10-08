"""Interfaz de línea de comandos ``transim`` (capa L5).

Subcomandos (ver docs/04 y docs/05):

- ``transim calc 1.5 + 2.25 --format binary32 --trace``: una operación en la FPU de
  transistores, con los bits de operandos y resultado, flags y etapas.
- ``transim asm programa.t754 -o programa.bin``: ensambla.
- ``transim run programa.t754``: ensambla y ejecuta en la máquina T754.
- ``transim metrics --out docs/metricas``: genera las tablas de métricas.
- ``transim gui``: abre la interfaz gráfica.

Regla (ADR-0006): los resultados se calculan con el hardware de transistores. Mientras
una unidad no esté integrada, el CLI usa el modelo de referencia y lo **avisa** en la
salida; nunca presenta un resultado de referencia como si fuera de transistores.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, cast

import typer

from transim import __version__
from transim.core.unit import EngineName
from transim.cpu import isa
from transim.cpu.assembler import AssemblyError, assemble, to_bytes
from transim.fpu.format import FORMATS, FloatFormat, FPResult
from transim.reference import fpu as ref
from transim.reference.machine import MachineState

app = typer.Typer(
    name="transim",
    help="TranSim754: procesador con transistores simulados (IEEE 754).",
    no_args_is_help=True,
    add_completion=False,
)

_DIGITOS = isa.WORD_BITS // 4  # dígitos hexadecimales de una palabra
ANCHO_COLUMNA = 10  # ancho mínimo de la columna de valores en `calc`
OPERADORES = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
ISSUE_UNIDAD = {"add": 17, "sub": 17, "mul": 19, "div": 21}


@app.callback()
def main() -> None:
    """Punto de entrada del CLI."""


@app.command()
def version() -> None:
    """Muestra la versión instalada."""
    typer.echo(f"transim754 {__version__}")


# ------------------------------------------------------------------- utilidades
def _formato(nombre: str) -> FloatFormat:
    try:
        return FORMATS[nombre]
    except KeyError:
        raise typer.BadParameter(f"formato desconocido {nombre!r}; use {sorted(FORMATS)}") from None


def _motor(nombre: str) -> EngineName:
    if nombre not in ("cached", "switch"):
        raise typer.BadParameter("el motor debe ser 'cached' o 'switch'")
    return cast(EngineName, nombre)


def _operando(texto: str, fmt: FloatFormat) -> tuple[int, str]:
    """Bits del operando y una nota si la conversión decimal no fue exacta."""
    if texto.lower().startswith("0x"):
        try:
            bits = int(texto, 16)
        except ValueError:
            raise typer.BadParameter(f"hexadecimal inválido {texto!r}") from None
        if bits >> fmt.width:
            raise typer.BadParameter(f"{texto} no cabe en {fmt.width} bits")
        return bits, ""
    try:
        r = ref.from_decimal(fmt, texto)
    except (ValueError, ZeroDivisionError):
        raise typer.BadParameter(f"número inválido {texto!r}") from None
    return r.bits, " (redondeado al convertir)" if r.flags.inexact else ""


def _campos(fmt: FloatFormat, bits: int) -> str:
    s, e, f = fmt.fields(bits)
    return f"{s} | {e:0{fmt.exp_bits}b} | {f:0{fmt.frac_bits}b}"


def _valor(fmt: FloatFormat, bits: int) -> str:
    return f"{ref.to_float(fmt, bits):.9g}"


def _hex(fmt: FloatFormat, bits: int) -> str:
    return f"0x{bits:0{fmt.width // 4}X}"


def _calcular_en_hardware(
    fmt: FloatFormat, operacion: str, a: int, b: int, motor: EngineName
) -> tuple[FPResult, dict[str, int | None], int, float]:
    """Resultado de la unidad de transistores, sus salidas, transistores y segundos."""
    from transim.fpu.add_sub import FPAddSub
    from transim.fpu.div import FPDiv
    from transim.fpu.mul import FPMul

    inicio = time.perf_counter()
    unidad: FPAddSub | FPMul | FPDiv
    if operacion in ("add", "sub"):
        unidad = FPAddSub(fmt, motor)
        entradas = {"a": a, "b": b, "sub": int(operacion == "sub")}
    elif operacion == "mul":
        unidad = FPMul(fmt, motor)
        entradas = {"a": a, "b": b}
    else:
        unidad = FPDiv(fmt, motor)
        entradas = {"a": a, "b": b}
    salidas = unidad.evaluate(entradas)
    return (
        FPResult.from_outputs({k: v for k, v in salidas.items() if not k.startswith("dbg_")}),
        salidas,
        unidad.transistor_count(),
        time.perf_counter() - inicio,
    )


# ------------------------------------------------------------------------ calc
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
    fmt = _formato(format)
    motor = _motor(engine)
    if op not in OPERADORES:
        raise typer.BadParameter(f"operación desconocida {op!r}; use + - * /")
    operacion = OPERADORES[op]
    bits_a, nota_a = _operando(a, fmt)
    bits_b, nota_b = _operando(b, fmt)

    origen: str
    salidas: dict[str, int | None] = {}
    try:
        resultado, salidas, transistores, segundos = _calcular_en_hardware(
            fmt, operacion, bits_a, bits_b, motor
        )
        origen = f"transistores ({transistores} T, motor {motor}, {segundos * 1000:.1f} ms)"
    except NotImplementedError:
        resultado = ref.OPERATIONS[op](fmt, bits_a, bits_b)
        origen = (
            f"MODELO DE REFERENCIA — la unidad de transistores de '{op}' aún no está "
            f"integrada (issue #{ISSUE_UNIDAD[operacion]})"
        )

    ancho = max(len(a), len(b), ANCHO_COLUMNA)
    typer.echo(f"Formato {fmt.name}   (s | exponente | fracción)")
    typer.echo(f"  a      = {a:>{ancho}}  {_hex(fmt, bits_a)}  {_campos(fmt, bits_a)}{nota_a}")
    typer.echo(f"  b      = {b:>{ancho}}  {_hex(fmt, bits_b)}  {_campos(fmt, bits_b)}{nota_b}")
    r = resultado.bits
    typer.echo(f"  a {op} b  = {_valor(fmt, r):>{ancho}}  {_hex(fmt, r)}  {_campos(fmt, r)}")
    typer.echo(f"  flags  = {resultado.flags}")
    typer.echo(f"  cálculo: {origen}")

    if trace:
        typer.echo("Traza:")
        for nombre, x in (("a", bits_a), ("b", bits_b), ("resultado", r)):
            typer.echo(f"  {nombre:<10} clase {fmt.classify(x).value}")
        etapas = {k: v for k, v in salidas.items() if k.startswith("dbg_")}
        if etapas:
            for nombre, v in etapas.items():
                typer.echo(f"  {nombre:<14} {'X' if v is None else hex(v)}")
        elif salidas:
            typer.echo("  (la unidad no expone buses dbg_ de etapas)")
        else:
            typer.echo("  (etapas disponibles cuando la unidad de transistores esté integrada)")


# ------------------------------------------------------------------- asm y run
def _ensamblar(source: Path) -> list[int]:
    try:
        return assemble(source.read_text(encoding="utf-8"), filename=str(source))
    except AssemblyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None
    except OSError as e:
        typer.echo(f"{source}: {e.strerror}", err=True)
        raise typer.Exit(1) from None


@app.command()
def asm(
    source: Annotated[Path, typer.Argument(help="Programa .t754")],
    output: Annotated[Path | None, typer.Option("-o", help="Archivo binario de salida")] = None,
) -> None:
    """Ensambla un programa .t754 (binario big-endian)."""
    palabras = _ensamblar(source)
    if output is not None:
        output.write_bytes(to_bytes(palabras))
        typer.echo(f"{len(palabras)} palabras escritas en {output}")
        return
    for i, w in enumerate(palabras):
        typer.echo(f"{i:04d}: 0x{w:0{_DIGITOS}X}")


def _ejecutar(palabras: list[int], motor: EngineName) -> tuple[MachineState, str]:
    try:
        from transim.cpu.machine import Machine

        return Machine(palabras, engine=motor).run(), f"máquina de transistores (motor {motor})"
    except NotImplementedError:
        from transim.reference.machine import run as run_referencia

        return run_referencia(palabras), (
            "MODELO DE REFERENCIA — la máquina de transistores aún no está integrada (issue #30)"
        )


def _fsr(fsr: int) -> str:
    from transim.fpu.format import Flags

    enteros = [
        n
        for n, bit in (("C", isa.FSR_C), ("V", isa.FSR_V), ("Z", isa.FSR_Z), ("N", isa.FSR_N))
        if fsr >> bit & 1
    ]
    return f"0x{fsr:0{_DIGITOS}X}  flags {Flags.from_bits(fsr)}  enteros {'|'.join(enteros) or '—'}"


@app.command()
def run(
    source: Annotated[Path, typer.Argument(help="Programa .t754")],
    engine: Annotated[str, typer.Option(help="Motor: cached o switch")] = "cached",
) -> None:
    """Ensambla y ejecuta un programa en la máquina T754."""
    palabras = _ensamblar(source)
    estado, origen = _ejecutar(palabras, _motor(engine))
    fmt = FORMATS["binary32"]
    typer.echo(f"Programa {source}: {len(palabras)} palabras, {estado.steps} instrucciones")
    typer.echo(f"Ejecución: {origen}")
    for i, valor in enumerate(estado.outputs):
        typer.echo(f"  OUT[{i}] = 0x{valor:0{_DIGITOS}X}  ({_valor(fmt, valor)})")
    typer.echo(f"  FSR    = {_fsr(estado.fsr)}")
    regs = "  ".join(f"F{i}=0x{v:0{_DIGITOS}X}" for i, v in enumerate(estado.regs))
    typer.echo(f"  {regs}")


# ------------------------------------------------------------- otros módulos
@app.command()
def metrics(
    out: Annotated[Path, typer.Option(help="Directorio de salida")] = Path("docs/metricas"),
) -> None:
    """Genera las tablas de métricas en Markdown y CSV."""
    from transim.metrics.report import generate_reports

    for ruta in generate_reports(out):
        typer.echo(str(ruta))


@app.command()
def gui() -> None:
    """Abre la interfaz gráfica (requiere ``make install-gui``)."""
    from transim.ui.gui.app import main as gui_main

    raise typer.Exit(gui_main())


if __name__ == "__main__":
    app()
