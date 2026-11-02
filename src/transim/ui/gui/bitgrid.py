"""Rejilla de bits de un bloque (ADR-0018): cada celda en la columna de su bit.

- **Columna:** el bit del puerto del bloque (entrada o salida) más cercano a la celda en
  el grafo de conexiones; si hay empate, el de menor índice. El FA del bit *i* de un
  sumador queda en la columna *i*; cada nivel de un desplazador, alineado bit a bit.
- **Fila:** el nivel lógico de la celda: el camino más largo, en celdas, desde las
  entradas del bloque. La cadena de acarreo se ve como una escalera.

La rejilla se calcula del netlist; no se dibuja a mano. El módulo no depende de Qt.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import cache

from transim.core.netlist import Instance, Netlist

BROADCAST = 4
"""Un nodo que llega a más celdas que esto es de control (no indica un bit)."""


@dataclass(frozen=True, slots=True)
class Slot:
    """Una celda en la rejilla. ``sub`` separa celdas que caen en la misma casilla."""

    inst: Instance
    column: int
    row: int
    sub: int


@dataclass(frozen=True)
class Grid:
    """La rejilla de un bloque.

    Attributes:
        slots: una por celda primitiva del bloque.
        columns: número de columnas (bits).
        rows: número de filas (niveles lógicos).
        depth: celdas que caben en la casilla más llena.
    """

    slots: tuple[Slot, ...]
    columns: int
    rows: int
    depth: int


def _bit(name: str) -> int:
    """Índice de un puerto ``bus[i]`` (0 si es un puerto suelto)."""
    if name.endswith("]") and "[" in name:
        return int(name[name.index("[") + 1 : -1])
    return 0


@cache
def _grid(netlist: Netlist, path: str) -> Grid:
    block = next(i for i in netlist.instances if i.path == path)
    prefix = f"{path}."
    cells = [c for c in netlist.leaf_instances() if c.path.startswith(prefix)]
    d = block.definition
    # Puertos del bloque: nodo del padre → índice de bit (el menor si se repite).
    port_bit: dict[int, int] = {}
    inputs: set[int] = set()
    for name, node in block.ports.items():
        bit = _bit(name)
        port_bit[node.id] = min(bit, port_bit.get(node.id, bit))
        if name.split("[")[0] in d.input_buses or name in d.inputs:
            inputs.add(node.id)
    # Grafo celda–nodo: entradas y salidas de cada celda.
    ins: dict[int, list[int]] = {}
    outs: dict[int, list[int]] = {}
    touching: dict[int, list[int]] = {}
    for k, c in enumerate(cells):
        cd = c.definition
        ins[k] = [c.ports[p].id for p in cd.inputs]
        outs[k] = [c.ports[p].id for p in cd.outputs]
        for n in ins[k] + outs[k]:
            touching.setdefault(n, []).append(k)
    # Los rieles y las señales que llegan a muchas celdas (un control como ``sub`` o los
    # bits de desplazamiento) no ubican a nadie: se saltan en la búsqueda.
    skip = {netlist.vdd.id, netlist.gnd.id}
    skip |= {n for n, ks in touching.items() if len(ks) > BROADCAST}
    # Columna: búsqueda en anchura desde todos los bits de los puertos a la vez.
    best: dict[int, tuple[int, int]] = {}  # celda → (distancia, bit)
    queue: deque[tuple[int, int, int]] = deque()  # (nodo, distancia, bit)
    seen_node: dict[int, tuple[int, int]] = {}
    for n, bit in sorted(port_bit.items(), key=lambda kv: kv[1]):
        if n in skip:
            continue
        seen_node[n] = (0, bit)
        queue.append((n, 0, bit))
    while queue:
        n, dist, bit = queue.popleft()
        if seen_node.get(n, (dist, bit)) < (dist, bit):
            continue
        for k in touching.get(n, ()):
            cand = (dist + 1, bit)
            if k in best and best[k] <= cand:
                continue
            best[k] = cand
            for m in ins[k] + outs[k]:
                nxt = (dist + 1, bit)
                if m in skip:
                    continue
                if m not in seen_node or nxt < seen_node[m]:
                    seen_node[m] = nxt
                    queue.append((m, dist + 1, bit))
    # Fila: nivel lógico desde las entradas del bloque (orden topológico de Kahn).
    driver = {n: k for k, ns in outs.items() for n in ns}
    deps = {k: {driver[n] for n in ins[k] if n in driver and n not in inputs} - {k} for k in ins}
    users: dict[int, list[int]] = {}
    for k, ds in deps.items():
        for j in ds:
            users.setdefault(j, []).append(k)
    pending = {k: len(ds) for k, ds in deps.items()}
    level = dict.fromkeys(ins, 0)
    ready = deque(k for k, n in pending.items() if n == 0)
    while ready:
        k = ready.popleft()
        for u in users.get(k, ()):
            level[u] = max(level[u], level[k] + 1)
            pending[u] -= 1
            if pending[u] == 0:
                ready.append(u)
    used: dict[tuple[int, int], int] = {}
    slots: list[Slot] = []
    for k, c in enumerate(cells):
        column = best.get(k, (0, 0))[1]
        row = level[k]
        sub = used.get((column, row), 0)
        used[(column, row)] = sub + 1
        slots.append(Slot(c, column, row, sub))
    return Grid(
        tuple(slots),
        max((s.column for s in slots), default=0) + 1,
        max((s.row for s in slots), default=0) + 1,
        max(used.values(), default=1),
    )


def grid(netlist: Netlist, path: str) -> Grid:
    """Rejilla del bloque ``path`` (una instancia con sub-instancias) de ``netlist``."""
    return _grid(netlist, path)


__all__ = ["Grid", "Slot", "grid"]
