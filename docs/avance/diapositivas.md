---
title: "TranSim754"
subtitle: "Procesador con transistores simulados y aritmética IEEE 754 — Avance"
author: "Arquitectura de Computadoras y Sistemas Operativos (SI421U) · UNI-FIIS · 2026-II"
date: "12 de octubre de 2026"
lang: es
---

## El problema

- El enunciado pide emular **al menos 100 transistores** y, con ellos, sumar, restar,
  multiplicar y dividir números con signo en **IEEE 754**.
- En los cursos, la aritmética de punto flotante se ve como fórmula; rara vez se ve
  cómo resulta de transistores que se abren y se cierran.
- TranSim754 calcula cada operación haciendo conducir o no a transistores nMOS y pMOS
  concretos, y lo compara bit a bit con el estándar.

## Arquitectura por capas

| Capa | Contenido |
|---|---|
| L0 | Simulador switch-level: nodos {0, 1, X, Z} con fuerzas (Bryant, 1984) |
| L1 | Celdas CMOS: INV, NAND2, NOR2, XOR2, MUX2, sumador completo, latch, flip-flop |
| L2 | Bloques: sumadores RCA y CLA, restador, comparador, desplazador, LZC |
| L3 | ALU entera de 32 bits y FPU: FADD, FSUB, FMUL, FDIV |
| L4 | Máquina T754: decodificador, banco de registros, control |
| L5 | CLI `transim`, interfaz gráfica y métricas |

## Del transistor a la celda

- **Inversor:** 1 pMOS + 1 nMOS (2 T).
- **NAND2:** pMOS en paralelo y nMOS en serie (4 T).
- **Sumador completo espejo:** 28 T, colocados directamente.
- **Flip-flop maestro-esclavo:** dos latches de transmission gates (22 T).
- Reglas de la biblioteca: las entradas solo llegan a compuertas y las salidas son
  restauradas. Así cada celda es componible y el motor acelerado puede tabularla.

## Dos motores de simulación

- **switch:** evaluación exacta por componentes conectados por canal; resuelve carga
  retenida, reparto de carga y cortocircuitos.
- **cached:** tabula las celdas combinacionales primitivas y simula el resto con el
  motor exacto.
- Mismo estado y mismos conteos en 300 secuencias de un circuito mixto y en 1 500
  circuitos aleatorios.

## FADD/FSUB en transistores

1. Desempaquetar y clasificar los operandos.
2. Ordenar por magnitud con el comparador.
3. Restar exponentes y alinear el menor (con sticky).
4. Sumar o restar mantisas de p + 4 bits.
5. Normalizar con el LZC y el desplazador.
6. Redondear al par (G, R, S) y empaquetar; elegir entre resultado numérico y
   especial (NaN, ±∞).

## Demostración

```
$ transim calc 1.5 + 2.25 --trace
  a      =  1.5   0x3FC00000
  b      =  2.25  0x40100000
  a + b  =  3.75  0x40700000
  cálculo: transistores (13974 T)
```

- `transim calc 1 / 3` → `0x3EAAAAAB`, inexacto.
- `transim run` y `transim gui`: programas en la máquina T754.

## Verificación

- Cada bloque se compara con un **modelo de referencia**, y este con NumPy.
- Cuatro operaciones × dos formatos: todos los pares borde y 10 000 aleatorios.
- **0 discrepancias** bit a bit, incluidos los cinco flags.
- 377 pruebas automáticas en la integración continua.

## Transistores por unidad

| Unidad (binary32) | Transistores | Profundidad (celdas) |
|---|---:|---:|
| ALU entera de 32 bits | 1 484 | 39 |
| FADD/FSUB | 13 974 | 176 |
| FMUL | 29 966 | 157 |
| FDIV | 40 048 | 852 |
| Banco de 8 registros de 32 bits | 14 230 | — |
| **Máquina T754 completa** | **≈ 100 600** | — |

## Área, velocidad y actividad

| Sumador de 32 bits | Transistores | Profundidad | Actividad α |
|---|---:|---:|---:|
| Ripple-carry | 896 | 32 | 0,39 |
| Carry-lookahead | 3 526 | 19 | 0,31 |

## Transistores en las CPU

- MOSFET: canal controlado por la tensión de compuerta; nMOS y pMOS.
- CMOS: redes complementarias, consumo estático casi nulo.
- Evolución: planar → FinFET (22 nm, 2011) → GAA/nanosheet (3 nm, 2022).
- Ley de Moore frente al escalamiento de Dennard, que terminó hacia 2005.
- TranSim754 modela la conmutación y simplifica tensiones, retardos y fugas.

## Conclusiones

- Las cuatro operaciones IEEE 754 se calculan en transistores simulados y coinciden
  bit a bit con el estándar.
- Cada decisión tiene un costo medible: el CLA gana profundidad desde 16 bits a
  cambio de casi 4 veces más transistores; α aproxima P ≈ α · C · V² · f.
- Siguiente paso: control de la máquina en compuertas y flip-flops, y optimización del
  divisor.

## Referencias

- Bryant, R. E. (1984). A switch-level model and simulator for MOS digital systems.
  *IEEE Transactions on Computers, C-33*(2), 160–177.
- IEEE. (2019). *IEEE standard for floating-point arithmetic* (IEEE Std 754-2019).
- Koren, I. (2002). *Computer arithmetic algorithms* (2.ª ed.). A K Peters.
- Weste, N. H. E., & Harris, D. M. (2011). *CMOS VLSI design* (4.ª ed.).
  Addison-Wesley.
