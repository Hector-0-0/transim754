---
title: "TranSim754: procesador con transistores simulados y aritmética IEEE 754"
subtitle: "Propuesta de implementación — Avance"
course: "Arquitectura de Computadoras y Sistemas Operativos (SI421U)"
institution: "Universidad Nacional de Ingeniería, Facultad de Ingeniería Industrial y de Sistemas"
instructor: "Carlos Nelson Ramos Montes"
date: "12 de octubre de 2026"
authors:
  - "Héctor David Flores Sánchez"
  - "Daniel"
  - "Jairo"
  - "Ronald"
  - "Fabricio"
  - "Yenny"
---

# TranSim754: procesador con transistores simulados y aritmética IEEE 754

**Propuesta de implementación — Avance**

Universidad Nacional de Ingeniería · Facultad de Ingeniería Industrial y de Sistemas
Arquitectura de Computadoras y Sistemas Operativos (SI421U) · Periodo 2026-II
Docente: Carlos Nelson Ramos Montes

Integrantes: Héctor David Flores Sánchez (líder técnico), Daniel, Jairo, Ronald,
Fabricio y Yenny.

Lima, 12 de octubre de 2026

---

## Resumen

Se propone TranSim754, un software que emula un procesador cuyas operaciones
aritméticas se realizan sobre transistores simulados. El núcleo es un simulador
*switch-level* en el que cada transistor nMOS o pMOS se modela como un interruptor
controlado por su compuerta. Sobre él se construyen, por composición jerárquica,
compuertas CMOS, sumadores, desplazadores, una ALU entera de 32 bits y una unidad de
punto flotante que suma, resta, multiplica y divide números con signo en el formato
IEEE 754-2019 binary32, con redondeo al par más cercano, números subnormales, valores
especiales y los cinco indicadores de excepción de la norma. Una CPU mínima con un
conjunto de instrucciones propio (T754) ejecuta programas sobre esa unidad. El sistema
supera en varios órdenes de magnitud el mínimo de 100 transistores del enunciado y
mide su costo en transistores, actividad de conmutación y profundidad lógica. La
corrección se verifica bit a bit contra la aritmética de punto flotante del hardware
mediante numpy.

**Palabras clave:** IEEE 754, CMOS, simulación switch-level, unidad de punto
flotante, arquitectura de computadoras.

## 1. Planteamiento del problema

Las unidades aritméticas de una CPU suelen estudiarse en dos niveles desconectados: el
de la representación numérica (formatos, redondeo, excepciones) y el de los circuitos
(transistores, compuertas). Rara vez se observa cómo una suma en punto flotante
resulta, literalmente, de miles de transistores que se abren y se cierran. El
enunciado del curso pide cerrar esa brecha: desarrollar un software que emule al menos
100 transistores y que, usando esos transistores, realice sumas, restas,
multiplicaciones y divisiones en IEEE 754 para cantidades con signo, e investigar el
funcionamiento de los transistores en las CPU.

La dificultad técnica es doble. Primero, la norma IEEE 754 exige un comportamiento
exacto en casos que una implementación ingenua ignora: empates en el redondeo,
números subnormales, ceros con signo, infinitos, NaN y la señalización de excepciones.
Segundo, simular decenas de miles de transistores en un lenguaje interpretado exige un
modelo de simulación adecuado y estrategias de aceleración que no comprometan la
fidelidad.

## 2. Objetivos

### 2.1 Objetivo general

Desarrollar un simulador de procesador en el que las operaciones de suma, resta,
multiplicación y división en IEEE 754 binary32 se calculen mediante la evaluación de
transistores nMOS y pMOS simulados, con resultados idénticos bit a bit a los de una
implementación de referencia.

### 2.2 Objetivos específicos

1. Implementar un simulador switch-level de cuatro valores lógicos y tres fuerzas que
   modele el transistor MOS como interruptor, con detección de cortocircuitos,
   oscilaciones y almacenamiento de carga.
2. Construir una biblioteca de celdas CMOS (compuertas, multiplexor, sumador completo,
   latch y flip-flop) verificada exhaustivamente contra su tabla de verdad.
3. Construir los bloques aritméticos (sumadores RCA y CLA, restador, desplazador,
   contador de ceros, comparador, multiplicador y divisor en arreglo) y una ALU entera
   de 32 bits en complemento a 2.
4. Construir una FPU binary32 con redondeo roundTiesToEven, subnormales, valores
   especiales y los cinco flags de IEEE 754-2019, verificada contra numpy.
5. Integrar una CPU mínima con conjunto de instrucciones propio, banco de registros de
   flip-flops y ensamblador.
6. Medir y comparar transistores, actividad de conmutación y profundidad lógica de
   distintos diseños.
7. Documentar el funcionamiento de los transistores en las CPU actuales, desde el
   MOSFET planar hasta las arquitecturas FinFET y GAA.

## 3. Alcance

| Incluido | Excluido |
|---|---|
| Formato binary32 (oficial) y binary16 (pruebas) | binary64 y formatos decimales |
| FADD, FSUB, FMUL, FDIV | raíz cuadrada, FMA, conversiones |
| Redondeo roundTiesToEven | los otros cuatro modos de redondeo |
| Normales, subnormales, ±0, ±∞, NaN | carga útil de NaN (se usa un NaN canónico) |
| Flags acumulativos sin trampas | manejo de excepciones con trampas |
| ALU entera ADD/SUB con C, V, Z, N | operaciones lógicas y desplazamientos enteros |
| CPU sin saltos, ISA propia de 12 instrucciones | memoria de datos, saltos, interrupciones |
| Modelo lógico de transistores (switch-level) | modelo eléctrico (tensiones, corrientes, retardos) |

## 4. Decisiones de diseño

Cada decisión está documentada en un registro de decisión de arquitectura (ADR) con su
contexto, consecuencias y alternativas descartadas.

| N.° | Decisión | Justificación principal |
|---|---|---|
| 1 | Formato binary32 parametrizado (binary16 para pruebas) | formato estándar de precisión simple; binary16 permite pruebas exhaustivas |
| 2 | Redondeo roundTiesToEven con bits G, R, S | modo por defecto de la norma; tres bits bastan |
| 3 | Subnormales, ±0, ±∞ y NaN canónico | comportamiento obligatorio de la norma |
| 4 | Cinco flags acumulativos; tininess tras redondeo | manejo por defecto de §7; misma opción que x86 |
| 5 | FADD, FSUB, FMUL, FDIV y ALU entera de 32 bits | requisito del enunciado; la FPU reutiliza la aritmética entera |
| 6 | Datapath desde transistores; control por niveles | el cálculo ocurre en transistores; la secuenciación se declara aparte |
| 7 | Simulador switch-level de 4 valores y 3 fuerzas | modelo de Bryant (1984): fiel en lo lógico y eficiente |
| 8 | Motores `switch` y `cached` con equivalencia probada | velocidad sin perder fidelidad |
| 9 | RCA → CLA, barrel shifter, multiplicador y divisor en arreglo | diseños verificables a tiempo y comparables |
| 10 | CPU mínima con ISA T754 | contexto de ejecución sin instrucciones ajenas al objetivo |
| 11 | Python 3.12, pytest, hypothesis, numpy como oráculo | stack común al equipo, verificación automática |
| 12 | Asistente de IA opcional que nunca calcula | valor didáctico sin comprometer la corrección |
| 13 | Métricas automáticas de transistores, α y profundidad | comparaciones reproducibles |

## 5. Arquitectura

El sistema se organiza en seis capas; cada una usa solo las inferiores.

```
 L5  Interfaz        CLI "transim" · GUI de escritorio
 L4  CPU             ISA T754 · banco F0–F7 · FSR · decodificador · control
 L3  FPU             codec · clasificación · redondeo · FADD/FSUB · FMUL · FDIV
 L2  Bloques / ALU   sumadores RCA/CLA · restador · barrel shifter · LZC · comparador
 L1  Celdas CMOS     INV · NAND · NOR · XOR · MUX2 · sumador completo · latch · flip-flop
 L0  Núcleo          transistor nMOS/pMOS · nodos · netlist · motores switch y cached
```

Una instrucción `FADD F3, F1, F2` recorre el ciclo FETCH → DECODE → EXECUTE →
WRITEBACK. En EXECUTE, la FPU desempaqueta los operandos, compara y resta los
exponentes, alinea la mantisa menor con un desplazador que acumula los bits perdidos
en el bit *sticky*, suma las mantisas, normaliza con un contador de ceros a la
izquierda, redondea y empaqueta el resultado junto con sus flags. Cada una de esas
etapas es un circuito de transistores.

## 6. Interacción de los transistores

En lógica CMOS estática cada compuerta combina una red de pMOS conectada a la
alimentación (pull-up) y una red de nMOS conectada a tierra (pull-down). Las redes son
complementarias: para cualquier combinación de entradas conduce exactamente una, por lo
que la salida queda siempre conectada a un nivel lógico definido y en reposo no circula
corriente entre alimentación y tierra (Weste y Harris, 2011).

```
        VDD ────┬──────────────┬────
                │              │
         A ──o[pMOS]    B ──o[pMOS]
                │              │
                └──────┬───────┘
                       ├──────────── Y = ¬(A·B)
                A ──[nMOS]
                       │ n1
                B ──[nMOS]
                       │
                      GND
```

| A | B | pMOS que conducen | Pila de nMOS en serie | Y |
|---|---|---|---|---|
| 0 | 0 | ambos | cortada | 1 |
| 0 | 1 | el de A | cortada | 1 |
| 1 | 0 | el de B | cortada | 1 |
| 1 | 1 | ninguno | conduce | 0 |

A partir de esta idea se construyen celdas más complejas. Un multiplexor de dos
entradas usa dos *transmission gates* (un nMOS y un pMOS en paralelo) que conectan una
u otra entrada a la salida según la señal de selección. Un sumador completo en
configuración espejo usa 28 transistores. Un flip-flop maestro-esclavo usa dos latches
de transmission gates con relojes complementarios: mientras uno captura, el otro
retiene. El simulador modela además el almacenamiento de carga: un nodo aislado
conserva su valor, que es el principio de la memoria dinámica.

**Estimación del tamaño del procesador** (orden de magnitud; las cifras definitivas
las genera la herramienta de métricas del proyecto):

| Unidad | Composición dominante | Transistores (estimado) |
|---|---|---|
| ALU entera de 32 bits (RCA) | 32 sumadores completos + inversión condicional | ≈ 1 500 |
| FADD/FSUB | restador de exponentes, 2 desplazadores, sumador de 28 bits, LZC, redondeo | ≈ 7 000 |
| FMUL | 576 compuertas AND + ≈ 550 sumadores completos | ≈ 20 000 |
| FDIV | ≈ 26 filas de ≈ 26 celdas suma/resta controlada | ≈ 27 000 |
| Banco de registros | 256 flip-flops + multiplexores de lectura | ≈ 8 000 |
| **Total** | | **≈ 60 000** |

## 7. Metodología

1. **Especificación ejecutable.** Antes de construir cada bloque en transistores existe
   un modelo de comportamiento en Python que define el resultado esperado. La FPU de
   referencia se valida contra numpy en binary32 y binary16.
2. **Pruebas primero.** Las pruebas de cada módulo se escriben antes que su
   implementación, a partir de la norma y de los ADR.
3. **Verificación en tres niveles:** tablas de verdad exhaustivas para las celdas;
   pruebas aleatorias y de casos borde para los bloques; comparación bit a bit contra
   numpy para la FPU (incluidos los flags).
4. **Dos motores equivalentes.** El motor exacto evalúa transistor por transistor; el
   motor acelerado reutiliza el comportamiento extraído de cada celda. Una prueba
   obligatoria demuestra que producen los mismos resultados y los mismos conteos.
5. **Integración continua.** Cada cambio pasa por análisis de estilo, verificación de
   tipos y las pruebas automáticas antes de integrarse.

## 8. Organización del equipo

| Integrante | Responsabilidad |
|---|---|
| Héctor David Flores Sánchez | Líder técnico e integración: núcleo del simulador, CPU, ensamblador, CLI, asistente, revisión |
| Jairo | Celdas CMOS (L1): compuertas, multiplexor, sumadores, latch, flip-flop, registro |
| Ronald | Bloques aritméticos (L2) y ALU entera |
| Daniel | FPU: codificación, casos especiales, redondeo, suma y resta |
| Fabricio | FPU: multiplicación y división |
| Yenny | Interfaz gráfica, métricas, investigación sobre transistores en CPU, informe y diapositivas |

## 9. Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Simulación lenta de la FPU completa en Python | Media | Alto | motor `cached` con equivalencia probada; binary16 para iterar |
| Errores sutiles de redondeo y subnormales | Alta | Alto | modelo de referencia validado contra numpy; casos borde dirigidos |
| Integración tardía entre módulos | Media | Alto | interfaces fijadas desde el inicio; integración continua |
| Divisor combinacional demasiado grande | Media | Medio | binary16 para pruebas; métricas para dimensionar |
| Plazo corto hasta el avance | Alta | Medio | alcance del avance limitado a FADD/FSUB en transistores |

## 10. Cronograma

| Fecha | Actividad | Entregable |
|---|---|---|
| Jue 8 oct | Andamiaje, documentación de diseño, núcleo del simulador | repositorio base, ADR |
| Vie 9 oct | Celdas semilla, motor acelerado, interfaces, pruebas, guías | `v0.0.1-base` |
| Sáb 10 oct | Implementación de módulos en paralelo | celdas, bloques, FPU en curso |
| Dom 11 oct | Integración de FADD/FSUB en transistores, demo, documento y ensayo | demo funcional |
| **Lun 12 oct** | **Presentación del avance** | **`v0.1.0-avance`** |
| Después del parcial | FMUL, FDIV, CPU completa, CLA, GUI, investigación | `v0.5.0-parcial` |
| Exposición final | Control en compuertas, métricas finales, ejecutable | `v1.0.0-final` |

## 11. Estado del avance

*Sección que se completa con la evidencia de la demostración: operaciones disponibles
en transistores, conteo de transistores medido y resultado de las pruebas contra el
oráculo.*

## Referencias

Bryant, R. E. (1984). A switch-level model and simulator for MOS digital systems.
*IEEE Transactions on Computers, C-33*(2), 160–177. https://doi.org/10.1109/TC.1984.1676408

Goldberg, D. (1991). What every computer scientist should know about floating-point
arithmetic. *ACM Computing Surveys, 23*(1), 5–48. https://doi.org/10.1145/103162.103163

IEEE. (2019). *IEEE standard for floating-point arithmetic* (IEEE Std 754-2019).
https://doi.org/10.1109/IEEESTD.2019.8766229

Koren, I. (2002). *Computer arithmetic algorithms* (2.ª ed.). A K Peters.

Muller, J.-M., Brunie, N., de Dinechin, F., Jeannerod, C.-P., Joldes, M., Lefèvre, V.,
Melquiond, G., Revol, N., & Torres, S. (2018). *Handbook of floating-point arithmetic*
(2.ª ed.). Birkhäuser. https://doi.org/10.1007/978-3-319-76526-6

Patterson, D. A., & Hennessy, J. L. (2021). *Computer organization and design RISC-V
edition: The hardware/software interface* (2.ª ed.). Morgan Kaufmann.

Rabaey, J. M., Chandrakasan, A., & Nikolić, B. (2003). *Digital integrated circuits:
A design perspective* (2.ª ed.). Pearson.

Weste, N. H. E., & Harris, D. M. (2011). *CMOS VLSI design: A circuits and systems
perspective* (4.ª ed.). Addison-Wesley.
