"""Comparador de magnitud sin signo (capa L2, responsable: Ronald). ADR-0009."""

from __future__ import annotations

from transim.core.netlist import Netlist


def magnitude_comparator(width: int) -> Netlist:
    """Compara ``a`` y ``b`` sin signo usando el restador: a − b.

    lt = ¬cout (hubo préstamo); eq = todos los bits de la diferencia en 0 (árbol NOR);
    gt = ¬lt · ¬eq.

    Puertos: buses ``a[width]``, ``b[width]``; salidas ``lt``, ``eq``, ``gt``.
    Nombre del netlist ``f"CMP{width}"``.
    """
    raise NotImplementedError("pendiente: #9")
