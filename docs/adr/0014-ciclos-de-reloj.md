# ADR-0014 · Ciclos de reloj estimados a partir del camino crítico

- **Estado:** Aceptada
- **Fecha:** 2026-10-25

## Contexto

El simulador es de retardo cero (ADR-0007): cada unidad de la FPU es combinacional y
se resuelve en una sola evaluación. Aun así, para explicar el funcionamiento de una CPU
conviene mostrar cuántos ciclos de reloj tardaría cada operación y qué etapa del
datapath ocupa cada ciclo. Inventar un número fijo de ciclos por operación (por ejemplo,
4 para la suma y 27 para la división) no se desprendería del hardware simulado.

## Decisión

Los ciclos se **estiman** a partir del camino crítico medido (ADR-0013):

1. Cada celda primitiva cuesta una unidad de retardo.
2. El periodo de reloj es un número fijo de celdas. Por convención es la profundidad del
   camino crítico de la ALU entera de 32 bits (39 celdas): una operación entera cabe en
   un ciclo. La interfaz gráfica permite cambiarlo.
3. El camino crítico de la unidad se recorre en orden, agrupado por la instancia de
   primer nivel que atraviesa (la etapa del datapath), y se reparte en ciclos de ese
   periodo (`metrics/stages.py`).
4. Junto a cada etapa se muestran las conmutaciones de nodo que el motor contó en la
   operación, atribuidas a la etapa cuyos canales manejan cada nodo.

Con el periodo por defecto, FADD/FSUB y FMUL de binary32 ocupan 5 ciclos y FDIV, 22.

## Consecuencias

- El número de ciclos se deriva del circuito y cambia si cambia el diseño (por ejemplo,
  un divisor más rápido reduce los ciclos de FDIV).
- Es una estimación de primer orden: supone celdas de igual retardo, registros sin costo
  entre etapas y la máquina sin segmentación. Se presenta siempre como "estimado".
- La máquina T754 sigue ejecutando cada instrucción en las cuatro fases de ADR-0006; el
  conteo de ciclos de la FPU es informativo y no altera el resultado.

## Alternativas descartadas

- **Número fijo de ciclos por tipo de operación.** No se deriva del hardware simulado.
- **FPU segmentada con registros entre etapas.** Fiel a un procesador real, pero cambia
  las interfaces de L3 y multiplica el tiempo de simulación; queda para una versión
  posterior si se justifica.
