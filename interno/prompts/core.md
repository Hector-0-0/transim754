# Material de apoyo · Núcleo L0 (simulador switch-level)

> USO INTERNO. No se presenta ni se exporta (ver `interno/README.md`).
> Responsable: Héctor · Guía: `docs/02_simulador_switch_level.md` · Issues: —

## A. Desarrollo

Copia el bloque en tu propia cuenta y trabaja en tu rama `feat/<ámbito>-<descripcion>`.

```text
Proyecto TranSim754 (curso SI421U, UNI-FIIS, 2026-II): software en Python 3.12 que emula
un procesador cuyas operaciones (suma, resta, multiplicación y división en IEEE 754
binary32) se calculan con transistores nMOS/pMOS simulados en un simulador switch-level.
Repositorio: https://github.com/Hector-0-0/transim754 (rama principal `main`).

Soy Héctor, responsable de: Núcleo L0 (simulador switch-level). Antes de escribir código, lee y resume en
5 líneas lo que entendiste de estos archivos (te los pego si no tienes acceso al repo):
   - `docs/02_simulador_switch_level.md`
   - `docs/adr/0007-simulador-switch-level.md`
   - `docs/adr/0008-dos-motores-equivalentes.md`
   - `src/transim/core/*.py`
   - `tests/core/*.py`

Decisiones del proyecto que aplican: ADR-0007, ADR-0008 (están en docs/adr/).

Tarea:
Mantener y extender el núcleo: corrección de defectos que encuentren los demás módulos,
rendimiento del motor `cached` cuando la FPU completa esté integrada, y paso de la FSM de
control a compuertas en v1.0. Cualquier cambio en la regla de conteo o de equivalencia se
documenta primero en ADR-0007/0008.

Cuidado especial: la equivalencia entre motores se define sobre el estado observable
(nodos 0/1 manejados) y los contadores; los nodos con carga retenida y las X dependen del
orden de eventos (ADR-0008, Precisiones). Toda corrección viene con una prueba de
regresión que falle con el código anterior.

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
mis archivos) del módulo Núcleo L0 (simulador switch-level). Revisa contra:
1. Los criterios de aceptación de la sección 5 de `docs/02_simulador_switch_level.md` (te los pego abajo).
2. Las decisiones de los ADR citados en la GUIA (ADR-0007, ADR-0008).
3. Las interfaces de la sección 2 de la GUIA: no deben haber cambiado.
4. Calidad: docstrings, nombres, sin código muerto, sin dependencias nuevas, sin literales
   8/23/32/127 fuera de `fpu/format.py` y `cpu/isa.py`.
5. Que no queden `@pendiente(...)` de mis issues (—) ni `NotImplementedError` en mis
   funciones.
6. Mensajes de commit en formato convencional y sin trailers de IA.
Para cada problema indica archivo, línea, por qué es un problema y cómo corregirlo.
Termina con un veredicto explícito: **APROBADO** o **CAMBIOS** (con la lista priorizada).

[pega aquí la sección 5 de la GUIA]
[pega aquí el diff o los archivos]
[pega aquí la salida de `make validar M=core`]
```

## C. Estudio

```text
Quiero prepararme para defender el módulo Núcleo L0 (simulador switch-level) de TranSim754 ante un docente exigente de
Arquitectura de Computadoras. Hazme, una por una, las preguntas de comprensión de la
sección 7 de `docs/02_simulador_switch_level.md` (te las pego abajo) y luego 5 preguntas adicionales tuyas sobre el
mismo tema, de dificultad creciente. Después de cada respuesta mía: dime si es correcta,
corrige con precisión lo que esté mal o incompleto, cita la fuente (ADR, docs/ o libro) y
solo entonces pasa a la siguiente. Al final, dame un resumen de mis puntos débiles y qué
debo repasar.

[pega aquí la sección 7 de la GUIA]
```
