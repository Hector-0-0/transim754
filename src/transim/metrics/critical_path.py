"""Profundidad del camino crítico en niveles de celda (responsable: Yenny). ADR-0013."""

from __future__ import annotations

from transim.core.netlist import Netlist


def critical_path(netlist: Netlist) -> list[str]:
    """Caminos de instancia de las celdas primitivas del camino más largo, desde una
    entrada hasta una salida, en orden. Una celda depende de otra si alguna de sus
    entradas es una salida de la otra. Las celdas secuenciales cortan el camino.

    Raises:
        ValueError: si el grafo de celdas combinacionales tiene un ciclo.
    """
    raise NotImplementedError("pendiente: #23")


def cell_depth(netlist: Netlist) -> int:
    """Longitud del camino crítico: ``len(critical_path(netlist))``."""
    raise NotImplementedError("pendiente: #23")
