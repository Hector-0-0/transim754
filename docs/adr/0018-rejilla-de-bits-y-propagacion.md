# ADR-0018 · Rejilla de bits de un bloque y propagación con retardo unitario por celda

- **Estado:** Aceptada
- **Fecha:** 2026-11-02

## Contexto

La pestaña Recorrido muestra la operación etapa por etapa (desempaquetar, alinear,
sumar…). Dentro de una etapa no se ve nada que avance. En el sumador de mantisas
(`ADDSUB28`: 28 FA en cadena, 28 XOR y 2 inversores) lo que se quiere mostrar es el
acarreo, que pasa de un bit al siguiente. En el desplazador (`SHR27`: 135 MUX2 en
5 niveles) se quiere mostrar cómo cada nivel corre los bits 1, 2, 4, 8 o 16 lugares.
Hoy un bloque en la vista Compuertas dibuja cada celda por dentro y se ve recargado.

El motor no sirve para mostrar ese avance. Es de nivel de interruptor sin tiempo
(ADR-0007): calcula el estado estable final, y el orden en que su cola procesa los nodos
no corresponde a ningún tiempo físico. Para hablar de tiempo, el proyecto ya adoptó un
modelo en ADR-0014: cada celda primitiva cuesta una unidad de retardo.

## Decisión

### 1. Rejilla de bits

La vista Compuertas de un bloque (más de una celda) deja de dibujar cada celda por
dentro y pasa a ser una **rejilla**:

- Cada celda primitiva del bloque es un recuadro pequeño con su tipo (FA, MUX2,
  XOR2…), pintado con el valor de su salida.
- **Columna:** el bit del puerto del bloque (entrada o salida) más cercano a la celda en
  el grafo de conexiones; si hay empate, el de menor índice. Así el FA del bit *i*
  queda en la columna *i* y cada nivel del desplazador queda alineado bit a bit.
- **Fila:** el nivel lógico de la celda, contado en celdas desde las entradas del
  bloque. La cadena de acarreo se ve como una escalera y los niveles del desplazador
  como filas.
- La rejilla se calcula del netlist, no se dibuja a mano. Doble clic en un recuadro
  abre esa celda.

### 2. Propagación con retardo unitario (modo de presentación, aparte del motor)

- Al calcular, la interfaz guarda el estado estable anterior de la unidad: el valor de
  cada nodo, unos 6 600 en el sumador.
- Al pedir la animación, la interfaz **reproduce el cambio por rondas**. En la ronda *t*
  se evalúan las celdas cuyas entradas cambiaron en la ronda *t − 1*, con la tabla de
  verdad de su tipo (la misma que usa el motor `cached`, ADR-0008). Sus salidas cambian
  en la ronda *t*. Todas las celdas cuestan una unidad, como en ADR-0014. La
  reproducción termina cuando una ronda no cambia nada.
- **Verificación obligatoria:** al terminar, el estado de la reproducción debe ser
  igual, nodo por nodo, al estado estable que calculó el motor. Si no lo es, no se anima
  y la interfaz lo dice. Las pruebas lo comprueban con los ejemplos de las cuatro
  unidades en binary32 y binary16.
- **Interfaz:** en la rejilla, un control "tiempo: *t* de *T* retardos" con ▶ y un
  deslizador resalta las celdas que cambian en cada ronda. El paso "Sumar mantisas" del
  Recorrido tiene un botón "Ver el acarreo" que abre la rejilla con la animación.
- La interfaz muestra en cuántas rondas se estabilizó esta operación y lo compara con
  el camino crítico, que es el peor caso de ADR-0014 (176 celdas en el sumador de
  binary32). Por ejemplo: "esta suma se estabilizó en *n* retardos; el peor caso es 176".

## Consecuencias

- El motor, sus resultados y sus métricas no cambian. La propagación es un modelo de
  presentación aparte, verificado contra el estado final del motor.
- **Puede mostrar valores transitorios (*glitches*)** que el motor no muestra, porque
  el motor salta al estado final. Son consecuencia del modelo de retardo unitario, no
  una medición del circuito, y la interfaz lo dice junto al control de tiempo.
- No se modelan retardos distintos por tipo de celda, cargas ni capacitancias. Eso es
  otro nivel de abstracción (ADR-0006). El número de rondas es comparable con la
  estimación de ciclos de ADR-0014, no con un tiempo en nanosegundos.
- `Calculation` guarda el estado anterior (una lista de valores por nodo). La
  reproducción se calcula solo cuando se pide y tiene un límite de evaluaciones. En la
  división, el bloque más grande tiene unos 29 000 transistores, y si la reproducción
  pasa el límite la interfaz avisa en vez de congelarse.
- Solo se aplica a las unidades de la FPU, que son combinacionales. Las celdas
  secuenciales (latch, flip-flop) tienen realimentación y con retardo unitario podrían
  oscilar, así que quedan fuera.

## Alternativas descartadas

- **Usar el orden de la cola del motor como tiempo.** Ese orden depende de cómo se
  encolan los nodos y no tiene sentido físico (ADR-0007).
- **Animar por nivel lógico, sin reproducir el cambio.** Iluminaría la red completa en
  su peor caso y no mostraría lo que pasó en esta operación, por ejemplo que el
  acarreo se detuvo en el bit 3.
- **Simulación eléctrica con retardos reales (SPICE, Elmore).** Es otro nivel de
  abstracción y está fuera del alcance (ADR-0006).
- **Dibujar a mano la rejilla de cada bloque.** Se desactualiza si cambia un bloque y
  no escala a las cuatro unidades en dos formatos.
