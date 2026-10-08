"""Transistores MOS ideales modelados como interruptores (ADR-0007).

Un nMOS conduce cuando su compuerta vale 1 y un pMOS cuando vale 0. Si la compuerta
vale X o Z, la conducción es desconocida. ``source`` y ``drain`` son intercambiables:
el canal es un interruptor bidireccional. No se modela la caída de umbral V_t.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum

from transim.core.node import Node
from transim.core.signals import Logic


class TransistorType(Enum):
    """Tipo de canal del transistor."""

    NMOS = "nmos"
    PMOS = "pmos"


class Conduction(IntEnum):
    """Estado del canal de un transistor."""

    OFF = 0
    ON = 1
    UNKNOWN = 2


def conduction_for(kind: TransistorType, gate: Logic) -> Conduction:
    """Estado del canal de un transistor de tipo ``kind`` con la compuerta en ``gate``."""
    if not gate.is_known:
        return Conduction.UNKNOWN
    on_value = Logic.ONE if kind is TransistorType.NMOS else Logic.ZERO
    return Conduction.ON if gate == on_value else Conduction.OFF


@dataclass(eq=False, slots=True, frozen=True)
class Transistor:
    """Un transistor del netlist.

    Attributes:
        id: índice del transistor dentro de su netlist.
        kind: nMOS o pMOS.
        gate: nodo de compuerta.
        source: un extremo del canal.
        drain: el otro extremo del canal.
        name: nombre descriptivo (con el camino de instancia si viene de un subcircuito).
    """

    id: int
    kind: TransistorType
    gate: Node
    source: Node
    drain: Node
    name: str

    def conduction(self, gate_value: Logic) -> Conduction:
        """Estado del canal si la compuerta vale ``gate_value``."""
        return conduction_for(self.kind, gate_value)

    def __repr__(self) -> str:
        return (
            f"Transistor({self.name!r}, {self.kind.value}, g={self.gate.name}, "
            f"s={self.source.name}, d={self.drain.name})"
        )
