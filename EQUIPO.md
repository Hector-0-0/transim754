# Equipo

Proyecto del procesador con transistores simulados · SI421U · UNI-FIIS · 2026-II ·
Docente: Carlos Nelson Ramos Montes.

## Integrantes y responsabilidades

| Integrante | GitHub | Responsabilidad | Guía | Issues |
|---|---|---|---|---|
| Héctor David Flores Sánchez | [@Hector-0-0](https://github.com/Hector-0-0) | Líder técnico e integrador: base, núcleo L0, CPU, ensamblador, CLI, asistente, revisión de PR y releases | [cpu](src/transim/cpu/GUIA.md), [assistant](src/transim/assistant/GUIA.md) | #29–#33 |
| Jairo Jhosimar Huaman Choque | [@JairoHCh](https://github.com/JairoHCh) | Celdas L1: AND, OR, XOR, XNOR, MUX2, HA, FA espejo, latch, flip-flop, registro | [cells](src/transim/cells/GUIA.md) | #1–#6 |
| Matthews Ronald Ayala Zubilete | [@devronaldaz](https://github.com/devronaldaz) | Bloques L2 y ALU: RCA, CLA, restador, comparador, multiplexores, barrel shifter, LZC, ALU entera | [blocks](src/transim/blocks/GUIA.md), [alu](src/transim/alu/GUIA.md) | #7–#14 |
| Daniel | *pendiente* | FPU común y FADD/FSUB: codec, casos especiales, redondeo RNE (dueño de `rounding.py`), suma y resta | [fpu addsub](src/transim/fpu/GUIA_ADDSUB.md) | #15–#17 |
| Fabricio | [@Fabrizzio-07](https://github.com/Fabrizzio-07) | FPU FMUL/FDIV: multiplicador en arreglo, divisor no restaurador | [fpu muldiv](src/transim/fpu/GUIA_MULDIV.md) | #18–#21 |
| Yenny | [@yennyestherchavez](https://github.com/yennyestherchavez) | GUI, métricas, investigación "transistores en las CPU", diapositivas e informe APA | [metrics](src/transim/metrics/GUIA.md), [gui](src/transim/ui/gui/GUIA.md), [investigación](docs/investigacion/transistores_en_cpus.md) | #22–#28 |

## Dependencias entre tareas

```mermaid
flowchart LR
    subgraph Jairo
      I1["#1 AND/OR"]; I2["#2 XOR/XNOR"]; I3["#3 MUX2"]; I4["#4 HA/FA"]; I5["#5 latch/DFF"]; I6["#6 REG"]
    end
    subgraph Ronald
      I7["#7 RCA"]; I8["#8 ADDSUB"]; I9["#9 CMP"]; I10["#10 MUX bus"]; I11["#11 shifter"]; I12["#12 LZC"]; I13["#13 ALU"]; I14["#14 CLA"]
    end
    subgraph Daniel
      I15["#15 codec/especiales"]; I16["#16 round_and_pack"]; I17["#17 FADD/FSUB"]
    end
    subgraph Fabricio
      I18["#18 ARRMUL"]; I19["#19 FMUL"]; I20["#20 NRDIV"]; I21["#21 FDIV"]
    end
    subgraph Héctor
      I29["#29 ensamblador"]; I30["#30 máquina"]; I31["#31 CLI"]; I33["#33 avance"]
    end
    I1 & I2 --> I4 --> I7 --> I14
    I2 & I4 --> I8 --> I9 & I13
    I3 --> I10
    I1 & I3 --> I11
    I1 --> I12
    I3 & I5 --> I6
    I1 --> I15
    I8 & I11 --> I16
    I9 & I11 & I12 & I15 & I16 --> I17
    I1 & I4 --> I18 --> I19
    I12 & I15 & I16 --> I19
    I8 --> I20 --> I21
    I15 & I16 --> I21
    I6 & I10 & I13 & I17 --> I30
    I17 & I29 --> I31 --> I33
```

Nadie espera a otro para empezar: cada módulo se desarrolla contra su interfaz (stub) y
se prueba con los modelos de `src/transim/reference/` y con las celdas semilla (INV,
NAND2, NOR2). Cuando la dependencia real llega a `main`, las mismas pruebas validan la
integración.

## Calendario hacia el avance

| Día | Actividad |
|---|---|
| Jue 8 oct | Base del repositorio (F0–F3). |
| **Vie 9 oct** | Base (F4–F6). Cada integrante: clona, configura su identidad git, `make install`, `make test`, lee su GUIA y hace un primer commit pequeño (ver CONTRIBUTING, "Primer día"). Daniel y Fabricio acuerdan el contrato de `round_and_pack`. |
| Sáb 10 oct | Implementación de módulos en paralelo; PR por issue. |
| Dom 11 oct | Integración de FADD/FSUB en transistores, demo, documento de propuesta, diapositivas y ensayo. |
| **Lun 12 oct** | **Presentación del avance**; tag `v0.1.0-avance`. |

Hitos: `v0.1.0-avance` (2026-10-12), `v0.5.0-parcial` (fecha por confirmar),
`v1.0.0-final` (fecha por confirmar).

## Cómo validar cada parte

| Parte | Comando | Debe decir |
|---|---|---|
| Todo (rápido) | `make test` | todas las pruebas en verde o como pendientes (`x`) |
| Celdas | `make validar M=cells` | `RESULTADO: PASS` |
| Bloques | `make validar M=blocks` | `RESULTADO: PASS` |
| ALU | `make validar M=alu` | `RESULTADO: PASS` |
| FADD/FSUB | `make validar M=fpu-addsub COMPLETO=1` | `RESULTADO: PASS` |
| FMUL/FDIV | `make validar M=fpu-muldiv COMPLETO=1` | `RESULTADO: PASS` |
| Métricas | `make validar M=metrics` | `RESULTADO: PASS` |
| GUI | `make validar M=gui` | `RESULTADO: PASS` |
| CPU / CLI / asistente | `make validar M=cpu` · `M=cli` · `M=ai` | `RESULTADO: PASS` |

`python scripts/validar.py --lista` muestra todos los módulos con sus issues.
