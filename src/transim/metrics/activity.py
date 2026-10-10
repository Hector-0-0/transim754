"""Actividad de conmutación por operación. ADR-0013."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from transim.core.engine_switch import InputValue, SwitchEngine
from transim.core.node import NodeKind


@dataclass(frozen=True, slots=True)
class ActivityReport:
    """Actividad medida sobre una secuencia de estímulos.

    Attributes:
        operations: número de estímulos aplicados.
        nodes: nodos internos del netlist.
        node_toggles: conmutaciones totales (regla de ADR-0007, punto 9).
        transistor_events: eventos de transistor totales.
        alpha: node_toggles / (nodes · operations).
        seconds: tiempo de simulación total.
    """

    operations: int
    nodes: int
    node_toggles: int
    transistor_events: int
    alpha: float
    seconds: float


def measure_activity(
    engine: SwitchEngine, stimuli: Sequence[Mapping[str, InputValue]]
) -> ActivityReport:
    """Aplica ``stimuli`` en orden y mide la actividad (pone a cero los contadores antes).

    Raises:
        ValueError: si ``stimuli`` está vacío.
    """
    if not stimuli:
        raise ValueError("measure_activity: la lista de estímulos está vacía")
    nodes = sum(1 for n in engine.netlist.nodes if n.kind is NodeKind.INTERNAL)
    engine.reset_counters()
    start = time.perf_counter()
    for stimulus in stimuli:
        engine.set_inputs(stimulus)
    seconds = time.perf_counter() - start
    stats = engine.stats()
    return ActivityReport(
        operations=len(stimuli),
        nodes=nodes,
        node_toggles=stats.node_toggles,
        transistor_events=stats.transistor_events,
        alpha=stats.node_toggles / (nodes * len(stimuli)) if nodes else 0.0,
        seconds=seconds,
    )
