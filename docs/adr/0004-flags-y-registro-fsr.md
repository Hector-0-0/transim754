# ADR-0004 · Cinco flags acumulativos en el registro de estado FSR

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

IEEE 754-2019 §7 define cinco excepciones. En el manejo por defecto (sin trampas) cada
excepción levanta un indicador de estado (flag) que permanece activo hasta que el
programa lo borra explícitamente. La ALU entera, por su parte, produce los indicadores
de condición clásicos C, V, Z y N.

## Decisión

1. Se implementan los cinco flags de IEEE 754, **acumulativos (sticky)**: cada operación
   hace OR de sus flags sobre los ya almacenados.

   | Bit FSR | Flag | Se levanta cuando |
   |---|---|---|
   | 0 | NX · inexact | el resultado redondeado difiere del exacto |
   | 1 | UF · underflow | el resultado es diminuto **y** inexacto (ver punto 3) |
   | 2 | OF · overflow | el resultado redondeado excede el mayor finito |
   | 3 | DZ · divideByZero | x / 0 con x finito ≠ 0 |
   | 4 | NV · invalid | operación inválida o sNaN de entrada |

   El orden de bits coincide con el de los registros `fflags` de RISC-V, lo que facilita
   la comparación con documentación de referencia.
2. **Overflow** implica también **inexact**, y el resultado es ±∞ en RNE.
3. **Underflow:** IEEE 754-2019 §7.5 permite al implementador detectar la condición de
   "diminuto" (tininess) **antes** o **después** del redondeo. Este proyecto la detecta
   **después del redondeo**: el resultado es diminuto si, redondeado como si el rango de
   exponentes fuera ilimitado, su magnitud es menor que 2^emin. Es la opción que usa la
   arquitectura x86, lo que permite comparar contra numpy en esa plataforma. En el
   manejo por defecto, la norma exige levantar el flag solo si el resultado, además de
   diminuto, es **inexacto**; un subnormal exacto no levanta underflow.
4. Los bits 8–11 del FSR guardan los indicadores de la ALU entera: **C** (bit 8),
   **V** (bit 9), **Z** (bit 10) y **N** (bit 11). Estos **no** son acumulativos: cada
   instrucción ADD o SUB los sobrescribe, como en las ALU convencionales.
5. La instrucción `CLRF` pone a cero todo el FSR. Los bits 5–7 y 12–31 están reservados
   y valen 0.

## Consecuencias

- La FPU entrega en cada operación un vector de cinco flags; el control hace el OR con
  el FSR en la etapa WRITEBACK.
- Al detectar la tininess después del redondeo, existe un caso límite: un resultado que
  antes de redondear es menor que 2^emin pero que al redondear alcanza exactamente
  2^emin **no** levanta underflow. Las pruebas lo cubren de forma explícita.

## Alternativas descartadas

- **Tininess antes del redondeo** (opción de ARM y otras arquitecturas). Igualmente
  válida, pero impediría verificar los flags contra numpy en x86.
- **Trampas (traps) por excepción.** La norma las define como opcionales; añaden un
  mecanismo de interrupción que no aporta al objetivo del curso.
- **Flags no acumulativos.** Contradicen la semántica de §7 de la norma.

## Referencias

IEEE. (2019). *IEEE standard for floating-point arithmetic* (IEEE Std 754-2019).
https://doi.org/10.1109/IEEESTD.2019.8766229

Waterman, A., & Asanović, K. (Eds.). (2019). *The RISC-V instruction set manual,
Volume I: Unprivileged ISA* (Documento 20191213). RISC-V Foundation.
