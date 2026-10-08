"""Adaptador opcional para la API de Anthropic (responsable: Héctor). ADR-0012.

Requiere el extra ``ai`` (``pip install -e ".[ai]"``). La clave se lee únicamente de
la variable de entorno ``ANTHROPIC_API_KEY``; nunca se guarda en el repositorio.
"""

from __future__ import annotations

from transim.fpu.format import FloatFormat

API_KEY_ENV = "ANTHROPIC_API_KEY"


class AnthropicAssistant:
    """Asistente sobre la API de Anthropic."""

    name = "anthropic"

    def __init__(self, model: str) -> None:
        raise NotImplementedError("pendiente: #32")

    def explain_trace(self, trace: str) -> str:
        raise NotImplementedError("pendiente: #32")

    def nl_to_program(self, request: str) -> str:
        raise NotImplementedError("pendiente: #32")

    def propose_edge_cases(self, op: str, fmt: FloatFormat, n: int) -> list[tuple[int, int]]:
        raise NotImplementedError("pendiente: #32")
