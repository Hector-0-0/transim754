#!/usr/bin/env bash
# Crea labels, milestones e issues #1–#33 desde TODO.md (idempotente).
# Uso: scripts/crear_issues.sh [--dry-run]
set -euo pipefail
cd "$(dirname "$0")/.."
gh auth status >/dev/null
python3 scripts/crear_issues.py "$@"
