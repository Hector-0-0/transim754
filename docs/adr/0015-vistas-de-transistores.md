# ADR-0015 · Vistas de la pestaña de transistores: esquema, silicio y corte

- **Estado:** Aceptada
- **Fecha:** 2026-10-25

## Contexto

La pestaña de transistores dibujaba cada transistor suelto, con el nombre de sus nodos
como texto. Era correcto pero no se parecía a un circuito: no se veía qué transistores
están en serie o en paralelo, ni cómo se ve un transistor en un chip. Al mostrarla surgió
la pregunta "¿dónde está la placa de silicio?". El simulador es de nivel de interruptor
(ADR-0007): no modela geometría, capas ni física de dispositivos.

## Decisión

La pestaña ofrece tres vistas, todas **generadas a partir del netlist** y pintadas con
el estado que calcula el motor:

1. **Esquema** (`ui/gui/circuit.py`, `ui/gui/schematic.py`). Cada celda se analiza en
   etapas CMOS: una red pull-up de pMOS de VDD a la salida y una pull-down de nMOS de la
   salida a GND, reducidas a árboles serie-paralelo; las transmission gates son un
   elemento aparte. Se dibuja como en un libro de diseño CMOS (Weste y Harris, 2011):
   serie apilada, paralelo lado a lado, cables reales entre etapas vecinas y nombres de
   nodo para las demás conexiones. El canal de un transistor se dibuja continuo si
   conduce y cortado si no.
2. **Silicio** (`ui/gui/silicon.py`). Un layout **ilustrativo** de celda estándar:
   difusión p+ en el pozo n arriba, difusión n+ abajo, columnas de polisilicio que
   comparten un pMOS y un nMOS, difusión compartida entre transistores vecinos, contactos,
   metal 1, metal 2 y vías. Todas las celdas tienen la misma altura, así un bloque se
   dibuja en filas y la unidad completa como el plano de un chip. El canal de un
   transistor que conduce se ilumina.
3. **Corte transversal** (`ui/gui/cross_section.py`) del transistor elegido: cuerpo,
   fuente y drenador, óxido y compuerta; la capa de inversión aparece cuando conduce.

El layout se verifica contra el netlist con una comparación simplificada tipo LVS
(`silicon.check`): sin cortocircuitos entre nodos en una misma capa, cada nodo en una
sola pieza y cada canal con la compuerta y los extremos de su transistor. Las pruebas la
corren para todas las celdas de la biblioteca.

## Consecuencias

- Las vistas son una representación del mismo netlist; no cambian la simulación ni sus
  métricas. El layout no respeta reglas de diseño de un proceso real ni sus medidas, y la
  interfaz lo indica ("layout ilustrativo, no a escala").
- En reposo, un canal que conduce une dos nodos con el mismo valor y no circula
  corriente. La animación de corriente solo se muestra en el transitorio, tras cambiar
  una entrada, en los transistores que cargaron o descargaron una salida.
- Una celda nueva de la biblioteca obtiene esquema y layout sin dibujarla a mano; si no
  es CMOS estática, sus transistores se dibujan sueltos y su layout se verifica igual.

## Alternativas descartadas

- **Dibujos hechos a mano para cada celda.** Más bonitos, pero se desactualizan si
  cambia una celda y no escalan a los miles de celdas de una unidad.
- **Layout real con un editor (Magic, KLayout) y reglas de un PDK.** Fuera del alcance
  del curso y sin efecto en el resultado de la simulación de nivel de interruptor.
- **Simulación eléctrica (SPICE) para animar corrientes.** Otro nivel de abstracción
  (ADR-0006); la animación es cualitativa y se deriva del cambio de valores lógicos.
