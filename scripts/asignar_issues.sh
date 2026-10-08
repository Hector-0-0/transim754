#!/usr/bin/env bash
# Asigna cada issue a su responsable (requiere que haya aceptado la invitación).
# Uso: scripts/asignar_issues.sh [--dry-run]
set -euo pipefail
cd "$(dirname "$0")/.."
gh auth status >/dev/null
python3 scripts/crear_issues.py --asignar "$@"
