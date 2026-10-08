"""Conteo de transistores por circuito y por módulo (ADR-0013)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from transim.core.netlist import Netlist
from transim.core.transistor import Transistor, TransistorType

UNOWNED = "(sin instancia)"
"""Clave de los transistores colocados directamente en el netlist, fuera de instancias."""


@dataclass(frozen=True, slots=True)
class TransistorCount:
    """Cantidad de nMOS y pMOS."""

    nmos: int
    pmos: int

    @property
    def total(self) -> int:
        """nMOS + pMOS."""
        return self.nmos + self.pmos

    def __add__(self, other: TransistorCount) -> TransistorCount:
        return TransistorCount(self.nmos + other.nmos, self.pmos + other.pmos)


def _count(transistors: list[Transistor]) -> TransistorCount:
    n = sum(1 for t in transistors if t.kind is TransistorType.NMOS)
    return TransistorCount(nmos=n, pmos=len(transistors) - n)


def count(netlist: Netlist) -> TransistorCount:
    """Transistores del netlist aplanado."""
    return _count(netlist.transistors)


def count_by_instance(netlist: Netlist) -> dict[str, TransistorCount]:
    """Transistores de cada instancia de primer nivel, más los que no pertenecen a
    ninguna (clave :data:`UNOWNED`, solo si hay alguno). La suma es el total."""
    result = {i.path: _count(i.transistors) for i in netlist.top_instances()}
    owned = {t.id for i in netlist.top_instances() for t in i.transistors}
    loose = [t for t in netlist.transistors if t.id not in owned]
    if loose:
        result[UNOWNED] = _count(loose)
    return result


def count_by_cell(netlist: Netlist) -> dict[str, tuple[int, TransistorCount]]:
    """Por tipo de celda primitiva: (número de instancias, transistores en total)."""
    uses: Counter[str] = Counter()
    totals: dict[str, TransistorCount] = {}
    for inst in netlist.leaf_instances():
        name = inst.definition.name
        uses[name] += 1
        totals[name] = totals.get(name, TransistorCount(0, 0)) + _count(inst.transistors)
    return {name: (uses[name], totals[name]) for name in sorted(uses)}
