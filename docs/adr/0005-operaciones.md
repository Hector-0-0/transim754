# ADR-0005 · Operaciones: FADD, FSUB, FMUL, FDIV y ALU entera de 32 bits

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

El enunciado pide sumas, restas, multiplicaciones y divisiones con signo en IEEE 754.
Una FPU real reutiliza aritmética entera para operar sobre exponentes y mantisas, y una
CPU también necesita aritmética entera propia.

## Decisión

1. Operaciones de punto flotante: **FADD**, **FSUB**, **FMUL** y **FDIV**, con el
   comportamiento de IEEE 754-2019 §5.4.1 para el formato de ADR-0001.
2. Una **ALU entera de 32 bits en complemento a 2** con **ADD** y **SUB** y los
   indicadores **C** (acarreo/préstamo), **V** (desbordamiento con signo), **Z** (cero)
   y **N** (negativo). Convención de C en la resta: C = 1 indica que **no** hubo
   préstamo (C es el acarreo de salida de A + ¬B + 1), como en ARM.
3. La FPU **reutiliza los bloques enteros** de la capa L2 (sumador, restador,
   comparador) para la aritmética de exponentes: diferencia de exponentes en FADD/FSUB,
   suma de exponentes menos el sesgo en FMUL y resta de exponentes más el sesgo en FDIV.

## Consecuencias

- Los bloques de L2 se diseñan parametrizados por ancho (N bits) para servir tanto a la
  ALU (32 bits) como a los exponentes (e + 2 bits, para representar los resultados
  intermedios con signo sin desbordar).
- La raíz cuadrada, el FMA y las conversiones entero↔flotante quedan fuera del alcance.

## Alternativas descartadas

- **Incluir FSQRT o FMA.** Interesantes, pero exceden el tiempo disponible del curso.
- **ALU entera con operaciones lógicas y desplazamientos.** No se piden; se dejan como
  posible extensión de la ISA (los opcodes 0x22–0x2F están libres).

## Referencias

IEEE. (2019). *IEEE standard for floating-point arithmetic* (IEEE Std 754-2019).
https://doi.org/10.1109/IEEESTD.2019.8766229

Patterson, D. A., & Hennessy, J. L. (2021). *Computer organization and design RISC-V
edition: The hardware/software interface* (2.ª ed.). Morgan Kaufmann.
