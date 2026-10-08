"""Puerto del asistente de IA (ADR-0012): explica, traduce y propone; nunca calcula."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from transim.fpu.format import FloatFormat


@runtime_checkable
class Assistant(Protocol):
    """Contrato de todos los adaptadores de asistente."""

    name: str

    def explain_trace(self, trace: str) -> str:
        """Explica en lenguaje natural una traza ya calculada por el simulador."""
        ...

    def nl_to_program(self, request: str) -> str:
        """Propone un programa ``.t754`` para ``request``. El llamador debe pasarlo por
        el ensamblador; si no ensambla, se rechaza."""
        ...

    def propose_edge_cases(self, op: str, fmt: FloatFormat, n: int) -> list[tuple[int, int]]:
        """Propone hasta ``n`` pares de operandos (patrones de bits) interesantes para
        ``op``. El resultado esperado lo decide siempre el modelo de referencia."""
        ...
