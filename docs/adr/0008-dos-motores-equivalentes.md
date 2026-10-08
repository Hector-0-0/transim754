# ADR-0008 · Dos motores de simulación con equivalencia probada

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

Simular transistor por transistor un multiplicador de 24×24 bits implica evaluar
decenas de miles de interruptores por operación. En Python eso es lento para pruebas
masivas (miles de casos contra el oráculo). Sin embargo, una celda combinacional CMOS
siempre produce la misma salida para la misma entrada: su comportamiento puede
extraerse una vez y reutilizarse.

## Decisión

1. **Motor `switch`:** exacto, evalúa cada transistor según ADR-0007.
2. **Motor `cached`:** para cada **tipo** de celda combinacional:
   - su **tabla de verdad** se extrae **automáticamente** de su netlist, ejecutando el
     motor `switch` sobre las 2^n combinaciones de entradas 0/1;
   - en tiempo de simulación, la celda se evalúa como una unidad mediante una tabla
     memoizada `(entradas, estado interno) → (nuevo estado interno, salidas,
     conmutaciones por nodo, eventos por transistor)`. Las entradas de la clave admiten
     los cuatro valores, por lo que también se cubren X y Z. Las entradas de la tabla
     que no se precalcularon se obtienen con el motor `switch` la primera vez que
     aparecen.
3. Se incluye el **estado interno** en la clave porque los nodos internos de las pilas
   en serie pueden quedar aislados y retener carga: su valor depende de la historia, y
   con él el número de conmutaciones. Con esta clave el motor `cached` reproduce
   exactamente los conteos del motor `switch`, no solo las salidas.
4. Las **celdas secuenciales** (latch, flip-flop) se marcan como tales en su netlist y
   siempre se simulan con `switch`.
5. **Prueba obligatoria de equivalencia:** para cada celda de la biblioteca y para
   bloques compuestos, secuencias aleatorias de entradas producen en ambos motores las
   mismas salidas, el mismo conteo de transistores y las mismas conmutaciones.
6. **Uso por defecto:** `switch` en las pruebas de celdas y bloques pequeños; `cached`
   en la FPU completa y en la CPU.

## Precisiones de implementación

Incorporadas al construir el motor (2026-10-08), sin cambiar la decisión:

1. **Criterio de tabulación.** El motor `cached` tabula una instancia solo si cumple,
   de forma verificada automáticamente: (a) su definición no es secuencial; (b) es una
   celda primitiva, sin sub-instancias; (c) cada entrada de la celda solo llega a
   compuertas de transistores de la celda; (d) cada salida de la instancia, fuera de
   la celda, solo llega a compuertas. Con (c) y (d), todos los componentes conectados
   por canal de la celda quedan dentro de ella, y su estado estable depende solo de
   sus entradas y de su estado interno previo, que es la clave de la tabla. Las
   instancias que no cumplen el criterio se simulan transistor por transistor dentro
   del mismo motor, y el motor informa cuáles y por qué.
2. **Regla de diseño de la biblioteca L1.** Para que todas las celdas sean tabulables,
   la biblioteca adopta dos reglas: **entradas de alta impedancia** (solo a
   compuertas) y **salidas restauradas** (manejadas por una red CMOS hacia los
   rieles). En particular, el MUX2 de transmission gates lleva inversores en sus
   entradas de datos y en su salida (12 transistores), lo que además evita cadenas
   largas de transmission gates sin restaurar en el barrel shifter.
3. **Definición precisa de equivalencia.** Ambos motores producen el mismo **estado
   observable** (el conjunto de nodos con valor 0 o 1 impuesto con fuerza `SUPPLY` o
   `DRIVEN`, y sus valores) y los mismos contadores de conmutaciones y de eventos por
   transistor (ADR-0007, punto 9). Los nodos que solo retienen carga o valen X quedan
   fuera de la comparación: su valor depende del orden de los eventos intermedios de
   un modelo de retardo cero y no es reproducible ni siquiera entre dos ejecuciones
   del motor `switch` con distinto orden de cola.
4. **Evidencia.** La prueba de equivalencia recorre cada celda con entradas 0, 1, X y
   Z, un sumador ripple-carry jerárquico, un circuito mixto (celdas tabulables, latch
   secuencial, MUX sin buffer y transistores sueltos) y circuitos aleatorios generados
   con hypothesis.

## Consecuencias

- La validez de `cached` no es un supuesto: se demuestra con la prueba de equivalencia,
  y la tabla proviene del mismo netlist de transistores, no de una descripción lógica
  escrita a mano.
- El conteo de transistores es una propiedad del netlist y no depende del motor.
- La memoria de la tabla crece con los estados internos alcanzados, que en celdas
  pequeñas es un número reducido.

## Alternativas descartadas

- **Tablas escritas a mano por celda.** Romperían la cadena de verificación: la tabla
  podría no corresponder al circuito de transistores.
- **Tabla de verdad sin estado interno.** Daría las salidas correctas, pero los conteos
  de conmutaciones internas no coincidirían con el motor `switch`.
- **Compilar el netlist completo a una función booleana.** Más rápido, pero perdería la
  actividad por nodo y el manejo de X.
