# ADR-0002 · Redondeo roundTiesToEven con bits guard, round y sticky

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

IEEE 754-2019 (§4.3) define cinco atributos de dirección de redondeo. El atributo por
defecto para formatos binarios es **roundTiesToEven** (RNE): se elige el valor
representable más cercano y, en caso de empate, el que tiene el bit menos significativo
par. Implementar los cinco modos multiplica los casos de prueba sin aportar una idea
de hardware distinta.

## Decisión

1. Solo se implementa **roundTiesToEven**.
2. El redondeo se realiza con tres bits adicionales a la derecha del bit menos
   significativo (LSB) de la mantisa resultado:
   - **G** (guard): primer bit descartado;
   - **R** (round): segundo bit descartado;
   - **S** (sticky): OR lógico de todos los bits descartados restantes.
3. La regla de incremento es:

   `incrementar = G · (R + S + LSB)`

   es decir, se suma 1 al LSB cuando lo descartado es mayor que medio ulp (G = 1 y
   R + S = 1) o cuando es exactamente medio ulp (G = 1, R = S = 0) y el LSB es impar.
4. El resultado es **inexacto** si `G + R + S = 1`.
5. Si el incremento desborda la mantisa (1.111…1 + ulp = 10.000…0), se desplaza una
   posición a la derecha y se incrementa el exponente; esto puede producir overflow.
6. `fpu/rounding.py` es el único módulo que implementa esta regla y lo comparten la
   suma/resta, la multiplicación y la división.

## Consecuencias

- El redondeo de hardware se reduce a una compuerta de decisión y a un incrementador
  (un sumador con un operando constante cero y acarreo de entrada controlado).
- Tres bits bastan para la suma y la resta (Goldberg, 1991): si la diferencia de
  exponentes es 0 o 1, la alineación pierde a lo sumo un bit, que G conserva, y el
  resultado es exacto antes de normalizar; si es 2 o más, la normalización desplaza a
  lo sumo una posición a la izquierda, de modo que G pasa a ser el LSB, R el nuevo G y
  S sigue resumiendo el resto. En la multiplicación y la división, G y R se toman
  directamente del producto o cociente y S resume el resto.
- Los resultados son comparables bit a bit con numpy, que usa RNE por defecto.

## Alternativas descartadas

- **Los cinco modos de redondeo.** Más completo, pero triplica las pruebas sin cambiar
  la arquitectura.
- **Truncamiento (roundTowardZero).** Más simple, pero no es el modo por defecto de la
  norma y no permitiría comparar contra numpy.
- **Guardar todos los bits descartados.** Correcto, pero el sticky resume la misma
  información en un solo bit; guardar todo agranda el datapath sin beneficio.

## Referencias

Goldberg, D. (1991). What every computer scientist should know about floating-point
arithmetic. *ACM Computing Surveys, 23*(1), 5–48. https://doi.org/10.1145/103162.103163

IEEE. (2019). *IEEE standard for floating-point arithmetic* (IEEE Std 754-2019).
https://doi.org/10.1109/IEEESTD.2019.8766229
