# ADR-0010 · CPU mínima con ISA propia T754

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

Las operaciones aritméticas cobran sentido dentro de un procesador: instrucciones que
se leen de memoria, se decodifican, leen registros, ejecutan y escriben resultados. Una
ISA existente (RISC-V, MIPS) obligaría a implementar muchas instrucciones ajenas al
objetivo. Se define una ISA mínima, completa para el propósito del curso.

## Decisión

1. **Estado arquitectónico:** 8 registros **F0–F7** de 32 bits (flip-flops D
   maestro-esclavo con transmission gates), el registro de estado **FSR** (ADR-0004) y
   el contador de programa **PC** (índice de palabra).
2. **Formato de instrucción** (palabra de 32 bits):

   | Bits | 31–24 | 23–21 | 20–18 | 17–15 | 14–0 |
   |---|---|---|---|---|---|
   | Campo | opcode | rd | rs1 | rs2 | reservado (0) |

   `LI` ocupa **2 palabras**: la instrucción y, a continuación, el literal binary32.
3. **Opcodes:**

   | Opcode | Mnemónico | Semántica |
   |---|---|---|
   | 0x00 | NOP | sin efecto |
   | 0x01 | LI rd, lit | rd ← lit (segunda palabra) |
   | 0x02 | MOV rd, rs1 | rd ← rs1 |
   | 0x10 | FADD rd, rs1, rs2 | rd ← rs1 + rs2 (IEEE 754) ; FSR.flags \|= flags |
   | 0x11 | FSUB rd, rs1, rs2 | rd ← rs1 − rs2 |
   | 0x12 | FMUL rd, rs1, rs2 | rd ← rs1 × rs2 |
   | 0x13 | FDIV rd, rs1, rs2 | rd ← rs1 / rs2 |
   | 0x20 | ADD rd, rs1, rs2 | rd ← rs1 + rs2 (entero C2) ; FSR.CVZN ← flags |
   | 0x21 | SUB rd, rs1, rs2 | rd ← rs1 − rs2 (entero C2) |
   | 0x30 | OUT rs1 | envía rs1 a la salida |
   | 0x31 | CLRF | FSR ← 0 |
   | 0xFF | HALT | detiene la máquina |

4. **Ciclo de instrucción:** FETCH (IR ← MEM[PC]) → DECODE (el decodificador de
   compuertas genera las señales de control y los índices de registro) → EXECUTE (ALU o
   FPU; en `LI` se lee MEM[PC + 1]) → WRITEBACK (escritura del registro destino en el
   flanco de reloj, actualización del FSR y PC ← PC + 1, o + 2 en `LI`).
5. **Instrucción ilegal:** un opcode no definido o un campo no usado distinto de cero
   detiene la máquina con `IllegalInstructionError`, indicando el PC.
6. **Ensamblador** de texto (`.t754`) a binario:
   - una instrucción por línea; comentarios con `;` o `#`; mayúsculas o minúsculas;
   - el literal de `LI` acepta decimal (`1.5`, `-2e-3`, `inf`, `nan`) o hexadecimal
     (`0x3FC00000`, interpretado como bits);
   - el binario es una secuencia de palabras de 32 bits en **big-endian**;
   - cada error informa número de línea, columna y causa.

## Consecuencias

- Los registros F guardan patrones de 32 bits sin tipo: las instrucciones F los
  interpretan como binary32 y ADD/SUB como enteros en C2.
- Sin saltos ni memoria de datos, los programas son lineales; basta para demostrar las
  cuatro operaciones, la evaluación de polinomios por Horner y los casos especiales.
- Los opcodes libres permiten extender la ISA sin cambiar el formato.

## Alternativas descartadas

- **Subconjunto de RISC-V (RV32F).** Exigiría saltos, cargas y almacenamientos, CSR y
  un formato de inmediatos más complejo, sin beneficio para el objetivo aritmético.
- **Literal de LI dentro de la propia palabra.** No caben 32 bits de literal en una
  instrucción de 32 bits; se necesitarían dos instrucciones (parte alta y baja).
- **Literal en little-endian.** Igualmente válido; big-endian se elige porque el volcado
  hexadecimal se lee en el mismo orden que la tabla de campos.
