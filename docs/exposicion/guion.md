# Guion de la exposición

Unos 10 minutos, seis bloques; cada expositor habla una sola vez. Las diapositivas
son apoyo: en cada bloque, quien expone muestra en vivo cómo se usa el programa.

## Orden

| Bloque | Expositor | Tema | Diapositivas | Tiempo |
|---|---|---|---|---|
| 1 | Héctor | Introducción y cómo se usa | 1–4 | 1 min 25 s |
| 2 | Daniel | Definiciones matemáticas | 5–8 | 1 min 45 s |
| 3 | Jairo | Capas L0 y L1: transistores y celdas | 9–12 | 1 min 40 s |
| 4 | Fabrizzio | Capas L2 y L3: bloques y FPU | 13–17 | 1 min 55 s |
| 5 | Yenny | Métricas y prueba integral | 18–20 | 1 min 35 s |
| 6 | Ronald | Casos especiales, verificación y cierre | 21–23 | 1 min 30 s |

La pauta del curso pide que todo el grupo exponga, por eso Ronald tiene el bloque 6. Si
al final no expone, Yenny dice también el bloque 6 (seguido del suyo) y responde sus
preguntas.

## Antes de exponer (5 minutos antes, en la computadora del aula)

1. Abrir el programa: `uv run transim gui` (F11 lo pone en pantalla completa).
2. En Operación, calcular 1 ÷ 3 (prepara la unidad de división, que es la más grande).
3. Luego calcular 1 + 1. NO calcular 1.5 + 2.25 antes: si se repite la misma suma, el
   acarreo no tiene nada que mostrar porque nada cambia.
4. Abrir una vez Transistores (Ctrl+3) › panel ☰ › Biblioteca › XOR2, y volver a
   Operación (Ctrl+1).
5. Abrir las diapositivas en otra ventana; se pasa de una a otra con Alt+Tab.

Si algo del programa falla en vivo: no se improvisa, se sigue con la diapositiva, que
tiene la misma captura.

## Bloque 1 · Héctor Flores · Introducción y cómo se usa · 1 min 25 s

### Diapositiva 1 · Presentación

Buenos días. Somos el grupo de TranSim754. Construimos una unidad de punto flotante
IEEE 754 que no calcula con las operaciones de Python, sino con transistores nMOS y
pMOS simulados uno por uno. Un ejemplo nos acompañará toda la exposición: 1.5 más 2.25
da 3.75, que en 32 bits se escribe 0x40700000.

### Diapositiva 2 · El reto

El enunciado pedía emular al menos 100 transistores y, con ellos, sumar, restar,
multiplicar y dividir en IEEE 754. Solo nuestra unidad de suma tiene 13 974
transistores; la de multiplicación, 29 966; la de división, 40 048; y la máquina
completa, unos 100 600. Hacemos las cuatro operaciones en 32 y en 16 bits.

### Diapositiva 3 · Cómo se usa · *en vivo*

El programa tiene cuatro pestañas, y cada una es una forma de mirar la misma FPU.

> **En vivo:** Pasar por las pestañas con Ctrl+1, Ctrl+2, Ctrl+3 y Ctrl+4 mientras se dice:

Operación es la FPU vista desde afuera: se escriben dos números y se calcula.
Recorrido muestra esa misma operación paso a paso, en las etapas del hardware.
Transistores la abre por dentro, desde el plano del chip hasta cada transistor.
Y Programa la pone dentro de una CPU pequeña que ejecuta instrucciones.
F1 abre una guía rápida con todos los controles.

> **En vivo:** Volver a Operación con Ctrl+1.

### Diapositiva 4 · Arquitectura por capas

Por dentro, el sistema tiene seis capas, y cada una se construye solo con la de abajo:
L0, el transistor; L1, las compuertas; L2, los bloques aritméticos; L3, la unidad de
punto flotante; L4, la CPU; y L5, la interfaz. Daniel explica la matemática.

## Bloque 2 · Daniel Alcantara · Definiciones matemáticas · 1 min 45 s

### Diapositiva 5 · IEEE 754 binary32

Un número binary32 usa 32 bits: 1 de signo, 8 de exponente y 23 de fracción. Su valor
es menos uno elevado a s, por 1 punto f, por 2 elevado a E menos 127; ese 127 se llama
sesgo. Por ejemplo, 1.5 es 0x3FC00000: E vale 127, así que el exponente real es 0, y
1 punto f es 1.1 en binario. Si E vale 0, el número es cero o subnormal; si vale 255,
es infinito o NaN.

### Diapositiva 6 · La suma en cinco pasos

La suma tiene cinco pasos: restar exponentes, alinear la mantisa menor, sumar,
normalizar y redondear. Con 1.5 más 2.25: la diferencia de exponentes es 1; la mantisa
1.1 se corre una posición y queda 0.11; sumada a 1.001 da 1.111; y 1.111 por 2 elevado
a 1 es 3.75.

### Diapositiva 7 · Redondeo y flags

Al alinear se pierden bits, y el hardware guarda tres de ellos: G, R y S. Se suma 1 al
resultado si G vale 1 y además R, S o el último bit valen 1; en un empate exacto se
elige el vecino par. Así el error nunca pasa de medio ulp. Se calculan los cinco flags
del estándar: operación inválida, división por cero, overflow, underflow e inexacto.

### Diapositiva 8 · En el programa · *en vivo · Operación*

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

## Bloque 3 · Jairo Huamán · Capas L0 y L1 · 1 min 40 s

### Diapositiva 9 · L0: el transistor es un interruptor

En L0, un nMOS conduce cuando su compuerta vale 1 y un pMOS cuando vale 0. Cada nodo
tiene un valor, que puede ser 0, 1, X o Z, y una fuerza: la de los rieles, la de las
entradas o la de una carga retenida. Gana la fuerza mayor, y si chocan un 0 y un 1 de
la misma fuerza, el nodo queda en X. Para ir rápido, el motor calcula la tabla de
verdad de cada celda una sola vez, desde sus transistores, y la reutiliza.

### Diapositiva 10 · L1: compuertas CMOS

Con esos interruptores se arman las compuertas. La NAND usa 4 transistores: dos pMOS
en paralelo hacia VDD y dos nMOS en serie hacia tierra. La XOR usa 12, el flip-flop D
22 y el sumador completo 28, con el diseño espejo.

### Diapositiva 11 · De transistores a compuertas · *en vivo · Transistores › Biblioteca*

> **En vivo:** Ctrl+3, panel ☰, pestaña Biblioteca, elegir XOR2.

En el programa, cada celda se ve primero como compuertas. El programa las deduce de los
transistores: nMOS en serie es un AND, en paralelo es un OR, y la salida sale negada.
Así, la XOR resulta ser dos inversores y una compuerta AND-OR invertida. Rojo es 1 y
azul es 0.

> **En vivo:** Hacer clic en la entrada a.

Si cambio una entrada, todo se recalcula y la salida cambia.

### Diapositiva 12 · Esquema y silicio · *en vivo*

> **En vivo:** Alt+E (vista Transistores).

Esta es la misma celda en transistores: arriba la red de pMOS, abajo la de nMOS. El
canal en verde es el que conduce.

> **En vivo:** Alt+S (vista Silicio) y pasar el ratón por un transistor.

Y así se fabricaría: difusión p en ocre, difusión n en verde y polisilicio en violeta
cruzando las dos. Al pasar el ratón por un transistor se resalta en los dos dibujos. Es
un dibujo ilustrativo, no a escala. Fabrizzio sigue con los bloques.

## Bloque 4 · Fabrizzio Ancajima · Capas L2 y L3 · 1 min 55 s

### Diapositiva 13 · L2: sumadores y restador

En L2, el sumador ripple-carry encadena un sumador completo por bit: a 32 bits son 896
transistores y 32 niveles de retardo. El carry-lookahead baja a 19 niveles, un 40 %
menos, pero usa 3 526 transistores, casi cuatro veces más. Para restar se invierte b
con XOR y se suma 1: complemento a 2.

### Diapositiva 14 · L2: alinear y normalizar

El desplazador barrel mueve 1, 2, 4, 8 o 16 posiciones en cada una de sus 5 etapas, y
los bits que salen por la derecha forman el bit sticky. El contador de ceros a la
izquierda es un árbol. Con estos dos bloques la FPU alinea y normaliza.

### Diapositiva 15 · L3: la suma en transistores

En L3, cada línea del código instancia un bloque: el comparador elige el mayor, el
restador calcula la diferencia de exponentes, el desplazador alinea y el sumador opera.
El redondeo es la etapa más cara: 3 812 transistores, el 27 % de los 13 974.

### Diapositiva 16 · L3: multiplicación y división

La multiplicación suma los exponentes, resta 127 y multiplica las mantisas con un
arreglo de AND y sumadores: 29 966 transistores. La división es no restauradora, con una
fila de suma o resta por cada bit del cociente: 40 048 transistores, casi el triple que
la suma.

### Diapositiva 17 · El plano del chip · *en vivo · Transistores › Última operación*

> **En vivo:** Ctrl+3, panel ☰, pestaña Última operación (la suma de Daniel), Alt+S.

Así se ve la unidad de suma completa. Cada rectángulo es un bloque y su área es
proporcional a sus transistores: el más grande es el redondeo.

> **En vivo:** Hacer clic en «Redondear y empaquetar»; luego doble clic para entrar y Retroceso para salir.

Con un clic veo sus datos y con doble clic entro a sus celdas, hasta llegar al
transistor. Yenny presenta las métricas.

## Bloque 5 · Yenny Chávez · Métricas y prueba integral · 1 min 35 s

### Diapositiva 18 · Métricas · *en vivo · Operación › Ciclos de reloj*

Medimos tres cosas en cada bloque: transistores, profundidad y actividad. El simulador
no tiene tiempo físico, así que los ciclos se derivan del camino crítico, y usamos como
reloj 39 celdas, el camino crítico de la ALU entera. La suma recorre 176 celdas: 5
ciclos; la multiplicación, 157: también 5; y la división, 852: 22 ciclos.

> **En vivo:** Ctrl+1 y mostrar abajo «Ciclos de reloj»: la barra de los 5 ciclos.

### Diapositiva 19 · Prueba integral · *en vivo · Recorrido*

> **En vivo:** Ctrl+2. Pulsar «Siguiente» (o →) paso por paso hasta el 5.

Para la prueba integral, Recorrido muestra la suma de Daniel dentro del circuito. Cada
caja es una etapa del hardware y el panel de la derecha explica la cuenta con los bits
de la simulación. La diferencia de exponentes vale 1, la mantisa alineada es 0.11 y la
suma da 1.111. Al final, G, R y S valen 0, así que el resultado es exacto: 0x40700000,
igual que el modelo de referencia.

### Diapositiva 20 · El acarreo, retardo a retardo · *en vivo*

> **En vivo:** En el paso 5, pulsar «Ver el acarreo ▸» y luego ⏵.

Aquí está el sumador de mantisas por dentro: cada columna es un bit y cada fila un
nivel lógico, así que la cadena de acarreo se ve como una escalera. Al reproducir,
cada instante es un retardo de celda y se ve el acarreo avanzar de bit en bit. En el
peor caso, la suma completa tarda 176 retardos. Ronald cierra con los casos especiales.

## Bloque 6 · Ronald Ayala · Casos especiales, verificación y cierre · 1 min 30 s

### Diapositiva 21 · Casos especiales · *en vivo · Operación › Ejemplos ▾*

> **En vivo:** Ctrl+1, «Ejemplos ▾» y elegir «1 ÷ 3»; después «1 ÷ 0» y «0 ÷ 0».

El estándar también define los casos difíciles, y el circuito los resuelve igual que el
estándar. 1 entre 3 no tiene representación exacta: da 0.33333334 y se enciende el flag
de inexacto. 1 entre 0 da más infinito, con el flag de división por cero. Y 0 entre 0
da NaN, con el flag de operación inválida.

> **En vivo:** Ctrl+4, «Ensamblar y reiniciar» y «Ejecutar hasta HALT» (F8).

Y la misma suma corre dentro de una CPU: este programa carga 1.5 y 2.25, ejecuta FADD
y su salida es otra vez 0x40700000.

### Diapositiva 22 · Verificación y conclusiones

Para saber que todo es correcto, comparamos cada resultado con un modelo de referencia
y con NumPy, en los casos borde y en 10 000 pares al azar por operación. No hubo
ninguna diferencia, ni en los bits ni en los flags. El proyecto tiene 613 pruebas
automáticas que se corren cada vez que cambiamos algo.
En conclusión: partimos de un transistor que solo es un interruptor y llegamos a una
máquina de unos 100 600 transistores que suma, resta, multiplica y divide según IEEE
754; cada decisión de diseño tiene un costo que se puede medir; y todo se puede ver en
el programa, del plano del chip a cada transistor.

### Diapositiva 23 · Cierre

Muchas gracias por su atención. Quedamos atentos a sus preguntas.

## Si el profesor pregunta

Responde primero quien expuso ese tema; luego cualquiera puede completar. Si la pregunta
es de uso, se responde mostrándolo en el programa.

### Uso del programa

- ¿Cómo ingreso otros números? En Operación, en decimal (−2.5, 1e-3), como fracción (1/3), inf, nan o en hexadecimal (0x3FC00000). Debajo de cada campo se ve cómo queda guardado. Enter calcula. (Héctor o Daniel)
- ¿Se puede en 16 bits? Sí: Formato › binary16 y Calcular. (Daniel)
- ¿Cómo veo los transistores de una etapa? En Recorrido, doble clic en la caja; o en Transistores, doble clic en el plano hasta llegar a la celda. (Jairo o Fabrizzio)
- ¿Cómo veo qué cambió? En Transistores, Ver ▾ › mapa de actividad. (Fabrizzio)
- ¿Cómo corro un programa propio? En Programa, se escribe o se abre un .t754, F5 ensambla, F10 avanza una instrucción y F8 corre hasta HALT. (Ronald o Yenny)

### Contenido

- Héctor · ¿El resultado lo calcula Python? No. El código solo coloca y conecta transistores; el resultado se lee de los nodos de salida al simular. NumPy solo se usa para comparar.
- Daniel · ¿Por qué bastan G, R y S? S es el OR de todos los bits restantes; con los tres se sabe si lo descartado es menor, igual o mayor que medio ulp.
- Jairo · ¿Por qué el pMOS conduce con 0? Su canal es de huecos y se forma con la compuerta en nivel bajo; el nMOS es el dual.
- Jairo · ¿Las compuertas están dibujadas a mano? No: se deducen de los transistores de cada celda (serie = AND, paralelo = OR) y se comprueban contra la simulación.
- Fabrizzio · ¿Qué es el sticky? El OR de todos los bits que salen al alinear; le avisa al redondeo que se perdió algo.
- Fabrizzio · ¿El plano es un layout real? No: el área de cada bloque sale de su número de transistores. Sirve para ver qué bloque pesa más.
- Yenny · ¿Por qué el reloj es de 39 celdas? Es el camino crítico de la ALU entera de 32 bits; así una operación entera cabe en un ciclo.
- Yenny · ¿El acarreo se mide en tiempo real? No. El simulador calcula el estado final; la propagación se reproduce aparte con un retardo por celda y se comprueba que llega al mismo resultado que el simulador.
- Ronald · ¿Cómo saben que el resultado es correcto? Cada operación se compara bit a bit con un modelo de referencia y con NumPy, en los casos borde y en 10 000 pares al azar, y no hubo ninguna diferencia.
