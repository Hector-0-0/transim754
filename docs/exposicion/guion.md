# Guion de la exposición

Unos 10 minutos y seis bloques; cada expositor habla una sola vez. Las diapositivas
son apoyo: en cada bloque, quien expone muestra en vivo cómo se usa el programa,
abierto en modo exposición (`transim gui`, ADR-0019).

## Orden

| Bloque | Expositor | Tema | Diapositivas | Tiempo |
|---|---|---|---|---|
| 1 | Héctor | Introducción y cómo se usa | 1 a 4 | 1 min 25 s |
| 2 | Daniel | Definiciones matemáticas | 5 a 8 | 1 min 45 s |
| 3 | Jairo | Capas L0 y L1: transistores y celdas | 9 a 12 | 1 min 40 s |
| 4 | Fabrizzio | Capas L2 y L3: bloques y FPU | 13 a 17 | 1 min 55 s |
| 5 | Yenny | Métricas y prueba integral | 18 a 20 | 1 min 35 s |
| 6 | Ronald | Casos especiales, verificación y cierre | 21 a 23 | 1 min 30 s |

  Bloque  Expositor   Tema                                      Diapositivas  Tiempo
La pauta del curso pide que todo el grupo exponga, por eso Ronald tiene el bloque 6. Si
al final no expone, Yenny dice también el bloque 6 (seguido del suyo) y responde sus
preguntas.

## Antes de exponer (5 minutos antes, en la computadora del aula)

1. Abrir el programa con `uv run transim gui` y maximizar la ventana.
2. En Operación, calcular 1 ÷ 3 (prepara la unidad de división, que es la más grande).
3. Luego calcular 1 + 1. NO calcular 1.5 + 2.25 antes: si se repite la misma suma, el
   acarreo no tiene nada que mostrar porque nada cambia.
4. Abrir una vez la pestaña Transistores, botón ☰, Biblioteca, XOR2; y volver a la
   pestaña Operación.
5. Abrir las diapositivas en otra ventana; se pasa de una a otra con Alt+Tab.

Si algo del programa falla en vivo: no se improvisa, se sigue con la diapositiva, que
tiene la misma captura.

## Bloque 1: Héctor Flores. Introducción y cómo se usa (1 min 25 s)

### Diapositiva 1: Presentación

Buenos días. Somos el grupo de TranSim754. Construimos una unidad de punto flotante
IEEE 754 que no calcula con las operaciones de Python, sino con transistores nMOS y
pMOS simulados uno por uno. Un ejemplo nos acompañará toda la exposición: 1.5 más 2.25
da 3.75, que en 32 bits se escribe 0x40700000.

### Diapositiva 2: El reto

El enunciado pedía emular al menos 100 transistores y, con ellos, sumar, restar,
multiplicar y dividir en IEEE 754. Solo nuestra unidad de suma tiene 13 974
transistores; la de multiplicación, 29 966; la de división, 40 048; y la máquina
completa, unos 100 600. Hacemos las cuatro operaciones en 32 y en 16 bits.

### Diapositiva 3: Cómo se usa (en vivo)

El programa tiene tres pestañas, y cada una es una forma de mirar la misma FPU.

> **En vivo:** Hacer clic en cada pestaña mientras se dice:

Operación es la FPU vista desde afuera: se escriben dos números y se calcula.
Recorrido muestra esa misma operación paso a paso, en las etapas del hardware.
Transistores la abre por dentro, desde el plano del chip hasta cada transistor.
Todo se maneja con el ratón: clic para elegir y doble clic para entrar.

> **En vivo:** Volver a la pestaña Operación.

### Diapositiva 4: Arquitectura por capas

Por dentro, el sistema tiene seis capas, y cada una se construye solo con la de abajo:
L0, el transistor; L1, las compuertas; L2, los bloques aritméticos; L3, la unidad de
punto flotante; L4, la CPU; y L5, la interfaz. Daniel explica la matemática.

## Bloque 2: Daniel Alcantara. Definiciones matemáticas (1 min 45 s)

### Diapositiva 5: IEEE 754 binary32

Un número binary32 usa 32 bits: 1 de signo, 8 de exponente y 23 de fracción. Su valor
es menos uno elevado a s, por 1 punto f, por 2 elevado a E menos 127; ese 127 se llama
sesgo. Por ejemplo, 1.5 es 0x3FC00000: E vale 127, así que el exponente real es 0, y
1 punto f es 1.1 en binario. Si E vale 0, el número es cero o subnormal; si vale 255,
es infinito o NaN.

### Diapositiva 6: La suma en cinco pasos

La suma tiene cinco pasos: restar exponentes, alinear la mantisa menor, sumar,
normalizar y redondear. Con 1.5 más 2.25: la diferencia de exponentes es 1; la mantisa
1.1 se corre una posición y queda 0.11; sumada a 1.001 da 1.111; y 1.111 por 2 elevado
a 1 es 3.75.

### Diapositiva 7: Redondeo y flags

Al alinear se pierden bits, y el hardware guarda tres de ellos: G, R y S. Se suma 1 al
resultado si G vale 1 y además R, S o el último bit valen 1; en un empate exacto se
elige el vecino par. Así el error nunca pasa de medio ulp. Se calculan los cinco flags
del estándar: operación inválida, división por cero, overflow, underflow e inexacto.

### Diapositiva 8: En el programa (en vivo: Operación)

Veamos la suma en el programa.

> **En vivo:** Escribir 1.5 en a y 2.25 en b, dejar + y binary32, pulsar «Calcular en transistores».

El resultado es 0x40700000, 3.75, y el programa confirma que coincide con el modelo de
referencia, bit a bit y en los flags. Aquí abajo están los 32 bits: el exponente 128
significa 2 elevado a 1, y la fracción 111 da 1.875; 1.875 por 2 es 3.75.

> **En vivo:** Hacer clic en el bit de signo de b.

Si hago clic en un bit, se invierte y la FPU recalcula: ahora b vale menos 2.25 y el
resultado es menos 0.75.

> **En vivo:** Volver a hacer clic en el mismo bit (regresa a 1.5 + 2.25). No calcular nada más.

Jairo sigue con los transistores.

## Bloque 3: Jairo Huamán. Capas L0 y L1 (1 min 40 s)

### Diapositiva 9: L0, el transistor es un interruptor

En L0, un nMOS conduce cuando su compuerta vale 1 y un pMOS cuando vale 0. Cada nodo
tiene un valor, que puede ser 0, 1, X o Z, y una fuerza: la de los rieles, la de las
entradas o la de una carga retenida. Gana la fuerza mayor, y si chocan un 0 y un 1 de
la misma fuerza, el nodo queda en X. Para ir rápido, el motor calcula la tabla de
verdad de cada celda una sola vez, desde sus transistores, y la reutiliza.

### Diapositiva 10: L1, compuertas CMOS

Con esos interruptores se arman las compuertas. La NAND usa 4 transistores: dos pMOS
en paralelo hacia VDD y dos nMOS en serie hacia tierra. La XOR usa 12, el flip-flop D
22 y el sumador completo 28, con el diseño espejo.

### Diapositiva 11: De transistores a compuertas (en vivo: Transistores, Biblioteca)

> **En vivo:** Pestaña Transistores, botón ☰, Biblioteca, elegir XOR2.

En el programa, cada celda se ve primero como compuertas. El programa las deduce de los
transistores: nMOS en serie es un AND, en paralelo es un OR, y la salida sale negada.
Así, la XOR resulta ser dos inversores y una compuerta AND-OR invertida. Rojo es 1 y
azul es 0.

> **En vivo:** Hacer clic en la entrada a.

Si cambio una entrada, todo se recalcula y la salida cambia.

### Diapositiva 12: Esquema y silicio (en vivo)

> **En vivo:** Botón «Transistores» de la barra de arriba (el esquema).

Esta es la misma celda en transistores: arriba la red de pMOS, abajo la de nMOS. El
canal en verde es el que conduce.

> **En vivo:** Botón «Silicio» y pasar el ratón por un transistor.

Y así se fabricaría: difusión p en ocre, difusión n en verde y polisilicio en violeta
cruzando las dos. Al pasar el ratón por un transistor se resalta en los dos dibujos. Es
un dibujo ilustrativo, no a escala. Fabrizzio sigue con los bloques.

## Bloque 4: Fabrizzio Ancajima. Capas L2 y L3 (1 min 55 s)

### Diapositiva 13: L2, sumadores y restador

En L2, el sumador ripple-carry encadena un sumador completo por bit: a 32 bits son 896
transistores y 32 niveles de retardo. El carry-lookahead baja a 19 niveles, un 40 %
menos, pero usa 3 526 transistores, casi cuatro veces más. Para restar se invierte b
con XOR y se suma 1: complemento a 2.

### Diapositiva 14: L2, alinear y normalizar

El desplazador barrel mueve 1, 2, 4, 8 o 16 posiciones en cada una de sus 5 etapas, y
los bits que salen por la derecha forman el bit sticky. El contador de ceros a la
izquierda es un árbol. Con estos dos bloques la FPU alinea y normaliza.

### Diapositiva 15: L3, la suma en transistores

En L3, cada línea del código instancia un bloque: el comparador elige el mayor, el
restador calcula la diferencia de exponentes, el desplazador alinea y el sumador opera.
El redondeo es la etapa más cara: 3 812 transistores, el 27 % de los 13 974.

### Diapositiva 16: L3, multiplicación y división

La multiplicación suma los exponentes, resta 127 y multiplica las mantisas con un
arreglo de AND y sumadores: 29 966 transistores. La división es no restauradora, con una
fila de suma o resta por cada bit del cociente: 40 048 transistores, casi el triple que
la suma.

### Diapositiva 17: El plano del chip (en vivo: Transistores, Silicio)

> **En vivo:** En el panel ☰, pestaña «Última operación» (la suma de Daniel): aparece el plano.

Así se ve la unidad de suma completa. Cada rectángulo es un bloque y su área es
proporcional a sus transistores: el más grande es el redondeo.

> **En vivo:** Doble clic en «Redondear y empaquetar» para entrar; para volver, clic en «Suma y resta en binary32» en la ruta de arriba.

Con doble clic entro a sus celdas, hasta llegar al transistor, y con la ruta de arriba
vuelvo. Yenny presenta las métricas.

## Bloque 5: Yenny Chávez. Métricas y prueba integral (1 min 35 s)

### Diapositiva 18: Métricas (en vivo: Operación, Ciclos de reloj)

Medimos tres cosas en cada bloque: transistores, profundidad y actividad. El simulador
no tiene tiempo físico, así que los ciclos se derivan del camino crítico, y usamos como
reloj 39 celdas, el camino crítico de la ALU entera. La suma recorre 176 celdas: 5
ciclos; la multiplicación, 157: también 5; y la división, 852: 22 ciclos.

> **En vivo:** Pestaña Operación, abajo «Ciclos de reloj»: la barra de los 5 ciclos.

### Diapositiva 19: Prueba integral (en vivo: Recorrido)

> **En vivo:** Pestaña Recorrido. Pulsar «Siguiente» paso por paso hasta el 5.

Para la prueba integral, Recorrido muestra la suma de Daniel dentro del circuito. Cada
caja es una etapa del hardware y el panel de la derecha explica la cuenta con los bits
de la simulación. La diferencia de exponentes vale 1, la mantisa alineada es 0.11 y la
suma da 1.111. Al final, G, R y S valen 0, así que el resultado es exacto: 0x40700000,
igual que el modelo de referencia.

### Diapositiva 20: El acarreo, retardo a retardo (en vivo)

> **En vivo:** En el paso 5, pulsar «Ver el acarreo ▸»: la animación empieza sola («Reproducir» la repite).

Aquí está el sumador de mantisas por dentro: cada columna es un bit y cada fila un
nivel lógico, así que la cadena de acarreo se ve como una escalera. Al reproducir,
cada instante es un retardo de celda y se ve el acarreo avanzar de bit en bit. En el
peor caso, la suma completa tarda 176 retardos. Ronald cierra con los casos especiales.

## Bloque 6: Ronald Ayala. Casos especiales, verificación y cierre (1 min 30 s)

### Diapositiva 21: Casos especiales (en vivo: Operación)

> **En vivo:** Pestaña Operación: escribir 1 en a y 3 en b, elegir ÷ y pulsar «Calcular en transistores».

El estándar también define los casos difíciles, y el circuito los resuelve igual que el
estándar. 1 entre 3 no tiene representación exacta: da 0.33333334 y se enciende el flag
de inexacto. En los bits se ve el redondeo de Daniel: 1 entre 3 en binario es 0.0101
repetido, y la fracción termina en 1011 porque lo que se descartaba pasaba de medio ulp
y el último bit subió.

> **En vivo:** Cambiar b a 0 y calcular; después cambiar a a 0 y calcular.

1 entre 0 da más infinito, con el flag de división por cero. Y 0 entre 0 da NaN, con el
flag de operación inválida. La tabla de la diapositiva tiene más casos calculados con
los transistores: 0.1 más 0.2 tampoco es exacto, infinito menos infinito da NaN y el
número más grande por 2 desborda a infinito.

### Diapositiva 22: Verificación y conclusiones

Para saber que todo es correcto, comparamos cada resultado con un modelo de referencia
y con NumPy, en los casos borde y en 10 000 pares al azar por operación. No hubo
ninguna diferencia, ni en los bits ni en los flags. El proyecto tiene 626 pruebas
automáticas que se corren cada vez que cambiamos algo.
En conclusión: partimos de un transistor que solo es un interruptor y llegamos a una
máquina de unos 100 600 transistores que suma, resta, multiplica y divide según IEEE
754; cada decisión de diseño tiene un costo que se puede medir; y todo se puede ver en
el programa, del plano del chip a cada transistor.

### Diapositiva 23: Cierre

Muchas gracias por su atención. Quedamos atentos a sus preguntas.

## Si el profesor pregunta

Responde primero quien expuso ese tema; luego cualquiera puede completar. Si la pregunta
es de uso, se responde mostrándolo en el programa.

### Uso del programa

- ¿Cómo ingreso otros números? En Operación, en decimal (−2.5, 1e-3), como fracción (1/3), inf, nan o en hexadecimal (0x3FC00000). Debajo de cada campo se ve cómo queda guardado. Enter calcula. (Héctor o Daniel)
- ¿Se puede en 16 bits? Sí: en Formato se elige binary16 y se calcula. (Daniel)
- ¿Cómo veo los transistores de una etapa? En Recorrido, doble clic en la caja; o en Transistores, doble clic en el plano hasta llegar a la celda. (Jairo o Fabrizzio)
- ¿Cómo veo qué cambió? En Transistores, menú «Ver ▾», opción «Mapa de actividad». (Fabrizzio)
- ¿Y la CPU del proyecto? Existe: `transim gui --completo` muestra la pestaña Programa, que corre programas .t754 en la máquina T754 con la misma FPU, y también el botón de ejemplos y el historial. Los ocultamos en la exposición porque no son parte de lo pedido. (Ronald o Yenny)
- ¿Por qué la propagación se ve en Compuertas y no en Transistores? Porque se reproduce con un retardo por celda: en cada instante se sabe qué celda cambia su salida, no qué hace cada transistor por dentro. Además, un bloque como el sumador tiene 1 136 transistores: en la rejilla cada celda es un recuadro y se entiende; con todos sus transistores no se leería. Para ver una celda por dentro se hace doble clic en ella. (Yenny)
- ¿Para qué sirve el mapa de actividad? Pinta cada bloque según cuántos nodos cambiaron en la última operación. En CMOS casi toda la energía se gasta cuando un nodo cambia (se carga o descarga), así que el mapa muestra qué partes trabajaron y cuáles no. Es la tercera métrica, junto a los transistores y la profundidad. (Fabrizzio o Yenny)
- ¿Por qué solo algunas compuertas «trabajan»? Todas calculan siempre, pero solo cambian su salida las que reciben entradas distintas a las de la operación anterior. En la rejilla, rojo es una salida en 1 y azul en 0; el borde amarillo marca las que cambian en ese instante. Si se repite la misma operación, no cambia ninguna. (Jairo o Yenny)

### Contenido

- Héctor: ¿El resultado lo calcula Python? No. El código solo coloca y conecta transistores; el resultado se lee de los nodos de salida al simular. NumPy solo se usa para comparar.
- Daniel: ¿Por qué bastan G, R y S? S es el OR de todos los bits restantes; con los tres se sabe si lo descartado es menor, igual o mayor que medio ulp.
- Jairo: ¿Por qué el pMOS conduce con 0? Su canal es de huecos y se forma con la compuerta en nivel bajo; el nMOS es el dual.
- Jairo: ¿Las compuertas están dibujadas a mano? No: se deducen de los transistores de cada celda (serie = AND, paralelo = OR) y se comprueban contra la simulación.
- Fabrizzio: ¿Qué es el sticky? El OR de todos los bits que salen al alinear; le avisa al redondeo que se perdió algo.
- Fabrizzio: ¿El plano es un layout real? No: el área de cada bloque sale de su número de transistores. Sirve para ver qué bloque pesa más.
- Yenny: ¿Por qué el reloj es de 39 celdas? Es el camino crítico de la ALU entera de 32 bits; así una operación entera cabe en un ciclo.
- Yenny: ¿El acarreo se mide en tiempo real? No. El simulador calcula el estado final; la propagación se reproduce aparte con un retardo por celda y se comprueba que llega al mismo resultado que el simulador.
- Ronald: ¿Cómo saben que el resultado es correcto? Cada operación se compara bit a bit con un modelo de referencia y con NumPy, en los casos borde y en 10 000 pares al azar, y no hubo ninguna diferencia.
