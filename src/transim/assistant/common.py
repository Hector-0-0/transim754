"""Plantillas de mensaje y lectura de respuestas comunes a los adaptadores (ADR-0012).

El asistente explica, traduce y propone; el simulador calcula. Por eso las respuestas
se tratan como texto no confiable: los programas se pasan por el ensamblador y los
pares de operandos se filtran y se acotan al ancho del formato.
"""

from __future__ import annotations

import re

from transim.cpu.isa import OPERANDS, Opcode
from transim.fpu.format import FloatFormat

SYSTEM = (
    "Eres un asistente del simulador TranSim754, un procesador de transistores que "
    "opera con IEEE 754. Nunca calculas resultados: el simulador los calcula. "
    "Responde en español y de forma breve."
)

_ISA = "; ".join(
    f"{op.name} {', '.join(ops)}".strip() for op, ops in OPERANDS.items() if isinstance(op, Opcode)
)


def explain_request(trace: str) -> str:
    """Mensaje para explicar una traza ya calculada."""
    return (
        "Explica paso a paso, para un estudiante, la siguiente traza de una operación de "
        f"punto flotante calculada por el simulador. No recalcules nada.\n\n{trace}"
    )


def program_request(request: str) -> str:
    """Mensaje para traducir una petición a un programa ``.t754``."""
    return (
        "Escribe un programa en el ensamblador T754 para la petición del usuario. "
        f"Instrucciones disponibles: {_ISA}. Registros F0–F7; LI acepta un literal "
        "decimal o hexadecimal; comentarios con ';'. Termina con HALT. Responde solo con "
        f"el programa.\n\nPetición: {request}"
    )


def edge_cases_request(op: str, fmt: FloatFormat, n: int) -> str:
    """Mensaje para proponer pares de operandos interesantes."""
    return (
        f"Propón hasta {n} pares de operandos {fmt.name} (patrones de bits en hexadecimal) "
        f"interesantes para probar la operación '{op}': subnormales, empates de redondeo, "
        "desbordamientos, cancelaciones, NaN e infinitos. Un par por línea, con el formato "
        "'0xAAAAAAAA 0xBBBBBBBB', sin resultados ni explicaciones."
    )


_FENCE = re.compile(r"^```[\w-]*\s*$")


def strip_code_fences(text: str) -> str:
    """Quita las cercas de código Markdown y deja el programa con un salto final."""
    lines = [line for line in text.strip().splitlines() if not _FENCE.match(line.strip())]
    return "\n".join(lines).strip() + "\n"


_PAIR = re.compile(r"^\s*(0x[0-9a-fA-F]+|\d+)[\s,;]+(0x[0-9a-fA-F]+|\d+)\s*$")


def parse_pairs(text: str, fmt: FloatFormat, n: int) -> list[tuple[int, int]]:
    """Pares ``(a, b)`` válidos del texto, uno por línea; descarta lo demás.

    Solo se aceptan patrones que caben en ``fmt.width`` bits; como máximo ``n``.
    """
    pairs: list[tuple[int, int]] = []
    limit = 1 << fmt.width
    for line in text.splitlines():
        m = _PAIR.match(line)
        if not m:
            continue
        a, b = (int(x, 0) for x in m.groups())
        if a < limit and b < limit:
            pairs.append((a, b))
        if len(pairs) >= n:
            break
    return pairs
