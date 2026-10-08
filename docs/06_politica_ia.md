# 06 · Política de uso de inteligencia artificial

Este documento distingue dos usos de la inteligencia artificial en el proyecto y fija
los principios y controles que se aplican a cada uno.

## 1. La IA como componente del software

El módulo `transim/assistant/` integra un asistente opcional con tres funciones
acotadas: explicar trazas de ejecución, traducir peticiones en lenguaje natural a
programas `.t754` y proponer operandos de casos borde (ADR-0012). Sus garantías son:

1. **No calcula.** Ningún resultado numérico mostrado por el sistema proviene del
   asistente; todos provienen de la simulación de transistores.
2. **Todo lo que produce se verifica:** los programas pasan por el ensamblador y su
   validador; los casos borde se evalúan con el modelo de referencia, que decide el
   resultado esperado.
3. **Es prescindible:** el adaptador por defecto (`NullAssistant`) no usa IA y el
   sistema funciona al 100 % sin ella. Todas las pruebas automáticas se ejecutan sin
   IA.
4. **Privacidad:** el adaptador local (Ollama) no envía datos fuera del equipo; el
   adaptador remoto es opcional y su clave se lee solo de una variable de entorno.

## 2. La IA como herramienta durante el desarrollo

Los integrantes pueden usar asistentes de IA para estudiar, diseñar y escribir código
y documentación, bajo los siguientes principios:

1. **Responsabilidad de autoría.** Quien incorpora un cambio al repositorio responde
   por él: debe poder explicarlo y defenderlo sin ayuda. Las guías de cada módulo
   incluyen preguntas de comprensión con ese fin.
2. **Verificación independiente.** Ningún código se acepta porque "lo generó una
   herramienta". Se acepta porque pasa las pruebas del módulo, la validación contra el
   oráculo (numpy y los modelos de referencia) y la revisión de otro integrante.
3. **Pruebas primero.** Las pruebas de cada módulo existen antes que su implementación
   y fueron escritas a partir de la norma IEEE 754-2019 y de los ADR, no a partir de la
   implementación; así, un error introducido por una herramienta se detecta.
4. **Transparencia.** El equipo mantiene un registro interno de qué partes se
   desarrollaron con ayuda de IA y cómo se verificaron. Ante el docente, cualquier
   integrante puede indicar qué partes de su módulo se apoyaron en IA.
5. **Fuentes.** Las afirmaciones técnicas de la documentación se respaldan en fuentes
   citadas en formato APA o en pruebas ejecutables, nunca solo en la respuesta de una
   herramienta.

## 3. Controles de verificación

| Control | Qué detecta | Dónde |
|---|---|---|
| Pruebas exhaustivas de celdas (2^n entradas) | errores lógicos en celdas | `tests/cells/` |
| Comparación bit a bit contra numpy (binary32 y binary16) | errores de redondeo, flags y casos especiales | `tests/oracle/` |
| Equivalencia entre motores `switch` y `cached` | tablas mal extraídas | `tests/core/` |
| Integración continua (ruff, mypy, pytest) | errores de estilo, de tipos y regresiones | `.github/workflows/ci.yml` |
| `make validar M=<modulo>` | módulos incompletos (pruebas pendientes) | `scripts/validar.py` |
| Revisión de pull request por otro integrante | errores de diseño y de comprensión | CODEOWNERS |
