# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto sigue [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Agregado
- Andamiaje del repositorio: estructura de paquetes `src/transim/` por capas (L0–L5),
  `pyproject.toml`, `Makefile`, configuración de pre-commit, integración continua
  (ruff, mypy, pytest), licencia MIT y plantillas de GitHub.
- Documentación de diseño: propuesta del avance, arquitectura, simulador switch-level,
  IEEE 754 con seis ejemplos verificados contra numpy, ISA T754, métricas, política de IA,
  glosario, esqueleto de investigación y los 13 ADR.
- Núcleo L0: valores y fuerzas, transistores, netlist jerárquico con buses e instancias,
  y motor `switch` con CCC, carga retenida, cortocircuitos, oscilación y conteo de actividad.

## Hitos previstos
- `v0.0.1-base` — base del repositorio lista para el trabajo en paralelo.
- `v0.1.0-avance` — 2026-10-12, presentación del avance.
- `v0.5.0-parcial` — fecha por confirmar.
- `v1.0.0-final` — fecha por confirmar.
