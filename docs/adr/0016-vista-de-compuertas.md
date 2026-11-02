# ADR-0016 · Vista de compuertas deducida de las etapas CMOS

- **Estado:** Aceptada
- **Fecha:** 2026-11-02

## Contexto

La pestaña de transistores mostraba cada celda como esquema CMOS (ADR-0015). Para quien
viene de la lógica digital, un esquema de 28 transistores no dice qué función calcula
la celda. Lo natural es ver primero las compuertas y después los transistores. Pero las
celdas de la biblioteca no están hechas de compuertas: el FA es un sumador espejo
(*mirror adder*), no un XOR más un AND. Dibujar la función "de libro" (s = a ⊕ b ⊕ cin
con dos XOR) mostraría un circuito que no es el que se simula.

## Decisión

La vista **Compuertas** se deduce del mismo análisis que el esquema
(`ui/gui/circuit.py`). Cada etapa CMOS se dibuja como la compuerta que implementa:

- La red pull-down de nMOS conduce cuando su expresión vale 1, con serie = AND y
  paralelo = OR. La etapa lleva la salida a 0 en ese caso: su función es la negación de
  esa expresión.
- Según la forma del árbol serie-paralelo se nombra inversor, NAND, NOR, AOI, OAI o
  compuerta compleja (Weste y Harris, 2011). Las compuertas complejas se dibujan como un
  recuadro con su fórmula.
- Una transmission gate se dibuja como un elemento de paso controlado; los transistores
  que no forman una etapa, como una red sin función propia.

Las compuertas se ordenan en columnas por dependencia de señal. Cada red sale de su
fuente por un cable vertical en el hueco siguiente y, si llega a una columna que no es
la siguiente, por un carril propio debajo de las compuertas, así ningún cable atraviesa
una compuerta. El panel "Qué está pasando" escribe la fórmula de cada etapa con los
valores de la simulación (`y = ¬(a·b) = ¬(1·0) = 1`). Doble clic en una compuerta abre
sus transistores con la etapa resaltada.

Las pruebas comprueban, para toda combinación de entradas de cada celda primitiva, que
la fórmula de cada etapa evaluada con los valores simulados de sus entradas da el valor
simulado de su salida, y que ningún cable cruza una compuerta.

## Consecuencias

- El FA aparece con dos compuertas complejas y dos inversores, como está construido; la
  función de libro se lee en la descripción de la celda y en su tabla de verdad.
- Las celdas nuevas obtienen su vista de compuertas sin dibujarla a mano.
- La vista no cambia la simulación ni sus métricas.

## Alternativas descartadas

- **Símbolos de libro por celda (XOR, MUX, FA como caja negra)**: legibles, pero no
  muestran la estructura que se simula y se desactualizan si cambia una celda.
- **Reconstruir compuertas de dos entradas a partir de la tabla de verdad**: daría un
  circuito equivalente distinto del real.
