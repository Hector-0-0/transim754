# ADR-0001 · Formato binary32 parametrizado con `FloatFormat`

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

El enunciado exige operar "en formato IEEE 754 para cantidades con signo". La norma
IEEE 754-2019 define varios formatos binarios de intercambio; el más difundido en las
CPU de propósito general para precisión simple es binary32. Para probar exhaustivamente
la lógica de redondeo y los casos especiales conviene, además, un formato pequeño cuyo
espacio de valores pueda recorrerse por completo.

## Decisión

1. El formato oficial del proyecto es **IEEE 754-2019 binary32**: 1 bit de signo,
   8 bits de exponente con sesgo 127 y 23 bits de fracción (precisión p = 24).
2. Toda la implementación se parametriza con un único tipo inmutable
   `FloatFormat(exp_bits, frac_bits)` definido en `transim/fpu/format.py`, del que se
   derivan las demás constantes:

   | Constante | Expresión | binary32 | binary16 |
   |---|---|---|---|
   | ancho total | 1 + e + f | 32 | 16 |
   | precisión p | f + 1 | 24 | 11 |
   | sesgo | 2^(e−1) − 1 | 127 | 15 |
   | emax | sesgo | 127 | 15 |
   | emin | 1 − sesgo | −126 | −14 |

3. **binary16** (1/5/10, sesgo 15) se usa para las demostraciones visuales y para las
   pruebas exhaustivas parciales (por ejemplo, todos los pares de operandos de una
   región del espacio de valores).
4. **Ningún módulo puede contener los literales 32, 8, 23 o 127** referidos al formato.
   Las únicas definiciones permitidas son `BINARY32 = FloatFormat(8, 23)` y
   `BINARY16 = FloatFormat(5, 10)` en `fpu/format.py`, y `WORD_BITS = 32` en
   `cpu/isa.py` para el ancho de palabra de la máquina. Una prueba automática recorre
   el código fuente y rechaza los literales fuera de esos lugares.

## Consecuencias

- Los circuitos se generan con el ancho que indica el formato; el mismo código produce
  una FPU de binary16 (pequeña y rápida de simular) o de binary32.
- Los errores de lógica aparecen primero en binary16, donde son baratos de encontrar.
- El costo es una capa de indirección: cada bloque recibe el formato como parámetro.

## Alternativas descartadas

- **Codificar binary32 de forma fija.** Más simple, pero impide las pruebas exhaustivas
  y mezcla constantes mágicas en todo el código.
- **binary64.** Multiplica el tamaño del multiplicador (53×53) y del divisor sin aportar
  nada conceptual nuevo; el costo de simulación sería prohibitivo.
- **Formatos de 8 bits (FP8).** No están definidos en IEEE 754-2019; se perdería la
  trazabilidad con la norma.

## Referencias

IEEE. (2019). *IEEE standard for floating-point arithmetic* (IEEE Std 754-2019).
https://doi.org/10.1109/IEEESTD.2019.8766229
