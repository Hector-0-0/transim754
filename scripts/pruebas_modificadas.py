"""Ejecuta las pruebas rápidas de los módulos afectados por los archivos indicados.

Lo invoca el gancho de pre-commit con la lista de archivos Python preparados.
Un archivo `src/transim/<modulo>/...` o `tests/<modulo>/...` activa `tests/<modulo>/`.
Cualquier otro archivo Python (scripts, conftest, raíz) activa la suite rápida completa.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SIN_PRUEBAS = 5


def modulos_afectados(archivos: list[str]) -> set[str] | None:
    """Devuelve los módulos a probar, o None si hay que correr toda la suite rápida."""
    modulos: set[str] = set()
    for archivo in archivos:
        partes = Path(archivo).parts
        if len(partes) >= 4 and partes[:2] == ("src", "transim"):
            modulos.add(partes[2])
        elif len(partes) >= 3 and partes[0] == "tests":
            modulos.add(partes[1])
        else:
            return None
    return modulos


def main() -> int:
    modulos = modulos_afectados(sys.argv[1:])
    if modulos is None:
        rutas = ["tests"]
    else:
        rutas = [f"tests/{m}" for m in sorted(modulos) if (RAIZ / "tests" / m).is_dir()]
    if not rutas:
        return 0
    cmd = [sys.executable, "-m", "pytest", "-m", "not slow", "-q", "-x", *rutas]
    codigo = subprocess.call(cmd, cwd=RAIZ)
    # 5 = pytest no recolectó pruebas (módulo aún sin pruebas): no es un fallo.
    return 0 if codigo == SIN_PRUEBAS else codigo


if __name__ == "__main__":
    raise SystemExit(main())
