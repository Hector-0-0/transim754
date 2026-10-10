"""Validación de un módulo: ``make validar M=<modulo>``.

Comprueba, en este orden:

1. **Pruebas:** ejecuta las pruebas del módulo (las lentas solo con ``--completo``).
2. **Pendientes:** no queda ningún ``@pendiente(N)`` de los issues del módulo en ``tests/``.
3. **Stubs:** no queda ningún ``NotImplementedError("pendiente: #N")`` del módulo en ``src/``.
4. **Métricas:** construye los circuitos del módulo que ya existan e informa transistores y
   conmutaciones medias por estímulo aleatorio (informativo; no decide el veredicto).

Termina con un resumen PASS/FAIL y código de salida 0 (PASS) o 1 (FAIL).

Uso::

    python scripts/validar.py cells
    python scripts/validar.py fpu-addsub --completo
    python scripts/validar.py --lista
"""

from __future__ import annotations

import argparse
import random
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


@dataclass
class Modulo:
    """Qué se valida para un módulo."""

    descripcion: str
    pruebas: list[str]
    issues: list[int]
    fuentes: list[str]
    circuitos: list[tuple[str, Callable[[], object]]] = field(default_factory=list)


def _circuitos_cells() -> list[tuple[str, Callable[[], object]]]:
    from transim.cells import combinational as c
    from transim.cells import sequential as s

    nombres = [
        "inv",
        "nand2",
        "nor2",
        "and2",
        "or2",
        "xor2",
        "xnor2",
        "mux2",
        "half_adder",
        "full_adder",
    ]
    return [(n.upper(), getattr(c, n)) for n in nombres] + [
        ("DLATCH", s.d_latch),
        ("DFF", s.dff),
        ("REG32", lambda: s.register(32)),
    ]


def _circuitos_blocks() -> list[tuple[str, Callable[[], object]]]:
    from transim.blocks import adders, comparator, lzc, mux, shifter, subtractor

    return [
        ("RCA32", lambda: adders.ripple_carry_adder(32)),
        ("CLA32", lambda: adders.carry_lookahead_adder(32)),
        ("ADDSUB32", lambda: subtractor.adder_subtractor(32)),
        ("CMP10", lambda: comparator.magnitude_comparator(10)),
        ("MUX8x32", lambda: mux.mux_n(32, 8)),
        ("SHR27", lambda: shifter.barrel_shifter(27, "right")),
        ("SHL27", lambda: shifter.barrel_shifter(27, "left")),
        ("LZC27", lambda: lzc.leading_zero_counter(27)),
    ]


def _circuitos_alu() -> list[tuple[str, Callable[[], object]]]:
    from transim.alu.int_alu import int_alu

    return [("ALU32", int_alu)]


def _circuitos_fpu(partes: list[str]) -> list[tuple[str, Callable[[], object]]]:
    from transim.fpu import add_sub, codec, div, mul, rounding, special
    from transim.fpu.format import BINARY16, BINARY32

    todos: dict[str, list[tuple[str, Callable[[], object]]]] = {
        "comun": [
            ("UNPACK_binary32", lambda: codec.unpacker(BINARY32)),
            ("CLASS_binary32", lambda: special.classifier(BINARY32)),
            ("ROUND_binary32", lambda: rounding.round_and_pack(BINARY32)),
        ],
        "addsub": [
            ("FADDSUB_binary16", lambda: add_sub.fp_add_sub(BINARY16)),
            ("FADDSUB_binary32", lambda: add_sub.fp_add_sub(BINARY32)),
        ],
        "muldiv": [
            ("ARRMUL24", lambda: mul.array_multiplier(24)),
            ("FMUL_binary32", lambda: mul.fp_multiplier(BINARY32)),
            ("NRDIV24x27", lambda: div.nonrestoring_divider(24, 27)),
            ("FDIV_binary32", lambda: div.fp_divider(BINARY32)),
        ],
    }
    return [c for p in partes for c in todos[p]]


def _circuitos_cpu() -> list[tuple[str, Callable[[], object]]]:
    from transim.cpu.decoder import instruction_decoder
    from transim.cpu.registers import register_file

    return [("DECODER", instruction_decoder), ("REGFILE8x32", register_file)]


MODULOS: dict[str, Modulo] = {
    "core": Modulo("Núcleo L0 (simulador)", ["tests/core"], [], ["src/transim/core"]),
    "reference": Modulo(
        "Modelos de referencia y oráculo",
        ["tests/reference", "tests/oracle"],
        [],
        ["src/transim/reference"],
    ),
    "cells": Modulo(
        "Celdas L1 (Jairo)", ["tests/cells"], [1, 2, 3, 4, 5, 6], ["src/transim/cells"], []
    ),
    "blocks": Modulo(
        "Bloques L2 (Ronald)", ["tests/blocks"], [7, 8, 9, 10, 11, 12, 14], ["src/transim/blocks"]
    ),
    "alu": Modulo("ALU entera (Ronald)", ["tests/alu"], [13], ["src/transim/alu"]),
    "fpu-addsub": Modulo(
        "FPU común y FADD/FSUB (Daniel)",
        [
            "tests/fpu/test_formato.py",
            "tests/fpu/test_codec_especiales.py",
            "tests/fpu/test_redondeo.py",
            "tests/fpu/test_suma_resta.py",
        ],
        [15, 16, 17],
        [
            "src/transim/fpu/codec.py",
            "src/transim/fpu/special.py",
            "src/transim/fpu/rounding.py",
            "src/transim/fpu/add_sub.py",
        ],
    ),
    "fpu-muldiv": Modulo(
        "FMUL/FDIV (Fabricio)",
        ["tests/fpu/test_multiplicacion.py", "tests/fpu/test_division.py"],
        [18, 19, 20, 21],
        ["src/transim/fpu/mul.py", "src/transim/fpu/div.py"],
    ),
    "metrics": Modulo("Métricas (Yenny)", ["tests/metrics"], [22, 23, 24], ["src/transim/metrics"]),
    "gui": Modulo("GUI (Yenny)", ["tests/ui/test_gui.py"], [25, 26], ["src/transim/ui/gui"]),
    "cpu": Modulo("CPU T754 (Héctor)", ["tests/cpu"], [29, 30], ["src/transim/cpu"]),
    "cli": Modulo("CLI (Héctor)", ["tests/ui/test_cli.py"], [31], ["src/transim/ui/cli.py"]),
    "ai": Modulo("Asistente (Héctor)", ["tests/assistant"], [32], ["src/transim/assistant"]),
}
CIRCUITOS: dict[str, Callable[[], list[tuple[str, Callable[[], object]]]]] = {
    "cells": _circuitos_cells,
    "blocks": _circuitos_blocks,
    "alu": _circuitos_alu,
    "fpu-addsub": lambda: _circuitos_fpu(["comun", "addsub"]),
    "fpu-muldiv": lambda: _circuitos_fpu(["muldiv"]),
    "cpu": _circuitos_cpu,
}


def _archivos(rutas: list[str], patron: str) -> list[Path]:
    salida: list[Path] = []
    for r in rutas:
        p = RAIZ / r
        salida.extend(sorted(p.rglob(patron)) if p.is_dir() else [p] if p.exists() else [])
    return salida


def buscar(rutas: list[str], regex: re.Pattern[str]) -> list[str]:
    """Líneas ``archivo:línea`` que coinciden con ``regex``."""
    hallazgos = []
    for archivo in _archivos(rutas, "*.py"):
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if regex.search(linea):
                hallazgos.append(f"{archivo.relative_to(RAIZ)}:{n}")
    return hallazgos


def pendientes_en_tablas(issues: list[int]) -> list[str]:
    """Issues del módulo que siguen listados en conjuntos ``PENDIENTES = {…}`` de las pruebas."""
    hallazgos = []
    regex = re.compile(r"^PENDIENTES\b[^=]*=\s*\{([^}]*)\}")
    for archivo in _archivos(["tests"], "*.py"):
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            m = regex.match(linea)
            if m:
                numeros = {int(x) for x in re.findall(r"\d+", m.group(1))}
                for i in sorted(numeros & set(issues)):
                    hallazgos.append(f"{archivo.relative_to(RAIZ)}:{n} (#{i} en PENDIENTES)")
    return hallazgos


def correr_pruebas(rutas: list[str], completo: bool) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *rutas]
    if not completo:
        cmd[3:3] = ["-m", "not slow"]
    r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)
    resumen = (r.stdout.strip().splitlines() or ["(sin salida)"])[-1]
    return r.returncode in (0, 5), resumen


def medir(nombre: str, construir: Callable[[], object]) -> str:
    from transim.core import CachedEngine, Netlist
    from transim.metrics.count import count

    try:
        nl = construir()
    except NotImplementedError:
        return f"  {nombre:<18} (pendiente)"
    assert isinstance(nl, Netlist)
    c = count(nl)
    if nl.sequential:
        return f"  {nombre:<18} {c.total:>7} T   (secuencial: sin estímulos aleatorios)"
    motor = CachedEngine(nl, max_events=10 * len(nl.nodes) + 1000)
    rng = random.Random(754)
    pasos = 20
    motor.reset_counters()
    inicio = time.perf_counter()
    for _ in range(pasos):
        entradas: dict[str, int] = {
            b: rng.getrandbits(len(bits)) for b, bits in nl.input_buses.items()
        }
        bits_de_bus = {n.id for bits in nl.input_buses.values() for n in bits}
        entradas |= {
            n: rng.getrandbits(1) for n, node in nl.inputs.items() if node.id not in bits_de_bus
        }
        motor.set_inputs(entradas)
    ms = (time.perf_counter() - inicio) * 1000 / pasos
    st = motor.stats()
    return (
        f"  {nombre:<18} {c.total:>7} T   {st.node_toggles / pasos:>8.1f} conm./estímulo"
        f"   {ms:>7.2f} ms/estímulo"
    )


def validar(nombre: str, completo: bool) -> bool:
    m = MODULOS[nombre]
    print(f"== Validación de '{nombre}': {m.descripcion}")
    ok_pruebas, resumen = correr_pruebas(m.pruebas, completo)
    tipo = "completas" if completo else "rápidas"
    print(f"[{'PASS' if ok_pruebas else 'FAIL'}] pruebas ({tipo}): {resumen}")

    if m.issues:
        alternativas = "|".join(map(str, m.issues))
        patron = re.compile(rf"pendiente\(({alternativas})\)")
        # tests/pendientes.py define el marcador y lo cita en su documentación.
        usos = [h for h in buscar(["tests"], patron) if not h.startswith("tests/pendientes.py:")]
        restantes = usos + pendientes_en_tablas(m.issues)
        ok_pend = not restantes
        print(f"[{'PASS' if ok_pend else 'FAIL'}] pendientes en tests/: {len(restantes)}")
        for r in restantes[:10]:
            print(f"         {r}")
        stubs = buscar(m.fuentes, re.compile(rf"pendiente: #({alternativas})\b"))
        ok_stub = not stubs
        print(f"[{'PASS' if ok_stub else 'FAIL'}] stubs sin implementar en src/: {len(stubs)}")
        for s in stubs[:10]:
            print(f"         {s}")
    else:
        ok_pend = ok_stub = True

    if nombre in CIRCUITOS:
        print("[INFO] métricas (motor cached, 20 estímulos aleatorios):")
        for etiqueta, construir in CIRCUITOS[nombre]():
            print(medir(etiqueta, construir))

    ok = ok_pruebas and ok_pend and ok_stub
    print(f"== RESULTADO: {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida un módulo de TranSim754.")
    parser.add_argument("modulo", nargs="?", help="nombre del módulo (ver --lista)")
    parser.add_argument("--completo", action="store_true", help="incluye las pruebas lentas")
    parser.add_argument("--lista", action="store_true", help="muestra los módulos disponibles")
    args = parser.parse_args()
    if args.lista or not args.modulo:
        for k, m in MODULOS.items():
            issues = ", ".join(f"#{i}" for i in m.issues) or "—"
            print(f"  {k:<11} {m.descripcion}  [{issues}]")
        return 0 if args.lista else 2
    if args.modulo not in MODULOS:
        print(f"Módulo desconocido {args.modulo!r}. Use --lista.")
        return 2
    return 0 if validar(args.modulo, args.completo) else 1


if __name__ == "__main__":
    raise SystemExit(main())
