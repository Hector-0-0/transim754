"""Pasos de una celda: sus etapas en orden de dependencia de señal.

Cada paso es una etapa CMOS (o un transmission gate, o un grupo suelto) en el orden en que
sus entradas ya tienen valor. Mostrar un paso significa resaltar los transistores de las
etapas hasta ese punto y atenuar el resto. Los valores que se muestran son los de la
simulación: el motor es de nivel de interruptor (ADR-0007), así que no hay tiempo
intermedio dentro de una operación; el orden sí sigue la dependencia entre etapas.
"""

from __future__ import annotations

from dataclasses import dataclass

from transim.core.netlist import Netlist
from transim.core.node import NodeKind
from transim.core.transistor import Transistor
from transim.ui.gui.circuit import Element, PassGate, Stage, analyze


@dataclass(frozen=True, slots=True)
class Step:
    """Una etapa de la celda.

    Attributes:
        label: nombres de las salidas que produce, separados por comas.
        outputs: ids locales de esas salidas.
        transistors: índices locales de los transistores de la etapa.
    """

    label: str
    outputs: tuple[int, ...]
    transistors: frozenset[int]


def _outputs(e: Element, ts: list[Transistor], rails: set[int]) -> set[int]:
    if isinstance(e, Stage):
        return {e.output}
    if isinstance(e, PassGate):
        return {e.right}
    return {n.id for i in e.transistors for n in (ts[i].source, ts[i].drain)} - rails


def cell_steps(netlist: Netlist) -> list[Step]:
    """Pasos de una celda primitiva, en orden de señal. Vacío si no tiene etapas."""
    circuit = analyze(netlist)
    rails = {n.id for n in circuit.nodes.values() if n.kind in (NodeKind.VDD, NodeKind.GND)}
    steps: list[Step] = []
    for e in circuit.elements:
        outs = tuple(sorted(_outputs(e, circuit.transistors, rails)))
        if not outs:
            continue
        label = ", ".join(circuit.label(n) for n in outs)
        steps.append(Step(label, outs, frozenset(e.transistors)))
    return steps


def input_ids(netlist: Netlist) -> frozenset[int]:
    """Ids locales de las entradas de la celda."""
    return frozenset(n.id for n in netlist.inputs.values())


__all__ = ["Step", "cell_steps", "input_ids"]
