"""Adaptador para un modelo local servido por Ollama (responsable: Héctor). ADR-0012.

Usa la API HTTP local de Ollama con ``urllib`` de la biblioteca estándar (sin
dependencias). Ningún dato sale del equipo.
"""

from __future__ import annotations

from transim.fpu.format import FloatFormat

DEFAULT_URL = "http://localhost:11434"


class OllamaAssistant:
    """Asistente sobre Ollama (``POST /api/generate``)."""

    name = "ollama"

    def __init__(self, model: str, url: str = DEFAULT_URL, timeout: float = 60.0) -> None:
        raise NotImplementedError("pendiente: #32")

    def explain_trace(self, trace: str) -> str:
        raise NotImplementedError("pendiente: #32")

    def nl_to_program(self, request: str) -> str:
        raise NotImplementedError("pendiente: #32")

    def propose_edge_cases(self, op: str, fmt: FloatFormat, n: int) -> list[tuple[int, int]]:
        raise NotImplementedError("pendiente: #32")
