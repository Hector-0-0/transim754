# 01 · Arquitectura de TranSim754

## 1. Visión por capas

El sistema se organiza en seis capas. Cada capa solo usa las capas inferiores, y cada
una tiene un **modelo de referencia** en Python puro (`src/transim/reference/`) que
define su comportamiento esperado y sirve de oráculo en las pruebas.

```mermaid
flowchart BT
    L0["L0 · core<br/>Transistor, Node, Netlist<br/>motores switch y cached"]
    L1["L1 · cells<br/>INV, NAND, NOR, AND, OR, XOR, XNOR,<br/>MUX2, HA, FA espejo, latch, flip-flop"]
    L2["L2 · blocks + alu<br/>RCA/CLA, restador, barrel shifter,<br/>LZC, comparador, ALU entera"]
    L3["L3 · fpu<br/>codec, clasificación, redondeo,<br/>FADD/FSUB, FMUL, FDIV"]
    L4["L4 · cpu<br/>registros F0–F7, FSR, decodificador,<br/>control, máquina, ensamblador"]
    L5["L5 · ui<br/>CLI transim y GUI PySide6"]
    M["metrics<br/>transistores, α, camino crítico"]
    A["assistant<br/>explica trazas; nunca calcula"]
    L0 --> L1 --> L2 --> L3 --> L4 --> L5
    M -.mide.-> L1 & L2 & L3 & L4
    A -.usa trazas de.-> L4
    L5 --> M & A
```

| Capa | Paquete | Unidad primitiva | Construida con |
|---|---|---|---|
| L0 | `core` | transistor nMOS/pMOS | Python (simulador) |
| L1 | `cells` | celda CMOS | transistores |
| L2 | `blocks`, `alu` | bloque aritmético | celdas L1 |
| L3 | `fpu` | unidad de punto flotante | bloques L2 y celdas L1 |
| L4 | `cpu` | procesador | L3, L2, flip-flops; control según ADR-0006 |
| L5 | `ui` | interfaz | — |

## 2. El netlist jerárquico

Todo circuito es un `Netlist`: una lista de transistores y nodos con **puertos con
nombre** (entradas y salidas) y **buses** (listas ordenadas de nodos, con el bit 0 como
LSB). Un netlist puede **instanciar** otro como subcircuito, conectando sus puertos a
nodos propios. Al simular, la jerarquía se aplana a transistores, pero se conserva la
pertenencia de cada transistor a su instancia para contar transistores por módulo y
calcular la profundidad en niveles de celda.

```mermaid
flowchart LR
    subgraph FA["Sumador completo (28 T)"]
      direction LR
      a((a)) & b((b)) & cin((cin)) --> carry["etapa de acarreo espejo"] --> cout((cout))
      a & b & cin & carry --> sum["etapa de suma espejo"] --> s((s))
    end
    subgraph RCA4["RCA de 4 bits"]
      FA0[FA0] --> FA1[FA1] --> FA2[FA2] --> FA3[FA3]
    end
```

## 3. Interacción de los transistores en una compuerta

En CMOS estático cada compuerta tiene una red **pull-up** de pMOS hacia VDD y una red
**pull-down** de nMOS hacia GND, complementarias: para cualquier combinación de entradas
exactamente una de las dos conduce. Ejemplo, NAND2 (4 transistores):

```mermaid
flowchart TB
    VDD[VDD] --- P1["pMOS A"] & P2["pMOS B"]
    P1 & P2 --- Y((Y))
    Y --- N1["nMOS A"]
    N1 --- n1((n1))
    n1 --- N2["nMOS B"]
    N2 --- GND[GND]
```

- A = B = 1: ambos nMOS conducen (Y conectado a GND) y ambos pMOS están abiertos → Y = 0.
- Cualquier entrada en 0: al menos un pMOS conduce (Y conectado a VDD) y la pila nMOS
  está cortada → Y = 1.
- El nodo interno `n1` queda aislado cuando B = 0 y A = 0: retiene su carga anterior.
  Este es el fenómeno que obliga al motor `cached` a incluir el estado interno en su
  tabla (ADR-0008).

## 4. Recorrido completo de una instrucción FADD

Programa: `FADD F3, F1, F2` con F1 = 1.5 (`0x3FC00000`) y F2 = 2.25 (`0x40100000`).

```mermaid
sequenceDiagram
    participant CTRL as Control (FSM)
    participant MEM as Memoria de programa
    participant DEC as Decodificador (compuertas)
    participant RF as Banco F0–F7 (flip-flops)
    participant FPU as FPU (transistores)
    participant FSR as FSR
    CTRL->>MEM: FETCH: IR ← MEM[PC]
    MEM-->>CTRL: 0x10 | rd=3 | rs1=1 | rs2=2
    CTRL->>DEC: DECODE: IR[31:15]
    DEC-->>CTRL: op=FADD, selección de lectura 1 y 2, escritura en F3
    CTRL->>RF: lee F1 y F2 (MUX de lectura)
    RF-->>FPU: a = 0x3FC00000, b = 0x40100000
    CTRL->>FPU: EXECUTE (evaluación de transistores hasta estabilizar)
    FPU-->>CTRL: r = 0x40700000, flags = 00000
    CTRL->>RF: WRITEBACK: flanco de reloj, F3 ← r
    CTRL->>FSR: FSR.flags ← FSR.flags OR flags
    CTRL->>CTRL: PC ← PC + 1
```

Dentro de la FPU, la operación atraviesa estas etapas, todas construidas con
transistores (ver el cálculo bit a bit en `docs/03_ieee754.md`, ejemplo 2):

```mermaid
flowchart LR
    U["Desempaquetar<br/>(codec)"] --> C["Clasificar<br/>(special)"]
    U --> X["Restar exponentes<br/>(restador L2)"]
    X --> W["Intercambiar si |b|>|a|<br/>(comparador + MUX2)"]
    W --> AL["Alinear menor<br/>(barrel shifter → G,R,S)"]
    AL --> AD["Sumar/restar mantisas<br/>(sumador p+3 bits)"]
    AD --> N["Normalizar<br/>(LZC + desplazador)"]
    N --> R["Redondear RNE<br/>(rounding: incrementador)"]
    R --> P["Empaquetar + flags"]
    C -->|"resultado especial"| P
```

| Etapa | Bloque | Valores en el ejemplo |
|---|---|---|
| Desempaquetar | `fpu.codec` | a: s=0, e=0, m=1.1000…; b: s=0, e=1, m=1.0010… |
| Clasificar | `fpu.special` | ambos normales → camino numérico |
| Restar exponentes | `blocks.subtractor` | 1 − 0 = 1 |
| Intercambiar | `blocks.comparator` + `blocks.mux` | b es el mayor → no se intercambia el orden lógico |
| Alinear | `blocks.shifter` (derecha, con sticky) | m_a → 0.1100…, G=R=S=0 |
| Sumar | `blocks.adders` | 1.0010… + 0.1100… = 1.1110… |
| Normalizar | `blocks.lzc` + `blocks.shifter` | ya normalizado |
| Redondear | `fpu.rounding` | GRS = 000 → sin incremento, exacto |
| Empaquetar | `fpu.codec` | `0x40700000`, flags 00000 |

## 5. Dependencias entre módulos y trabajo en paralelo

```mermaid
flowchart LR
    core --> cells --> blocks --> alu
    blocks --> fpu_addsub["fpu suma/resta"]
    blocks --> fpu_muldiv["fpu mul/div"]
    fpu_common["fpu común: format, codec, special, rounding"] --> fpu_addsub & fpu_muldiv
    alu & fpu_addsub & fpu_muldiv --> cpu --> ui
    cells & blocks --> metrics --> ui
    reference -.especifica.-> cells & blocks & alu & fpu_common & fpu_addsub & fpu_muldiv & cpu
```

Cada módulo de alto nivel puede desarrollarse antes de que existan sus dependencias en
transistores, porque su interfaz y su comportamiento esperado ya están fijados por los
stubs y por `reference/`. La integración final reemplaza el modelo de referencia por la
implementación en transistores, y las mismas pruebas validan ambos.
