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
