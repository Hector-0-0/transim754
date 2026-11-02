"""Pestaña Recorrido: la última operación, paso a paso, por sus etapas de hardware.

A la izquierda, las etapas como cajas conectadas en el orden del datapath, desde las
entradas hasta el resultado; las que ya pasaron muestran su resultado y las que faltan
aparecen en gris. A la derecha, «Qué está pasando»: la explicación del paso actual con
la cuenta hecha con los bits de la simulación. Un doble clic en una caja (o Enter) abre
sus transistores en la pestaña Transistores.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QShortcut,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from transim.ui.gui import theme as th
from transim.ui.gui import walkthrough as wt
from transim.ui.gui.model import Calculation
from transim.ui.gui.widgets import card, hint, stage_color, thousands

BOX_W = 236.0
BOX_H = 92.0
GAP_X = 52.0
GAP_Y = 54.0
MARGIN = 20.0
MAX_SCALE = 1.35
PLAY_MS = 1700
ARROW = 8.0
PILL_INSET = 8.0
"""Margen vertical de las píldoras de entradas y resultado dentro de su casilla."""


def _mono(size: float) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSizeF(size)
    return font


def _font(size: float, bold: bool = False) -> QFont:
    font = QFont()
    font.setPointSizeF(size)
    font.setBold(bold)
    return font


# ---------------------------------------------------------------- dibujo
class StepItem(QGraphicsItem):
    """Caja de un paso. ``state``: ``done`` (ya pasó), ``now`` (actual) o ``todo``."""

    def __init__(self, index: int, step: wt.Step, state: str) -> None:
        super().__init__()
        self.index = index
        self.step = step
        self.state = state
        self.setData(0, index)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{step.title}\nClic: ir a este paso · Doble clic: ver sus transistores")
        self._hover = False

    def boundingRect(self) -> QRectF:  # noqa: N802 - API de Qt
        return QRectF(-3, -3, BOX_W + 6, BOX_H + 6)

    def hoverEnterEvent(self, event: object) -> None:  # noqa: N802 - API de Qt
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event: object) -> None:  # noqa: N802 - API de Qt
        self._hover = False
        self.update()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        t = th.current()
        todo = self.state == "todo"
        now = self.state == "now"
        rect = QRectF(0, 0, BOX_W, BOX_H)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        fill = QColor(t.surface_alt if todo else t.surface)
        painter.fillPath(path, fill)
        if now:
            tint = QColor(t.accent)
            tint.setAlpha(26)
            painter.fillPath(path, tint)
        color = stage_color(self.step.key)
        if todo:
            color.setAlpha(80)
        painter.save()
        painter.setClipPath(path)
        painter.fillRect(QRectF(0, 0, 6, BOX_H), color)
        painter.restore()
        if now:
            pen = QPen(QColor(t.accent), 2.6)
        elif self._hover:
            pen = QPen(QColor(t.select), 1.6)
        else:
            pen = QPen(QColor(t.border), 1.1)
            if todo:
                pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawPath(path)

        text = QColor(t.muted if todo else t.text)
        muted = QColor(t.muted)
        # Número del paso en un círculo.
        circle = QRectF(16, 12, 22, 22)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(t.accent) if not todo else QColor(t.border))
        painter.drawEllipse(circle)
        painter.setPen(QColor(t.accent_text) if not todo else muted)
        painter.setFont(_font(8.5, bold=True))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(self.index + 1))
        # Título.
        painter.setPen(text)
        painter.setFont(_font(10.5, bold=True))
        title_rect = QRectF(46, 10, BOX_W - 54, 26)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            painter.fontMetrics().elidedText(
                self.step.title, Qt.TextElideMode.ElideRight, int(title_rect.width())
            ),
        )
        # Resultado del paso.
        painter.setFont(_mono(10.0))
        painter.setPen(QColor(t.accent) if not todo else muted)
        summary = "—" if todo else self.step.summary
        sum_rect = QRectF(16, 42, BOX_W - 28, 22)
        painter.drawText(
            sum_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            painter.fontMetrics().elidedText(
                summary, Qt.TextElideMode.ElideRight, int(sum_rect.width())
            ),
        )
        # Transistores.
        painter.setPen(muted)
        painter.setFont(_font(8.5))
        painter.drawText(
            QRectF(16, 66, BOX_W - 28, 18),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"{thousands(self.step.transistors)} transistores",
        )


class PillItem(QGraphicsItem):
    """Las entradas (al comienzo) o el resultado (al final)."""

    def __init__(self, title: str, lines: tuple[str, ...], lit: bool) -> None:
        super().__init__()
        self.title = title
        self.lines = lines
        self.lit = lit

    def boundingRect(self) -> QRectF:  # noqa: N802 - API de Qt
        return QRectF(-2, -2, BOX_W + 4, BOX_H + 4)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        t = th.current()
        rect = QRectF(0, PILL_INSET, BOX_W, BOX_H - 2 * PILL_INSET)
        path = QPainterPath()
        path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        if self.lit:
            fill = QColor(t.accent)
            fill.setAlpha(34)
            painter.fillPath(path, fill)
            painter.setPen(QPen(QColor(t.accent), 1.6))
        else:
            painter.fillPath(path, QColor(t.surface_alt))
            pen = QPen(QColor(t.border), 1.1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
        painter.drawPath(path)
        painter.setPen(QColor(t.muted))
        painter.setFont(_font(8.5, bold=True))
        painter.drawText(QRectF(0, 16, BOX_W, 16), Qt.AlignmentFlag.AlignCenter, self.title.upper())
        painter.setPen(QColor(t.text if self.lit else t.muted))
        painter.setFont(_mono(10.5))
        body = "   ".join(self.lines)
        painter.drawText(
            QRectF(10, 34, BOX_W - 20, 40),
            Qt.AlignmentFlag.AlignCenter,
            painter.fontMetrics().elidedText(body, Qt.TextElideMode.ElideRight, int(BOX_W - 20)),
        )


class StepDiagram(QGraphicsView):
    """Las etapas como cajas conectadas, en filas que se leen de izquierda a derecha."""

    step_clicked = Signal(int)
    step_activated = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumSize(420, 300)
        self.walk: wt.Walkthrough | None = None
        self.current = 0
        self.columns = 3
        self.boxes: list[StepItem] = []

    def show_walk(self, walk: wt.Walkthrough | None, current: int) -> None:
        self.walk = walk
        self.current = current
        self.rebuild()

    def set_current(self, current: int) -> None:
        self.current = current
        self.rebuild()

    def _best_columns(self, count: int) -> int:
        """Columnas que dejan las cajas más grandes en el espacio de la vista."""
        vw, vh = max(1, self.viewport().width()), max(1, self.viewport().height())
        best, best_scale = 3, 0.0
        for cols in range(2, 6):
            rows = -(-count // cols)
            w = cols * BOX_W + (cols - 1) * GAP_X + 2 * MARGIN
            h = rows * BOX_H + (rows - 1) * GAP_Y + 2 * MARGIN
            scale = min(vw / w, vh / h, MAX_SCALE)
            if scale > best_scale + 0.02:
                best, best_scale = cols, scale
        return best

    def rebuild(self) -> None:
        self._scene.clear()
        self.boxes = []
        t = th.current()
        self.setBackgroundBrush(QBrush(QColor(t.paper)))
        walk = self.walk
        if walk is None:
            return
        n = len(walk.steps)
        count = n + 2
        cols = self._best_columns(count)
        self.columns = cols
        reached_end = self.current >= n - 1

        def slot(k: int) -> QPointF:
            r, c = divmod(k, cols)
            return QPointF(MARGIN + c * (BOX_W + GAP_X), MARGIN + r * (BOX_H + GAP_Y))

        start = PillItem("entradas", walk.inputs, lit=True)
        start.setPos(slot(0))
        self._scene.addItem(start)
        for k, step in enumerate(walk.steps):
            state = "done" if k < self.current else "now" if k == self.current else "todo"
            item = StepItem(k, step, state)
            item.setPos(slot(k + 1))
            self._scene.addItem(item)
            self.boxes.append(item)
        end = PillItem("resultado", (walk.result if reached_end else "?",), lit=reached_end)
        end.setPos(slot(n + 1))
        self._scene.addItem(end)

        for k in range(count - 1):
            lit = k <= self.current or reached_end
            self._edge(slot(k), slot(k + 1), QColor(t.accent if lit else t.border), lit)

        rows = -(-count // cols)
        w = cols * BOX_W + (cols - 1) * GAP_X + 2 * MARGIN
        h = rows * BOX_H + (rows - 1) * GAP_Y + 2 * MARGIN
        self._scene.setSceneRect(QRectF(0, 0, w, h))
        self._fit()

    def _edge(self, a: QPointF, b: QPointF, color: QColor, lit: bool) -> None:
        if abs(a.y() - b.y()) < 1:  # misma fila: flecha recta
            p0 = QPointF(a.x() + BOX_W + 4, a.y() + BOX_H / 2)
            p1 = QPointF(b.x() - 4, b.y() + BOX_H / 2)
            path = QPainterPath(p0)
            path.lineTo(p1)
            tip, direction = p1, QPointF(1, 0)
        else:  # cambio de fila: baja, cruza por el hueco entre filas y vuelve a bajar
            p0 = QPointF(a.x() + BOX_W / 2, a.y() + BOX_H + 4)
            mid_y = a.y() + BOX_H + GAP_Y / 2
            p1 = QPointF(b.x() + BOX_W / 2, b.y() - 4)
            path = QPainterPath(p0)
            path.lineTo(p0.x(), mid_y)
            path.lineTo(p1.x(), mid_y)
            path.lineTo(p1)
            tip, direction = p1, QPointF(0, 1)
        item = QGraphicsPathItem(path)
        pen = QPen(color, 2.0 if lit else 1.4)
        if not lit:
            pen.setStyle(Qt.PenStyle.DashLine)
        item.setPen(pen)
        self._scene.addItem(item)
        back = QPointF(tip.x() - direction.x() * ARROW, tip.y() - direction.y() * ARROW)
        side = QPointF(-direction.y() * ARROW / 2, direction.x() * ARROW / 2)
        head = QGraphicsPolygonItem(QPolygonF([tip, back + side, back - side]))
        head.setBrush(QBrush(color))
        head.setPen(QPen(Qt.PenStyle.NoPen))
        self._scene.addItem(head)

    def _fit(self) -> None:
        rect = self._scene.sceneRect()
        if rect.isEmpty():
            return
        self.resetTransform()
        vw, vh = self.viewport().width(), self.viewport().height()
        scale = min(vw / rect.width(), vh / rect.height(), MAX_SCALE)
        self.scale(scale, scale)
        self.centerOn(rect.center())

    def resizeEvent(self, event: object) -> None:  # noqa: N802 - API de Qt
        super().resizeEvent(event)  # type: ignore[arg-type]
        if self.walk is not None:
            if self._best_columns(len(self.walk.steps) + 2) != self.columns:
                self.rebuild()
            else:
                self._fit()

    def _index_at(self, event: object) -> int | None:
        item = self.itemAt(event.position().toPoint())  # type: ignore[attr-defined]
        while item is not None and not isinstance(item, StepItem):
            item = item.parentItem()
        return item.index if isinstance(item, StepItem) else None

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - API de Qt
        k = self._index_at(event)
        if k is not None and event.button() == Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
            self.step_clicked.emit(k)
        super().mousePressEvent(event)  # type: ignore[arg-type]

    def mouseDoubleClickEvent(self, event: object) -> None:  # noqa: N802 - API de Qt
        k = self._index_at(event)
        if k is not None:
            self.step_activated.emit(k)
        super().mouseDoubleClickEvent(event)  # type: ignore[arg-type]

    def item_center(self, k: int) -> QPointF:
        """Centro de la caja del paso ``k`` en coordenadas de la escena (para pruebas)."""
        return self.boxes[k].sceneBoundingRect().center()


# ---------------------------------------------------------------- pestaña
class WalkthroughTab(QWidget):
    """Recorrido paso a paso de la última operación."""

    open_block = Signal(str)
    open_propagation = Signal(str)
    go_operation = Signal()
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.walk: wt.Walkthrough | None = None
        self.index = 0
        self.timer = QTimer(self)
        self.timer.setInterval(PLAY_MS)
        self.timer.timeout.connect(self._tick)

        # Estado vacío.
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch(1)
        msg = QLabel(
            "Todavía no hay una operación.\n\nCalcule una en la pestaña Operación y aquí "
            "podrá recorrerla paso a paso: cómo la FPU desempaqueta los operandos, alinea "
            "las mantisas, suma, normaliza y redondea, con los bits de la simulación."
        )
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setMaximumWidth(560)
        go = QPushButton("Ir a Operación")
        go.setObjectName("primary")
        go.clicked.connect(self.go_operation)
        el.addWidget(msg, 0, Qt.AlignmentFlag.AlignCenter)
        el.addSpacing(12)
        el.addWidget(go, 0, Qt.AlignmentFlag.AlignCenter)
        el.addStretch(2)

        # Encabezado: la operación y los controles del paso a paso.
        self.expression = QLabel()
        self.expression.setObjectName("bigResult")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("muted")
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(self.expression)
        heading.addWidget(self.subtitle)
        self.prev = self._tool("◀ Anterior", "Paso anterior (←)", lambda: self.step_move(-1))
        self.counter = QLabel()
        self.counter.setMinimumWidth(92)
        self.counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next = self._tool("Siguiente ▶", "Paso siguiente (→)", lambda: self.step_move(1))
        self.next.setObjectName("primary")
        self.play = self._tool(
            "⏵ Reproducir", "Avanza solo, un paso cada vez (Espacio)", self.toggle_play
        )
        self.restart = self._tool(
            "Desde el inicio", "Volver al paso 1 (Inicio)", lambda: self.go(0)
        )
        self.all = self._tool(
            "Ver todo", "Mostrar todos los pasos con sus valores (Fin)", self.show_all
        )
        top = QHBoxLayout()
        top.addLayout(heading, 1)
        for w in (self.restart, self.prev, self.counter, self.next, self.play, self.all):
            top.addWidget(w)

        # Diagrama.
        self.diagram = StepDiagram()
        self.diagram.step_clicked.connect(self.go)
        self.diagram.step_activated.connect(self._activate)
        diagram_frame = QFrame()
        diagram_frame.setObjectName("card")
        dl = QVBoxLayout(diagram_frame)
        dl.setContentsMargins(1, 1, 1, 1)
        dl.addWidget(self.diagram)

        # Panel «Qué está pasando».
        panel, pl = card("Qué está pasando")
        panel.setMinimumWidth(360)
        panel.setMaximumWidth(470)
        self.p_step = QLabel()
        self.p_step.setObjectName("muted")
        self.p_title = QLabel()
        self.p_title.setFont(_font(14.0, bold=True))
        self.p_title.setWordWrap(True)
        self.p_meta = hint("")
        self.p_text = QLabel()
        self.p_text.setWordWrap(True)
        self.p_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.p_detail = QLabel()
        self.p_detail.setObjectName("detail")
        self.p_detail.setFont(_mono(10.0))
        self.p_detail.setWordWrap(True)
        self.p_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.p_detail.setMargin(10)
        self.p_links = hint("")
        self.p_open = QPushButton("Ver sus transistores ▸")
        self.p_open.setToolTip("Abrir este bloque en la pestaña Transistores (Enter)")
        self.p_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.p_open.clicked.connect(lambda: self._activate(self.index))
        self.p_wave = QPushButton("Ver la propagación ▸")
        self.p_wave.setToolTip(
            "Abrir la rejilla de bits del bloque y ver el cambio avanzar celda por celda"
        )
        self.p_wave.setCursor(Qt.CursorShape.PointingHandCursor)
        self.p_wave.clicked.connect(self._propagate)
        for w in (self.p_step, self.p_title, self.p_meta, self.p_text, self.p_detail, self.p_links):
            pl.addWidget(w)
        pl.addWidget(self.p_open)
        pl.addWidget(self.p_wave)
        self.p_note = hint("")
        pl.addWidget(self.p_note)
        pl.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(diagram_frame, 1)
        body.addWidget(panel)
        self.keys = hint(
            "← → cambian de paso · Espacio reproduce · Enter o doble clic en una caja abre "
            "sus transistores · Los valores son los de la simulación; el orden es el del "
            "flujo de datos (el simulador no mide tiempos)."
        )

        full = QWidget()
        fl = QVBoxLayout(full)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(10)
        fl.addLayout(top)
        fl.addLayout(body, 1)
        fl.addWidget(self.keys)

        self.stack = QStackedWidget()
        self.stack.addWidget(empty)
        self.stack.addWidget(full)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.addWidget(self.stack)

        for keys, fn in (
            ("Right", lambda: self.step_move(1)),
            ("Left", lambda: self.step_move(-1)),
            ("Space", self.toggle_play),
            ("Home", lambda: self.go(0)),
            ("End", self.show_all),
            ("Return", lambda: self._activate(self.index)),
            ("Enter", lambda: self._activate(self.index)),
        ):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
        self.apply_theme()

    def _tool(self, text: str, tip: str, fn: object) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("tool")
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # las flechas y Espacio son del recorrido
        b.clicked.connect(fn)
        return b

    # ------------------------------------------------------------ datos
    def show_calculation(self, calc: Calculation) -> None:
        """Arma el recorrido de ``calc``. Lee los valores ya: la unidad puede cambiar después."""
        walk = wt.build(calc)
        same = (
            self.walk is not None
            and self.walk.unit == walk.unit
            and len(self.walk.steps) == len(walk.steps)
        )
        self.walk = walk
        if not same:
            self.index = 0
        self.stop()
        self.stack.setCurrentIndex(1)
        self.expression.setText(walk.expression)
        kind = "explicado paso a paso" if walk.narrated else "bloques en orden de flujo"
        self.subtitle.setText(f"{walk.unit} · {len(walk.steps)} pasos · {kind}")
        self.p_note.setText(
            ""
            if walk.narrated
            else "Esta operación muestra las entradas y salidas de cada bloque, sin la "
            "explicación con las cuentas."
        )
        self.diagram.show_walk(walk, self.index)
        self._fill()

    # ------------------------------------------------------------ navegación
    @property
    def count(self) -> int:
        return 0 if self.walk is None else len(self.walk.steps)

    def go(self, k: int) -> None:
        if self.walk is None:
            return
        k = max(0, min(self.count - 1, k))
        if k == self.index and self.diagram.current == k:
            return
        self.index = k
        self.diagram.set_current(k)
        self._fill()

    def step_move(self, delta: int) -> None:
        if self.walk is None:
            return
        if delta > 0 and self.index >= self.count - 1:
            self.stop()
            return
        self.go(self.index + delta)

    def show_all(self) -> None:
        self.stop()
        self.go(self.count - 1)

    def toggle_play(self) -> None:
        if self.walk is None:
            return
        if self.timer.isActive():
            self.stop()
            return
        if self.index >= self.count - 1:
            self.go(0)
        self.timer.start()
        self.play.setText("⏸ Pausa")

    def stop(self) -> None:
        self.timer.stop()
        self.play.setText("⏵ Reproducir")

    def _tick(self) -> None:
        if self.index >= self.count - 1:
            self.stop()
        else:
            self.go(self.index + 1)

    def _activate(self, k: int) -> None:
        if self.walk is None or not 0 <= k < self.count:
            return
        self.stop()
        step = self.walk.steps[k]
        self.status.emit(f"Abriendo «{step.title}» en Transistores")
        self.open_block.emit(step.paths[0])

    def _propagate(self) -> None:
        if self.walk is None:
            return
        self.stop()
        step = self.walk.steps[self.index]
        self.open_propagation.emit(step.paths[0])

    # ------------------------------------------------------------ panel
    def _fill(self) -> None:
        walk = self.walk
        if walk is None:
            return
        step = walk.steps[self.index]
        n = len(walk.steps)
        self.counter.setText(f"Paso {self.index + 1} de {n}")
        self.prev.setEnabled(self.index > 0)
        self.restart.setEnabled(self.index > 0)
        self.next.setEnabled(self.index < n - 1)
        self.all.setEnabled(self.index < n - 1)
        self.p_step.setText(f"PASO {self.index + 1} DE {n}")
        color = stage_color(step.key).name()
        self.p_title.setText(f"<span style='color:{color}'>■</span>&nbsp;{step.title}")
        blocks = ", ".join(step.paths)
        self.p_meta.setText(f"{thousands(step.transistors)} transistores · bloque {blocks}")
        self.p_text.setText(step.text)
        self.p_detail.setText(step.detail)
        self.p_wave.setText(
            "Ver el acarreo ▸" if step.key == "mant_addsub" else "Ver la propagación ▸"
        )
        parts = []
        if step.sources:
            parts.append("Recibe de: " + ", ".join(walk.steps[i].title for i in step.sources))
        else:
            parts.append("Recibe de: las entradas a y b")
        if step.targets:
            parts.append("Entrega a: " + ", ".join(walk.steps[i].title for i in step.targets))
        else:
            parts.append("Entrega a: el resultado")
        self.p_links.setText("\n".join(parts))

    def apply_theme(self) -> None:
        t = th.current()
        self.p_detail.setStyleSheet(
            f"QLabel#detail {{ background: {t.surface_alt}; border: 1px solid {t.border};"
            f" border-radius: 8px; color: {t.text}; }}"
        )
        self.diagram.rebuild()


__all__ = ["PillItem", "StepDiagram", "StepItem", "WalkthroughTab"]
