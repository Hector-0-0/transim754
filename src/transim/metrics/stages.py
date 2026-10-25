"""Etapas del camino crítico, ciclos de reloj estimados y actividad por etapa. ADR-0014.

El simulador es de retardo cero: una unidad combinacional se resuelve en una sola
evaluación. Para hablar de ciclos de reloj se adopta el modelo de ADR-0014: cada celda
primitiva cuesta una unidad de retardo y el periodo de reloj es un número fijo de
celdas. El camino crítico se recorre en orden, agrupado por la instancia de primer
nivel que atraviesa (la etapa del datapath), y se reparte en ciclos de ese periodo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

from transim.core.engine_switch import SwitchEngine
from transim.core.netlist import Netlist
from transim.metrics.critical_path import cell_depth, critical_path

GLUE = "(enlace)"
"""Etapa de las celdas colocadas directamente en el netlist, fuera de toda instancia."""

STAGE_NAMES = {
    "unpack_a": "desempaquetar a",
    "unpack_b": "desempaquetar b",
    "class_a": "clasificar a",
    "class_b": "clasificar b",
    "order": "comparar magnitudes",
    "exp_diff": "restar exponentes",
    "align": "alinear mantisa",
    "mant_addsub": "sumar/restar mantisas",
    "mant_mul": "multiplicar mantisas",
    "mant_div": "dividir mantisas",
    "lzc": "contar ceros",
    "lzc_a": "contar ceros de a",
    "lzc_b": "contar ceros de b",
    "normalize": "normalizar",
    "normalize_a": "normalizar a",
    "normalize_b": "normalizar b",
    "round": "redondear y empaquetar",
    "special": "casos especiales",
    "addsub": "sumar/restar",
    GLUE: "selección y enlace",
    "(entradas)": "entradas",
}
"""Nombre legible de las etapas de las unidades de la FPU y de la ALU."""


@dataclass(frozen=True, slots=True)
class Stage:
    """Tramo del camino crítico que pertenece a una misma etapa.

    Attributes:
        instance: instancia de primer nivel (o :data:`GLUE`).
        cells: celdas primitivas del camino crítico dentro del tramo.
    """

    instance: str
    cells: int

    @property
    def label(self) -> str:
        """Nombre legible de la etapa."""
        return STAGE_NAMES.get(self.instance, self.instance)


@dataclass(frozen=True, slots=True)
class Cycle:
    """Un ciclo de reloj del modelo de ADR-0014.

    Attributes:
        index: número de ciclo, desde 1.
        first_cell, last_cell: posiciones (desde 1) del camino crítico que cubre.
        stages: etapas que se ejecutan, total o parcialmente, en este ciclo.
    """

    index: int
    first_cell: int
    last_cell: int
    stages: tuple[str, ...]


@cache
def _stage_instances(netlist: Netlist) -> frozenset[str]:
    """Instancias de primer nivel que son bloques (tienen sub-instancias): las etapas.
    Las celdas sueltas de primer nivel forman la lógica de enlace (:data:`GLUE`)."""
    return frozenset(i.path for i in netlist.top_instances() if not i.is_leaf)


def _top(netlist: Netlist, path: str) -> str:
    """Etapa de un camino jerárquico (de instancia o de transistor)."""
    first = path.split(".", 1)[0]
    return first if first in _stage_instances(netlist) else GLUE


@cache
def critical_stages(netlist: Netlist) -> tuple[Stage, ...]:
    """El camino crítico agrupado en tramos consecutivos por etapa."""
    stages: list[Stage] = []
    for path in critical_path(netlist):
        top = _top(netlist, path)
        if stages and stages[-1].instance == top:
            stages[-1] = Stage(top, stages[-1].cells + 1)
        else:
            stages.append(Stage(top, 1))
    return tuple(stages)


def schedule(stages: tuple[Stage, ...], period: int) -> list[Cycle]:
    """Reparte el camino crítico en ciclos de ``period`` celdas.

    Raises:
        ValueError: si ``period`` < 1.
    """
    if period < 1:
        raise ValueError("el periodo de reloj debe ser de al menos una celda")
    total = sum(s.cells for s in stages)
    cycles = []
    for k in range(math.ceil(total / period)):
        first, last = k * period + 1, min((k + 1) * period, total)
        names: list[str] = []
        start = 1
        for s in stages:
            end = start + s.cells - 1
            if start <= last and end >= first and s.label not in names:
                names.append(s.label)
            start = end + 1
        cycles.append(Cycle(k + 1, first, last, tuple(names)))
    return cycles


@cache
def reference_period() -> int:
    """Periodo de reloj por defecto: el camino crítico de la ALU entera de 32 bits.

    Es la convención de ADR-0014: una operación entera cabe en un ciclo.
    """
    from transim.alu.int_alu import int_alu

    return cell_depth(int_alu())


INPUTS = "(entradas)"
"""Dueño de los nodos que ningún canal maneja: las entradas externas."""


@cache
def _node_owner(netlist: Netlist) -> tuple[str, ...]:
    """Etapa dueña de cada nodo: la instancia de primer nivel cuyos canales lo manejan.

    Por las reglas de la biblioteca (ADR-0008), un nodo solo lo manejan los canales de
    la celda que lo produce; las entradas de una celda llegan solo a compuertas.
    """
    owner = [INPUTS] * len(netlist.nodes)
    for t in netlist.transistors:
        top = _top(netlist, t.name)
        for node in (t.source, t.drain):
            if not node.is_source:
                owner[node.id] = top
    return tuple(owner)


def activity_by_stage(engine: SwitchEngine) -> dict[str, int]:
    """Conmutaciones de nodo de los contadores actuales del motor, agrupadas por la etapa
    que maneja cada nodo (instancia de primer nivel, :data:`GLUE` o :data:`INPUTS`)."""
    owner = _node_owner(engine.netlist)
    totals: dict[str, int] = {}
    for node_id, toggles in enumerate(engine.node_toggles):
        if toggles:
            totals[owner[node_id]] = totals.get(owner[node_id], 0) + toggles
    return totals
