"""Nodos eléctricos del netlist."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NodeKind(Enum):
    """Papel de un nodo en el circuito."""

    VDD = "vdd"  # riel de alimentación: 1 con fuerza SUPPLY
    GND = "gnd"  # riel de tierra: 0 con fuerza SUPPLY
    INPUT = "input"  # entrada externa: valor puesto por el usuario con fuerza DRIVEN
    INTERNAL = "internal"  # nodo cuyo valor calcula el simulador


@dataclass(eq=False, slots=True)
class Node:
    """Un nodo (red eléctrica) del netlist.

    Attributes:
        id: índice del nodo dentro de su netlist (VDD = 0, GND = 1).
        name: nombre único dentro del netlist; los nodos de subcircuitos se nombran
            ``instancia.nodo``.
        kind: papel del nodo (ver :class:`NodeKind`).
    """

    id: int
    name: str
    kind: NodeKind

    @property
    def is_source(self) -> bool:
        """True si el valor del nodo lo fija el exterior (rieles o entradas)."""
        return self.kind is not NodeKind.INTERNAL

    def __repr__(self) -> str:
        return f"Node({self.name!r}, {self.kind.value})"
