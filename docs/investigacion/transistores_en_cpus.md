# Funcionamiento de los transistores en las CPU

> **Estado:** esqueleto. Responsable de la redacción: Yenny. Cada sección indica su
> contenido mínimo y las fuentes recomendadas. Extensión objetivo: 8 a 12 páginas en
> formato APA 7.ª edición.

## Pautas de redacción y fuentes

- Usar fuentes académicas o técnicas primarias: libros de texto de diseño VLSI,
  artículos de IEEE, documentación pública de fabricantes (Intel, TSMC, Samsung,
  IBM Research) y el *International Roadmap for Devices and Systems* (IRDS) de IEEE.
- Evitar blogs sin autor ni fecha y sitios de divulgación sin referencias.
- Toda cifra (tamaño de nodo, densidad, tensión, número de transistores de un chip)
  lleva cita con año: estos valores cambian rápidamente.
- Distinguir el **nombre comercial** de un nodo ("3 nm") de las dimensiones físicas
  reales del transistor; desde hace años no coinciden.
- Relacionar cada sección con el simulador: qué fenómeno modela TranSim754 y cuál
  simplifica (ADR-0007).

## 1. El transistor MOSFET

Contenido mínimo: estructura (compuerta, óxido, canal, fuente, drenador, sustrato);
regiones de operación (corte, lineal, saturación); tensión umbral V_t; nMOS frente a
pMOS y movilidad de electrones y huecos.

Fuentes sugeridas: Weste y Harris (2011), cap. 2; Rabaey et al. (2003), cap. 3;
Sedra y Smith, *Microelectronic circuits*.

## 2. Del transistor al interruptor: lógica CMOS

Contenido mínimo: inversor CMOS y su curva de transferencia; redes pull-up y pull-down
complementarias; NAND y NOR; por qué NAND se prefiere a NOR (movilidad); transmission
gates; consumo estático casi nulo. Vincular con el modelo switch-level (Bryant, 1984).

## 3. De las compuertas a la CPU

Contenido mínimo: sumadores, registros (latches y flip-flops), ALU y FPU como
composición jerárquica de celdas; número de transistores de procesadores de referencia
a lo largo del tiempo (Intel 4004 → procesadores actuales), con fuente.

## 4. Evolución de la tecnología del transistor

Contenido mínimo:

1. **MOSFET planar** y el escalamiento de Dennard (Dennard et al., 1974).
2. **Fin del escalamiento de Dennard** (~2005): por qué la tensión dejó de bajar y
   apareció el límite de potencia.
3. **FinFET** (tri-gate, Intel 22 nm, 2011): control electrostático del canal en tres
   caras.
4. **GAA / nanosheet** (Samsung 3 nm, 2022; Intel 20A/18A; TSMC N2): compuerta que
   rodea el canal.
5. Perspectivas: CFET, transistores apilados, materiales 2D (citar IRDS).

## 5. Escalamiento y ley de Moore

Contenido mínimo: enunciado original de Moore (1965) y su revisión (1975); diferencia
entre ley de Moore y escalamiento de Dennard; estado actual con fuente reciente.

## 6. Potencia

Contenido mínimo: potencia dinámica P ≈ α·C·V²·f y su relación con la métrica de
actividad del simulador (ADR-0013); potencia estática y corrientes de fuga; *dark
silicon*; técnicas de reducción (clock gating, DVFS, power gating).

## 7. Relación con TranSim754

Contenido mínimo: tabla de "fenómeno real → cómo lo modela el simulador → qué
simplifica" (umbral V_t, capacitancias, retardos, reparto de carga, fugas).

## Referencias (iniciales; completar)

Bryant, R. E. (1984). A switch-level model and simulator for MOS digital systems.
*IEEE Transactions on Computers, C-33*(2), 160–177. https://doi.org/10.1109/TC.1984.1676408

Dennard, R. H., Gaensslen, F. H., Yu, H.-N., Rideout, V. L., Bassous, E., & LeBlanc,
A. R. (1974). Design of ion-implanted MOSFET's with very small physical dimensions.
*IEEE Journal of Solid-State Circuits, 9*(5), 256–268. https://doi.org/10.1109/JSSC.1974.1050511

Moore, G. E. (1965). Cramming more components onto integrated circuits. *Electronics,
38*(8), 114–117.

Rabaey, J. M., Chandrakasan, A., & Nikolić, B. (2003). *Digital integrated circuits:
A design perspective* (2.ª ed.). Pearson.

Weste, N. H. E., & Harris, D. M. (2011). *CMOS VLSI design: A circuits and systems
perspective* (4.ª ed.). Addison-Wesley.
