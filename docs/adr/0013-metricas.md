# ADR-0013 · Métricas de transistores, actividad, profundidad y tiempo

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

Para comparar alternativas de diseño (por ejemplo RCA frente a CLA) y responder a la
pregunta del enunciado sobre cómo funcionan los transistores en una CPU, el proyecto
debe producir números medibles y reproducibles, no estimaciones.

## Decisión

Se miden cuatro métricas de forma automática:

1. **Transistores por módulo:** conteo de nMOS y pMOS del netlist aplanado, total y por
   jerarquía (celda, bloque, unidad).
2. **Conmutaciones por operación:** número de transiciones 0↔1 de los nodos durante una
   operación. Dividido entre el número de nodos da la **actividad α**, que se usa como
   aproximación de la potencia dinámica según

   P_din ≈ α · C · V_DD² · f

   donde C es la capacitancia conmutada, V_DD la tensión de alimentación y f la
   frecuencia de reloj (Rabaey et al., 2003). El simulador no conoce C ni f; por eso se
   reporta α y no vatios.
3. **Profundidad del camino crítico** en **niveles de celda**: longitud del camino más
   largo, en número de celdas L1, desde una entrada hasta una salida del bloque. Es la
   métrica de velocidad disponible, porque el simulador es de retardo cero (ADR-0007).
4. **Tiempo de simulación** por operación, en el motor usado (útil para justificar el
   motor `cached`).

El comando `transim metrics` genera las tablas en **Markdown** (para el informe) y
**CSV** (para gráficos en las diapositivas) en `docs/metricas/`.

## Consecuencias

- Las tablas del informe se regeneran con un comando: no hay números copiados a mano.
- La profundidad en niveles de celda no distingue celdas rápidas de lentas; se declara
  como aproximación.

## Alternativas descartadas

- **Retardos con unidades de tiempo por celda.** Requeriría un modelo de retardo por
  tipo de celda sin datos de un proceso real; aportaría precisión aparente, no real.
- **Potencia en vatios.** Requiere capacitancias de un proceso concreto; se reporta la
  actividad, que es la magnitud que el simulador sí mide.

## Referencias

Rabaey, J. M., Chandrakasan, A., & Nikolić, B. (2003). *Digital integrated circuits:
A design perspective* (2.ª ed.). Pearson.
