# ADR-0009 · Algoritmos de hardware de cada bloque

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

Cada operación aritmética admite varias realizaciones en hardware con distinto
compromiso entre área (transistores), profundidad lógica y complejidad de diseño. El
proyecto debe elegir algoritmos que puedan construirse y verificarse a tiempo y, a la
vez, permitir una comparación cuantitativa.

## Decisión

| Bloque | Algoritmo v0 | Mejora prevista |
|---|---|---|
| Sumador de N bits | Ripple-carry (RCA) con sumador completo espejo (mirror adder) de 28 transistores | Carry-lookahead (CLA) en v1, con comparación de métricas |
| Restador | Sumador + inversión del sustraendo + acarreo de entrada 1 (A − B = A + ¬B + 1) | — |
| Desplazador | Barrel shifter logarítmico de ⌈log₂ N⌉ etapas de MUX2, izquierda y derecha, con salida **sticky** (OR de los bits que salen por la derecha) | — |
| Contador de ceros a la izquierda (LZC) | Combinacional, árbol de codificación de prioridad | — |
| Comparador de magnitud | A − B con el restador; A < B se lee del acarreo de salida | Comparador en árbol |
| Multiplicador de mantisas | Arreglo (array multiplier) p × p con productos parciales AND y filas de sumadores completos | Árbol de Wallace (opcional) |
| Divisor de mantisas | Arreglo combinacional **no restaurador** | — |

### Anchos de datapath (binary32, p = 24)

- **FADD/FSUB:** mantisas de p bits ampliadas con G, R y S → sumador de p + 3 bits más
  un bit de acarreo. La alineación desplaza el menor operando a la derecha la diferencia
  de exponentes (saturada en p + 2) y acumula los bits perdidos en S.
- **FMUL:** producto exacto de 2p = 48 bits; G y R son los dos bits siguientes al LSB
  tras normalizar y S es el OR del resto.
- **FDIV:** se generan p + 2 = 26 bits de cociente (p bits de mantisa más G y R); el
  resto parcial final distinto de cero activa **S**. Como el cociente de dos mantisas
  normalizadas está en (0.5, 2), se genera un bit adicional para normalizar sin perder
  precisión. El algoritmo no restaurador produce dígitos en {−1, +1}; la conversión a
  binario y la corrección final del resto se hacen con el mismo sumador.
- **Operandos subnormales** en FMUL y FDIV se normalizan primero con LZC + desplazador.
  **Resultados diminutos** se desplazan a la derecha hasta el exponente mínimo con el
  barrel shifter con sticky antes de redondear (ADR-0002, ADR-0003).

## Consecuencias

- El RCA y el multiplicador en arreglo tienen profundidad lineal en N; servirán como
  línea base para cuantificar la mejora del CLA y, si se implementa, de Wallace.
- El divisor combinacional es grande (≈ 26 filas de p + 2 celdas), pero mantiene el
  mismo modelo de simulación que el resto del datapath, sin secuenciación iterativa.
- La salida sticky del desplazador concentra en un solo bloque la parte más delicada
  del redondeo.

## Alternativas descartadas

- **Divisor SRT o Newton-Raphson.** Más rápidos en hardware real, pero requieren tablas
  de selección o un multiplicador iterativo; su verificación excede el plazo.
- **Divisor secuencial (un bit por ciclo).** Menos transistores, pero exige una FSM de
  control a nivel de compuertas desde v0.
- **Multiplicador de Booth.** Reduce productos parciales en operandos con signo; las
  mantisas son sin signo, por lo que el beneficio es menor que su complejidad.

## Referencias

Koren, I. (2002). *Computer arithmetic algorithms* (2.ª ed.). A K Peters.

Parhami, B. (2010). *Computer arithmetic: Algorithms and hardware designs* (2.ª ed.).
Oxford University Press.

Wallace, C. S. (1964). A suggestion for a fast multiplier. *IEEE Transactions on
Electronic Computers, EC-13*(1), 14–17. https://doi.org/10.1109/PGEC.1964.263830

Weste, N. H. E., & Harris, D. M. (2011). *CMOS VLSI design: A circuits and systems
perspective* (4.ª ed.). Addison-Wesley.
