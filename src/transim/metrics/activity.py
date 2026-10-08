"""Actividad de conmutación por operación (responsable: Yenny). ADR-0013."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from transim.core.engine_switch import InputValue, SwitchEngine


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
    raise NotImplementedError("pendiente: #22")
