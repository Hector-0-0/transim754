"""TranSim754: procesador con transistores simulados y aritmética IEEE 754.

Capas del sistema (ver docs/01_arquitectura.md):

- L0 `core`: simulador switch-level (transistores, nodos, motores switch y cached).
- L1 `cells`: celdas CMOS (compuertas, sumador completo, latch, flip-flop).
- L2 `blocks` y `alu`: sumadores, desplazador, LZC, comparador, ALU entera.
- L3 `fpu`: suma, resta, multiplicación y división en punto flotante.
- L4 `cpu`: ISA T754, registros, decodificador, control y máquina.
- L5 `ui`: CLI y GUI.
"""

__version__ = "0.0.1"
