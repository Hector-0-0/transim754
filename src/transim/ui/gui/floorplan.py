"""Plano del chip: cada bloque como un rectángulo de área proporcional a sus transistores.

Es la vista de silicio a escala de chip y de bloque, como las fotos anotadas de un
procesador: no se dibujan las celdas una por una sino las regiones que ocupan. Se usa
el algoritmo de rectángulos casi cuadrados (*squarified treemap*) de Bruls, Huizing y
van Wijk (2000), que reparte un rectángulo en filas o columnas de piezas con una
proporción lo más cercana a 1 posible, para que los nombres quepan.

El plano es ilustrativo: el área sale del número de transistores, no de un layout real
con sus reglas de diseño (ADR-0015). El módulo no depende de Qt.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

Rect = tuple[float, float, float, float]
"""(x, y, ancho, alto)."""


@dataclass(frozen=True, slots=True)
class Tile:
    """Una región del plano.

    Attributes:
        key: lo que se abre al hacer doble clic (camino de la instancia o ``"glue"``).
        title: nombre para mostrar.
        weight: transistores (define el área).
        color: etapa cuyo color se usa.
    """

    key: str
    title: str
    weight: int
    color: str


def _worst(row: Sequence[float], side: float) -> float:
    """Peor proporción (lado mayor / lado menor) de una fila de áreas sobre ``side``."""
    total = sum(row)
    if total <= 0 or side <= 0:
        return float("inf")
    big, small = max(row), min(row)
    return max(side * side * big / (total * total), (total * total) / (side * side * small))


def _lay_row(row: Sequence[float], rect: Rect) -> tuple[list[Rect], Rect]:
    """Coloca ``row`` a lo largo del lado corto de ``rect``; devuelve lo que sobra."""
    x, y, w, h = rect
    total = sum(row)
    out: list[Rect] = []
    if w >= h:  # columna a la izquierda
        cw = total / h if h else 0.0
        cy = y
        for a in row:
            ch = a / cw if cw else 0.0
            out.append((x, cy, cw, ch))
            cy += ch
        return out, (x + cw, y, w - cw, h)
    rh = total / w if w else 0.0  # fila arriba
    cx = x
    for a in row:
        cw = a / rh if rh else 0.0
        out.append((cx, y, cw, rh))
        cx += cw
    return out, (x, y + rh, w, h - rh)


def squarify(weights: Sequence[float], rect: Rect) -> list[Rect]:
    """Reparte ``rect`` en piezas de área proporcional a ``weights`` (mismo orden).

    Los pesos se ordenan de mayor a menor para colocarlos; el resultado vuelve al orden
    de entrada. Un peso cero recibe un rectángulo vacío.
    """
    x, y, w, h = rect
    total = sum(weights)
    if total <= 0:
        return [(x, y, 0.0, 0.0) for _ in weights]
    scale = w * h / total
    order = sorted(range(len(weights)), key=lambda k: -weights[k])
    areas = [weights[k] * scale for k in order if weights[k] > 0]
    placed: list[Rect] = []
    free = rect
    row: list[float] = []
    for a in areas:
        side = min(free[2], free[3])
        if not row or _worst([*row, a], side) <= _worst(row, side):
            row.append(a)
            continue
        done, free = _lay_row(row, free)
        placed.extend(done)
        row = [a]
    if row:
        done, free = _lay_row(row, free)
        placed.extend(done)
    result: list[Rect] = [(x, y, 0.0, 0.0)] * len(weights)
    it = iter(placed)
    for k in order:
        if weights[k] > 0:
            result[k] = next(it)
    return result


def plan(tiles: Sequence[Tile], width: float, height: float, gap: float) -> list[Rect]:
    """Rectángulos de ``tiles`` dentro de ``width × height``, separados por ``gap``."""
    rects = squarify([t.weight for t in tiles], (0.0, 0.0, width, height))
    half = gap / 2
    return [
        (rx + half, ry + half, max(0.0, rw - gap), max(0.0, rh - gap)) for rx, ry, rw, rh in rects
    ]


__all__ = ["Rect", "Tile", "plan", "squarify"]
