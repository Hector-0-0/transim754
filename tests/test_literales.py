"""ADR-0001: ningún módulo escribe a mano los parámetros del formato.

Los literales enteros 8, 23, 32 y 127 solo pueden aparecer en ``fpu/format.py``
(definición de los formatos) y ``cpu/isa.py`` (ancho de palabra y campos de la ISA).
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

PROHIBIDOS = {8, 23, 32, 127}
PERMITIDOS = {Path("fpu/format.py"), Path("cpu/isa.py")}
RAIZ = Path(__file__).resolve().parent.parent / "src" / "transim"


def literales_prohibidos(fuente: str) -> list[tuple[int, str]]:
    hallados = []
    for tok in tokenize.generate_tokens(io.StringIO(fuente).readline):
        if tok.type == tokenize.NUMBER:
            try:
                valor = int(tok.string.replace("_", ""), 0)
            except ValueError:
                continue  # flotantes
            if valor in PROHIBIDOS:
                hallados.append((tok.start[0], tok.string))
    return hallados


def test_detector_funciona() -> None:
    assert literales_prohibidos("x = 23\ny = 0x20\nz = 1.5\nw = 7") == [(1, "23"), (2, "0x20")]


def test_sin_literales_de_formato_fuera_de_format_e_isa() -> None:
    errores = []
    for archivo in sorted(RAIZ.rglob("*.py")):
        relativo = archivo.relative_to(RAIZ)
        if relativo in PERMITIDOS:
            continue
        for linea, texto in literales_prohibidos(archivo.read_text(encoding="utf-8")):
            errores.append(f"src/transim/{relativo}:{linea}: literal {texto}")
    assert not errores, "Literales prohibidos (ADR-0001):\n" + "\n".join(errores)
