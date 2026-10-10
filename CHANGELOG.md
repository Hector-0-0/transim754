# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto sigue [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.1.0-avance] — 2026-10-10

Las cuatro operaciones IEEE 754 se calculan en transistores simulados y la máquina T754
ejecuta programas completos sobre ese hardware.

### Agregado
- Biblioteca de celdas L1 completa: AND2, OR2, XOR2, XNOR2, MUX2 restaurador, medio
  sumador, sumador completo espejo de 28 transistores, latch D, flip-flop maestro-esclavo
  y registro de N bits con habilitación.
- Bloques L2: sumadores ripple-carry y carry-lookahead jerárquico, sumador/restador con
  desbordamiento, comparador de magnitud, multiplexores de bus, desplazador barrel con
  sticky y contador de ceros a la izquierda; ALU entera de 32 bits con C, V, Z y N.
- FPU en transistores: desempaquetado, clasificador, casos especiales, `round_and_pack`
  con RNE y tininess después de redondear, FADD/FSUB, multiplicador en arreglo con FMUL
  y divisor no restaurador con FDIV, en binary32 y binary16. Sin discrepancias de bits ni
  de indicadores frente al oráculo en todos los pares borde y 10 000 pares aleatorios por
  operación y formato.
- Máquina T754: decodificador de compuertas, banco de ocho registros de flip-flops,
  secuenciador de control y ejecución con el mismo estado final que la referencia.
- Métricas: actividad de conmutación, camino crítico y reportes Markdown/CSV
  (`transim metrics`, `docs/metricas/`).
- Interfaz gráfica con PySide6 (`transim gui`): operaciones con vista de bits, etapas y
  métricas, y ejecución de programas `.t754` paso a paso.
- Adaptadores de asistente para Ollama y Anthropic, opcionales y sin cálculo.
- Investigación sobre transistores en las CPU y diapositivas del avance.

### Cambiado
- El CLI calcula siempre en transistores: ya no recurre al modelo de referencia.
- `main` exige integración continua en verde, pero no aprobación de revisión.

### Corregido
- `make validar` ya no cuenta como pendiente el ejemplo del docstring de
  `tests/pendientes.py`.

## [0.0.1-base] — 2026-10-08

Base del repositorio lista para el trabajo en paralelo del equipo.

### Agregado
- Andamiaje del repositorio: estructura de paquetes `src/transim/` por capas (L0–L5),
  `pyproject.toml`, `Makefile`, configuración de pre-commit, integración continua
  (ruff, mypy, pytest), licencia MIT y plantillas de GitHub.
- Documentación de diseño: propuesta del avance, arquitectura, simulador switch-level,
  IEEE 754 con seis ejemplos verificados contra numpy, ISA T754, métricas, política de IA,
  glosario, esqueleto de investigación y los 13 ADR.
- Núcleo L0: valores y fuerzas, transistores, netlist jerárquico con buses e instancias,
  y motor `switch` con CCC, carga retenida, cortocircuitos, oscilación y conteo de actividad.
- Celdas semilla INV, NAND2 y NOR2; motor `cached` con tablas extraídas automáticamente y
  equivalencia probada; conteo de transistores por módulo y por celda.
- Modelos de referencia completos (FPU exacta parametrizada, ALU, bloques, celdas, ISS de
  T754) validados contra numpy; interfaces de todos los módulos; oráculo de pruebas;
  pruebas por adelantado marcadas como pendientes; programas de ejemplo `.t754`.
- Guías técnicas de cada módulo, EQUIPO.md, CONTRIBUTING.md y `make validar M=<modulo>`.
- Labels, milestones e issues #1–#33 en GitHub (`scripts/crear_issues.sh`, idempotente)
  y asignación verificada (`scripts/asignar_issues.sh`).

### Corregido
- El contador de conmutaciones considera los cambios solo de fuerza; los cortocircuitos se
  reportan solo si persisten en el estado estable.
- `HardwareUnit.evaluate` reporta las salidas sueltas definidas sobre un bit de bus.

## Hitos previstos
- `v0.0.1-base` — base del repositorio lista para el trabajo en paralelo.
- `v0.1.0-avance` — 2026-10-12, presentación del avance.
- `v0.5.0-parcial` — fecha por confirmar.
- `v1.0.0-final` — fecha por confirmar.
