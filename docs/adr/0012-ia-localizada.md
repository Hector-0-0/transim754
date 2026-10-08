# ADR-0012 · Asistente de IA localizado que nunca calcula

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

Un modelo de lenguaje puede ayudar a un estudiante a entender una traza de ejecución o
a escribir un programa, pero no es confiable como calculador: puede producir resultados
plausibles e incorrectos. Si se integra en el software, su papel debe quedar acotado y
verificable, y el sistema no puede depender de él.

## Decisión

1. Se define un **puerto** `Assistant` (`transim/assistant/port.py`) con tres
   operaciones y nada más:
   - `explain_trace(trace)`: explica en lenguaje natural una traza de ejecución ya
     calculada por el simulador;
   - `nl_to_program(text)`: traduce una petición en lenguaje natural a un programa
     `.t754`. El texto devuelto **siempre** pasa por el ensamblador y su validador; si
     no ensambla, se rechaza;
   - `propose_edge_cases(op, fmt)`: propone operandos de casos borde. **El resultado
     esperado lo decide el oráculo** (modelo de `reference/`), nunca el asistente.
2. **Adaptadores** (patrón puertos y adaptadores):
   - `NullAssistant` (por defecto): no usa IA; devuelve respuestas vacías o explicaciones
     generadas por plantillas;
   - `OllamaAssistant`: modelo local servido por Ollama, sin enviar datos fuera del
     equipo;
   - `AnthropicAssistant` (opcional): API de Anthropic; la clave se lee únicamente de la
     variable de entorno `ANTHROPIC_API_KEY` y nunca se guarda en el repositorio.
3. **La IA nunca calcula.** Ningún valor numérico mostrado como resultado de una
   operación proviene del asistente.
4. El sistema funciona **al 100 % sin IA**: todas las pruebas usan `NullAssistant`.

## Consecuencias

- El asistente agrega valor didáctico (explicaciones, generación de programas) sin
  comprometer la corrección: todo lo que produce pasa por un verificador determinista.
- Al ser un puerto, se puede cambiar de proveedor sin tocar el resto del sistema.
- La política sobre el uso de IA durante el *desarrollo* del proyecto es un tema
  distinto y está en `docs/06_politica_ia.md`.

## Alternativas descartadas

- **Sin asistente.** Válido; se descarta porque la explicación de trazas tiene valor
  didáctico para la exposición.
- **Asistente que calcula o corrige resultados.** Inaceptable: introduciría resultados
  no verificables en un simulador cuyo propósito es la exactitud bit a bit.
- **Depender de un único proveedor remoto.** Haría que la demo dependa de internet y de
  una clave; por eso el adaptador por defecto no usa red.
