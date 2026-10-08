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
    """Contadores acumulados desde el último :meth:`SwitchEngine.reset_counters`."""

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
        self._channel: list[list[Transistor]] = [[] for _ in range(n_nodes)]
        self._gated: list[list[Transistor]] = [[] for _ in range(n_nodes)]
        for t in netlist.transistors:
            self._channel[t.source.id].append(t)
            if t.drain is not t.source:
                self._channel[t.drain.id].append(t)
            self._gated[t.gate.id].append(t)
        for node in netlist.nodes:
            if node.kind is NodeKind.VDD:
                self._values[node.id], self._strengths[node.id] = Logic.ONE, Strength.SUPPLY
            elif node.kind is NodeKind.GND:
                self._values[node.id], self._strengths[node.id] = Logic.ZERO, Strength.SUPPLY
            elif node.kind is NodeKind.INPUT:
                self._strengths[node.id] = Strength.DRIVEN
        self._conduction: list[Conduction] = [
            conduction_for(t.kind, self._values[t.gate.id]) for t in netlist.transistors
        ]
        # Último valor definido (0/1) de cada nodo y último estado definido (ON/OFF) de
        # cada transistor: base para contar conmutaciones aunque se pase por X.
        self._last_known: list[Logic | None] = [v if v.is_known else None for v in self._values]
        self._last_conduction: list[Conduction | None] = [
            c if c is not Conduction.UNKNOWN else None for c in self._conduction
        ]
        self.node_toggles: list[int] = [0] * n_nodes
        self.transistor_events: list[int] = [0] * len(netlist.transistors)
        self.evaluations = 0
        self.short_circuits: list[str] = []
        self._settle([n.id for n in netlist.nodes if not n.is_source])

    # ------------------------------------------------------------- entradas
    def set_inputs(self, values: Mapping[str, InputValue]) -> None:
        """Asigna entradas (por puerto o por bus) y estabiliza el circuito.

        Ejemplo: ``sim.set_inputs({"a": 1, "b": "X", "bus": 0b1011})``.

        Raises:
            KeyError: si un nombre no es una entrada ni un bus de entrada.
            ValueError: si un valor no es válido o no cabe en el bus.
            OscillationError: si el circuito no se estabiliza.
        """
        changed: list[int] = []
        for name, value in values.items():
            for node, level in self._expand(name, value):
                if self._values[node.id] != level:
                    self._values[node.id] = level
                    changed.append(node.id)
        if not changed:
            return
        seeds: list[int] = []
        for nid in changed:
            self._count_toggle(nid)
            seeds.extend(self._on_gate_change(nid))
            seeds.extend(self._channel_neighbors(nid))
        self._settle(seeds)

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

    # -------------------------------------------------------------- lectura
    def value(self, node: Node) -> Logic:
        """Valor actual de ``node``."""
        return self._values[node.id]

    def strength(self, node: Node) -> Strength:
        """Fuerza con la que ``node`` tiene su valor actual."""
        return self._strengths[node.id]

    def read(self, name: str) -> Logic:
        """Valor actual del nodo ``name`` (puerto o nodo interno)."""
        return self._values[self.netlist.find(name).id]

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
        return self._conduction[transistor.id]

    # ----------------------------------------------------------- contadores
    def stats(self) -> SimStats:
        """Totales de conmutaciones, eventos de transistor y evaluaciones de CCC."""
        return SimStats(sum(self.node_toggles), sum(self.transistor_events), self.evaluations)

    def reset_counters(self) -> None:
        """Pone a cero los contadores de actividad (no altera el estado del circuito)."""
        self.node_toggles = [0] * len(self.node_toggles)
        self.transistor_events = [0] * len(self.transistor_events)
        self.evaluations = 0

    def _count_toggle(self, nid: int) -> None:
        v = self._values[nid]
        if not v.is_known:
            return
        last = self._last_known[nid]
        if last is not None and last != v:
            self.node_toggles[nid] += 1
        self._last_known[nid] = v

    # ------------------------------------------------------------ simulación
    def _on_gate_change(self, nid: int) -> list[int]:
        """Actualiza los transistores con compuerta en ``nid``; devuelve nodos a reevaluar."""
        seeds: list[int] = []
        gate_value = self._values[nid]
        for t in self._gated[nid]:
            new = conduction_for(t.kind, gate_value)
            if new is self._conduction[t.id]:
                continue
            self._conduction[t.id] = new
            if new is not Conduction.UNKNOWN:
                last = self._last_conduction[t.id]
                if last is not None and last is not new:
                    self.transistor_events[t.id] += 1
                self._last_conduction[t.id] = new
            seeds.append(t.source.id)
            seeds.append(t.drain.id)
        return seeds

    def _channel_neighbors(self, nid: int) -> list[int]:
        """Nodos al otro lado de los canales que tocan ``nid``."""
        return [t.drain.id if t.source.id == nid else t.source.id for t in self._channel[nid]]

    def _settle(self, seeds: Sequence[int]) -> None:
        queue: deque[int] = deque()
        pending: set[int] = set()
        for nid in seeds:
            if not self._is_source[nid] and nid not in pending:
                pending.add(nid)
                queue.append(nid)
        events = 0
        while queue:
            nid = queue.popleft()
            if nid not in pending:
                continue
            members, edges, boundary = self._component(nid)
            pending.difference_update(members)
            self.evaluations += 1
            new_values = self._evaluate(members, edges, boundary)
            for m, (value, strength) in new_values.items():
                self._strengths[m] = strength
                if self._values[m] == value:
                    continue
                self._values[m] = value
                self._count_toggle(m)
                events += 1
                if events > self.max_events:
                    raise OscillationError(
                        f"{self.netlist.name}: sin estado estable tras {self.max_events} "
                        f"eventos (último nodo: {self.netlist.nodes[m].name!r})"
                    )
                for s in self._on_gate_change(m):
                    if not self._is_source[s] and s not in pending:
                        pending.add(s)
                        queue.append(s)

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
            if v_on == v_maybe:
                result[m] = (v_on, s_on)
            else:
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

        attached: dict[int, list[int]] = {}
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
                names = ", ".join(sorted(self.netlist.nodes[n].name for n in nodes))
                self.short_circuits.append(names)
                warnings.warn(
                    f"{self.netlist.name}: cortocircuito VDD–GND en {{{names}}}",
                    ShortCircuitWarning,
                    stacklevel=4,
                )
            if resolved.value is Logic.Z:
                for n in nodes:
                    result[n] = (Logic.Z, Strength.NONE)
            else:
                for n in nodes:
                    result[n] = (resolved.value, resolved.strength)
        return result

    def _shorted(self, sources: list[int]) -> bool:
        kinds = {self.netlist.nodes[s].kind for s in sources}
        return NodeKind.VDD in kinds and NodeKind.GND in kinds
