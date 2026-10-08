# Material de apoyo · Celdas CMOS L1

> USO INTERNO. No se presenta ni se exporta (ver `interno/README.md`).
> Responsable: Jairo · Guía: `src/transim/cells/GUIA.md` · Issues: #1–#6

## A. Desarrollo

Copia el bloque en tu propia cuenta y trabaja en tu rama `feat/<ámbito>-<descripcion>`.

```text
Proyecto TranSim754 (curso SI421U, UNI-FIIS, 2026-II): software en Python 3.12 que emula
un procesador cuyas operaciones (suma, resta, multiplicación y división en IEEE 754
binary32) se calculan con transistores nMOS/pMOS simulados en un simulador switch-level.
Repositorio: https://github.com/Hector-0-0/transim754 (rama principal `main`).

Soy Jairo, responsable de: Celdas CMOS L1. Antes de escribir código, lee y resume en
5 líneas lo que entendiste de estos archivos (te los pego si no tienes acceso al repo):
   - `src/transim/cells/GUIA.md`
   - `docs/02_simulador_switch_level.md`
   - `docs/adr/0008-dos-motores-equivalentes.md` (sección Precisiones)
   - `src/transim/cells/combinational.py` y sequential.py (incluidas INV, NAND2, NOR2 ya hechas como ejemplo)
   - `tests/cells/*.py`
   - `src/transim/core/netlist.py` (API: input, output, node, nmos, pmos, transmission_gate, instantiate)

Decisiones del proyecto que aplican: ADR-0006, ADR-0007, ADR-0008 (están en docs/adr/).

Tarea:
Implementar las celdas de los issues #1 a #6 en el orden de la GUIA: AND2/OR2, XOR2/XNOR2
de 12 T, MUX2 restaurador de 12 T, HA y FA espejo de 28 T (celda primitiva, sin
sub-instancias), latch D y flip-flop maestro-esclavo con transmission gates, y registro de N
bits con habilitación.

Reglas que verifican las pruebas: entradas solo a compuertas (nunca a source/drain),
salidas restauradas por una red CMOS, conteos exactos de transistores, nMOS = pMOS, `@cache`
en los constructores combinacionales y `sequential=True` en las secuenciales. Antes de
escribir cada celda, pídeme que dibuje su esquema de transistores y revísalo conmigo.

Restricciones (obligatorias):
- Trabaja con TDD: las pruebas ya existen y están marcadas `@pendiente(N)`. Implementa hasta
  que pasen, quita el marcador y vuelve a correr `make test`.
- No toques archivos fuera de mi módulo ni cambies interfaces (firmas, nombres de celda,
  puertos). Si crees que una interfaz es incorrecta, detente y explícame por qué para que
  yo proponga un ADR.
- No agregues dependencias.
- Avanza **punto de commit por punto de commit** (C1, C2, … de mi GUIA). Al terminar cada
  punto: `make lint`, `make test`, y dime el comando de commit exacto con el mensaje de la
  GUIA. Los commits los hago yo con MI identidad git (`git config user.name/user.email`);
  sin trailers `Co-Authored-By` ni menciones a herramientas de IA.
- Explícame cada decisión de diseño (por qué esa topología, ese ancho, ese orden) para que
  pueda defender el código ante el docente. No te limites a entregar código.
- Si algo no está claro en la GUIA o en un ADR, pregúntame antes de suponer.

Empecemos por el punto de commit C1 de la GUIA.
```

## B. Autovalidación

```text
Actúa como revisor exigente de un pull request del proyecto TranSim754. Te pego mi diff (o
mis archivos) del módulo Celdas CMOS L1. Revisa contra:
1. Los criterios de aceptación de la sección 5 de `src/transim/cells/GUIA.md` (te los pego abajo).
2. Las decisiones de los ADR citados en la GUIA (ADR-0006, ADR-0007, ADR-0008).
3. Las interfaces de la sección 2 de la GUIA: no deben haber cambiado.
4. Calidad: docstrings, nombres, sin código muerto, sin dependencias nuevas, sin literales
   8/23/32/127 fuera de `fpu/format.py` y `cpu/isa.py`.
5. Que no queden `@pendiente(...)` de mis issues (#1–#6) ni `NotImplementedError` en mis
   funciones.
6. Mensajes de commit en formato convencional y sin trailers de IA.
Para cada problema indica archivo, línea, por qué es un problema y cómo corregirlo.
Termina con un veredicto explícito: **APROBADO** o **CAMBIOS** (con la lista priorizada).

[pega aquí la sección 5 de la GUIA]
[pega aquí el diff o los archivos]
[pega aquí la salida de `make validar M=cells`]
```

## C. Estudio

```text
Quiero prepararme para defender el módulo Celdas CMOS L1 de TranSim754 ante un docente exigente de
Arquitectura de Computadoras. Hazme, una por una, las preguntas de comprensión de la
sección 7 de `src/transim/cells/GUIA.md` (te las pego abajo) y luego 5 preguntas adicionales tuyas sobre el
mismo tema, de dificultad creciente. Después de cada respuesta mía: dime si es correcta,
corrige con precisión lo que esté mal o incompleto, cita la fuente (ADR, docs/ o libro) y
solo entonces pasa a la siguiente. Al final, dame un resumen de mis puntos débiles y qué
debo repasar.

[pega aquí la sección 7 de la GUIA]
```
