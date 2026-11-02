# TranSim754 (rama de exposición)

Procesador con transistores simulados: una unidad de punto flotante IEEE 754 que suma,
resta, multiplica y divide haciendo conducir transistores nMOS y pMOS, sin usar las
operaciones de Python.

Esta rama tiene solo lo necesario para exponer: el programa y el material de la
exposición. El proyecto completo, con las pruebas y la documentación de diseño, está en
la rama `main`.

## Contenido

| Carpeta o archivo | Qué es |
|---|---|
| `src/transim/` | El programa: transistores, celdas, bloques, FPU e interfaz |
| `exposicion/TranSim754_exposicion_final.html` | La presentación (se abre con el navegador) |
| `exposicion/GUION.txt` | El guion: qué dice cada integrante y qué hace en el programa |
| `exposicion/GUIA_CODIGO.txt` | Qué archivos y líneas explica cada integrante |

## Instalar y abrir

Requiere Python 3.12. Con uv no hace falta instalarlo aparte.

En Linux o macOS, con `make`:

```bash
make install-gui   # una sola vez
make gui           # abre el programa
```

Con uv, en cualquier sistema:

```bash
uv run --extra gui transim gui
```

En Windows, sin `make` ni uv:

```bash
py -3.12 -m venv .venv
.venv\Scripts\pip install -e ".[gui]"
.venv\Scripts\transim gui
```

El programa abre en modo exposición: oscuro, sin menús ni atajos de teclado, con las
pestañas Operación, Recorrido y Transistores. `transim gui --completo` muestra además
los menús, la pestaña Programa y el historial.

En la consola: `make demo` calcula 1.5 + 2.25 con los transistores y muestra los buses
internos.

## Autores

Alcantara Miranda, Sergio Daniel; Ancajima Cruz, Fabrizzio Alessandro; Ayala Zubilete,
Matthews Ronald; Chávez Yauri, Yenny Esther; Flores Sánchez, Héctor David; Huamán Choque,
Jairo Jhosimar. SI421U, FIIS, Universidad Nacional de Ingeniería, 2026-II.
