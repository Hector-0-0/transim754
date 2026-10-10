"""Adaptador opcional para la API de Anthropic. ADR-0012.

Requiere el extra ``ai`` (``pip install -e ".[ai]"``). La clave se lee únicamente de
la variable de entorno ``ANTHROPIC_API_KEY``; nunca se guarda en el repositorio.
"""

from __future__ import annotations

import os
from typing import Any

from transim.assistant import common
from transim.fpu.format import FloatFormat

API_KEY_ENV = "ANTHROPIC_API_KEY"
MAX_TOKENS = 1024


class AnthropicAssistant:
    """Asistente sobre la API de Anthropic."""

    name = "anthropic"

    def __init__(self, model: str) -> None:
        """Crea el cliente.

        Raises:
            RuntimeError: si falta la variable ``ANTHROPIC_API_KEY`` o el extra ``ai``.
        """
        key = os.environ.get(API_KEY_ENV)
        if not key:
            raise RuntimeError(f"defina la variable de entorno {API_KEY_ENV} con su clave")
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError('instale el extra de IA: pip install -e ".[ai]"') from exc
        self.model = model
        self._client: Any = anthropic.Anthropic(api_key=key)

    def _generate(self, message: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=common.SYSTEM,
            messages=[{"role": "user", "content": message}],
        )
        return "".join(getattr(block, "text", "") for block in response.content)

    def explain_trace(self, trace: str) -> str:
        """Explica en lenguaje natural una traza ya calculada por el simulador."""
        return self._generate(common.explain_request(trace)).strip()

    def nl_to_program(self, request: str) -> str:
        """Propone un programa ``.t754`` (sin cercas de código) para ``request``."""
        return common.strip_code_fences(self._generate(common.program_request(request)))

    def propose_edge_cases(self, op: str, fmt: FloatFormat, n: int) -> list[tuple[int, int]]:
        """Pares de operandos propuestos por el modelo, filtrados y acotados."""
        text = self._generate(common.edge_cases_request(op, fmt, n))
        return common.parse_pairs(text, fmt, n)
