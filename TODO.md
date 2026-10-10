# Tareas

Espejo de los issues de GitHub. **El número de cada tarea es el número de su issue**:
las pruebas pendientes citan `#N` (`@pendiente(N)`), y `scripts/crear_issues.sh` crea los
issues en este orden y verifica que coincidan. No se reordena ni se renumera.

Formato: `#N · [Responsable] ámbito: título — dependencias — hito`.
Hitos: **A** = `v0.1.0-avance` (2026-10-12), **P** = `v0.5.0-parcial`, **F** = `v1.0.0-final`.

## Celdas L1 — Jairo

- [x] #1 · [Jairo] cells: AND2 y OR2 — sin dependencias — A
- [x] #2 · [Jairo] cells: XOR2 y XNOR2 de 12 transistores — sin dependencias — A
- [x] #3 · [Jairo] cells: MUX2 restaurador de 12 transistores — sin dependencias — A
- [x] #4 · [Jairo] cells: medio sumador y sumador completo espejo de 28 transistores — bloqueado por #1, #2 — A
- [x] #5 · [Jairo] cells: latch D y flip-flop D maestro-esclavo con transmission gates — sin dependencias — A
- [x] #6 · [Jairo] cells: registro de N bits con habilitación — bloqueado por #3, #5 — A

## Bloques L2 y ALU — Ronald

- [x] #7 · [Ronald] blocks: sumador ripple-carry de N bits — bloqueado por #4 — A
- [x] #8 · [Ronald] blocks: sumador/restador en complemento a 2 con desbordamiento — bloqueado por #2, #4 — A
- [x] #9 · [Ronald] blocks: comparador de magnitud — bloqueado por #8 — A
- [x] #10 · [Ronald] blocks: multiplexores de bus (MUX2×N y árbol MUX-N) — bloqueado por #3 — A
- [x] #11 · [Ronald] blocks: barrel shifter izquierda/derecha con sticky — bloqueado por #1, #3 — A
- [x] #12 · [Ronald] blocks: contador de ceros a la izquierda (LZC) — bloqueado por #1 — A
- [x] #13 · [Ronald] alu: ALU entera ADD/SUB con C, V, Z, N — bloqueado por #8 — A
- [x] #14 · [Ronald] blocks: sumador carry-lookahead y comparación con RCA — bloqueado por #7 — P

## FPU suma/resta — Daniel

- [x] #15 · [Daniel] fpu-common: desempaquetado, clasificador y casos especiales — bloqueado por #1 — A
- [x] #16 · [Daniel] fpu-common: redondeo RNE y empaquetado (round_and_pack) — bloqueado por #8, #11 — A
- [x] #17 · [Daniel] fpu-addsub: FADD/FSUB a nivel de transistor — bloqueado por #9, #11, #12, #15, #16 — A

## FPU multiplicación/división — Fabricio

- [x] #18 · [Fabricio] fpu-muldiv: multiplicador de mantisas en arreglo — bloqueado por #1, #4 — A
- [x] #19 · [Fabricio] fpu-muldiv: FMUL a nivel de transistor — bloqueado por #12, #15, #16, #18 — P
- [x] #20 · [Fabricio] fpu-muldiv: divisor no restaurador de mantisas — bloqueado por #8 — P
- [x] #21 · [Fabricio] fpu-muldiv: FDIV a nivel de transistor — bloqueado por #15, #16, #20 — P

## Métricas, GUI e investigación — Yenny

- [x] #22 · [Yenny] metrics: actividad de conmutación por operación (α) — sin dependencias — A
- [x] #23 · [Yenny] metrics: profundidad del camino crítico en niveles de celda — sin dependencias — A
- [x] #24 · [Yenny] metrics: reportes Markdown/CSV y comando `transim metrics` — bloqueado por #22, #23 — A
- [x] #25 · [Yenny] gui: ventana principal con operandos y vista de bits — sin dependencias — A
- [x] #26 · [Yenny] gui: etapas, conteos y ejecución de programas .t754 — bloqueado por #25, #30 — P
- [x] #27 · [Yenny] research: investigación "transistores en las CPU" — sin dependencias — A (borrador), F (final)
- [x] #28 · [Yenny] docs: diapositivas e informe APA del avance — bloqueado por #27 — A

## Integración — Héctor

- [x] #29 · [Héctor] cpu: ensamblador .t754 con errores por línea y columna — sin dependencias — A
- [x] #30 · [Héctor] cpu: máquina T754 (decodificador, banco de registros, control) — bloqueado por #6, #10, #13, #17 — P
- [x] #31 · [Héctor] cli: `transim calc`, `asm` y `run` — bloqueado por #17, #29 — A
- [x] #32 · [Héctor] ai: adaptadores Ollama y Anthropic — bloqueado por #29 — P
- [x] #33 · [Héctor] repo: integración del avance (FADD/FSUB en transistores, demo, tag v0.1.0-avance) — bloqueado por #17, #24, #31 — A
