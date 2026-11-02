"""Plano del chip (sin Qt): áreas proporcionales, sin solaparse y dentro del recuadro."""

from __future__ import annotations

import random

import pytest

from transim.ui.gui.floorplan import Tile, plan, squarify


@pytest.mark.parametrize("semilla", range(20))
def test_areas_proporcionales_y_sin_solaparse(semilla: int) -> None:
    rnd = random.Random(semilla)
    pesos = [rnd.randint(1, 4000) for _ in range(rnd.randint(1, 40))]
    ancho, alto = 1600.0, 1100.0
    rects = squarify(pesos, (0.0, 0.0, ancho, alto))
    total = sum(pesos)
    for peso, (x, y, w, h) in zip(pesos, rects, strict=True):
        assert w * h == pytest.approx(peso / total * ancho * alto, rel=1e-6)
        assert x >= -1e-6
        assert y >= -1e-6
        assert x + w <= ancho + 1e-6
        assert y + h <= alto + 1e-6
    for i, (x1, y1, w1, h1) in enumerate(rects):
        for x2, y2, w2, h2 in rects[i + 1 :]:
            solape_x = min(x1 + w1, x2 + w2) - max(x1, x2)
            solape_y = min(y1 + h1, y2 + h2) - max(y1, y2)
            assert solape_x <= 1e-6 or solape_y <= 1e-6


def test_piezas_casi_cuadradas() -> None:
    """Con pesos parecidos, ninguna pieza queda como una tira delgada."""
    rects = squarify([100] * 12, (0.0, 0.0, 1600.0, 1100.0))
    for _, _, w, h in rects:
        assert max(w, h) / min(w, h) < 2.5


def test_plan_respeta_el_orden_y_deja_huecos() -> None:
    tiles = [Tile("b", "B", 10, "#000"), Tile("a", "A", 30, "#000"), Tile("z", "Z", 0, "#000")]
    rects = plan(tiles, 400.0, 300.0, 10.0)
    assert len(rects) == 3
    area_b, area_a = rects[0][2] * rects[0][3], rects[1][2] * rects[1][3]
    assert area_a > area_b
    assert rects[2][2] == 0.0
    assert rects[2][3] == 0.0
