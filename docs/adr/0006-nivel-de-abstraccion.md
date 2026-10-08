# ADR-0006 · Nivel de abstracción de cada parte del procesador

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

El enunciado exige que las operaciones se realicen "usando los transistores emulados".
Modelar absolutamente todo (memoria, E/S, control) a nivel de transistor no agrega
comprensión sobre la aritmética y haría la simulación impracticable en Python. Hay que
declarar con precisión qué está construido desde transistores y qué no.

## Decisión

| Parte | Nivel en v0.x | Nivel en v1.0 |
|---|---|---|
| ALU entera (sumador, restador, flags) | Transistores nMOS/pMOS, CMOS estático | Igual |
| FPU completa (alineación, suma, multiplicación, división, normalización, redondeo, flags) | Transistores | Igual |
| Banco de registros F0–F7 y FSR | Flip-flops D maestro-esclavo con transmission gates (transistores) | Igual |
| Multiplexores de lectura del banco de registros | Transistores (MUX2 con transmission gates) | Igual |
| Decodificador de instrucciones | Compuertas de la biblioteca L1 (por lo tanto, transistores) | Igual |
| Secuenciador de control (FSM FETCH→DECODE→EXECUTE→WRITEBACK) y PC | Comportamiento en Python | Compuertas y flip-flops |
| Memoria de programa | Modelo en Python (lista de palabras) | Igual |
| Entrada/salida (`OUT`) | Modelo en Python | Igual |

Criterio general: **todo lo que transforma o almacena datos aritméticos es hardware
simulado**; lo que solo secuencia el tiempo o comunica con el exterior puede ser de
comportamiento mientras se declare.

## Consecuencias

- Cada resultado aritmético que muestra el sistema proviene de la evaluación de
  transistores; los modelos de `reference/` solo se usan como especificación y en las
  pruebas, nunca para producir resultados en la máquina.
- La memoria de programa en Python evita simular miles de celdas de almacenamiento que
  no aportan al objetivo aritmético del curso.
- La FSM de comportamiento permite tener la CPU funcionando para el avance; su paso a
  compuertas en v1.0 está planificado y no cambia la interfaz.

## Alternativas descartadas

- **Todo a nivel de transistor, incluida la memoria.** Fiel pero impracticable en tiempo
  de simulación y de desarrollo.
- **FPU de comportamiento con "conteo estimado" de transistores.** No cumple el
  enunciado: el cálculo no ocurriría en los transistores.
