# Registros de decisiones de arquitectura (ADR)

Cada ADR documenta una decisión firme del proyecto con el formato de Nygard (2011):
**contexto**, **decisión**, **consecuencias** y **alternativas descartadas**. Una
decisión aceptada solo se modifica mediante un ADR nuevo que la reemplace; el ADR
anterior se conserva y se marca como "Reemplazada por ADR-XXXX".

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-formato-binary32-parametrizado.md) | Formato binary32 parametrizado con `FloatFormat` | Aceptada |
| [0002](0002-redondeo-ties-to-even.md) | Redondeo roundTiesToEven con guard, round y sticky | Aceptada |
| [0003](0003-clases-de-valores.md) | Normales, subnormales, ±0, ±∞ y NaN canónico | Aceptada |
| [0004](0004-flags-y-registro-fsr.md) | Cinco flags acumulativos en el registro FSR | Aceptada |
| [0005](0005-operaciones.md) | FADD, FSUB, FMUL, FDIV y ALU entera de 32 bits | Aceptada |
| [0006](0006-nivel-de-abstraccion.md) | Datapath desde transistores; control por niveles | Aceptada |
| [0007](0007-simulador-switch-level.md) | Simulador switch-level de cuatro valores y tres fuerzas | Aceptada |
| [0008](0008-dos-motores-equivalentes.md) | Motores `switch` y `cached` con equivalencia probada | Aceptada |
| [0009](0009-algoritmos-de-hardware.md) | Algoritmos de hardware de cada bloque | Aceptada |
| [0010](0010-cpu-e-isa-t754.md) | CPU mínima con ISA propia T754 | Aceptada |
| [0011](0011-stack-tecnologico.md) | Python 3.12 y herramientas de desarrollo | Aceptada |
| [0012](0012-ia-localizada.md) | Asistente de IA localizado que nunca calcula | Aceptada |
| [0013](0013-metricas.md) | Métricas de transistores, actividad y camino crítico | Aceptada |

## Referencia

Nygard, M. (2011, 15 de noviembre). *Documenting architecture decisions*. Cognitect.
https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
