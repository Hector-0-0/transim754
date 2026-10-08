"""Modelos de comportamiento en Python puro: especificación ejecutable de cada bloque.

- :mod:`transim.reference.cells`: celdas L1.
- :mod:`transim.reference.blocks`: bloques L2 (sumadores, desplazadores, LZC…).
- :mod:`transim.reference.integer`: ALU entera con C, V, Z, N.
- :mod:`transim.reference.fpu`: FPU IEEE 754 exacta y parametrizada (validada contra numpy).
- :mod:`transim.reference.machine`: simulador de la ISA T754.

Estos modelos nunca producen los resultados que muestra la máquina: solo definen el
comportamiento esperado y sirven de oráculo en las pruebas (ADR-0006).
"""
