# ADR-0003 · Clases de valores: normales, subnormales, ±0, ±∞ y NaN canónico

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

Una FPU que solo maneja números normales falla precisamente en los casos que más
interesan al evaluar una implementación de IEEE 754: valores muy pequeños, divisiones
entre cero y operaciones indefinidas. La norma define el comportamiento de cada caso.

## Decisión

Se soportan las cinco clases de valores con la codificación de IEEE 754-2019 §3.4:

| Clase | Exponente almacenado | Fracción | Valor |
|---|---|---|---|
| ±0 | 0 | 0 | ±0 |
| Subnormal | 0 | ≠ 0 | (−1)^s · 0.f · 2^emin |
| Normal | 1 … 2^e − 2 | cualquiera | (−1)^s · 1.f · 2^(E − sesgo) |
| ±∞ | 2^e − 1 | 0 | ±∞ |
| NaN | 2^e − 1 | ≠ 0 | NaN (quiet si el MSB de f es 1; signaling si es 0) |

Reglas obligatorias:

1. **Underflow gradual:** los resultados con magnitud menor que 2^emin se representan
   como subnormales, redondeados con RNE (ADR-0002).
2. **Ceros con signo:** x − x = +0 y (+0) + (−0) = +0 en RNE; (−0) + (−0) = −0. En la
   multiplicación y la división, el signo es el XOR de los signos de los operandos.
3. **Operaciones inválidas:** ∞ − ∞ (y ∞ + (−∞)), 0 × ∞, 0 / 0 e ∞ / ∞ producen NaN y
   levantan **invalid**.
4. **División entre cero:** x / 0 con x finito distinto de cero produce ±∞ (signo XOR)
   y levanta **divideByZero**.
5. **Propagación de NaN:** si algún operando es NaN, el resultado es el **NaN canónico**:
   signo 0, exponente todo unos y fracción `10…0` (binary32: `0x7FC00000`; binary16:
   `0x7E00`). Un **sNaN** de entrada además levanta **invalid** (§7.2); un qNaN de
   entrada no levanta ningún flag.
6. Las operaciones con ∞ que no son inválidas devuelven el ∞ correspondiente sin flags
   (por ejemplo ∞ + 1 = ∞, ∞ × −2 = −∞, 1 / ∞ = +0).

## Consecuencias

- La FPU necesita un bloque de clasificación (`fpu/special.py`) que detecte la clase de
  cada operando y anule el datapath numérico cuando el resultado es especial.
- El oráculo compara bits exactos salvo en NaN: el hardware x86 que usa numpy produce
  `0xFFC00000` (signo 1) como NaN por defecto, por lo que para NaN se exige que el
  resultado del simulador sea exactamente el canónico y que el de numpy sea "algún NaN".
- La norma recomienda conservar la carga útil del NaN de entrada; aquí se descarta para
  simplificar el hardware. La norma lo permite, porque es una recomendación ("should"),
  no una obligación.

## Alternativas descartadas

- **Flush-to-zero de subnormales.** Simplifica el hardware, pero no cumple la norma y
  rompe la identidad x − y = 0 ⇔ x = y.
- **Propagar la carga útil del NaN.** Más fiel a la recomendación de §6.2.3, pero exige
  una lógica de selección adicional sin valor didáctico.

## Referencias

IEEE. (2019). *IEEE standard for floating-point arithmetic* (IEEE Std 754-2019).
https://doi.org/10.1109/IEEESTD.2019.8766229

Muller, J.-M., Brunie, N., de Dinechin, F., Jeannerod, C.-P., Joldes, M., Lefèvre, V.,
Melquiond, G., Revol, N., & Torres, S. (2018). *Handbook of floating-point arithmetic*
(2.ª ed.). Birkhäuser. https://doi.org/10.1007/978-3-319-76526-6
