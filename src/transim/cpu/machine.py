"""Máquina T754 con datapath de transistores (responsable: Héctor). ADR-0006, ADR-0010.

Integra memoria de programa (Python), ``ControlFSM``, decodificador de compuertas,
banco de registros de flip-flops, ``IntALU`` y las unidades de la FPU. Para cualquier
programa debe producir el mismo :class:`MachineState` que ``reference.machine.run``.
"""

from __future__ import annotations

from collections.abc import Sequence

from transim.core.unit import EngineName
from transim.fpu.format import BINARY32, FloatFormat
from transim.reference.machine import DEFAULT_MAX_STEPS, MachineState


class Machine:
    """Procesador T754 simulado.

    Args:
        program: palabras de 32 bits (salida del ensamblador).
        fmt: formato de punto flotante (binary32).
        engine: motor de simulación para el datapath.
    """

    def __init__(
        self,
        program: Sequence[int],
        fmt: FloatFormat = BINARY32,
        engine: EngineName = "cached",
    ) -> None:
        raise NotImplementedError("pendiente: #30")

    @property
    def state(self) -> MachineState:
        """Estado arquitectónico actual."""
        raise NotImplementedError("pendiente: #30")

    def step(self) -> None:
        """Ejecuta una instrucción completa (las cuatro fases)."""
        raise NotImplementedError("pendiente: #30")

    def run(self, max_steps: int = DEFAULT_MAX_STEPS) -> MachineState:
        """Ejecuta hasta HALT y devuelve el estado final."""
        raise NotImplementedError("pendiente: #30")
