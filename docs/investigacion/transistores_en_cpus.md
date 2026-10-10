# Funcionamiento de los transistores en las CPU

> Investigación del proyecto TranSim754 (SI421U, 2026-II). Cada sección relaciona el
> fenómeno físico con lo que modela o simplifica el simulador (ADR-0007). Las cifras de
> TranSim754 provienen de `transim metrics` (`docs/metricas/`).

## Introducción

Una unidad central de procesamiento (CPU) moderna es, en su nivel más bajo, una red de
miles de millones de transistores que se comportan como interruptores controlados por
tensión. Las operaciones aritméticas que un programador escribe en una línea, como
`x = a + b` sobre números en punto flotante, se resuelven mediante la conmutación
coordinada de miles de esos interruptores. Este documento recorre ese camino en cinco
pasos: el transistor MOSFET como dispositivo físico (sección 1), su uso como interruptor
en la lógica CMOS (sección 2), la composición jerárquica de compuertas hasta formar una
CPU (sección 3), la evolución tecnológica del transistor y su escalamiento (secciones 4
y 5) y el costo energético de conmutar (sección 6). La sección 7 resume qué aspectos de
esa realidad reproduce TranSim754 y cuáles simplifica de forma deliberada.

## 1. El transistor MOSFET

El transistor de efecto de campo metal-óxido-semiconductor (MOSFET) es un dispositivo
de cuatro terminales: compuerta (*gate*), fuente (*source*), drenador (*drain*) y
sustrato (*body*). La compuerta está separada del semiconductor por una capa delgada de
aislante, históricamente dióxido de silicio y hoy dieléctricos de alta permitividad
(*high-k*). Entre la fuente y el drenador se encuentra la región del canal (Weste y
Harris, 2011, cap. 2).

En un transistor **nMOS**, la fuente y el drenador son regiones de silicio dopado tipo n
sobre un sustrato tipo p. Cuando la tensión entre compuerta y fuente (V_GS) supera la
**tensión umbral** V_t, el campo eléctrico de la compuerta atrae electrones a la
superficie del sustrato y forma un canal de inversión que conecta la fuente con el
drenador. Por debajo del umbral, el canal no existe y el transistor está, en primera
aproximación, apagado. El transistor **pMOS** es el dual: regiones p sobre un pozo n,
canal formado por huecos y conducción cuando la compuerta está suficientemente por
debajo de la fuente, es decir, con la compuerta en 0 lógico (Rabaey et al., 2003,
cap. 3).

Según las tensiones aplicadas, el MOSFET opera en tres regiones:

| Región | Condición (nMOS) | Comportamiento |
|---|---|---|
| Corte | V_GS < V_t | no hay canal; solo fluye una corriente de fuga pequeña |
| Lineal (óhmica) | V_GS > V_t y V_DS < V_GS − V_t | el canal se comporta como una resistencia controlada por V_GS |
| Saturación | V_GS > V_t y V_DS ≥ V_GS − V_t | la corriente depende casi solo de V_GS (fuente de corriente) |

En los circuitos digitales el transistor se lleva casi siempre a los extremos: corte
(interruptor abierto) o conducción plena (interruptor cerrado). La región de saturación
interviene durante las transiciones y determina la rapidez con que se cargan y
descargan las capacitancias del circuito.

Los electrones tienen una **movilidad** mayor que los huecos, del orden de dos a tres
veces en el silicio (Weste y Harris, 2011). Por eso, a igual tamaño, un nMOS conduce
más corriente que un pMOS, y los diseñadores ensanchan los pMOS para equilibrar los
tiempos de subida y de bajada.

**En TranSim754.** Cada transistor se modela como un interruptor ideal con tres estados
de conducción según el valor de su compuerta: conduce, no conduce o incierto si la
compuerta vale X (ADR-0007). No hay tensión umbral, regiones de operación ni movilidad:
el simulador es de nivel de interruptor (*switch-level*).

## 2. Del transistor al interruptor: lógica CMOS

La lógica CMOS (*complementary MOS*) combina en cada compuerta una **red pull-up** de
pMOS, que conecta la salida a la alimentación V_DD, y una **red pull-down** de nMOS, que
la conecta a tierra. Las dos redes son complementarias: para cada combinación de
entradas conduce exactamente una de ellas, de modo que la salida siempre queda
conectada a un riel y nunca a ambos (Weste y Harris, 2011, cap. 1).

El caso más simple es el **inversor**: un pMOS entre V_DD y la salida y un nMOS entre la
salida y tierra, con las compuertas unidas a la entrada. Con la entrada en 0 conduce el
pMOS y la salida sube a 1; con la entrada en 1 conduce el nMOS y la salida baja a 0. Su
curva de transferencia de tensión tiene una transición abrupta alrededor de V_DD/2, lo
que da márgenes de ruido amplios y **restaura** los niveles lógicos: una entrada algo
degradada produce una salida a nivel pleno.

Las compuertas de dos entradas siguen la misma regla de dualidad:

- **NAND2:** dos pMOS en paralelo arriba y dos nMOS en serie abajo. La salida baja solo
  si ambas entradas valen 1.
- **NOR2:** dos pMOS en serie arriba y dos nMOS en paralelo abajo.

Ambas usan cuatro transistores, pero la NAND se prefiere: sus transistores en serie son
nMOS, que son los de mayor movilidad, mientras que la NOR coloca en serie los pMOS, más
lentos. Por eso las bibliotecas estándar construyen gran parte de la lógica sobre NAND e
inversores (Rabaey et al., 2003).

La **transmission gate** es un nMOS y un pMOS en paralelo, controlados por señales
complementarias. Cuando está habilitada deja pasar tanto un 0 como un 1 sin degradarlos,
porque el nMOS transmite bien el 0 y el pMOS el 1. Se usa en multiplexores y en elementos
de memoria.

Una propiedad clave de CMOS es su **consumo estático casi nulo**: en reposo no existe un
camino conductor entre V_DD y tierra, y la energía se gasta principalmente al conmutar
(sección 6). Esta propiedad explica el dominio de CMOS desde la década de 1980.

**En TranSim754.** El modelo de Bryant (1984) representa cada nodo con un valor lógico
{0, 1, X, Z} y una fuerza (alimentación, manejado o carga retenida); la salida de una
compuerta resulta de qué rieles alcanza a través de los transistores que conducen. Las
celdas de la biblioteca L1 son exactamente las redes CMOS descritas: INV de 2
transistores, NAND2 y NOR2 de 4, XOR2 complementario de 12, MUX2 restaurador de 12 con
transmission gates y sumador completo espejo de 28.

## 3. De las compuertas a la CPU

Una CPU se construye por **composición jerárquica**: transistores forman compuertas,
compuertas forman bloques aritméticos y de memoria, y esos bloques forman la ruta de
datos y la unidad de control.

- **Sumadores.** El sumador completo de un bit calcula la suma y el acarreo de tres
  bits. Encadenando N sumadores completos se obtiene el sumador *ripple-carry*, cuyo
  retardo crece linealmente con N porque cada acarreo espera al anterior. El
  *carry-lookahead* calcula los acarreos por adelantado con señales de generación
  (g = a·b) y propagación (p = a ⊕ b), a cambio de más transistores (Koren, 2002).
- **Memoria de estado.** Un *latch* D retiene un bit con dos inversores en lazo y
  transmission gates que abren o cierran la entrada según el reloj. Dos latches con
  relojes complementarios forman un **flip-flop maestro-esclavo**, que captura el dato
  solo en el flanco del reloj. Un registro de 32 bits son 32 flip-flops.
- **ALU y FPU.** La unidad aritmético-lógica combina sumadores, multiplexores e
  indicadores. La unidad de punto flotante agrega desplazadores, contadores de ceros a
  la izquierda, multiplicadores en arreglo, divisores y la lógica de redondeo del
  estándar IEEE 754 (IEEE, 2019).

El número de transistores de un procesador refleja esta composición y su crecimiento
histórico. El Intel 4004, de 1971, tenía unos 2 300 transistores (Intel, s. f.). El
Apple M2 Ultra, presentado en 2023, integra 134 000 millones (Apple, 2023): un
crecimiento de siete órdenes de magnitud en cinco décadas.

**En TranSim754.** La jerarquía es la misma: celdas L1, bloques L2 (sumadores RCA y CLA,
restador, comparador, desplazador barrel, LZC, multiplexores), unidades L3 (ALU entera y
FPU) y la máquina T754 de L4. La FPU de binary32 suma 13 974 transistores en FADD/FSUB,
29 966 en FMUL y 40 048 en FDIV; el banco de ocho registros de 32 bits, 14 230. Son
cifras pequeñas frente a un chip comercial, pero suficientes para que la aritmética
IEEE 754 completa ocurra literalmente en transistores.

## 4. Evolución de la tecnología del transistor

### 4.1. MOSFET planar y escalamiento de Dennard

Durante décadas el transistor fue **planar**: un canal en la superficie del silicio
controlado por una compuerta desde arriba. Dennard et al. (1974) formularon las reglas
de escalamiento a campo eléctrico constante: si las dimensiones y la tensión se reducen
por un factor κ, la densidad crece en κ², el retardo baja en κ y la **densidad de
potencia se mantiene constante**. Cada generación ofrecía más transistores, más rápidos
y sin aumentar el consumo por unidad de área (Bohr, 2007).

### 4.2. Fin del escalamiento de Dennard

Hacia mediados de la década de 2000 la tensión de alimentación dejó de bajar al ritmo
previsto. La tensión umbral no puede reducirse indefinidamente sin que la corriente de
fuga por debajo del umbral crezca de forma exponencial; al estancarse V_t, también se
estancó V_DD. Con más transistores por área y la misma tensión, la densidad de potencia
aumentó y la frecuencia de reloj dejó de crecer. La industria respondió con
procesadores multinúcleo y, más tarde, con la especialización del hardware
(Esmaeilzadeh et al., 2011).

### 4.3. FinFET

Al reducir la longitud del canal, la compuerta planar pierde control sobre él: el
drenador influye en la barrera de potencial (efectos de canal corto) y la fuga aumenta.
El **FinFET** eleva el canal en forma de aleta (*fin*) y lo envuelve con la compuerta por
tres lados, lo que mejora el control electrostático (Hisamoto et al., 2000). Intel lo
llevó a producción en su proceso de 22 nm con el nombre *tri-gate* (Auth et al., 2012),
y desde entonces fue la estructura dominante de los nodos avanzados.

### 4.4. GAA o nanosheet

El paso siguiente es la compuerta que **rodea por completo** el canal
(*gate-all-around*, GAA), formada por láminas de silicio apiladas (*nanosheets*).
Samsung inició en 2022 la producción de su proceso de 3 nm con transistores GAA
(Samsung Electronics, 2022); Intel anunció su variante RibbonFET para los nodos 20A y
18A (Intel, 2021) y TSMC adoptó nanosheets en su nodo N2. El control del canal por los
cuatro lados permite seguir reduciendo dimensiones con fugas acotadas.

### 4.5. Perspectivas

La hoja de ruta internacional de dispositivos y sistemas (IRDS) prevé, tras las
nanosheets, el **CFET** (*complementary FET*), que apila verticalmente el nMOS y el pMOS
de una compuerta para reducir el área, así como la exploración de materiales
bidimensionales para canales de pocos átomos de espesor (IEEE IRDS, 2023).

Conviene distinguir el **nombre comercial** de un nodo de sus dimensiones físicas. Desde
hace años, "3 nm" o "2 nm" no corresponden a la longitud de la compuerta ni a ninguna
medida concreta del transistor: son etiquetas de generación que indican una mejora de
densidad respecto de la anterior (IEEE IRDS, 2023).

## 5. Escalamiento y ley de Moore

Moore (1965) observó que el número de componentes por circuito integrado de costo
mínimo se duplicaba aproximadamente cada año y proyectó que la tendencia continuaría al
menos una década. En 1975 revisó la estimación a una duplicación cada dos años (Moore,
1975). Esta observación empírica, conocida como **ley de Moore**, describe la densidad y
el costo por transistor; no es una ley física.

La ley de Moore y el escalamiento de Dennard suelen confundirse, pero son distintos. La
primera habla de **cuántos** transistores caben; el segundo explicaba por qué esos
transistores eran además **más rápidos y no más costosos en potencia**. El escalamiento
de Dennard terminó hacia 2005 (sección 4.2), mientras que la densidad siguió creciendo
gracias a FinFET, GAA, litografía ultravioleta extrema y técnicas de empaquetado
tridimensional, aunque a un ritmo y con un costo por transistor que ya no mejoran como
antes (IEEE IRDS, 2023).

## 6. Potencia

La potencia de un circuito CMOS tiene dos componentes principales (Weste y Harris, 2011,
cap. 5).

**Potencia dinámica.** Cada vez que un nodo pasa de 0 a 1, la red pull-up carga su
capacitancia desde V_DD; al volver a 0, la red pull-down la descarga a tierra. La
potencia promedio es

  P_din ≈ α · C · V_DD² · f

donde α es el **factor de actividad** (fracción de nodos que conmutan por ciclo), C la
capacitancia conmutada, V_DD la tensión de alimentación y f la frecuencia de reloj. La
dependencia cuadrática con V_DD explica por qué reducir la tensión fue la palanca más
eficaz mientras duró el escalamiento de Dennard.

**Potencia estática.** Aunque un transistor esté "apagado", conduce corrientes de fuga:
por debajo del umbral, a través del óxido de compuerta y en las uniones. En los nodos
avanzados la fuga es una fracción importante del consumo total.

Como la densidad de potencia ya no se mantiene constante, no todos los transistores de
un chip pueden funcionar a la vez a plena frecuencia sin exceder el límite térmico. La
fracción que debe permanecer apagada o a baja frecuencia se conoce como **silicio
oscuro** (*dark silicon*) (Esmaeilzadeh et al., 2011). Las técnicas de reducción más
comunes son:

- **Clock gating:** se detiene el reloj de los bloques inactivos para anular su α.
- **DVFS** (*dynamic voltage and frequency scaling*): se bajan V_DD y f cuando la
  carga lo permite, con ganancia cúbica en potencia dinámica.
- **Power gating:** se desconecta la alimentación de bloques completos para eliminar
  también su fuga.

**En TranSim754.** El simulador no conoce capacitancias ni tensiones, pero mide α: el
número de nodos que conmutan entre estados estables por operación, dividido entre los
nodos internos (ADR-0013). Con 12 operaciones aleatorias, el sumador ripple-carry de 32
bits obtiene α ≈ 0,39 y el carry-lookahead ≈ 0,31, a cambio de casi cuatro veces más
transistores (3 526 frente a 896) y una profundidad lógica de 19 celdas frente a 32
(`docs/metricas/comparacion_sumadores.md`). Es el mismo compromiso entre área, velocidad
y energía que enfrenta un diseñador real.

## 7. Relación con TranSim754

| Fenómeno real | Cómo lo modela TranSim754 | Qué simplifica |
|---|---|---|
| Tensión umbral V_t | compuerta 1 → nMOS conduce; 0 → pMOS conduce | no hay V_t ni conducción parcial |
| Niveles de tensión | valores {0, 1, X, Z} con fuerzas | no hay tensiones intermedias ni márgenes de ruido |
| Conflicto entre redes (cortocircuito) | dos fuerzas iguales y opuestas producen X y una advertencia | no se calcula la corriente ni el calor |
| Capacitancia y carga retenida | un nodo aislado conserva su último valor con fuerza de carga | no hay fuga: la carga se retiene indefinidamente |
| Reparto de carga | la unión de cargas distintas produce X | no se calcula la tensión resultante |
| Retardos | modelo de retardo cero; la velocidad se estima por profundidad lógica | no hay tiempos de subida ni de bajada |
| Potencia dinámica | se cuentan conmutaciones y se calcula α | no hay C, V_DD ni f |
| Fugas y potencia estática | no se modelan | — |
| Tamaño de los transistores | todos son iguales | no hay dimensionamiento W/L |

El simulador conserva lo esencial para estudiar la lógica digital: cada resultado se
obtiene haciendo conducir o no a transistores nMOS y pMOS concretos, y las métricas de
conteo, actividad y profundidad permiten comparar diseños con los mismos criterios
cualitativos que se usan en la industria. Lo que simplifica, como los retardos, las
tensiones y las fugas, es propio de un simulador eléctrico (tipo SPICE) y queda fuera
del alcance del proyecto.

## Referencias

Apple. (2023, 5 de junio). *Apple introduces M2 Ultra* [Comunicado de prensa].
https://www.apple.com/newsroom/2023/06/apple-introduces-m2-ultra/

Auth, C., Allen, C., Blattner, A., Bergstrom, D., Brazier, M., Bost, M., … Mistry, K.
(2012). A 22nm high performance and low-power CMOS technology featuring fully-depleted
tri-gate transistors, self-aligned contacts and high density MIM capacitors. En *2012
Symposium on VLSI Technology* (pp. 131–132). IEEE. https://doi.org/10.1109/VLSIT.2012.6242496

Bohr, M. (2007). A 30 year retrospective on Dennard's MOSFET scaling paper. *IEEE
Solid-State Circuits Society Newsletter, 12*(1), 11–13. https://doi.org/10.1109/N-SSC.2007.4785534

Bryant, R. E. (1984). A switch-level model and simulator for MOS digital systems.
*IEEE Transactions on Computers, C-33*(2), 160–177. https://doi.org/10.1109/TC.1984.1676408

Dennard, R. H., Gaensslen, F. H., Yu, H.-N., Rideout, V. L., Bassous, E., & LeBlanc,
A. R. (1974). Design of ion-implanted MOSFET's with very small physical dimensions.
*IEEE Journal of Solid-State Circuits, 9*(5), 256–268. https://doi.org/10.1109/JSSC.1974.1050511

Esmaeilzadeh, H., Blem, E., St. Amant, R., Sankaralingam, K., & Burger, D. (2011). Dark
silicon and the end of multicore scaling. En *Proceedings of the 38th Annual
International Symposium on Computer Architecture* (pp. 365–376). ACM.
https://doi.org/10.1145/2000064.2000108

Hisamoto, D., Lee, W.-C., Kedzierski, J., Takeuchi, H., Asano, K., Kuo, C., Anderson,
E., King, T.-J., Bokor, J., & Hu, C. (2000). FinFET: A self-aligned double-gate MOSFET
scalable to 20 nm. *IEEE Transactions on Electron Devices, 47*(12), 2320–2325.
https://doi.org/10.1109/16.887014

IEEE. (2019). *IEEE standard for floating-point arithmetic* (IEEE Std 754-2019).
https://doi.org/10.1109/IEEESTD.2019.8766229

IEEE IRDS. (2023). *International Roadmap for Devices and Systems: More Moore* (Ed.
2023). IEEE. https://irds.ieee.org/editions/2023

Intel. (2021, 26 de julio). *Intel accelerates process and packaging innovations*
[Comunicado de prensa]. https://www.intel.com/content/www/us/en/newsroom/news/intel-technology-roadmaps-milestones.html

Intel. (s. f.). *The story of the Intel 4004*. Recuperado el 10 de octubre de 2026, de
https://www.intel.com/content/www/us/en/history/museum-story-of-intel-4004.html

Koren, I. (2002). *Computer arithmetic algorithms* (2.ª ed.). A K Peters.

Moore, G. E. (1965). Cramming more components onto integrated circuits. *Electronics,
38*(8), 114–117.

Moore, G. E. (1975). Progress in digital integrated electronics. En *International
Electron Devices Meeting, Technical Digest* (pp. 11–13). IEEE.

Rabaey, J. M., Chandrakasan, A., & Nikolić, B. (2003). *Digital integrated circuits:
A design perspective* (2.ª ed.). Pearson.

Samsung Electronics. (2022, 30 de junio). *Samsung begins chip production using 3nm
process technology with GAA architecture* [Comunicado de prensa].
https://news.samsung.com/global/samsung-begins-chip-production-using-3nm-process-technology-with-gaa-architecture

Weste, N. H. E., & Harris, D. M. (2011). *CMOS VLSI design: A circuits and systems
perspective* (4.ª ed.). Addison-Wesley.
