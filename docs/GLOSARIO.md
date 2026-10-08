# Glosario

| Término | Definición |
|---|---|
| **α (actividad)** | Fracción de nodos que conmutan por operación; factor de la potencia dinámica P ≈ α·C·V²·f. |
| **ADR** | Architecture Decision Record: documento breve que registra una decisión de diseño, su contexto, consecuencias y alternativas. |
| **binary16 / binary32** | Formatos binarios de intercambio de IEEE 754 de 16 y 32 bits (precisión media y simple). |
| **Barrel shifter** | Desplazador combinacional que desplaza k posiciones en ⌈log₂ N⌉ etapas de multiplexores, cada una desplazando 2^i posiciones. |
| **Bit implícito** | Bit entero de la mantisa (1 en normales, 0 en subnormales) que no se almacena. |
| **CCC** | Componente conectado por canal: conjunto de nodos unidos por canales de transistores; unidad de evaluación del simulador. |
| **CLA** | Carry-lookahead adder: sumador que calcula los acarreos en paralelo a partir de señales de generación y propagación. |
| **CMOS estático** | Lógica con red pull-up de pMOS y red pull-down de nMOS complementarias; en reposo no hay camino de VDD a GND. |
| **Complemento a 2 (C2)** | Representación de enteros con signo en la que −x = ¬x + 1. |
| **Conmutación** | Transición de un nodo de 0 a 1 o de 1 a 0. |
| **Diminuto (tiny)** | Resultado no nulo con magnitud menor que 2^emin. |
| **emin / emax** | Exponentes mínimo y máximo de los números normales de un formato. |
| **Flag** | Indicador de estado que se levanta ante una excepción de IEEE 754 y permanece hasta borrarse (sticky). |
| **Flip-flop D maestro-esclavo** | Elemento de memoria disparado por flanco, formado por dos latches en serie con relojes complementarios. |
| **FSR** | Floating-point Status Register: registro de estado con los flags IEEE y los indicadores enteros C, V, Z, N. |
| **Fuerza (strength)** | Prioridad de una señal en el simulador: SUPPLY > DRIVEN > CHARGE. |
| **Guard, round, sticky (G, R, S)** | Primer bit descartado, segundo bit descartado y OR del resto; bastan para redondear correctamente. |
| **LZC** | Leading Zero Counter: cuenta los ceros a la izquierda de una palabra; se usa para normalizar. |
| **Mantisa (significand)** | Parte significativa del número: bit implícito más fracción, p bits en total. |
| **Mirror adder** | Sumador completo CMOS de 28 transistores cuyas redes pull-up y pull-down son simétricas (espejo). |
| **NaN (qNaN / sNaN)** | Not a Number. El quiet NaN se propaga sin excepción; el signaling NaN levanta invalid al usarse. |
| **NaN canónico** | NaN único que entrega TranSim754: signo 0, exponente todo unos, fracción 10…0 (`0x7FC00000`). |
| **Netlist** | Descripción de un circuito como transistores y los nodos que conectan. |
| **nMOS / pMOS** | Transistores MOS de canal n (conduce con compuerta en 1) y de canal p (conduce con compuerta en 0). |
| **Normalizar** | Desplazar la mantisa y ajustar el exponente para que el bit entero sea 1. |
| **Oráculo** | Fuente de verdad independiente contra la que se comparan los resultados en las pruebas (numpy y `reference/`). |
| **Overflow** | Resultado redondeado mayor en magnitud que el mayor número finito. |
| **RCA** | Ripple-carry adder: sumador en el que el acarreo se propaga de un sumador completo al siguiente. |
| **RNE (roundTiesToEven)** | Redondeo al más cercano; en empate, al de LSB par. Modo por defecto de IEEE 754. |
| **Sesgo (bias)** | Constante que se suma al exponente para almacenarlo sin signo: 2^(e−1) − 1. |
| **Subnormal** | Número con exponente almacenado 0 y fracción ≠ 0; permite el underflow gradual. |
| **Switch-level** | Nivel de simulación en el que los transistores son interruptores controlados por su compuerta. |
| **Transmission gate (TG)** | Par nMOS + pMOS en paralelo con compuertas complementarias; transmite 0 y 1 sin degradación. |
| **ulp** | Unit in the last place: valor del LSB de la mantisa en un exponente dado. |
| **Underflow** | Excepción de resultado diminuto e inexacto. |
| **X / Z** | Valores lógicos desconocido y alta impedancia del simulador. |
