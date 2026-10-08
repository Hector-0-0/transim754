# Material de apoyo · FPU común y FADD/FSUB

> USO INTERNO. No se presenta ni se exporta (ver `interno/README.md`).
> Responsable: Daniel · Guía: `src/transim/fpu/GUIA_ADDSUB.md` · Issues: #15–#17

## A. Desarrollo

Copia el bloque en tu propia cuenta y trabaja en tu rama `feat/<ámbito>-<descripcion>`.

```text
Proyecto TranSim754 (curso SI421U, UNI-FIIS, 2026-II): software en Python 3.12 que emula
un procesador cuyas operaciones (suma, resta, multiplicación y división en IEEE 754
binary32) se calculan con transistores nMOS/pMOS simulados en un simulador switch-level.
Repositorio: https://github.com/Hector-0-0/transim754 (rama principal `main`).

Soy Daniel, responsable de: FPU común y FADD/FSUB. Antes de escribir código, lee y resume en
5 líneas lo que entendiste de estos archivos (te los pego si no tienes acceso al repo):
   - `src/transim/fpu/GUIA_ADDSUB.md`
   - `docs/03_ieee754.md` (ejemplos resueltos y tablas de casos especiales)
   - `docs/adr/0002,` 0003, 0004
   - `src/transim/fpu/format.py` (completo, solo lectura)
   - `src/transim/reference/fpu.py` (en especial round_and_pack: es el contrato exacto)
   - `tests/fpu/test_codec_especiales.py,` test_redondeo.py, test_suma_resta.py

Decisiones del proyecto que aplican: ADR-0001 a ADR-0004, ADR-0009 (están en docs/adr/).

Tarea:
Implementar `unpacker`, `classifier`, `special_cases` (#15), el bloque compartido
`round_and_pack` (#16) y `fp_add_sub` (#17) siguiendo el datapath de la sección 1 de la GUIA.

`round_and_pack` es compartido con Fabricio: su interfaz no cambia sin ADR. Para depurar
FADD, construye primero cada etapa por separado y compárala con la referencia; agrega buses
`dbg_` (exp_diff, aligned, sum, lz) para la traza del CLI. Recuerda: x − x = +0, (−0)+(−0) = −0,
sNaN levanta invalid, qNaN no, y el NaN de salida es siempre el canónico.

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
mis archivos) del módulo FPU común y FADD/FSUB. Revisa contra:
1. Los criterios de aceptación de la sección 5 de `src/transim/fpu/GUIA_ADDSUB.md` (te los pego abajo).
2. Las decisiones de los ADR citados en la GUIA (ADR-0001 a ADR-0004, ADR-0009).
3. Las interfaces de la sección 2 de la GUIA: no deben haber cambiado.
4. Calidad: docstrings, nombres, sin código muerto, sin dependencias nuevas, sin literales
   8/23/32/127 fuera de `fpu/format.py` y `cpu/isa.py`.
5. Que no queden `@pendiente(...)` de mis issues (#15–#17) ni `NotImplementedError` en mis
   funciones.
6. Mensajes de commit en formato convencional y sin trailers de IA.
Para cada problema indica archivo, línea, por qué es un problema y cómo corregirlo.
Termina con un veredicto explícito: **APROBADO** o **CAMBIOS** (con la lista priorizada).

[pega aquí la sección 5 de la GUIA]
[pega aquí el diff o los archivos]
[pega aquí la salida de `make validar M=fpu-addsub`]
```

## C. Estudio

```text
Quiero prepararme para defender el módulo FPU común y FADD/FSUB de TranSim754 ante un docente exigente de
Arquitectura de Computadoras. Hazme, una por una, las preguntas de comprensión de la
sección 7 de `src/transim/fpu/GUIA_ADDSUB.md` (te las pego abajo) y luego 5 preguntas adicionales tuyas sobre el
mismo tema, de dificultad creciente. Después de cada respuesta mía: dime si es correcta,
corrige con precisión lo que esté mal o incompleto, cita la fuente (ADR, docs/ o libro) y
solo entonces pasa a la siguiente. Al final, dame un resumen de mis puntos débiles y qué
debo repasar.

[pega aquí la sección 7 de la GUIA]
```
