"""Profundidad del camino crítico en niveles de celda. ADR-0013."""

from __future__ import annotations

from transim.core.netlist import Instance, Netlist


def critical_path(netlist: Netlist) -> list[str]:
    """Caminos de instancia de las celdas primitivas del camino más largo, desde una
    entrada hasta una salida, en orden. Una celda depende de otra si alguna de sus
    entradas es una salida de la otra. Las celdas secuenciales cortan el camino.

    Raises:
        ValueError: si el grafo de celdas combinacionales tiene un ciclo.
    """
    cells = [i for i in netlist.leaf_instances() if not i.definition.sequential]
    producer: dict[int, int] = {}
    for k, inst in enumerate(cells):
        for port in inst.definition.outputs:
            producer[inst.ports[port].id] = k
    preds: list[set[int]] = [set() for _ in cells]
    succs: list[set[int]] = [set() for _ in cells]
    for k, inst in enumerate(cells):
        for port in inst.definition.inputs:
            src = producer.get(inst.ports[port].id)
            if src is not None and src != k:
                preds[k].add(src)
                succs[src].add(k)

    # Programación dinámica en orden topológico (Kahn).
    pending = [len(p) for p in preds]
    ready = [k for k in range(len(cells)) if not pending[k]]
    depth = [1] * len(cells)
    best_pred: list[int | None] = [None] * len(cells)
    visited = 0
    while ready:
        k = ready.pop()
        visited += 1
        for nxt in sorted(succs[k]):
            if depth[k] + 1 > depth[nxt]:
                depth[nxt], best_pred[nxt] = depth[k] + 1, k
            pending[nxt] -= 1
            if not pending[nxt]:
                ready.append(nxt)
    if visited != len(cells):
        raise ValueError(f"{netlist.name}: el grafo de celdas combinacionales tiene un ciclo")
    if not cells:
        return []
    end: int | None = max(range(len(cells)), key=lambda k: (depth[k], -k))
    path: list[Instance] = []
    while end is not None:
        path.append(cells[end])
        end = best_pred[end]
    return [inst.path for inst in reversed(path)]


def cell_depth(netlist: Netlist) -> int:
    """Longitud del camino crítico: ``len(critical_path(netlist))``."""
    return len(critical_path(netlist))
