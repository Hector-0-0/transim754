# Bitácora del proyecto (interno)

Estado vivo. Entrada nueva arriba. Cada entrada: qué se hizo, decisiones, pendientes, siguiente paso.

---

## 2026-10-08 · F2 — Núcleo L0

**Hecho**
- `core/signals.py` (Logic, Strength, Signal, `resolve`, `to_logic`), `core/node.py`,
  `core/transistor.py` (TransistorType, Conduction), `core/netlist.py` (puertos, buses,
  `transmission_gate`, `instantiate` jerárquico con `Instance`), `core/engine_switch.py`.
- 65 pruebas en `tests/core/`: inversor, NAND2, NOR2, AND2 jerárquico, TG, carga retenida
  (TG y nodo interno de la pila), reparto de carga → X, cortocircuito → X + `ShortCircuitWarning`,
  anillo NAND+2 INV → `OscillationError`, propagación de X/Z, conteo de conmutaciones y
  eventos, buses, errores de construcción, propiedad con hypothesis.
- Rendimiento medido: cadena de 2000 inversores (4000 T) ≈ 200 000 eventos de transistor/s.

**Decisiones**
- Conmutación = nuevo valor definido distinto del último valor definido (1→X→0 cuenta 1).
  Documentado en docs/02 §3.
- Las fuentes (VDD, GND, entradas) no se atraviesan al formar el CCC.
- `instantiate` aplana al instanciar y registra `Instance` con camino, padre y transistores;
  `leaf_instances()` da las celdas primitivas (base del motor cached y del camino crítico).
- Ayudas de prueba compartidas en `tests/core/circuitos.py`; pytest con `pythonpath = ["tests"]`.
- El anillo de prueba usa NAND + 2 INV porque un anillo de 3 INV puro arranca en X y se
  queda estable en X (el modelo es correcto: no hay valor definido que oscile).

**Pendientes**
- Nombres completos del equipo (portada APA) y usuarios de GitHub (F8).

**Siguiente paso**
- F3: celdas INV, NAND2, NOR2 en `cells/`, `engine_cached` con extracción automática y
  memoización con estado interno, prueba de equivalencia de motores y `metrics/count.py`.

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
