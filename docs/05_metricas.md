# 05 · Métricas

Las métricas cuantifican el costo de cada diseño en transistores, actividad y
profundidad lógica (ADR-0013). Todas se calculan de forma automática con
`transim metrics`, que escribe tablas en Markdown y CSV en `docs/metricas/`.

## 1. Definiciones

| Métrica | Definición | Unidad | Módulo |
|---|---|---|---|
| Transistores | número de nMOS + pMOS del netlist aplanado | transistores | `metrics/count.py` |
| Conmutaciones | transiciones 0↔1 de nodos durante una operación | eventos | `metrics/activity.py` |
| Actividad α | conmutaciones / (nodos × operaciones) | adimensional | `metrics/activity.py` |
| Profundidad crítica | celdas L1 en el camino más largo entrada→salida | niveles de celda | `metrics/critical_path.py` |
| Tiempo de simulación | tiempo de reloj de pared por operación | ms | `metrics/report.py` |

## 2. Relación con la potencia

La potencia dinámica de un circuito CMOS se aproxima por

  P_din ≈ α · C · V_DD² · f

La actividad α es lo único de esa expresión que depende de los datos y del diseño
lógico; C, V_DD y f dependen del proceso de fabricación y del reloj. Comparar α entre
dos diseños que resuelven la misma operación (por ejemplo RCA y CLA) indica cuál
conmuta más por operación y, a igualdad de proceso, cuál consumiría más energía
dinámica.

## 3. Profundidad del camino crítico

El simulador es de retardo cero, por lo que la velocidad se estima con la profundidad
lógica: el número de celdas L1 que atraviesa la señal en el camino más largo. En un
RCA de N bits la profundidad crece linealmente con N (la cadena de acarreos); en un CLA
crece de forma logarítmica. La métrica no distingue celdas rápidas de lentas: es una
aproximación de primer orden.

## 4. Conteo esperado de las celdas base

Estos valores corresponden a los diseños de la biblioteca de celdas y se verifican en
las pruebas de L1:

| Celda | Transistores | Estructura |
|---|---|---|
| INV | 2 | 1 pMOS + 1 nMOS |
| NAND2 | 4 | pMOS en paralelo, nMOS en serie |
| NOR2 | 4 | pMOS en serie, nMOS en paralelo |
| AND2 | 6 | NAND2 + INV |
| OR2 | 6 | NOR2 + INV |
| XOR2 | 12 | CMOS complementario con entradas invertidas |
| XNOR2 | 12 | CMOS complementario con entradas invertidas |
| MUX2 | 6 | 2 transmission gates + INV de selección |
| Sumador completo espejo | 28 | etapa de acarreo y de suma espejo con inversores |

## 5. Formato de los reportes

`transim metrics` genera, por lo menos:

- `transistores.md` / `.csv`: módulo, nMOS, pMOS, total;
- `actividad.md` / `.csv`: operación, formato, conmutaciones promedio, α;
- `camino_critico.md` / `.csv`: bloque, ancho, profundidad;
- `comparacion_sumadores.md` / `.csv`: RCA frente a CLA para N = 8, 16, 24, 32.

Las tablas del informe y de las diapositivas se toman directamente de estos archivos.
