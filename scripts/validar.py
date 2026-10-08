"""Validación de un módulo: `make validar M=<modulo>`.

Implementación completa en la fase F5 de la base (pruebas del módulo, ausencia de
xfail propios, conteo de transistores y conmutaciones, resumen PASS/FAIL).
"""

from __future__ import annotations

import sys


def main() -> int:
    modulo = sys.argv[1] if len(sys.argv) > 1 else "?"
    print(f"validar {modulo}: aún no disponible (se implementa en la fase F5).")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
