"""Ayudas para cablear celdas dentro de un netlist (capas L2 y L3).

Cada función instancia celdas de la biblioteca L1 con nombres únicos y devuelve el
nodo de salida, de modo que los bloques se escriben como expresiones lógicas.
"""

from __future__ import annotations

from collections.abc import Sequence

from transim.cells import combinational as cells
from transim.core.netlist import Netlist
from transim.core.node import Node


class Wiring:
    """Instancia celdas en ``nl`` con nombres ``{prefijo}{n}`` correlativos."""

    def __init__(self, nl: Netlist, prefix: str = "g") -> None:
        self.nl = nl
        self.prefix = prefix
        self._n = 0

    def _name(self, kind: str) -> str:
        self._n += 1
        return f"{self.prefix}{kind}{self._n}"

    def _cell(self, sub: Netlist, kind: str, ins: dict[str, Node], out: Node | None) -> Node:
        target = out if out is not None else self.nl.node(self._name(kind) + "_y")
        self.nl.instantiate(sub, self._name(kind), {**ins, "y": target})
        return target

    def inv(self, a: Node, out: Node | None = None) -> Node:
        """¬a."""
        return self._cell(cells.inv(), "inv", {"a": a}, out)

    def buf(self, a: Node, out: Node | None = None) -> Node:
        """Copia restaurada de ``a`` (dos inversores)."""
        return self.inv(self.inv(a), out)

    def const(self, value: int, out: Node | None = None) -> Node:
        """Salida manejada con el valor constante ``value`` (inversor desde un riel)."""
        return self.inv(self.nl.gnd if value else self.nl.vdd, out)

    def and2(self, a: Node, b: Node, out: Node | None = None) -> Node:
        """a·b."""
        return self._cell(cells.and2(), "and", {"a": a, "b": b}, out)

    def or2(self, a: Node, b: Node, out: Node | None = None) -> Node:
        """a + b."""
        return self._cell(cells.or2(), "or", {"a": a, "b": b}, out)

    def nor2(self, a: Node, b: Node, out: Node | None = None) -> Node:
        """¬(a + b)."""
        return self._cell(cells.nor2(), "nor", {"a": a, "b": b}, out)

    def xor2(self, a: Node, b: Node, out: Node | None = None) -> Node:
        """a ⊕ b."""
        return self._cell(cells.xor2(), "xor", {"a": a, "b": b}, out)

    def mux2(self, a: Node, b: Node, s: Node, out: Node | None = None) -> Node:
        """a si s = 0, b si s = 1."""
        return self._cell(cells.mux2(), "mux", {"a": a, "b": b, "s": s}, out)

    def full_adder(self, a: Node, b: Node, cin: Node, s: Node | None = None) -> Node:
        """Coloca un FA; conecta la suma a ``s`` (o a un nodo nuevo) y devuelve cout."""
        name = self._name("fa")
        target = s if s is not None else self.nl.node(name + "_s")
        cout = self.nl.node(name + "_cout")
        self.nl.instantiate(
            cells.full_adder(), name, {"a": a, "b": b, "cin": cin, "s": target, "cout": cout}
        )
        return cout

    def and_tree(self, nodes: Sequence[Node]) -> Node:
        """AND de todos los nodos con un árbol balanceado de AND2."""
        return self._tree(list(nodes), self.and2)

    def or_tree(self, nodes: Sequence[Node]) -> Node:
        """OR de todos los nodos con un árbol balanceado de OR2."""
        return self._tree(list(nodes), self.or2)

    @staticmethod
    def _tree(nodes: list[Node], op: object) -> Node:
        if not nodes:
            raise ValueError("árbol sin entradas")
        while len(nodes) > 1:
            pairs = [op(nodes[i], nodes[i + 1]) for i in range(0, len(nodes) - 1, 2)]  # type: ignore[operator]
            nodes = pairs + ([nodes[-1]] if len(nodes) % 2 else [])
        return nodes[0]


def ripple_add(
    w: Wiring, a: Sequence[Node], b: Sequence[Node], cin: Node
) -> tuple[list[Node], Node]:
    """Suma ``a + b + cin`` con una cadena de FA. Devuelve (suma, acarreo de salida)."""
    tag = w._name("sum")
    s = [w.nl.node(f"{tag}_{i}") for i in range(len(a))]
    carries = ripple_chain(w, a, b, cin, s)
    return s, carries[-1]


def ripple_chain(
    w: Wiring, a: Sequence[Node], b: Sequence[Node], cin: Node, s: Sequence[Node]
) -> list[Node]:
    """Cadena de FA (bit 0 = LSB). Devuelve los acarreos c[0] = cin … c[n] = cout."""
    carries = [cin]
    for i in range(len(a)):
        carries.append(w.full_adder(a[i], b[i], carries[i], s[i]))
    return carries


def constant_bus(nl: Netlist, value: int, width: int) -> list[Node]:
    """Constante ``value`` en complemento a 2 de ``width`` bits, tomada de los rieles."""
    return [nl.vdd if (value >> i) & 1 else nl.gnd for i in range(width)]
