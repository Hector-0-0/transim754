# Material de apoyo · Revisión de pull requests

> USO INTERNO. Lo usa quien revisa un PR asignado por CODEOWNERS.

```text
Proyecto TranSim754 (curso SI421U, UNI-FIIS, 2026-II): software en Python 3.12 que emula
un procesador cuyas operaciones (suma, resta, multiplicación y división en IEEE 754
binary32) se calculan con transistores nMOS/pMOS simulados en un simulador switch-level.
Repositorio: https://github.com/Hector-0-0/transim754 (rama principal `main`).

Revisa este pull request como revisor del equipo. Datos:
- Módulo y GUIA: [completar]
- Issue que cierra: #[N]
- Salida de `make validar M=<modulo>`: [pegar]
- Diff: [pegar `git diff origin/main...HEAD`]

Comprueba, en este orden:
1. CI en verde y `make validar` en PASS (si no, veredicto CAMBIOS inmediato).
2. Criterios de aceptación de la GUIA cumplidos; no quedan `@pendiente` del issue.
3. Interfaces sin cambios respecto de la GUIA y los stubs; si cambian, debe haber un ADR.
4. Solo se tocaron archivos del módulo (más su GUIA y la bitácora).
5. Corrección técnica: busca casos borde no cubiertos por las pruebas y propón pruebas
   concretas (entradas y salida esperada según la referencia).
6. Legibilidad: docstrings, nombres, comentarios en español, identificadores en inglés.
7. Commits: formato convencional, ámbito correcto, autor = el integrante, sin trailers de IA.
8. Definition of Done de CONTRIBUTING.md completa.

Responde con: resumen de 3 líneas, lista de hallazgos (bloqueante / sugerencia) con archivo
y línea, y veredicto APROBADO o CAMBIOS. Redacta también el comentario de revisión listo
para pegar en GitHub, en español y en tono respetuoso.
```
