# ADR-0007 · Simulador switch-level de cuatro valores y tres fuerzas

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

Para que las operaciones "ocurran en transistores" se necesita un simulador en el que
la unidad primitiva sea el transistor MOS y no la compuerta lógica. Los simuladores
eléctricos (SPICE) resuelven ecuaciones diferenciales y son demasiado lentos para
decenas de miles de transistores. El modelo **switch-level** de Bryant (1984) trata al
transistor como un interruptor controlado por su compuerta y conserva los fenómenos
digitales relevantes: conducción complementaria, almacenamiento de carga, conflictos y
valores indeterminados.

## Decisión

1. **Valores lógicos** `{0, 1, X, Z}`: X = desconocido o en conflicto; Z = alta
   impedancia (nodo sin fuente y sin carga conocida).
2. **Fuerzas**, de mayor a menor: `SUPPLY` (VDD y GND) > `DRIVEN` (entradas externas)
   > `CHARGE` (carga almacenada en un nodo aislado).
3. **Transistores ideales como interruptores:**
   - nMOS conduce si su compuerta vale 1; pMOS conduce si vale 0;
   - si la compuerta vale X o Z, la conducción es **desconocida**;
   - no se modela la caída de umbral V_t (un nMOS transmite un 1 "fuerte"). Es una
     simplificación declarada: en CMOS estático no altera el valor lógico.
4. **Evaluación por componentes conectados por canal (CCC).** Un CCC es un conjunto
   maximal de nodos unidos por transistores que pueden conducir. Para cada CCC afectado
   por un cambio se calcula el valor de cada nodo dos veces:
   - con el grafo de transistores que conducen **con certeza** (`G_on`);
   - con el grafo de los que conducen **con certeza o posiblemente** (`G_maybe`).

   En cada grafo, el valor de un nodo es el de las fuentes alcanzables de mayor fuerza:
   si todas valen lo mismo, ese valor; si hay 0 y 1 a la misma fuerza, X. Si el valor
   según `G_on` y según `G_maybe` difiere, el nodo vale **X**. Así una compuerta en X
   propaga X solo cuando su conducción podría cambiar el resultado.
5. **Propagación dirigida por eventos:** cuando un nodo cambia de valor, se reevalúan
   los CCC de los transistores cuya compuerta es ese nodo. La simulación de un cambio
   de entradas termina cuando no quedan eventos (estado estable, retardo cero).
6. **Almacenamiento dinámico:** un nodo sin camino a ninguna fuente `SUPPLY` o `DRIVEN`
   conserva su valor previo con fuerza `CHARGE`. Si varios nodos con carga distinta
   quedan unidos, el resultado es X (no se modelan capacitancias para el reparto de
   carga; simplificación declarada).
7. **Cortocircuito:** si un nodo queda conectado a la vez a VDD y a GND por caminos que
   conducen con certeza, vale X. Si la conexión **persiste en el estado estable**, se
   registra una advertencia `ShortCircuitWarning` con los nombres de los nodos. Los
   solapamientos transitorios dentro de una estabilización (por ejemplo, las dos
   transmission gates de un multiplexor conduciendo mientras se actualiza el
   complemento de la selección) son artefactos del modelo de retardo cero y no se
   reportan.
8. **Oscilación:** un límite configurable de iteraciones por cambio de entradas
   (por defecto 10 000 eventos) detecta circuitos que no se estabilizan (por ejemplo,
   un anillo de inversores) y lanza `OscillationError`.
9. **Conteo de actividad sobre estados estables:** al terminar cada estabilización se
   compara el estado nuevo con el anterior. Un nodo **conmuta** cuando su valor
   manejado (0 o 1 con fuerza `SUPPLY` o `DRIVEN`) difiere del último valor manejado
   que tuvo; la carga retenida no cuenta, porque un nodo aislado no se carga ni se
   descarga. Un transistor genera un **evento** cuando su estado definido (conduce o
   cortado) difiere del último estado definido que tuvo. Los valores intermedios de
   una estabilización (glitches) no se cuentan: en un modelo de retardo cero dependen
   del orden de procesamiento de los eventos y no corresponden a tiempos físicos.
10. **Fuerza de una X:** cuando el resultado de un nodo es X, su fuerza es la máxima de
    las obtenidas en `G_on` y `G_maybe`, de modo que no depende del orden de
    evaluación.

## Consecuencias

- El simulador reproduce el comportamiento lógico de CMOS estático, de las
  transmission gates y de los latches dinámicos, con un costo que crece con el número
  de transistores que efectivamente cambian.
- La ausencia de tiempos de propagación impide medir retardos reales; la métrica de
  velocidad es la profundidad lógica en niveles de celda (ADR-0013).
- El conteo de conmutaciones es una aproximación de la actividad α usada en la
  estimación de potencia dinámica. Al excluir los glitches es una **cota inferior** de
  la actividad real: medir los glitches exigiría un modelo de retardos, fuera de
  alcance.

## Alternativas descartadas

- **SPICE u otro simulador analógico.** Precisión eléctrica innecesaria y costo
  computacional inviable para una FPU completa.
- **Simulación a nivel de compuerta.** Más rápida, pero no cumple el enunciado: las
  compuertas serían la unidad primitiva, no los transistores.
- **Modelo de dos valores {0, 1}.** No puede representar conflictos, nodos flotantes ni
  el estado inicial desconocido de un flip-flop.

## Referencias

Bryant, R. E. (1984). A switch-level model and simulator for MOS digital systems.
*IEEE Transactions on Computers, C-33*(2), 160–177. https://doi.org/10.1109/TC.1984.1676408

Weste, N. H. E., & Harris, D. M. (2011). *CMOS VLSI design: A circuits and systems
perspective* (4.ª ed.). Addison-Wesley.
