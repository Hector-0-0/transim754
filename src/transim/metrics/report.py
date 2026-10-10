"""Reportes de métricas en Markdown y CSV. ADR-0013, docs/05 §5."""

from __future__ import annotations

import csv
import random
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path

from transim.core.engine_switch import InputValue
from transim.core.netlist import Netlist
from transim.core.unit import make_engine
from transim.metrics.activity import measure_activity
from transim.metrics.count import count
from transim.metrics.critical_path import cell_depth

ACTIVITY_OPERATIONS = 12
"""Estímulos aleatorios por módulo en la tabla de actividad."""

ADDER_WIDTHS = (8, 16, 32)
"""Anchos de la comparación RCA frente a CLA."""

Builder = Callable[[], Netlist]


def _modules() -> list[tuple[str, Builder]]:
    """Módulos medidos, de la celda a la máquina, con su constructor."""
    from transim.alu.int_alu import int_alu
    from transim.blocks import adders, comparator, lzc, mux, shifter, subtractor
    from transim.cells.library import CELLS
    from transim.cells.sequential import register
    from transim.cpu.decoder import instruction_decoder
    from transim.cpu.isa import WORD_BITS
    from transim.cpu.registers import register_file
    from transim.fpu import add_sub, div, mul
    from transim.fpu.format import BINARY16, BINARY32
    from transim.fpu.rounding import round_and_pack

    mods: list[tuple[str, Builder]] = list(CELLS.items())
    mods += [
        (f"REG{WORD_BITS}", lambda: register(WORD_BITS)),
        (f"RCA{WORD_BITS}", lambda: adders.ripple_carry_adder(WORD_BITS)),
        (f"CLA{WORD_BITS}", lambda: adders.carry_lookahead_adder(WORD_BITS)),
        (f"ADDSUB{WORD_BITS}", lambda: subtractor.adder_subtractor(WORD_BITS)),
        (f"CMP{WORD_BITS}", lambda: comparator.magnitude_comparator(WORD_BITS)),
        (f"MUX8x{WORD_BITS}", lambda: mux.mux_n(WORD_BITS, 8)),
        ("SHR27", lambda: shifter.barrel_shifter(BINARY32.precision + 3, "right")),
        ("LZC28", lambda: lzc.leading_zero_counter(BINARY32.precision + 4)),
        (f"ALU{WORD_BITS}", lambda: int_alu(WORD_BITS)),
        ("DECODER", instruction_decoder),
        ("REGFILE", register_file),
    ]
    for fmt in (BINARY16, BINARY32):
        mods += [
            (f"ROUND_{fmt.name}", partial(round_and_pack, fmt)),
            (f"FADDSUB_{fmt.name}", partial(add_sub.fp_add_sub, fmt)),
            (f"FMUL_{fmt.name}", partial(mul.fp_multiplier, fmt)),
            (f"FDIV_{fmt.name}", partial(div.fp_divider, fmt)),
        ]
    return mods


def _random_stimuli(netlist: Netlist, n: int, seed: int) -> list[dict[str, InputValue]]:
    """``n`` asignaciones aleatorias de todas las entradas y buses de entrada."""
    rng = random.Random(seed)
    in_bus = {bit.name for bits in netlist.input_buses.values() for bit in bits}
    singles = [name for name, node in netlist.inputs.items() if node.name not in in_bus]
    stimuli: list[dict[str, InputValue]] = []
    for _ in range(n):
        s: dict[str, InputValue] = {
            k: rng.getrandbits(len(v)) for k, v in netlist.input_buses.items()
        }
        s |= {k: rng.getrandbits(1) for k in singles}
        stimuli.append(s)
    return stimuli


def _write(
    out_dir: Path,
    base: str,
    title: str,
    header: Sequence[str],
    rows: list[list[object]],
    notes: list[str],
) -> list[Path]:
    """Escribe ``base.csv`` y ``base.md`` con la misma tabla."""
    csv_path, md_path = out_dir / f"{base}.csv", out_dir / f"{base}.md"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    lines = [f"# {title}", "", "| " + " | ".join(header) + " |"]
    lines.append("|" + "|".join("---" for _ in header) + "|")
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    if notes:
        lines += ["", *(f"> {n}" for n in notes)]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [md_path, csv_path]


def _build_all(modules: list[tuple[str, Builder]]) -> tuple[dict[str, Netlist], list[str]]:
    built: dict[str, Netlist] = {}
    notes = []
    for name, build in modules:
        try:
            built[name] = build()
        except NotImplementedError:
            notes.append(f"{name}: aún no implementado, se omite.")
    return built, notes


def _activity_row(name: str, netlist: Netlist, seed: int) -> list[object]:
    engine = make_engine(netlist, "cached")
    stimuli = _random_stimuli(netlist, ACTIVITY_OPERATIONS + 1, seed)
    engine.set_inputs(stimuli[0])  # estado inicial definido, fuera de la medición
    r = measure_activity(engine, stimuli[1:])
    return [
        name,
        r.operations,
        r.nodes,
        r.node_toggles,
        r.transistor_events,
        f"{r.alpha:.4f}",
        f"{1000 * r.seconds / r.operations:.2f}",
    ]


def generate_reports(out_dir: Path) -> list[Path]:
    """Genera ``transistores``, ``actividad``, ``camino_critico`` y
    ``comparacion_sumadores`` en ``.md`` y ``.csv`` dentro de ``out_dir``.

    Los bloques aún no implementados se omiten con una nota en el Markdown.

    Returns:
        Rutas de los archivos escritos.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    built, notes = _build_all(_modules())
    paths: list[Path] = []

    rows: list[list[object]] = []
    for name, nl in built.items():
        c = count(nl)
        rows.append([name, c.nmos, c.pmos, c.total])
    paths += _write(
        out_dir,
        "transistores",
        "Transistores por módulo",
        ["modulo", "nmos", "pmos", "total"],
        rows,
        notes,
    )

    combinational = {k: v for k, v in built.items() if not v.sequential}
    rows = [_activity_row(name, nl, seed) for seed, (name, nl) in enumerate(combinational.items())]
    paths += _write(
        out_dir,
        "actividad",
        f"Actividad de conmutación ({ACTIVITY_OPERATIONS} estímulos aleatorios, motor cached)",
        [
            "modulo",
            "operaciones",
            "nodos",
            "conmutaciones",
            "eventos_transistor",
            "alpha",
            "ms_por_op",
        ],
        rows,
        notes,
    )

    rows = [[name, cell_depth(nl)] for name, nl in combinational.items()]
    paths += _write(
        out_dir,
        "camino_critico",
        "Profundidad del camino crítico (celdas primitivas)",
        ["modulo", "profundidad"],
        rows,
        [*notes, "Las celdas secuenciales cortan el camino; los módulos secuenciales se omiten."],
    )

    paths += _write(out_dir, *_adder_comparison())
    return paths


def _adder_comparison() -> tuple[str, str, list[str], list[list[object]], list[str]]:
    from transim.blocks.adders import carry_lookahead_adder, ripple_carry_adder

    rows: list[list[object]] = []
    builders: Mapping[str, Callable[[int], Netlist]] = {
        "RCA": ripple_carry_adder,
        "CLA": carry_lookahead_adder,
    }
    for width in ADDER_WIDTHS:
        for kind, build in builders.items():
            nl = build(width)
            act = _activity_row(nl.name, nl, width)
            rows.append([kind, width, count(nl).total, cell_depth(nl), act[5], act[6]])
    return (
        "comparacion_sumadores",
        "Comparación de sumadores: ripple-carry frente a carry-lookahead",
        ["sumador", "ancho", "transistores", "profundidad", "alpha", "ms_por_op"],
        rows,
        ["La profundidad se mide en celdas primitivas sobre el camino más largo."],
    )
