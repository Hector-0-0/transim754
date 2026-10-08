# Bitácora del proyecto (interno)

Estado vivo. Entrada nueva arriba. Cada entrada: qué se hizo, decisiones, pendientes, siguiente paso.

---

## 2026-10-08 · F0 — Andamiaje

**Hecho**
- Identidad git local del repo: Héctor David Flores Sánchez <floressanchezhectordavid@gmail.com>.
- Estructura `src/transim/` por capas (L0–L5), `tests/` espejo, `docs/`, `examples/`, `scripts/`, `interno/`.
- `pyproject.toml` (hatchling; extras `dev`, `gui`, `dist`, `ai`), `Makefile`, pre-commit
  (ruff + pruebas rápidas del módulo tocado), CI de GitHub Actions, LICENSE MIT, CHANGELOG,
  plantillas de issue/PR, CODEOWNERS con marcadores `@PENDIENTE-<nombre>`.
- CLI mínimo `transim version` y prueba de humo.

**Decisiones / observaciones técnicas planteadas al líder**
- D4: la detección de tininess "tras redondeo" es una opción permitida por IEEE 754-2019 §7.5
  (la de x86), no "la" regla por defecto; lo por defecto es exigir además inexactitud.
- D3: sNaN de entrada levanta invalid; qNaN no. Salida siempre NaN canónico.
- D8: el motor cached memoiza (entradas, estado interno) → (nuevo estado, salidas) para que el
  conteo de conmutaciones internas coincida exactamente con el motor switch.
- D11: PySide6, PyInstaller y anthropic como extras opcionales; Ollama vía urllib (stdlib).

**Pendientes**
- Repositorio remoto `Hector-0-0/transim754` no existe todavía: commits solo locales.
- Confirmar correo de GitHub de Héctor.
- F8 (asignación a usuarios de GitHub): a la espera de los usuarios de los compañeros.

**Siguiente paso**
- F1: documentación de diseño (docs 00–06, 13 ADR, glosario, investigación, README).
