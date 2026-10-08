"""Reportes de métricas (responsable: Yenny). Issue #24."""

from __future__ import annotations

import csv
from pathlib import Path

from pendientes import pendiente
from transim.metrics.report import generate_reports

ESPERADOS = ["transistores", "actividad", "camino_critico", "comparacion_sumadores"]


@pendiente(24)
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
