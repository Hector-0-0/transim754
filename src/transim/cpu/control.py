"""Secuenciador de control FETCH → DECODE → EXECUTE → WRITEBACK (responsable: Héctor).

En v0.x es de comportamiento (ADR-0006); en v1.0 pasa a compuertas y flip-flops sin
cambiar esta interfaz.
"""

from __future__ import annotations

from enum import Enum


class Phase(Enum):
    """Fase del ciclo de instrucción."""

    FETCH = "fetch"
    DECODE = "decode"
    EXECUTE = "execute"
    WRITEBACK = "writeback"
    HALTED = "halted"


class ControlFSM:
    """Máquina de estados del ciclo de instrucción."""

    def __init__(self) -> None:
        self.phase = Phase.FETCH

    def advance(self, *, halt: bool = False) -> Phase:
        """Pasa a la fase siguiente (``halt`` en DECODE lleva a HALTED) y la devuelve."""
        raise NotImplementedError("pendiente: #30")
