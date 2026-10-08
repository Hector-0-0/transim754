"""Capa L0: simulador switch-level (ver ADR-0007, ADR-0008)."""

from transim.core.engine_switch import (
    OscillationError,
    ShortCircuitWarning,
    SimStats,
    SwitchEngine,
)
from transim.core.netlist import Instance, Netlist, NetlistError
from transim.core.node import Node, NodeKind
from transim.core.signals import Logic, Signal, Strength, to_logic
from transim.core.transistor import Conduction, Transistor, TransistorType

__all__ = [
    "Conduction",
    "Instance",
    "Logic",
    "Netlist",
    "NetlistError",
    "Node",
    "NodeKind",
    "OscillationError",
    "ShortCircuitWarning",
    "Signal",
    "SimStats",
    "Strength",
    "SwitchEngine",
    "Transistor",
    "TransistorType",
    "to_logic",
]
