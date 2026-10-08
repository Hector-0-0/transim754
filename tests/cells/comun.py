"""Verificaciones comunes de celdas L1 (usadas por las pruebas de cells/)."""

from __future__ import annotations

import itertools
import random
from collections.abc import Callable, Sequence

from transim.core import CachedEngine, Logic, Netlist, SwitchEngine
from transim.core.engine_cached import CellTable


def tabla_exhaustiva(
    nl: Netlist,
    entradas: Sequence[str],
    salidas: Sequence[str],
    referencia: Callable[..., int | tuple[int, ...]],
) -> None:
    """Las 2^n combinaciones con el motor switch contra la función de referencia."""
    sim = SwitchEngine(nl)
    for combo in itertools.product((0, 1), repeat=len(entradas)):
        sim.set_inputs(dict(zip(entradas, combo, strict=True)))
        esperado = referencia(*combo)
        esperado_t = esperado if isinstance(esperado, tuple) else (esperado,)
        obtenido = tuple(sim.read(s) for s in salidas)
        assert obtenido == tuple(Logic(v) for v in esperado_t), (nl.name, combo)


def entradas_solo_a_compuertas(nl: Netlist) -> bool:
    """Regla de biblioteca (ADR-0008): ninguna entrada toca un canal en ninguna hoja."""
    canales = {t.source.id for t in nl.transistors} | {t.drain.id for t in nl.transistors}
    return all(n.id not in canales for n in nl.inputs.values())


def hojas_tabulables(nl: Netlist) -> None:
    """Cada celda primitiva del netlist es combinacional y tabulable (salida restaurada)."""
    hojas = [i.definition for i in nl.leaf_instances()] or [nl]
    for definicion in hojas:
        CellTable(definicion)  # NotCombinationalError si una salida queda indefinida


def equivalencia_motores(nl: Netlist, entradas: Sequence[str], pasos: int = 60) -> None:
    """Misma salida en ambos motores para una secuencia aleatoria con 0, 1 y X."""
    top = Netlist(f"top_{nl.name}")
    conn = {n: top.input(n) for n in entradas}
    inst = top.instantiate(nl, "u", conn)
    for nombre in nl.outputs:
        top.mark_output(nombre, inst[nombre])
    sw, ca = SwitchEngine(top), CachedEngine(top)
    rng = random.Random(nl.name)
    for _ in range(pasos):
        paso = {n: rng.choice([0, 1, 1, 0, "X"]) for n in entradas}
        sw.set_inputs(paso)
        ca.set_inputs(paso)
        for nombre in nl.outputs:
            assert sw.read(nombre) is ca.read(nombre), (nl.name, paso)
    assert sw.node_toggles == ca.node_toggles
