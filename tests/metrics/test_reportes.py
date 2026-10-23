"""Reportes de métricas (responsable: Yenny). Issue #24."""

from __future__ import annotations

import csv
from pathlib import Path

from transim.metrics.report import generate_reports

ESPERADOS = ["transistores", "actividad", "camino_critico", "comparacion_sumadores"]


def test_genera_markdown_y_csv(tmp_path: Path) -> None:
    rutas = generate_reports(tmp_path)
    nombres = {p.name for p in rutas}
    for base in ESPERADOS:
        assert f"{base}.md" in nombres
        assert f"{base}.csv" in nombres
    with (tmp_path / "transistores.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert {"modulo", "nmos", "pmos", "total"} <= set(filas[0])
    assert any(fila["modulo"] == "INV" and fila["total"] == "2" for fila in filas)
    assert "|" in (tmp_path / "transistores.md").read_text(encoding="utf-8")


def test_comparacion_sumadores_incluye_diferencias(tmp_path: Path) -> None:
    """Verifica que las conclusiones coincidan con los datos CSV."""
    generate_reports(tmp_path)

    reporte = (tmp_path / "comparacion_sumadores.md").read_text(encoding="utf-8")

    with (tmp_path / "comparacion_sumadores.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    datos: dict[int, dict[str, tuple[int, int]]] = {}

    for fila in filas:
        ancho = int(fila["ancho"])
        datos.setdefault(ancho, {})[fila["sumador"]] = (
            int(fila["transistores"]),
            int(fila["profundidad"]),
        )

    for ancho, valores in datos.items():
        rca_t, rca_p = valores["RCA"]
        cla_t, cla_p = valores["CLA"]

        conclusion = (
            f"{ancho} bits: CLA frente a RCA = "
            f"{cla_t - rca_t:+d} transistores y "
            f"{cla_p - rca_p:+d} niveles de profundidad."
        )

        assert conclusion in reporte
