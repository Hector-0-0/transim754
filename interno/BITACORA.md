# Bitácora del proyecto (interno)

Estado vivo. Entrada nueva arriba. Cada entrada: qué se hizo, decisiones, pendientes, siguiente paso.

---

## 2026-10-08 · F1 — Documentación de diseño

**Hecho**
- Repositorio público creado: https://github.com/Hector-0-0/transim754 (push de `main`, CI en verde).
- 13 ADR en `docs/adr/` con índice; docs 00–06, GLOSARIO, esqueleto de investigación y README.
- Los 6 ejemplos de `docs/03_ieee754.md` verificados contra numpy en
  `tests/docs/test_ejemplos_ieee754.py` (valores, flags que reporta numpy y exactitud con `Fraction`).
- Los 9 diagramas Mermaid validados con el parser oficial de mermaid 11.
- Revisión de material formal: grep de "prompt|claude|chat|ia generativa" en docs/ y README → 0 coincidencias.

**Decisiones**
- Objeciones D3/D4/D8/D11 aprobadas por Héctor (delegó la decisión): redactadas en ADR-0003/0004/0008/0011.
- FSR: bits 0–4 = NX, UF, OF, DZ, NV (orden de `fflags` de RISC-V); bits 8–11 = C, V, Z, N (no sticky).
- C en la resta entera = acarreo de salida de A + ¬B + 1 (convención ARM: C = 1 si no hubo préstamo).
- Binario del ensamblador en big-endian; instrucción ilegal → `IllegalInstructionError`.
- PC y FSM de comportamiento en v0.x; FSR y banco de registros en flip-flops (ADR-0006).
- `00_propuesta.md` sin Mermaid (no se renderiza al exportar a Word/PDF): diagramas en texto y tablas.
- numpy en x86 devuelve `0xFFC00000` para NaN: el oráculo compara NaN por clase y exige el canónico al simulador.
- pytest con `--import-mode=importlib` para permitir nombres de archivo de prueba repetidos.

**Pendientes**
- Nombres completos de Daniel, Jairo, Ronald, Fabricio y Yenny para la portada APA de 00_propuesta.
- F8: usuarios de GitHub del equipo.

**Siguiente paso**
- F2: núcleo L0 (Transistor, Node, señales, Netlist jerárquico, engine_switch) y sus pruebas.

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
