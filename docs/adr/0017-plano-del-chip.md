# ADR-0017 · Plano del chip proporcional y celda junto a su silicio

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Reemplaza:** la parte de ADR-0015 que dibuja un bloque en filas de celdas estándar y
  la unidad completa como plano de filas.

## Contexto

Con ADR-0015, el silicio de un bloque o de la unidad completa dibujaba cada celda
estándar en filas. A escala de chip son 1 411 celdas: se ven como franjas de colores y
no se reconoce ningún bloque. A escala de celda, el layout solo es legible para quien ya
sabe leer un layout, y no se ve qué rectángulo corresponde a qué transistor del esquema.

## Decisión

1. **Plano del chip y de un bloque.** Cada región es un rectángulo de área proporcional
   a sus transistores, con el nombre de la etapa y el color de la etapa (el mismo de
   Ciclos de reloj y Recorrido), como las fotos anotadas de un procesador
   (`ui/gui/floorplan.py`, rectángulos casi cuadrados de Bruls, Huizing y van Wijk,
   2000). En un bloque, los sub-bloques son una región cada uno; si tiene más de 24
   celdas sueltas, se agrupan por tipo ("OR2 × 35"). Doble clic entra en la región; el
   mapa de actividad tiñe cada región según cuánto conmutó.
2. **Una celda en silicio se dibuja junto a su esquema.** Pasar el ratón por un
   transistor en cualquiera de los dos lo resalta en ambos; los nombres de los puertos
   van encima de la celda, con una línea hasta su metal.
3. Unas pocas celdas (HA, DFF de la biblioteca) siguen en una fila de celdas estándar.

## Consecuencias

- El plano no es un layout: el área sale del número de transistores, no de reglas de
  diseño ni de cableado entre bloques. La interfaz lo dice ("plano ilustrativo").
- El layout de cada celda y su verificación contra el netlist (ADR-0015) no cambian.
- La vista no cambia la simulación ni sus métricas.

## Alternativas descartadas

- **Mantener las filas y mejorar sus colores**: a escala de chip seguiría sin
  distinguirse ningún bloque.
- **Placement real con un colocador y un enrutador**: fuera del alcance del curso y sin
  efecto en la simulación (ADR-0015).
