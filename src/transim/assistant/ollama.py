"""Adaptador para un modelo local servido por Ollama. ADR-0012.

Usa la API HTTP local de Ollama con ``urllib`` de la biblioteca estándar (sin
dependencias). Ningún dato sale del equipo.
"""

from __future__ import annotations

import json
import urllib.request

from transim.assistant import common
from transim.fpu.format import FloatFormat

DEFAULT_URL = "http://localhost:11434"


class OllamaAssistant:
    """Asistente sobre Ollama (``POST /api/generate``)."""

    name = "ollama"

    def __init__(self, model: str, url: str = DEFAULT_URL, timeout: float = 60.0) -> None:
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout

    def _generate(self, message: str) -> str:
        """Envía ``message`` al modelo y devuelve el texto de la respuesta.

        Raises:
            RuntimeError: si Ollama no responde o la respuesta no es válida.
        """
        body = json.dumps(
            {"model": self.model, "system": common.SYSTEM, "prompt": message, "stream": False}
        ).encode()
        req = urllib.request.Request(
            f"{self.url}/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Ollama en {self.url} no respondió: {exc}") from exc
        return str(data.get("response", ""))

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
