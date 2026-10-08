# Registro de uso de IA (interno)

Una fila por sesión o tarea en la que se usó un asistente de IA. La política formal
está en `docs/06_politica_ia.md`; aquí va el detalle operativo.

| Fecha | Integrante | Herramienta | Parte del proyecto | Qué hizo la IA | Cómo se verificó |
|---|---|---|---|---|---|
| 2026-10-08 | Héctor | Claude (Claude Code) | Base F0: andamiaje del repositorio | Propuso y escribió `pyproject.toml`, `Makefile`, CI, plantillas de GitHub y CLI mínimo | `make install`, `make lint`, `make typecheck`, `make test` en verde; revisión manual de cada archivo |
| 2026-10-08 | Héctor | Claude (Claude Code) | Base F1: docs 00–06, 13 ADR, glosario, investigación, README | Redactó la documentación de diseño y los ejemplos IEEE 754 | Ejemplos verificados contra numpy (`tests/docs`); diagramas validados con el parser de mermaid; revisión técnica de cada ADR |
| 2026-10-08 | Héctor | Claude (Claude Code) | Base F2: núcleo L0 (señales, netlist, motor switch) | Diseñó e implementó el núcleo y sus pruebas | 65 pruebas propias (casos de ADR-0007 + hypothesis), mypy estricto, revisión del algoritmo G_on/G_maybe |
| 2026-10-08 | Héctor | Claude (Claude Code) | Base F3: celdas semilla, motor cached, conteo de transistores | Diseñó el criterio de tabulación y la regla de conteo sobre estados estables; implementó y probó | Prueba de equivalencia (celdas, RCA, circuito mixto, hypothesis) + estrés local (300 semillas, 1500 circuitos) sin discrepancias |
| 2026-10-08 | Héctor | Claude (Claude Code) | Base F4: referencia, stubs, oráculo y pruebas por adelantado | Escribió modelos de referencia, interfaces y pruebas; validó las pruebas con soluciones desechables | Referencia vs numpy (331 552 casos, 0 discrepancias de valor); pruebas por adelantado ejecutadas contra soluciones de validación (88/88 celdas-bloques-ALU) |
| 2026-10-08 | Héctor | Claude (Claude Code) | Base F5: GUIA de módulos, EQUIPO, CONTRIBUTING, validar.py, material interno | Redactó guías y material de apoyo; diseñó los datapaths descritos | Datapaths verificados con modelo numérico (176 928 operaciones, 0 discrepancias); validar.py probado hasta PASS; grep de material formal; parser Mermaid |
