"""Motor de simulación acelerado con tablas extraídas de las celdas (ADR-0008).

Cada instancia de **celda tabulable** se evalúa como una unidad con una tabla
memoizada ``(entradas, estado interno) → (nuevo estado interno, fuerzas)``. La tabla
de cada tipo de celda se construye ejecutando el motor :class:`SwitchEngine` sobre el
netlist de transistores de la propia celda, por lo que nunca se escribe a mano.

Una instancia es tabulable si cumple las cuatro condiciones siguientes (se verifican de
forma automática; las que no las cumplen se simulan transistor por transistor):

1. su definición no está marcada como secuencial;
2. es una celda primitiva (sin sub-instancias);
3. cada entrada de la celda solo llega a compuertas de transistores de la celda (la
   celda no carga sus entradas a través de un canal);
4. cada salida de la instancia solo toca canales de transistores de la propia
   instancia (fuera de ella solo llega a compuertas).

Con 3 y 4, todos los CCC de la celda quedan dentro de ella: su estado estable depende
solo de sus entradas y de su estado interno previo, que es exactamente la clave de la
tabla. Los contadores de actividad se calculan con la misma regla que el motor switch
(comparación de estados estables), así que ambos motores reportan los mismos conteos.
"""

from __future__ import annotations

import itertools
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from transim.core.engine_switch import DEFAULT_MAX_EVENTS, SwitchEngine
from transim.core.netlist import Instance, Netlist
from transim.core.node import NodeKind
from transim.core.signals import Logic, Strength
from transim.core.transistor import Transistor

StateKey = tuple[tuple[Logic, ...], tuple[Logic, ...]]
StepResult = tuple[tuple[Logic, ...], tuple[Strength, ...]]


class NotCombinationalError(ValueError):
    """La celda no produce salidas definidas para alguna combinación de entradas 0/1."""


def tabulable_definition(definition: Netlist) -> str | None:
    """Motivo por el que ``definition`` no se puede tabular, o None si se puede.

    Comprueba las condiciones 1–3 del módulo (las que dependen solo de la celda).
    """
    if definition.sequential:
        return "es secuencial"
    if definition.instances:
        return "no es una celda primitiva (tiene sub-instancias)"
    channel_nodes = {t.source.id for t in definition.transistors} | {
        t.drain.id for t in definition.transistors
    }
    for name, node in definition.inputs.items():
        if node.id in channel_nodes:
            return f"la entrada {name!r} toca un canal"
    return None


class CellTable:
    """Tabla de comportamiento de un tipo de celda, extraída de su netlist.

    Args:
        definition: netlist de la celda. Debe cumplir :func:`tabulable_definition`.
    """

    def __init__(self, definition: Netlist) -> None:
        reason = tabulable_definition(definition)
        if reason is not None:
            raise ValueError(f"{definition.name}: no se puede tabular: {reason}")
        self.definition = definition
        self.input_names: list[str] = list(definition.inputs)
        self.output_names: list[str] = list(definition.outputs)
        self._input_ids = [definition.inputs[n].id for n in self.input_names]
        self.state_ids: list[int] = [n.id for n in definition.nodes if n.kind is NodeKind.INTERNAL]
        self._output_pos = [
            self.state_ids.index(definition.outputs[n].id) for n in self.output_names
        ]
        self._sim = SwitchEngine(definition)
        self._memo: dict[StateKey, StepResult] = {}
        self.hits = 0
        self.misses = 0
        self.truth_table: dict[tuple[int, ...], tuple[Logic, ...]] = self._extract_truth_table()

    def _extract_truth_table(self) -> dict[tuple[int, ...], tuple[Logic, ...]]:
        """Salidas para las 2^n combinaciones de entradas 0/1, partiendo de todo en X."""
        table: dict[tuple[int, ...], tuple[Logic, ...]] = {}
        x_state = tuple(Logic.X for _ in self.state_ids)
        for combo in itertools.product((0, 1), repeat=len(self.input_names)):
            new_state, _ = self.step(tuple(Logic(v) for v in combo), x_state)
            outputs = tuple(new_state[p] for p in self._output_pos)
            if not all(v.is_known for v in outputs):
                raise NotCombinationalError(
                    f"{self.definition.name}: salida indefinida para entradas {combo}"
                )
            table[combo] = outputs
        return table

    def step(self, inputs: tuple[Logic, ...], state: tuple[Logic, ...]) -> StepResult:
        """Nuevo estado interno (y sus fuerzas) para ``inputs`` desde ``state``."""
        key = (inputs, state)
        cached = self._memo.get(key)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        values = [Logic.X] * len(self.definition.nodes)
        values[self.definition.vdd.id] = Logic.ONE
        values[self.definition.gnd.id] = Logic.ZERO
        for nid, v in zip(self._input_ids, inputs, strict=True):
            values[nid] = v
        for nid, v in zip(self.state_ids, state, strict=True):
            values[nid] = v
        self._sim.load_state(values)
        self._sim.resettle()
        result_values = self._sim.values()
        result_strengths = self._sim.strengths()
        result = (
            tuple(result_values[n] for n in self.state_ids),
            tuple(result_strengths[n] for n in self.state_ids),
        )
        self._memo[key] = result
        return result


_TABLES: dict[int, CellTable] = {}


def table_for(definition: Netlist) -> CellTable:
    """Tabla compartida del tipo de celda ``definition`` (se construye una sola vez)."""
    table = _TABLES.get(id(definition))
    if table is None or table.definition is not definition:
        table = CellTable(definition)
        _TABLES[id(definition)] = table
    return table


@dataclass(eq=False)
class _Box:
    """Instancia tabulada dentro del netlist simulado."""

    instance: Instance
    table: CellTable
    inputs: list[int]  # ids globales de las entradas, en el orden de la tabla
    state: list[int]  # ids globales de los nodos internos, en el orden de la tabla
    transistors: list[Transistor] = field(default_factory=list)


class CachedEngine(SwitchEngine):
    """Motor mixto: celdas tabulables por tabla; el resto, transistor por transistor.

    Tiene la misma interfaz que :class:`SwitchEngine`.

    Attributes:
        cached_instances: caminos de las instancias evaluadas por tabla.
        switch_instances: caminos de las celdas primitivas simuladas transistor por
            transistor, con el motivo.
    """

    def __init__(self, netlist: Netlist, *, max_events: int = DEFAULT_MAX_EVENTS) -> None:
        self._boxes: list[_Box] = []
        self.switch_instances: dict[str, str] = {}
        self._box_of_input: dict[int, list[int]] = {}
        self._build_boxes(netlist)
        self._box_queue: deque[int] = deque()
        self._box_pending: set[int] = set()
        super().__init__(netlist, max_events=max_events)

    @property
    def cached_instances(self) -> list[str]:
        """Caminos de las instancias evaluadas por tabla."""
        return [b.instance.path for b in self._boxes]

    # --------------------------------------------------------- particionado
    def _build_boxes(self, netlist: Netlist) -> None:
        channel_owner: dict[int, set[int]] = {}
        for t in netlist.transistors:
            channel_owner.setdefault(t.source.id, set()).add(t.id)
            channel_owner.setdefault(t.drain.id, set()).add(t.id)
        for inst in netlist.leaf_instances():
            reason = tabulable_definition(inst.definition)
            if reason is None:
                own = {t.id for t in inst.transistors}
                for port in inst.definition.outputs:
                    node = inst.ports[port]
                    if node.is_source:
                        reason = f"la salida {port!r} está conectada a una fuente"
                        break
                    if channel_owner.get(node.id, set()) - own:
                        reason = f"la salida {port!r} toca canales fuera de la celda"
                        break
            if reason is not None:
                self.switch_instances[inst.path] = reason
                continue
            table = table_for(inst.definition)
            node_map = self._instance_node_map(inst, netlist)
            box = _Box(
                instance=inst,
                table=table,
                inputs=[inst.ports[name].id for name in table.input_names],
                state=[node_map[lid] for lid in table.state_ids],
                transistors=list(inst.transistors),
            )
            index = len(self._boxes)
            self._boxes.append(box)
            for nid in set(box.inputs):
                self._box_of_input.setdefault(nid, []).append(index)

    @staticmethod
    def _instance_node_map(inst: Instance, netlist: Netlist) -> dict[int, int]:
        """Id local (en la definición) → id global de cada nodo interno de la instancia."""
        mapping: dict[int, int] = {}
        for name, node in inst.definition.outputs.items():
            mapping[node.id] = inst.ports[name].id
        for node in inst.definition.nodes:
            if node.kind is NodeKind.INTERNAL and node.id not in mapping:
                mapping[node.id] = netlist.find(f"{inst.path}.{node.name}").id
        return mapping

    # ------------------------------------------------- puntos de extensión
    def _switch_region(self) -> list[Transistor]:
        boxed = {t.id for b in self._boxes for t in b.transistors}
        return [t for t in self.netlist.transistors if t.id not in boxed]

    def _initial_seeds(self) -> list[int]:
        boxed_nodes = {n for b in self._boxes for n in b.state}
        for i in range(len(self._boxes)):
            self._enqueue_box(i)
        return [n.id for n in self.netlist.nodes if not n.is_source and n.id not in boxed_nodes]

    def _work_pending(self) -> bool:
        return bool(self._queue) or bool(self._box_queue)

    def _step(self, touched: set[int]) -> None:
        if self._queue:
            super()._step(touched)
            return
        index = self._box_queue.popleft()
        self._box_pending.discard(index)
        box = self._boxes[index]
        self.evaluations += 1
        inputs = tuple(self._values[n] for n in box.inputs)
        state = tuple(self._values[n] for n in box.state)
        new_values, new_strengths = box.table.step(inputs, state)
        for nid, value, strength in zip(box.state, new_values, new_strengths, strict=True):
            self._apply(nid, value, strength, touched)

    def _node_changed(self, nid: int) -> None:
        super()._node_changed(nid)
        for index in self._box_of_input.get(nid, ()):
            self._enqueue_box(index)

    def _enqueue_box(self, index: int) -> None:
        if index not in self._box_pending:
            self._box_pending.add(index)
            self._box_queue.append(index)

    def _settle(
        self, seeds: Sequence[int], touched: set[int], changed_sources: set[int] | None = None
    ) -> None:
        try:
            super()._settle(seeds, touched, changed_sources)
        finally:
            self._box_queue.clear()
            self._box_pending.clear()

    def table_stats(self) -> dict[str, tuple[int, int]]:
        """Aciertos y fallos de memoización por tipo de celda: nombre → (hits, misses)."""
        return {b.table.definition.name: (b.table.hits, b.table.misses) for b in self._boxes}
