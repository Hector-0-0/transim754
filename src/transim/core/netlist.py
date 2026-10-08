"""Netlist jerárquico de transistores.

Un :class:`Netlist` describe un circuito como transistores y los nodos que conectan,
con **puertos con nombre** (entradas y salidas) y **buses** (listas ordenadas de nodos,
bit 0 = LSB). Un netlist puede **instanciar** otro como subcircuito; al hacerlo, el
subcircuito se copia aplanado en el netlist padre y se registra una :class:`Instance`
que conserva la jerarquía (para contar transistores por módulo, calcular el camino
crítico en niveles de celda y acelerar celdas en el motor ``cached``).

Ejemplo (NAND2 de 4 transistores)::

    nl = Netlist("nand2")
    a, b = nl.input("a"), nl.input("b")
    y = nl.output("y")
    nl.pmos(gate=a, source=nl.vdd, drain=y)
    nl.pmos(gate=b, source=nl.vdd, drain=y)
    n1 = nl.node("n1")
    nl.nmos(gate=a, source=y, drain=n1)
    nl.nmos(gate=b, source=n1, drain=nl.gnd)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from transim.core.node import Node, NodeKind
from transim.core.transistor import Transistor, TransistorType


class NetlistError(ValueError):
    """Error de construcción del netlist (nombres repetidos, puertos mal conectados…)."""


@dataclass(eq=False)
class Instance:
    """Una instancia de subcircuito dentro de un netlist aplanado.

    Attributes:
        path: camino jerárquico, por ejemplo ``"fa3.xor1"``.
        definition: netlist que se instanció (la "celda" o "bloque").
        ports: puerto del subcircuito → nodo del netlist padre.
        buses: bus del subcircuito → nodos del netlist padre (LSB primero).
        transistors: transistores del netlist padre que pertenecen a esta instancia
            (incluidos los de sus sub-instancias).
        parent: camino de la instancia que la contiene, o None si es de primer nivel.
    """

    path: str
    definition: Netlist
    ports: dict[str, Node]
    buses: dict[str, list[Node]]
    transistors: list[Transistor] = field(default_factory=list)
    parent: str | None = None

    @property
    def is_leaf(self) -> bool:
        """True si la definición no contiene sub-instancias (es una celda primitiva)."""
        return not self.definition.instances

    def __getitem__(self, port: str) -> Node:
        """Nodo del padre conectado al puerto ``port`` del subcircuito."""
        return self.ports[port]

    def bus(self, name: str) -> list[Node]:
        """Nodos del padre conectados al bus ``name`` del subcircuito."""
        return self.buses[name]


def _bit_name(bus: str, index: int) -> str:
    return f"{bus}[{index}]"


class Netlist:
    """Circuito de transistores con puertos, buses y subcircuitos.

    Args:
        name: nombre del circuito (por ejemplo ``"nand2"``).
        sequential: True si el circuito almacena estado (latch, flip-flop, registro).
            El motor ``cached`` nunca tabula circuitos secuenciales (ADR-0008).
    """

    def __init__(self, name: str, *, sequential: bool = False) -> None:
        self.name = name
        self.sequential = sequential
        self.nodes: list[Node] = []
        self.transistors: list[Transistor] = []
        self.inputs: dict[str, Node] = {}
        self.outputs: dict[str, Node] = {}
        self.input_buses: dict[str, list[Node]] = {}
        self.output_buses: dict[str, list[Node]] = {}
        self.instances: list[Instance] = []
        self._by_name: dict[str, Node] = {}
        self._instance_names: set[str] = set()
        self._auto = 0
        self.vdd = self._new_node("VDD", NodeKind.VDD)
        self.gnd = self._new_node("GND", NodeKind.GND)

    # ------------------------------------------------------------------ nodos
    def _new_node(self, name: str, kind: NodeKind) -> Node:
        if name in self._by_name:
            raise NetlistError(f"{self.name}: nombre de nodo repetido {name!r}")
        node = Node(len(self.nodes), name, kind)
        self.nodes.append(node)
        self._by_name[name] = node
        return node

    def node(self, name: str | None = None) -> Node:
        """Crea un nodo interno. Sin nombre, se genera uno automático (``_n0``, ``_n1``…)."""
        if name is None:
            while f"_n{self._auto}" in self._by_name:
                self._auto += 1
            name = f"_n{self._auto}"
            self._auto += 1
        return self._new_node(name, NodeKind.INTERNAL)

    def input(self, name: str) -> Node:
        """Crea un puerto de entrada."""
        node = self._new_node(name, NodeKind.INPUT)
        self.inputs[name] = node
        return node

    def output(self, name: str) -> Node:
        """Crea un puerto de salida (un nodo interno visible desde fuera)."""
        node = self._new_node(name, NodeKind.INTERNAL)
        self.outputs[name] = node
        return node

    def mark_output(self, name: str, node: Node) -> Node:
        """Expone un nodo ya existente como puerto de salida ``name``."""
        if name in self.outputs:
            raise NetlistError(f"{self.name}: salida repetida {name!r}")
        if node.kind is not NodeKind.INTERNAL:
            raise NetlistError(f"{self.name}: solo un nodo interno puede ser salida ({name!r})")
        self.outputs[name] = node
        return node

    def input_bus(self, name: str, width: int) -> list[Node]:
        """Crea un bus de entrada de ``width`` bits llamados ``name[0]`` … (LSB primero)."""
        bits = [self.input(_bit_name(name, i)) for i in range(width)]
        self.input_buses[name] = bits
        return bits

    def output_bus(self, name: str, width: int) -> list[Node]:
        """Crea un bus de salida de ``width`` bits llamados ``name[0]`` … (LSB primero)."""
        bits = [self.output(_bit_name(name, i)) for i in range(width)]
        self.output_buses[name] = bits
        return bits

    def mark_output_bus(self, name: str, nodes: Sequence[Node]) -> list[Node]:
        """Expone nodos existentes como bus de salida ``name``."""
        bits = [self.mark_output(_bit_name(name, i), n) for i, n in enumerate(nodes)]
        self.output_buses[name] = bits
        return bits

    def find(self, name: str) -> Node:
        """Busca un nodo por nombre.

        Raises:
            KeyError: si no existe.
        """
        try:
            return self._by_name[name]
        except KeyError:
            raise KeyError(f"{self.name}: no existe el nodo {name!r}") from None

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    # ------------------------------------------------------------ transistores
    def _own(self, node: Node) -> Node:
        if node.id >= len(self.nodes) or self.nodes[node.id] is not node:
            raise NetlistError(f"{self.name}: el nodo {node.name!r} pertenece a otro netlist")
        return node

    def _add_transistor(
        self, kind: TransistorType, gate: Node, source: Node, drain: Node, name: str | None
    ) -> Transistor:
        t = Transistor(
            id=len(self.transistors),
            kind=kind,
            gate=self._own(gate),
            source=self._own(source),
            drain=self._own(drain),
            name=name if name is not None else f"{kind.value}{len(self.transistors)}",
        )
        self.transistors.append(t)
        return t

    def nmos(self, gate: Node, source: Node, drain: Node, name: str | None = None) -> Transistor:
        """Agrega un nMOS (conduce con compuerta en 1)."""
        return self._add_transistor(TransistorType.NMOS, gate, source, drain, name)

    def pmos(self, gate: Node, source: Node, drain: Node, name: str | None = None) -> Transistor:
        """Agrega un pMOS (conduce con compuerta en 0)."""
        return self._add_transistor(TransistorType.PMOS, gate, source, drain, name)

    def transmission_gate(
        self, a: Node, b: Node, enable: Node, enable_n: Node, name: str | None = None
    ) -> tuple[Transistor, Transistor]:
        """Agrega una transmission gate entre ``a`` y ``b``.

        Conduce cuando ``enable`` = 1 y ``enable_n`` = 0 (nMOS y pMOS en paralelo).
        """
        prefix = name or f"tg{len(self.transistors)}"
        n = self.nmos(enable, a, b, f"{prefix}.n")
        p = self.pmos(enable_n, a, b, f"{prefix}.p")
        return n, p

    # ------------------------------------------------------------- jerarquía
    def instantiate(
        self,
        sub: Netlist,
        name: str,
        connections: Mapping[str, Node | Sequence[Node]],
    ) -> Instance:
        """Copia ``sub`` dentro de este netlist como la instancia ``name``.

        Args:
            sub: netlist a instanciar.
            name: nombre de la instancia; los nodos internos se nombran ``name.nodo``.
            connections: puerto o bus del subcircuito → nodo(s) de este netlist. Todas
                las entradas deben conectarse. Las salidas no conectadas generan nodos
                nuevos llamados ``name.puerto``.

        Returns:
            La :class:`Instance` creada, que permite consultar los nodos de sus puertos.

        Raises:
            NetlistError: puerto desconocido, entrada sin conectar, ancho de bus
                distinto, nombre de instancia repetido o un subcircuito que se
                instancia a sí mismo.
        """
        if sub is self:
            raise NetlistError(f"{self.name}: un netlist no puede instanciarse a sí mismo")
        if name in self._instance_names or "." in name:
            raise NetlistError(f"{self.name}: nombre de instancia inválido o repetido {name!r}")

        port_map = self._expand_connections(sub, name, connections)
        missing = [p for p in sub.inputs if p not in port_map]
        if missing:
            raise NetlistError(f"{self.name}.{name}: entradas sin conectar {missing}")

        node_map: dict[int, Node] = {sub.vdd.id: self.vdd, sub.gnd.id: self.gnd}
        for port, node in sub.inputs.items():
            node_map[node.id] = port_map[port]
        for port, node in sub.outputs.items():
            if port in port_map:
                target = port_map[port]
                if node.id in node_map and node_map[node.id] is not target:
                    raise NetlistError(f"{self.name}.{name}: salida {port!r} conectada dos veces")
                node_map[node.id] = target
        for node in sub.nodes:
            if node.id not in node_map:
                node_map[node.id] = self.node(f"{name}.{node.name}")

        first = len(self.transistors)
        for t in sub.transistors:
            self._add_transistor(
                t.kind,
                node_map[t.gate.id],
                node_map[t.source.id],
                node_map[t.drain.id],
                f"{name}.{t.name}",
            )
        created = self.transistors[first:]

        for inner in sub.instances:
            self.instances.append(
                Instance(
                    path=f"{name}.{inner.path}",
                    definition=inner.definition,
                    ports={p: node_map[n.id] for p, n in inner.ports.items()},
                    buses={b: [node_map[n.id] for n in ns] for b, ns in inner.buses.items()},
                    transistors=[created[t.id] for t in inner.transistors],
                    parent=name if inner.parent is None else f"{name}.{inner.parent}",
                )
            )

        ports = {p: node_map[n.id] for p, n in (sub.inputs | sub.outputs).items()}
        buses = {
            b: [node_map[n.id] for n in ns]
            for b, ns in (sub.input_buses | sub.output_buses).items()
        }
        instance = Instance(name, sub, ports, buses, list(created), None)
        self.instances.append(instance)
        self._instance_names.add(name)
        return instance

    def _expand_connections(
        self, sub: Netlist, name: str, connections: Mapping[str, Node | Sequence[Node]]
    ) -> dict[str, Node]:
        """Traduce conexiones por puerto o por bus a un mapa puerto → nodo."""
        port_map: dict[str, Node] = {}
        sub_buses = sub.input_buses | sub.output_buses
        for key, target in connections.items():
            if isinstance(target, Node):
                if key not in sub.inputs and key not in sub.outputs:
                    raise NetlistError(f"{self.name}.{name}: {sub.name} no tiene el puerto {key!r}")
                port_map[key] = self._own(target)
            else:
                if key not in sub_buses:
                    raise NetlistError(f"{self.name}.{name}: {sub.name} no tiene el bus {key!r}")
                bits = sub_buses[key]
                if len(target) != len(bits):
                    raise NetlistError(
                        f"{self.name}.{name}: el bus {key!r} tiene {len(bits)} bits "
                        f"y se conectaron {len(target)}"
                    )
                for i, node in enumerate(target):
                    port_map[_bit_name(key, i)] = self._own(node)
        return port_map

    # ------------------------------------------------------------- consultas
    def transistor_count(self) -> dict[str, int]:
        """Conteo de transistores: ``{"nmos": …, "pmos": …, "total": …}``."""
        n = sum(1 for t in self.transistors if t.kind is TransistorType.NMOS)
        return {"nmos": n, "pmos": len(self.transistors) - n, "total": len(self.transistors)}

    def top_instances(self) -> list[Instance]:
        """Instancias de primer nivel (sin padre)."""
        return [i for i in self.instances if i.parent is None]

    def leaf_instances(self) -> list[Instance]:
        """Instancias de celdas primitivas (sin sub-instancias), a cualquier profundidad."""
        return [i for i in self.instances if i.is_leaf]

    def __repr__(self) -> str:
        c = self.transistor_count()
        return (
            f"Netlist({self.name!r}, nodos={len(self.nodes)}, transistores={c['total']}, "
            f"instancias={len(self.instances)})"
        )
