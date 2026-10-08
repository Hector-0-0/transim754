"""Registro de las celdas de la biblioteca L1, por nombre."""

from __future__ import annotations

from collections.abc import Callable

from transim.cells import combinational
from transim.core.netlist import Netlist

CELLS: dict[str, Callable[[], Netlist]] = {
    "INV": combinational.inv,
    "NAND2": combinational.nand2,
    "NOR2": combinational.nor2,
}
"""Nombre de celda → constructor. Cada módulo de celdas registra aquí las suyas."""


def cell(name: str) -> Netlist:
    """Netlist de la celda ``name`` (por ejemplo ``"NAND2"``).

    Raises:
        KeyError: si la celda no existe.
    """
    try:
        return CELLS[name]()
    except KeyError:
        raise KeyError(f"no existe la celda {name!r}; disponibles: {sorted(CELLS)}") from None


def available() -> list[str]:
    """Nombres de las celdas registradas, en orden alfabético."""
    return sorted(CELLS)
