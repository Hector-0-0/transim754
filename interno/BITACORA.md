# Bitácora del proyecto (interno)

Estado vivo. Entrada nueva arriba. Cada entrada: qué se hizo, decisiones, pendientes, siguiente paso.

---

## 2026-10-08 · F7 — Ensamblador, CLI y propuesta del avance

**Hecho (todo por PR: main está protegida)**
- PR #34 `feat/cpu-ensamblador` (Closes #29): ensamblador .t754 con errores
  archivo:línea:columna, literales decimales/fracciones/hex, binario big-endian,
  desensamblador. Validado con las pruebas escritas en F4 (todas pasan sin cambios).
- PR #35 `feat/cli-calc` (Refs #31, depende de #34): `transim calc/asm/run`. Si una unidad de
  transistores no está integrada usa la referencia y lo dice en la salida (ADR-0006).
  `make demo` funciona.
- PR #36 `docs/propuesta-avance` (Refs #33): propuesta final; exportada a DOCX (pandoc 3.9 en
  un entorno desechable) y PDF (LibreOffice): 11 páginas, sin cortes.

**Errores propios detectados y corregidos**
- La prueba `test_calc_con_traza_y_flags` (escrita en F4) comparaba "0x…" contra la salida en
  mayúsculas: imposible de pasar. Corregida en #35. Era una de las pruebas no validadas.
- La guarda de ADR-0001 detectó literales 8 (`WORD_BITS // 8`, `:08X`, ancho de columna).
  Corregido con `isa.WORD_BYTES` y constantes con nombre. Un push del CLI salió con la suite
  en rojo porque el `&&` encadenado a `tail` no detuvo el flujo; corregido de inmediato
  (force-with-lease sobre mi rama). Desde entonces: push solo si `pytest` devuelve 0.

**Pendientes para el avance (lunes 12)**
- Aprobación de un compañero para #34, #35 y #36 (main exige 1 aprobación).
- Que los integrantes acepten la invitación → `scripts/asignar_issues.sh`.
- Celdas (#1–#6), bloques (#7–#13), FADD/FSUB (#15–#17), métricas (#22–#24), investigación y
  diapositivas (#27, #28).
- Domingo: integrar FADD/FSUB, actualizar la tabla 11.1 de la propuesta, apellidos de Daniel,
  Fabricio y Yenny, ensayo; lunes: tag v0.1.0-avance.

---

## 2026-10-08 · F6 — GitHub (+ F8)

**Hecho**
- Daniel → @Sergiodam73 (verificado). CODEOWNERS sin marcadores pendientes; EQUIPO.md completo.
- Invitaciones de colaborador (permiso write) enviadas a los 5: JairoHCh, devronaldaz,
  Sergiodam73, Fabrizzio-07, yennyestherchavez (autorizado por la especificación de F8).
- 29 labels propios (16 modulo:*, 4 tipo:*, 3 prioridad:*, 6 persona:*; más los 10 por defecto), 3 milestones (v0.1.0-avance con
  fecha 2026-10-12, v0.5.0-parcial, v1.0.0-final) e issues #1–#33 creados desde TODO.md con
  `scripts/crear_issues.sh`; numeración verificada (#N = tarea N); re-ejecución → 0 cambios.
- Asignación: #29–#33 a Héctor. Hallazgo: GitHub ignora sin error la asignación a quien no
  aceptó la invitación → `scripts/asignar_issues.sh` ahora verifica y lista pendientes.
- Tag `v0.0.1-base` y protección de `main` (ver abajo).

**Decisiones**
- Protección de main: PR obligatorio, 1 aprobación, CI "ruff + mypy + pytest (rápidas)"
  obligatorio y al día, sin force push ni borrado, **enforce_admins = true** (la excepción de
  push directo de Héctor terminó con el tag). **No** se exige aprobación del code owner: con un
  solo dueño por módulo, el autor-dueño no podría integrar (no puede aprobarse a sí mismo).
  CODEOWNERS solo solicita revisores automáticamente.

**Pendientes**
- Cuando cada integrante acepte su invitación: `scripts/asignar_issues.sh`.
- Apellidos de Daniel, Fabricio y Yenny para la portada APA (si se desea).
- F7: demo CLI y versión final de docs/00_propuesta.md. Ahora todo cambio de Héctor va por PR
  y necesita la aprobación de otro integrante.

---

## 2026-10-08 · F5 — Guías, validación y material interno (+ F8 parcial)

**Hecho**
- GUIA.md (plantilla de 7 secciones) de cells, blocks, alu, fpu (ADDSUB y MULDIV), cpu,
  metrics, assistant y ui/gui; EQUIPO.md (integrantes, grafo de dependencias, calendario,
  validación) y CONTRIBUTING.md (primer día, identidad, ramas, commits, PR, DoD, reglas).
- `scripts/validar.py` + `make validar M=<modulo> [COMPLETO=1]`: pruebas, pendientes
  (`@pendiente(N)` y conjuntos `PENDIENTES = {…}`), stubs y métricas, con resumen PASS/FAIL.
  Comprobado: `core` PASS hoy; `cells` llega a PASS con las soluciones de validación.
- Datapaths FADD/FSUB, FMUL y FDIV descritos en las GUIA verificados con un modelo numérico
  paso a paso contra la referencia: 176 928 operaciones, 0 discrepancias.
- `interno/prompts/`: core, cells, blocks, fpu_addsub, fpu_muldiv, cpu, gui_metricas,
  assistant, investigacion (A desarrollo, B autovalidación, C estudio) y revision_pr.
- Revisión de material formal: grep "prompt|claude|chat|ia generativa" → solo el campo
  `"prompt"` de la API de Ollama en la GUIA del asistente (excepción permitida). Ningún
  documento formal enlaza a `interno/`. 21/21 diagramas Mermaid válidos.
- Corrección: `HardwareUnit.evaluate` omitía salidas sueltas definidas sobre un bit de bus.

**F8 parcial (usuarios recibidos)**
- Jairo → @JairoHCh (Jairo Jhosimar Huaman Choque), Ronald → @devronaldaz (Matthews Ronald
  Ayala Zubilete), Fabricio → @Fabrizzio-07, Yenny → @yennyestherchavez. Verificados con la
  API de GitHub. Aplicados en CODEOWNERS y EQUIPO.md.
- Daniel: usuario pendiente (`@PENDIENTE-Daniel` en CODEOWNERS).
- Pendiente: invitar como colaboradores (requisito para asignar issues y para que CODEOWNERS
  los reconozca) — esperando confirmación de Héctor.

**Pendientes**
- Usuario de GitHub y nombre completo de Daniel; apellidos de Fabricio y Yenny (portada APA).
- Validar las pruebas de ensamblador, máquina, CLI, adaptadores IA y GUI al implementarlos.

**Siguiente paso**
- F6: labels, milestones, issues #1–#33 desde TODO.md (con verificación de numeración),
  protección de `main` y tag `v0.0.1-base`.

---

## 2026-10-08 · F4 — Interfaces, referencia y pruebas por adelantado

**Hecho**
- Completos (son especificación): `fpu/format.py` (FloatFormat, Flags, FPClass, FPResult
  con `from_outputs`), `cpu/isa.py` (opcodes, encode/decode, FSR), `core/unit.py`
  (`HardwareUnit`, `make_engine`), `assistant/port.py` + `assistant/null.py`.
- `reference/`: `fpu.py` (aritmética racional exacta, RNE, subnormales, flags, tininess
  después de redondear, `round_and_pack`, `from_decimal` sin doble redondeo), `integer.py`,
  `blocks.py`, `cells.py`, `machine.py` (ISS de T754).
- Validación de la referencia contra numpy: 331 552 casos (2 formatos × 4 ops) → 0
  discrepancias de valor; binary32: 0 discrepancias de flags NV/DZ/OF/UF vs x86.
- Stubs con firmas, puertos y nombres de celda para todos los módulos; CLI con subcomandos
  stub; `examples/*.t754` (4 programas).
- `tests/oracle/` (oráculo verificado en cada uso, casos borde, aleatorios dirigidos,
  comparación legible), `tests/pendientes.py` (`@pendiente(N)` = xfail estricto con
  `raises=NotImplementedError`), `TODO.md` con la numeración #1–#33.
- Suite: 210 pasan, 164 pendientes (xfail), 1 omitida (GUI sin PySide6).

**Validación de las pruebas por adelantado (en copia desechable, nada se commitea)**
- Soluciones rápidas de celdas (incl. FA espejo 28 T, MUX2 12 T, latch/DFF/registro),
  bloques (RCA, CLA plano, add/sub, comparador, muxes, shifters con sticky, LZC) y ALU:
  88/88 pruebas pasan → interfaces implementables y pruebas correctas.
- FPU con dobles de referencia (valida lógica de pruebas, oráculo y umbrales): 61/63 +
  17/17 lentas (las 2 restantes requieren estructura real de compuertas, esperado).
- Métricas con implementación rápida: pasan.
- **No validadas aún:** ensamblador, decodificador, banco de registros, máquina, CLI,
  adaptadores Ollama/Anthropic, GUI (las de Héctor se validan al implementarlas en F7).

**Defectos del motor encontrados por la validación y corregidos (con regresiones)**
- Un nodo que pasaba de carga retenida a valor manejado sin cambiar de valor no actualizaba
  su último valor manejado → conteos distintos entre motores. Ahora un cambio de fuerza
  también marca el nodo.
- Cortocircuitos transitorios (solapamiento de TG al cambiar la selección) se advertían;
  ahora solo se reportan si persisten en el estado estable (ADR-0007 p. 7, docs/02).

**Decisiones**
- Hallazgo binary16: numpy detecta tininess antes de redondear (conversión por software);
  el oráculo compara UF de binary16 contra la referencia. Caso fijado en prueba.
- `round_and_pack(fmt)` es la interfaz compartida Daniel/Fabricio; su contrato exacto es
  `reference.fpu.round_and_pack` (exponente sesgado del MSB con signo en e+2 bits).
- Divisor: `quotient_bits = p + 3`; desplazadores y LZC: `width.bit_length()` bits.
- Recomendación para Jairo: latch con INV en la entrada de datos (entradas solo a
  compuertas también en celdas secuenciales).
- Nuevo ámbito de commit `reference` (se agrega a CONTRIBUTING en F5).

**Pendientes**
- Nombres completos del equipo (portada APA) y usuarios de GitHub (F8).

**Siguiente paso**
- F5: GUIA.md de cada módulo, EQUIPO.md, CONTRIBUTING.md, prompts internos,
  `scripts/validar.py` y revisión de palabras prohibidas en material formal.

---

## 2026-10-08 · F3 — Celdas semilla, motor cached y conteo

**Hecho**
- `cells/combinational.py`: INV (2 T), NAND2 (4 T), NOR2 (4 T), constructores memoizados
  (siempre el mismo objeto). `cells/library.py`: registro `CELLS`, `cell()`, `available()`.
- `core/engine_cached.py`: `CellTable` (tabla de verdad extraída con el motor switch +
  memoización `(entradas, estado) → (estado, fuerzas)`), `table_for`, `CachedEngine` mixto
  (celdas tabulables por tabla; el resto transistor por transistor) con `cached_instances`,
  `switch_instances` (con motivo) y `table_stats`.
- `metrics/count.py`: `count`, `count_by_instance`, `count_by_cell`.
- Pruebas: 101 en total. Equivalencia: cada celda con 0/1/X/Z, RCA jerárquico de 9 NAND
  por bit, circuito mixto, 60 circuitos aleatorios (hypothesis) en CI.
  Estrés local: 300 semillas del mixto + 1500 aleatorios → 0 discrepancias.
- Rendimiento RCA de 16 bits: switch 1,20 ms/op, cached 0,27 ms/op (×4,4), conteos idénticos.

**Decisiones (documentadas en ADR-0007 p. 9–10, ADR-0008 "Precisiones", docs/02 §3–4, docs/05)**
- Actividad contada sobre **estados estables** y sobre **valores manejados** (fuerza ≥ DRIVEN):
  los glitches de retardo cero dependen del orden de eventos; la carga retenida no conmuta.
- Equivalencia definida sobre el **estado observable** (nodos 0/1 manejados) + contadores.
  Hallazgo que lo motivó: con un MUX de TG sin buffer y selección X, el nodo de salida flota y
  su carga depende del orden de eventos (distinto entre motores, y también entre dos órdenes
  del mismo motor switch).
- Fuerza de una X = máximo de G_on y G_maybe (determinista).
- Criterio de tabulación automático (no secuencial, primitiva, entradas solo a compuertas,
  salidas sin canales externos). Regla de biblioteca L1: entradas de alta impedancia y
  salidas restauradas → **MUX2 de 12 T** (INV en entradas de datos y salida). Afecta a Jairo
  (celda) y a Ronald (barrel shifter: sin cadenas largas de TG).
- `Engine.read()` busca primero en puertos (alias de `mark_output`).

**Pendientes**
- Nombres completos del equipo (portada APA) y usuarios de GitHub (F8).

**Siguiente paso**
- F4: stubs con firmas para todos los módulos, `reference/` completo (FPU parametrizada con RNE,
  subnormales y flags, validada contra numpy en binary32 y binary16), harness `tests/oracle/`,
  pruebas por adelantado con `xfail(strict=True)`.

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
