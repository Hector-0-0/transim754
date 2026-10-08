"""Adaptador por defecto: no usa IA (ADR-0012). El sistema funciona al 100 % con él."""

from __future__ import annotations

from transim.fpu.format import FloatFormat


class NullAssistant:
    """Asistente nulo: respuestas deterministas sin ningún modelo de lenguaje."""

    name = "ninguno"

    def explain_trace(self, trace: str) -> str:
        """Devuelve la traza tal cual, con una nota de que no hay asistente activo."""
        return f"(Sin asistente de IA configurado.)\n{trace}"

    def nl_to_program(self, request: str) -> str:
        """Devuelve un programa vacío comentado: la traducción requiere un asistente."""
        return f"; sin asistente de IA: escriba el programa a mano\n; petición: {request}\nHALT\n"

    def propose_edge_cases(self, op: str, fmt: FloatFormat, n: int) -> list[tuple[int, int]]:
        """Pares fijos y deterministas de casos borde (ceros, ∞, NaN, extremos)."""
        values = [
            fmt.zero(0),
            fmt.zero(1),
            1,
            fmt.max_finite(0),
            fmt.inf(0),
            fmt.inf(1),
            fmt.canonical_nan,
            fmt.compose(0, fmt.bias, 0),
        ]
        pairs = [(a, b) for a in values for b in values]
        return pairs[: max(0, n)]
