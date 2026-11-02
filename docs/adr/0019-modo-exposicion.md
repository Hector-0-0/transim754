# ADR-0019 · Modo exposición de la interfaz gráfica

- **Estado:** Aceptada
- **Fecha:** 2026-11-02

## Contexto

La interfaz se usa sobre todo para exponer el proyecto en clase. Lo que se evalúa es la
parte visual de lo que pide el enunciado: los transistores, las compuertas y las
operaciones entre números. Al revisar la interfaz clic por clic se ve que tiene más de
lo que hace falta para eso:

- menús Archivo, Ver y Ayuda, y atajos de teclado (Ctrl, Alt, teclas F) que en una
  exposición no se usan y que, pulsados sin querer, cambian la vista;
- la pestaña Programa (la CPU T754), que es un extra y no forma parte de la demostración;
- el historial de operaciones;
- en Transistores, el panel de detalle con el corte del transistor. Aparece y desaparece
  según lo que esté bajo el ratón y explica física de dispositivos que el curso no pide;
- textos largos: líneas de ayuda, leyendas con frases enteras y datos separados por
  « · » («cached · rápido», «0x40700000 · normal · binary32»).

Además, el tema seguía al del sistema. En un escritorio claro la interfaz arrancaba en
claro aunque se hubiera preparado en oscuro.

## Decisión

1. **Dos modos.** `transim gui` abre el **modo exposición**. `transim gui --completo`
   abre la interfaz con todo, como antes. En el código, `create_window(full=...)` y
   `MainWindow(full=...)`.
2. **En modo exposición se oculta, sin eliminarse:**
   - la barra de menús y la guía rápida (F1);
   - la pestaña Programa;
   - el botón Ejemplos, el historial, el indicador de eventos y las notas al pie en
     Operación (los casos notables pasan a las diapositivas);
   - en Recorrido, la línea de teclas y la de conexiones («Recibe de, Entrega a»);
   - en Transistores, el panel de detalle, la línea de descripción y las casillas de
     capas del silicio.

   Cada pestaña lo hace en `set_presentation(on)`: oculta los widgets y no los borra. El
   historial se sigue guardando.
3. **Atajos.** En modo exposición se desactivan los atajos con Ctrl, Alt o teclas F.
   Quedan las teclas de navegación propias de cada vista: Enter en un operando calcula,
   las flechas cambian de paso en Recorrido (un control de presentación envía flechas),
   y Esc y Retroceso sueltan la selección y suben un nivel en Transistores.
4. **Siempre oscuro.** La aplicación arranca en el tema oscuro y no sigue al sistema. El
   menú de tema solo existe en el modo completo.
5. **Texto natural en los dos modos.** Ningún texto visible separa datos con « · ».
   Las listas usan comas o paréntesis («0x40700000 (normal en binary32)», «INV (2
   transistores)»). Las unidades se nombran como operación («Suma y resta en binary32»)
   y no por su netlist. Las leyendas muestran solo los colores. Una prueba recorre las
   pestañas y falla si algún texto visible usa « · ».

## Consecuencias

- La pantalla deja más lugar a lo que se muestra: sin el panel de detalle, el dibujo de
  Transistores usa todo el ancho.
- Las pruebas de la interfaz completa abren la ventana con `full=True`. El modo
  exposición tiene sus propias pruebas (`tests/ui/test_exposicion.py`).
- La guía rápida (F1) solo se abre en el modo completo. La documentación de usuario
  indica cómo abrirlo.
- En Recorrido, un clic en las entradas vuelve al primer paso y un clic en el resultado
  muestra todos.

## Alternativas descartadas

- **Borrar lo que no se usa en la exposición.** Se perdería trabajo hecho y probado: la
  CPU T754 y el panel de detalle siguen siendo útiles para estudiar el proyecto.
- **Una casilla en la interfaz para cambiar de modo.** Sería otro control más en
  pantalla, que es justo lo que se quiere evitar. El modo se elige al abrir.
- **Mantener el tema del sistema.** Las capturas y las diapositivas son oscuras. Con un
  tema que depende del equipo, la demostración no se vería igual en la computadora del
  aula.
