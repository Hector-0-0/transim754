"""Motor de simulación switch-level exacto (ADR-0007).

Algoritmo, por cada cambio de entradas:

1. Los nodos afectados se encolan.
2. Para cada nodo encolado se forma su **componente conectado por canal** (CCC):
   los nodos internos alcanzables a través de transistores que conducen o podrían
   conducir. Los nodos fuente (VDD, GND, entradas) delimitan el CCC y no se atraviesan.
3. El CCC se resuelve dos veces: con los transistores que conducen con certeza
   (``G_on``) y con los que conducen con certeza o posiblemente (``G_maybe``). Si los
   resultados difieren, el nodo vale X.
4. Cada nodo que cambia de valor actualiza la conducción de los transistores cuya
   compuerta es ese nodo, y los extremos de esos transistores se encolan.
5. Se repite hasta que la cola queda vacía (estado estable) o se supera el límite de
   eventos (``OscillationError``).

Los contadores de actividad se actualizan al final de cada estabilización comparando
estados estables (ver :meth:`SwitchEngine._commit_counts`): los valores intermedios de
un modelo de retardo cero dependen del orden de los eventos y no representan tiempos
físicos, por lo que no se cuentan.
"""

from __future__ import annotations

import warnings
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from transim.core.netlist import Netlist
from transim.core.node import Node, NodeKind
from transim.core.signals import Logic, LogicLike, Signal, Strength, resolve, to_logic
from transim.core.transistor import Conduction, Transistor, conduction_for

DEFAULT_MAX_EVENTS = 10_000

InputValue = LogicLike | int | Sequence[LogicLike]
"""Valor para :meth:`SwitchEngine.set_inputs`: un nivel para un puerto, o un entero
(LSB = bit 0) o una secuencia de niveles para un bus."""


class OscillationError(RuntimeError):
    """El circuito no alcanzó un estado estable dentro del límite de eventos."""


class ShortCircuitWarning(UserWarning):
    """Un nodo quedó conectado a VDD y a GND a la vez por transistores que conducen."""


@dataclass(frozen=True, slots=True)
class SimStats:
    """Contadores acumulados desde el último ``reset_counters``.

    Attributes:
        node_toggles: conmutaciones de nodos entre estados estables.
        transistor_events: cambios de conducción de transistores entre estados estables.
        evaluations: unidades evaluadas (CCC o celdas tabuladas). Depende del motor y
            del orden de eventos; no forma parte de la equivalencia entre motores.
    """

    node_toggles: int
    transistor_events: int
    evaluations: int


class SwitchEngine:
    """Simulador transistor por transistor de un :class:`Netlist`.

    Al construirse, todos los nodos internos valen X (fuerza ``CHARGE``) y las
    entradas valen X (fuerza ``DRIVEN``); luego se estabiliza el circuito.

    Args:
        netlist: circuito a simular. No debe modificarse después de crear el motor.
        max_events: número máximo de cambios de valor de nodos por estabilización.
    """

    def __init__(self, netlist: Netlist, *, max_events: int = DEFAULT_MAX_EVENTS) -> None:
        self.netlist = netlist
        self.max_events = max_events
        n_nodes = len(netlist.nodes)
        self._values: list[Logic] = [Logic.X] * n_nodes
        self._strengths: list[Strength] = [Strength.CHARGE] * n_nodes
        self._is_source: list[bool] = [node.is_source for node in netlist.nodes]
        for node in netlist.nodes:
            if node.kind is NodeKind.VDD:
                self._values[node.id], self._strengths[node.id] = Logic.ONE, Strength.SUPPLY
            elif node.kind is NodeKind.GND:
                self._values[node.id], self._strengths[node.id] = Logic.ZERO, Strength.SUPPLY
            elif node.kind is NodeKind.INPUT:
                self._strengths[node.id] = Strength.DRIVEN

        # Adyacencias. `_channel` y `_gated` solo incluyen los transistores que este
        # motor evalúa por CCC; `_gated_all` incluye todos (para contar eventos).
        self._channel: list[list[Transistor]] = [[] for _ in range(n_nodes)]
        self._gated: list[list[Transistor]] = [[] for _ in range(n_nodes)]
        self._gated_all: list[list[Transistor]] = [[] for _ in range(n_nodes)]
        for t in netlist.transistors:
            self._gated_all[t.gate.id].append(t)
        for t in self._switch_region():
            self._channel[t.source.id].append(t)
            if t.drain is not t.source:
                self._channel[t.drain.id].append(t)
            self._gated[t.gate.id].append(t)
        self._conduction: list[Conduction] = [
            conduction_for(t.kind, self._values[t.gate.id]) for t in netlist.transistors
        ]

        # Último valor manejado (0/1 con fuerza ≥ DRIVEN) de cada nodo y último estado
        # definido (ON/OFF) de cada transistor: base de los contadores de actividad.
        self._last_driven: list[Logic | None] = [v if v.is_known else None for v in self._values]
        self._last_conduction: list[Conduction | None] = [None] * len(netlist.transistors)
        self.node_toggles: list[int] = [0] * n_nodes
        self.transistor_events: list[int] = [0] * len(netlist.transistors)
        self.evaluations = 0
        self.short_circuits: list[str] = []

        self._queue: deque[int] = deque()
        self._pending: set[int] = set()
        self._events = 0
        self._short_candidates: set[int] = set()
        self._settle(self._initial_seeds(), set())

    # ------------------------------------------------------ puntos de extensión
    def _switch_region(self) -> list[Transistor]:
        """Transistores que este motor evalúa por CCC (todos, en el motor exacto)."""
        return self.netlist.transistors

    def _initial_seeds(self) -> list[int]:
        """Nodos a evaluar en la estabilización inicial."""
        return [n.id for n in self.netlist.nodes if not n.is_source]

    def _work_pending(self) -> bool:
        return bool(self._queue)

    def _step(self, touched: set[int]) -> None:
        """Procesa una unidad de trabajo pendiente (aquí, un CCC)."""
        nid = self._queue.popleft()
        if nid not in self._pending:
            return
        members, edges, boundary = self._component(nid)
        self._pending.difference_update(members)
        self.evaluations += 1
        for m, (value, strength) in self._evaluate(members, edges, boundary).items():
            self._apply(m, value, strength, touched)

    def _node_changed(self, nid: int) -> None:
        """Reacciona al cambio de valor de ``nid``: actualiza los transistores con
        compuerta en ese nodo y encola los extremos de los que cambiaron."""
        gate_value = self._values[nid]
        for t in self._gated[nid]:
            new = conduction_for(t.kind, gate_value)
            if new is not self._conduction[t.id]:
                self._conduction[t.id] = new
                self._enqueue(t.source.id)
                self._enqueue(t.drain.id)

    # ------------------------------------------------------------- entradas
    def set_inputs(self, values: Mapping[str, InputValue]) -> None:
        """Asigna entradas (por puerto o por bus) y estabiliza el circuito.

        Ejemplo: ``sim.set_inputs({"a": 1, "b": "X", "bus": 0b1011})``.

        Raises:
            KeyError: si un nombre no es una entrada ni un bus de entrada.
            ValueError: si un valor no es válido o no cabe en el bus.
            OscillationError: si el circuito no se estabiliza.
        """
        changes: list[tuple[Node, Logic]] = []
        for name, value in values.items():
            changes.extend(self._expand(name, value))
        touched: set[int] = set()
        seeds: list[int] = []
        for node, level in changes:
            if self._values[node.id] != level:
                self._values[node.id] = level
                touched.add(node.id)
                seeds.extend(self._channel_neighbors(node.id))
        if not touched:
            return
        self._settle(seeds, touched, changed_sources=set(touched))

    def _expand(self, name: str, value: InputValue) -> list[tuple[Node, Logic]]:
        nl = self.netlist
        if name in nl.input_buses:
            bits = nl.input_buses[name]
            if isinstance(value, int) and not isinstance(value, bool):
                if not 0 <= value < (1 << len(bits)):
                    raise ValueError(f"{value} no cabe en el bus {name!r} de {len(bits)} bits")
                return [(b, Logic((value >> i) & 1)) for i, b in enumerate(bits)]
            if isinstance(value, str) or not isinstance(value, Sequence):
                raise ValueError(f"el bus {name!r} espera un entero o una secuencia de niveles")
            if len(value) != len(bits):
                raise ValueError(f"el bus {name!r} tiene {len(bits)} bits; se dieron {len(value)}")
            return [(b, to_logic(v)) for b, v in zip(bits, value, strict=True)]
        if name in nl.inputs:
            if not isinstance(value, Logic | int | bool | str):
                raise ValueError(f"la entrada {name!r} espera un solo nivel lógico")
            return [(nl.inputs[name], to_logic(value))]
        raise KeyError(f"{nl.name}: {name!r} no es una entrada ni un bus de entrada")

    def load_state(self, values: Sequence[Logic]) -> None:
        """Carga el valor de todos los nodos (indexados por ``Node.id``) sin estabilizar.

        Los rieles conservan su valor. Se usa junto con :meth:`resettle` para evaluar
        una celda a partir de un estado dado (motor ``cached``).
        """
        if len(values) != len(self._values):
            raise ValueError("load_state: cantidad de valores distinta del número de nodos")
        for node in self.netlist.nodes:
            if node.kind in (NodeKind.VDD, NodeKind.GND):
                continue
            self._values[node.id] = values[node.id]
            if node.kind is NodeKind.INTERNAL:
                self._strengths[node.id] = Strength.CHARGE
        for t in self.netlist.transistors:
            self._conduction[t.id] = conduction_for(t.kind, self._values[t.gate.id])

    def resettle(self) -> None:
        """Reevalúa todos los nodos internos desde el estado actual."""
        self._settle(self._initial_seeds(), set())

    # -------------------------------------------------------------- lectura
    def value(self, node: Node) -> Logic:
        """Valor actual de ``node``."""
        return self._values[node.id]

    def values(self) -> list[Logic]:
        """Copia de los valores de todos los nodos, indexados por ``Node.id``."""
        return list(self._values)

    def strength(self, node: Node) -> Strength:
        """Fuerza con la que ``node`` tiene su valor actual."""
        return self._strengths[node.id]

    def strengths(self) -> list[Strength]:
        """Copia de las fuerzas de todos los nodos, indexadas por ``Node.id``."""
        return list(self._strengths)

    def read(self, name: str) -> Logic:
        """Valor actual del nodo ``name`` (puerto o nodo interno)."""
        nl = self.netlist
        node = nl.outputs.get(name) or nl.inputs.get(name) or nl.find(name)
        return self._values[node.id]

    def read_bus(self, name: str) -> list[Logic]:
        """Valores de un bus de entrada o salida, LSB primero."""
        nl = self.netlist
        bits = nl.output_buses.get(name) or nl.input_buses.get(name)
        if bits is None:
            raise KeyError(f"{nl.name}: no existe el bus {name!r}")
        return [self._values[b.id] for b in bits]

    def read_int(self, name: str) -> int | None:
        """Valor entero sin signo de un bus, o None si algún bit no es 0/1."""
        result = 0
        for i, v in enumerate(self.read_bus(name)):
            if not v.is_known:
                return None
            result |= int(v) << i
        return result

    def conduction(self, transistor: Transistor) -> Conduction:
        """Estado actual del canal de ``transistor``."""
        return conduction_for(transistor.kind, self._values[transistor.gate.id])

    # ----------------------------------------------------------- contadores
    def stats(self) -> SimStats:
        """Totales de conmutaciones, eventos de transistor y evaluaciones."""
        return SimStats(sum(self.node_toggles), sum(self.transistor_events), self.evaluations)

    def reset_counters(self) -> None:
        """Pone a cero los contadores de actividad (no altera el estado del circuito)."""
        self.node_toggles = [0] * len(self.node_toggles)
        self.transistor_events = [0] * len(self.transistor_events)
        self.evaluations = 0

    def _commit_counts(self, touched: set[int]) -> None:
        """Actualiza los contadores comparando el estado estable nuevo con el anterior.

        - Un nodo conmuta cuando su valor **manejado** (0/1 con fuerza ≥ DRIVEN) difiere
          del último valor manejado que tuvo. La carga retenida no cuenta: un nodo
          aislado no se carga ni se descarga.
        - Un transistor genera un evento cuando su estado definido (ON/OFF) difiere del
          último estado definido que tuvo.
        """
        gates: set[Transistor] = set()
        for nid in touched:
            gates.update(self._gated_all[nid])
            value = self._values[nid]
            if not value.is_known or self._strengths[nid] < Strength.DRIVEN:
                continue
            last = self._last_driven[nid]
            if last is not None and last != value:
                self.node_toggles[nid] += 1
            self._last_driven[nid] = value
        for t in gates:
            c = conduction_for(t.kind, self._values[t.gate.id])
            if c is Conduction.UNKNOWN:
                continue
            last_c = self._last_conduction[t.id]
            if last_c is not None and last_c is not c:
                self.transistor_events[t.id] += 1
            self._last_conduction[t.id] = c

    # ------------------------------------------------------------ simulación
    def _enqueue(self, nid: int) -> None:
        if not self._is_source[nid] and nid not in self._pending:
            self._pending.add(nid)
            self._queue.append(nid)

    def _channel_neighbors(self, nid: int) -> list[int]:
        """Nodos al otro lado de los canales que tocan ``nid``."""
        return [t.drain.id if t.source.id == nid else t.source.id for t in self._channel[nid]]

    def _apply(self, nid: int, value: Logic, strength: Strength, touched: set[int]) -> None:
        """Asigna (valor, fuerza) a un nodo interno y propaga si el valor cambió.

        Un cambio solo de fuerza (por ejemplo, de carga retenida a valor manejado) no se
        propaga, pero el nodo se marca para que los contadores lo consideren.
        """
        if self._strengths[nid] != strength:
            self._strengths[nid] = strength
            touched.add(nid)
        if self._values[nid] == value:
            return
        self._values[nid] = value
        touched.add(nid)
        self._events += 1
        if self._events > self.max_events:
            raise OscillationError(
                f"{self.netlist.name}: sin estado estable tras {self.max_events} "
                f"eventos (último nodo: {self.netlist.nodes[nid].name!r})"
            )
        self._node_changed(nid)

    def _settle(
        self, seeds: Sequence[int], touched: set[int], changed_sources: set[int] | None = None
    ) -> None:
        self._events = 0
        for nid in changed_sources or ():
            self._node_changed(nid)
        for nid in seeds:
            self._enqueue(nid)
        try:
            while self._work_pending():
                self._step(touched)
        finally:
            self._queue.clear()
            self._pending.clear()
        self._report_shorts()
        self._commit_counts(touched)

    def _report_shorts(self) -> None:
        """Advierte los cortocircuitos que **persisten** en el estado estable.

        Durante una estabilización puede haber solapamientos transitorios (por ejemplo,
        las dos transmission gates de un MUX conduciendo mientras se actualiza el
        complemento de la selección); en un modelo de retardo cero son artefactos del
        orden de eventos y no se reportan.
        """
        candidates, self._short_candidates = self._short_candidates, set()
        reported: set[int] = set()
        for nid in sorted(candidates):
            if nid in reported:
                continue
            group, sources = self._sure_group(nid)
            reported.update(group)
            if not self._shorted(sources):
                continue
            names = ", ".join(sorted(self.netlist.nodes[n].name for n in group))
            self.short_circuits.append(names)
            warnings.warn(
                f"{self.netlist.name}: cortocircuito VDD–GND en {{{names}}}",
                ShortCircuitWarning,
                stacklevel=4,
            )

    def _sure_group(self, start: int) -> tuple[set[int], list[int]]:
        """Nodos unidos a ``start`` por transistores que conducen con certeza, y fuentes."""
        group, sources, stack = {start}, [], [start]
        while stack:
            nid = stack.pop()
            for t in self._channel[nid]:
                if self._conduction[t.id] is not Conduction.ON:
                    continue
                other = t.drain.id if t.source.id == nid else t.source.id
                if self._is_source[other]:
                    sources.append(other)
                elif other not in group:
                    group.add(other)
                    stack.append(other)
        return group, sources

    def _component(self, start: int) -> tuple[list[int], list[Transistor], set[int]]:
        """CCC de ``start``: nodos internos, transistores no cortados y nodos fuente."""
        members = [start]
        seen = {start}
        edges: list[Transistor] = []
        seen_edges: set[int] = set()
        boundary: set[int] = set()
        i = 0
        while i < len(members):
            nid = members[i]
            i += 1
            for t in self._channel[nid]:
                if self._conduction[t.id] is Conduction.OFF or t.id in seen_edges:
                    continue
                seen_edges.add(t.id)
                edges.append(t)
                other = t.drain.id if t.source.id == nid else t.source.id
                if self._is_source[other]:
                    boundary.add(other)
                elif other not in seen:
                    seen.add(other)
                    members.append(other)
        return members, edges, boundary

    def _evaluate(
        self, members: list[int], edges: list[Transistor], boundary: set[int]
    ) -> dict[int, tuple[Logic, Strength]]:
        """Nuevo (valor, fuerza) de cada nodo del CCC según los grafos G_on y G_maybe."""
        sure = [t for t in edges if self._conduction[t.id] is Conduction.ON]
        on = self._resolve_graph(members, sure, warn=True)
        maybe = self._resolve_graph(members, edges, warn=False)
        result: dict[int, tuple[Logic, Strength]] = {}
        for m in members:
            v_on, s_on = on[m]
            v_maybe, s_maybe = maybe[m]
            if v_on == v_maybe and v_on is not Logic.X:
                result[m] = (v_on, s_on)
            else:
                # Una X lleva la fuerza máxima de ambos grafos: así no depende de cuál
                # de los dos la produjo ni del orden de evaluación.
                result[m] = (Logic.X, max(s_on, s_maybe))
        return result

    def _resolve_graph(
        self, members: list[int], edges: list[Transistor], *, warn: bool
    ) -> dict[int, tuple[Logic, Strength]]:
        parent = {m: m for m in members}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        pending_sources: list[tuple[int, int]] = []
        for t in edges:
            a, b = t.source.id, t.drain.id
            a_src, b_src = self._is_source[a], self._is_source[b]
            if not a_src and not b_src:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb
            elif a_src and not b_src:
                pending_sources.append((b, a))
            elif b_src and not a_src:
                pending_sources.append((a, b))
        attached: dict[int, list[int]] = {}
        for member, source in pending_sources:
            attached.setdefault(find(member), []).append(source)

        groups: dict[int, list[int]] = {}
        for m in members:
            groups.setdefault(find(m), []).append(m)

        result: dict[int, tuple[Logic, Strength]] = {}
        for root, nodes in groups.items():
            signals = [Signal(self._values[s], self._strengths[s]) for s in attached.get(root, [])]
            signals.extend(
                Signal(self._values[n], Strength.CHARGE)
                for n in nodes
                if self._values[n] is not Logic.Z
            )
            resolved = resolve(signals)
            if (
                warn
                and resolved.strength is Strength.SUPPLY
                and resolved.value is Logic.X
                and self._shorted(attached.get(root, []))
            ):
                self._short_candidates.add(nodes[0])
            for n in nodes:
                result[n] = (resolved.value, resolved.strength)
        return result

    def _shorted(self, sources: list[int]) -> bool:
        kinds = {self.netlist.nodes[s].kind for s in sources}
        return NodeKind.VDD in kinds and NodeKind.GND in kinds
