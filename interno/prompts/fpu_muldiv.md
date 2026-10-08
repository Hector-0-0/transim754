# Material de apoyo · FMUL y FDIV

> USO INTERNO. No se presenta ni se exporta (ver `interno/README.md`).
> Responsable: Fabricio · Guía: `src/transim/fpu/GUIA_MULDIV.md` · Issues: #18–#21

## A. Desarrollo

Copia el bloque en tu propia cuenta y trabaja en tu rama `feat/<ámbito>-<descripcion>`.

```text
Proyecto TranSim754 (curso SI421U, UNI-FIIS, 2026-II): software en Python 3.12 que emula
un procesador cuyas operaciones (suma, resta, multiplicación y división en IEEE 754
binary32) se calculan con transistores nMOS/pMOS simulados en un simulador switch-level.
Repositorio: https://github.com/Hector-0-0/transim754 (rama principal `main`).

Soy Fabricio, responsable de: FMUL y FDIV. Antes de escribir código, lee y resume en
5 líneas lo que entendiste de estos archivos (te los pego si no tienes acceso al repo):
   - `src/transim/fpu/GUIA_MULDIV.md`
   - `docs/03_ieee754.md` (ejemplos 4, 5 y 6)
   - `docs/adr/0009-algoritmos-de-hardware.md`
   - `src/transim/fpu/mul.py` y div.py
   - `src/transim/reference/blocks.py` (multiply, divide_mantissas) y reference/fpu.py (round_and_pack)
   - `tests/fpu/test_multiplicacion.py,` test_division.py

Decisiones del proyecto que aplican: ADR-0002 a ADR-0004, ADR-0009 (están en docs/adr/).

Tarea:
Implementar el multiplicador de mantisas en arreglo (#18), el divisor no restaurador (#20),
FMUL (#19) y FDIV (#21) siguiendo los pasos de la sección 1 de la GUIA.

Mientras `round_and_pack` de Daniel no esté listo, valida tu datapath llamando a
`transim.reference.fpu.round_and_pack` con las mismas entradas (m, G, R, S, e). Verifica los
anchos de exponente con los extremos (subnormal mínimo y normal máximo).

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
mis archivos) del módulo FMUL y FDIV. Revisa contra:
1. Los criterios de aceptación de la sección 5 de `src/transim/fpu/GUIA_MULDIV.md` (te los pego abajo).
2. Las decisiones de los ADR citados en la GUIA (ADR-0002 a ADR-0004, ADR-0009).
3. Las interfaces de la sección 2 de la GUIA: no deben haber cambiado.
4. Calidad: docstrings, nombres, sin código muerto, sin dependencias nuevas, sin literales
   8/23/32/127 fuera de `fpu/format.py` y `cpu/isa.py`.
5. Que no queden `@pendiente(...)` de mis issues (#18–#21) ni `NotImplementedError` en mis
   funciones.
6. Mensajes de commit en formato convencional y sin trailers de IA.
Para cada problema indica archivo, línea, por qué es un problema y cómo corregirlo.
Termina con un veredicto explícito: **APROBADO** o **CAMBIOS** (con la lista priorizada).

[pega aquí la sección 5 de la GUIA]
[pega aquí el diff o los archivos]
[pega aquí la salida de `make validar M=fpu-muldiv`]
```

## C. Estudio

```text
Quiero prepararme para defender el módulo FMUL y FDIV de TranSim754 ante un docente exigente de
Arquitectura de Computadoras. Hazme, una por una, las preguntas de comprensión de la
sección 7 de `src/transim/fpu/GUIA_MULDIV.md` (te las pego abajo) y luego 5 preguntas adicionales tuyas sobre el
mismo tema, de dificultad creciente. Después de cada respuesta mía: dime si es correcta,
corrige con precisión lo que esté mal o incompleto, cita la fuente (ADR, docs/ o libro) y
solo entonces pasa a la siguiente. Al final, dame un resumen de mis puntos débiles y qué
debo repasar.

[pega aquí la sección 7 de la GUIA]
```
