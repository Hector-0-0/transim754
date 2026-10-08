# Registro de uso de IA (interno)

Una fila por sesión o tarea en la que se usó un asistente de IA. La política formal
está en `docs/06_politica_ia.md`; aquí va el detalle operativo.

| Fecha | Integrante | Herramienta | Parte del proyecto | Qué hizo la IA | Cómo se verificó |
|---|---|---|---|---|---|
| 2026-10-08 | Héctor | Claude (Claude Code) | Base F0: andamiaje del repositorio | Propuso y escribió `pyproject.toml`, `Makefile`, CI, plantillas de GitHub y CLI mínimo | `make install`, `make lint`, `make typecheck`, `make test` en verde; revisión manual de cada archivo |
| 2026-10-08 | Héctor | Claude (Claude Code) | Base F1: docs 00–06, 13 ADR, glosario, investigación, README | Redactó la documentación de diseño y los ejemplos IEEE 754 | Ejemplos verificados contra numpy (`tests/docs`); diagramas validados con el parser de mermaid; revisión técnica de cada ADR |
