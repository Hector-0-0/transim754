"""Propagación de una operación con retardo unitario por celda (ADR-0018).

El motor salta del estado estable anterior al nuevo sin tiempo (ADR-0007). Para mostrar
cómo avanza un cambio (el acarreo de bit en bit, los niveles de un desplazador), este
módulo **reproduce** el cambio por rondas, aparte del motor:

- se parte del estado estable anterior de la unidad, con las entradas nuevas;
- en cada ronda se evalúan las celdas primitivas cuyas entradas cambiaron en la ronda
  anterior, con la tabla de verdad de su tipo (la del motor ``cached``, ADR-0008); todas
  sus salidas cambian a la vez en la ronda siguiente: cada celda cuesta una unidad de
  retardo, como en ADR-0014;
- termina cuando una ronda no cambia nada.

Al final se compara, nodo por nodo, con el estado que calculó el motor; si no coincide,
la reproducción se marca como no válida y no se anima. Los valores intermedios pueden
tener *glitches* que el motor no muestra: son del modelo de retardo unitario, no una
medición. El módulo no depende de Qt.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache

from transim.core.engine_cached import table_for, tabulable_definition
from transim.core.netlist import Instance, Netlist
from transim.core.node import Node
from transim.core.signals import Logic
from transim.core.transistor import Conduction, Transistor

MAX_EVALUATIONS = 400_000
"""Límite de evaluaciones de celdas: más allá se avisa en vez de congelar la interfaz."""

Values = tuple[Logic, ...]


@dataclass(frozen=True)
class _Cell:
    inst: Instance
    ins: tuple[int, ...]
    outs: tuple[int, ...]
    table: dict[tuple[int, ...], tuple[Logic, ...]]


@cache
def _cells(netlist: Netlist) -> tuple[tuple[_Cell, ...], dict[int, tuple[int, ...]]] | None:
    """Celdas primitivas de la unidad con su tabla, y qué celdas lee cada nodo.

    None si alguna celda no se puede tabular (secuencial, por ejemplo).
    """
    cells: list[_Cell] = []
    readers: dict[int, list[int]] = {}
    for inst in netlist.leaf_instances():
        d = inst.definition
        if tabulable_definition(d) is not None:
            return None
        table = table_for(d)
        ins = tuple(inst.ports[name].id for name in table.input_names)
        outs = tuple(inst.ports[name].id for name in table.output_names)
        for n in ins:
            readers.setdefault(n, []).append(len(cells))
        cells.append(_Cell(inst, ins, outs, table.truth_table))
    return tuple(cells), {n: tuple(ks) for n, ks in readers.items()}


def _evaluate(cell: _Cell, values: Sequence[Logic]) -> tuple[Logic, ...]:
    """Salidas de la celda; con entradas X, lo que den igual todas sus completaciones."""
    known = [values[n] for n in cell.ins]
    if all(v in (Logic.ZERO, Logic.ONE) for v in known):
        return cell.table[tuple(int(v is Logic.ONE) for v in known)]
    unknown = [k for k, v in enumerate(known) if v not in (Logic.ZERO, Logic.ONE)]
    results: set[tuple[Logic, ...]] = set()
    for combo in itertools.product((0, 1), repeat=len(unknown)):
        bits = [int(v is Logic.ONE) for v in known]
        for k, b in zip(unknown, combo, strict=True):
            bits[k] = b
        results.add(cell.table[tuple(bits)])
    if len(results) == 1:
        return results.pop()
    outs = list(zip(*results, strict=True))
    return tuple(o[0] if len(set(o)) == 1 else Logic.X for o in outs)


@dataclass
class Replay:
    """Una operación reproducida por rondas.

    Attributes:
        start: valores de partida (estado anterior con las entradas nuevas).
        rounds: cambios de cada ronda (nodo → valor nuevo); la ronda ``t`` es el
            instante ``t + 1``.
        valid: True si el estado final coincide con el del motor en cada nodo seguido.
        reason: por qué no es válida, si no lo es.
        evaluations: celdas evaluadas en total.
        cells_changed: por ronda, las instancias cuyas salidas cambiaron.
    """

    start: Values
    rounds: list[dict[int, Logic]] = field(default_factory=list)
    valid: bool = True
    reason: str = ""
    evaluations: int = 0
    cells_changed: list[frozenset[str]] = field(default_factory=list)

    @property
    def length(self) -> int:
        """Rondas hasta estabilizarse (en retardos de celda)."""
        return len(self.rounds)

    def values_at(self, t: int) -> list[Logic]:
        """Valores en el instante ``t`` (0: recién aplicadas las entradas)."""
        values = list(self.start)
        for changes in self.rounds[: max(0, t)]:
            for n, v in changes.items():
                values[n] = v
        return values

    def last_change(self, paths: frozenset[str]) -> int:
        """Último instante en que cambió alguna de las instancias ``paths`` (0 si ninguna)."""
        last = 0
        for t, changed in enumerate(self.cells_changed, start=1):
            if changed & paths:
                last = t
        return last


def replay(netlist: Netlist, before: Values, after: Values, inputs: Sequence[int]) -> Replay:
    """Reproduce el paso de ``before`` a ``after`` con retardo unitario por celda.

    Args:
        netlist: la unidad.
        before: estado estable anterior (valor de cada nodo, por id).
        after: estado estable que calculó el motor para la operación nueva.
        inputs: ids de los nodos de entrada de la unidad.
    """
    start = list(before)
    for n in inputs:
        start[n] = after[n]
    result = Replay(tuple(start))
    built = _cells(netlist)
    if built is None:
        result.valid = False
        result.reason = "la unidad tiene celdas que no se pueden tabular"
        return result
    cells, readers = built
    values = list(start)
    changed = {n for n in inputs if before[n] != after[n]}
    while changed:
        pending = sorted({k for n in changed for k in readers.get(n, ())})
        result.evaluations += len(pending)
        if result.evaluations > MAX_EVALUATIONS:
            result.valid = False
            result.reason = f"más de {MAX_EVALUATIONS:,} evaluaciones".replace(",", " ")
            return result
        diff: dict[int, Logic] = {}
        moved: set[str] = set()
        for k in pending:
            cell = cells[k]
            for n, v in zip(cell.outs, _evaluate(cell, values), strict=True):
                if values[n] != v and diff.get(n, v) == v:
                    diff[n] = v
                    moved.add(cell.inst.path)
        for n, v in diff.items():
            values[n] = v
        if diff:
            result.rounds.append(diff)
            result.cells_changed.append(frozenset(moved))
        changed = set(diff)
    followed = {n for c in cells for n in (*c.ins, *c.outs)}
    wrong = [n for n in followed if values[n] != after[n]]
    if wrong:
        result.valid = False
        result.reason = f"{len(wrong)} nodos no coinciden con el motor"
    return result


class ReplayReader:
    """Lo que las vistas leen en el instante ``t``: valores de la reproducción para los
    puertos de las celdas; el resto (nodos internos, canales) es el estado del motor."""

    def __init__(self, values: Sequence[Logic], engine: object) -> None:
        self._values = values
        self._engine = engine

    def value(self, node: Node) -> Logic:
        return self._values[node.id]

    def conduction(self, transistor: Transistor) -> Conduction:
        return self._engine.conduction(transistor)  # type: ignore[attr-defined, no-any-return]


__all__ = ["MAX_EVALUATIONS", "Replay", "ReplayReader", "replay"]
