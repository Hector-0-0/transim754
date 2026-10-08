"""Reportes de métricas en Markdown y CSV (responsable: Yenny). ADR-0013, docs/05 §5."""

from __future__ import annotations

from pathlib import Path


def generate_reports(out_dir: Path) -> list[Path]:
    """Genera ``transistores``, ``actividad``, ``camino_critico`` y
    ``comparacion_sumadores`` en ``.md`` y ``.csv`` dentro de ``out_dir``.

    Los bloques aún no implementados se omiten con una nota en el Markdown.

    Returns:
        Rutas de los archivos escritos.
    """
    raise NotImplementedError("pendiente: #24")
