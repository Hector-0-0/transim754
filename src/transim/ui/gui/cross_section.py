"""Corte transversal ilustrativo de un transistor MOS con su estado.

Muestra el dispositivo como se fabrica en el silicio (Weste y Harris, 2011, §1.3):
el cuerpo (sustrato p para un nMOS, pozo n para un pMOS), las dos regiones muy dopadas
de fuente y drenador, el óxido de compuerta (SiO₂), la compuerta de polisilicio y el
aislamiento lateral (STI). Cuando el transistor conduce, el campo de la compuerta forma
la **capa de inversión**: un canal de electrones (nMOS) o de huecos (pMOS) que une
fuente y drenador.

En reposo, un canal que conduce une dos nodos que ya tienen el mismo valor, así que no
circula corriente: la corriente solo fluye mientras un nodo se carga o se descarga
(:attr:`CrossSection.flowing`). El dibujo no está a escala.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from transim.core.signals import Logic
from transim.core.transistor import Conduction
from transim.ui.gui import theme as th
from transim.ui.gui.canvas import alpha, logic_text, pen

N_TYPE = "#6f9ff0"  # silicio tipo n
N_PLUS = "#3567d6"
P_TYPE = "#eba3a0"  # silicio tipo p
P_PLUS = "#d4524c"
POLY = "#d8433c"
OXIDE = "#d9e2ec"
STI = "#8b939e"
METAL = "#9aa7b8"


@dataclass(frozen=True)
class Device:
    """Lo que se dibuja: tipo, nombres y valores de los terminales y estado del canal."""

    pmos: bool
    name: str
    gate: str
    source: str
    drain: str
    gate_value: Logic
    source_value: Logic
    drain_value: Logic
    state: Conduction


class CrossSection(QWidget):
    """Corte de un transistor; se anima mientras circula corriente."""

    def __init__(self) -> None:
        super().__init__()
        self.device: Device | None = None
        self.flowing = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802 - API de Qt
        return QSize(300, 250)

    def show_device(self, device: Device | None, flowing: bool = False) -> None:
        """Dibuja ``device``; con ``flowing`` anima los portadores a lo largo del canal."""
        self.device = device
        self.flowing = flowing and device is not None and device.state is Conduction.ON
        animate = device is not None and device.state is Conduction.ON
        if animate and not self._timer.isActive():
            self._timer.start()
        elif not animate:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + (0.035 if self.flowing else 0.006)) % 1.0
        self.update()

    # ---------------------------------------------------------------- pintura
    def paintEvent(self, event: object) -> None:  # noqa: N802
        t = th.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        p.fillRect(QRectF(0, 0, w, h), QColor(t.surface))
        d = self.device
        if d is None:
            p.setPen(pen(t.muted, 1))
            p.drawText(
                QRectF(10, 0, w - 20, h),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Pase el ratón por un transistor para ver su corte transversal.",
            )
            p.end()
            return
        small = QFont()
        small.setPointSizeF(7.5)
        bold = QFont()
        bold.setPointSizeF(8.5)
        bold.setBold(True)

        m = 12.0
        x0, x1 = m, w - m
        width = x1 - x0
        top = 64.0  # superficie del silicio
        bottom = h - 26.0
        sd_w = width * 0.27
        sd_h = (bottom - top) * 0.34
        g0, g1 = x0 + sd_w + width * 0.02, x1 - sd_w - width * 0.02
        ox = 5.0
        gate_h = 22.0

        body = N_TYPE if d.pmos else P_TYPE
        plus = P_PLUS if d.pmos else N_PLUS
        # Cuerpo y aislamiento
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(body)))
        p.drawRect(QRectF(x0, top, width, bottom - top))
        sti_w = width * 0.045
        p.setBrush(QBrush(QColor(STI)))
        p.drawRect(QRectF(x0, top, sti_w, sd_h * 1.25))
        p.drawRect(QRectF(x1 - sti_w, top, sti_w, sd_h * 1.25))
        # Fuente y drenador
        p.setBrush(QBrush(QColor(plus)))
        left = QRectF(x0 + sti_w, top, sd_w - sti_w, sd_h)
        right = QRectF(x1 - sd_w, top, sd_w - sti_w, sd_h)
        for r in (left, right):
            path = QPainterPath()
            path.addRoundedRect(r.adjusted(0, -6, 0, 0), 10, 10)
            p.drawPath(path)
        # Capa de inversión (canal)
        channel = QRectF(left.right() - 4, top, right.left() - left.right() + 8.0, 6)
        if d.state is Conduction.ON:
            p.setBrush(QBrush(QColor(plus)))
            p.drawRect(channel)
        elif d.state is Conduction.UNKNOWN:
            p.setBrush(QBrush(alpha(t.unknown, 160)))
            p.drawRect(channel)
        # Óxido y compuerta
        p.setBrush(QBrush(QColor(OXIDE)))
        p.drawRect(QRectF(g0, top - ox, g1 - g0, ox))
        p.setBrush(QBrush(QColor(POLY)))
        gate = QRectF(g0, top - ox - gate_h, g1 - g0, gate_h)
        p.drawRect(gate)
        # Contactos de metal y terminales
        p.setBrush(QBrush(QColor(METAL)))
        for cx in (left.center().x(), right.center().x(), gate.center().x()):
            p.drawRect(
                QRectF(cx - 5, 18, 10, (gate.top() if cx == gate.center().x() else top) - 18)
            )
        # Cargas: en la compuerta y en el canal
        p.setFont(bold)
        gate_sign = "+" if not d.pmos else "−"
        carrier = "−" if not d.pmos else "+"
        if d.state is Conduction.ON:
            p.setPen(pen("#ffffff", 1))
            for k in range(5):
                cx = gate.left() + (k + 0.5) * gate.width() / 5
                p.drawText(
                    QRectF(cx - 6, gate.top() + 2, 12, gate_h - 4),
                    Qt.AlignmentFlag.AlignCenter,
                    gate_sign,
                )
            self._carriers(p, d, channel, carrier)
        # Etiquetas de los terminales
        self._terminal(p, t, left.center().x(), "S", d.source, d.source_value, small)
        self._terminal(p, t, right.center().x(), "D", d.drain, d.drain_value, small)
        self._terminal(p, t, gate.center().x(), "G", d.gate, d.gate_value, small)
        # Nombres de las regiones
        p.setFont(small)
        p.setPen(pen("#1b1d22", 1))
        sd = "p+" if d.pmos else "n+"
        p.drawText(
            left.adjusted(0, 4, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, sd
        )
        p.drawText(
            right.adjusted(0, 4, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            sd,
        )
        p.setPen(pen("#ffffff", 1))
        p.drawText(
            gate, Qt.AlignmentFlag.AlignCenter, "" if d.state is Conduction.ON else "polisilicio"
        )
        p.setPen(pen("#1b1d22", 1))
        body_name = "pozo n (cuerpo a VDD)" if d.pmos else "sustrato p (cuerpo a GND)"
        p.drawText(QRectF(x0, bottom - 22, width, 18), Qt.AlignmentFlag.AlignCenter, body_name)
        oxide_label = QRectF(g0, top + 8.0, g1 - g0, 14)
        p.drawText(oxide_label, Qt.AlignmentFlag.AlignCenter, self._channel_text(d))
        p.setPen(pen(t.muted, 1))
        p.drawText(
            QRectF(0, h - 18, w, 16), Qt.AlignmentFlag.AlignCenter, "corte ilustrativo, no a escala"
        )
        p.end()

    def _channel_text(self, d: Device) -> str:
        if d.state is Conduction.ON:
            kind = "electrones" if not d.pmos else "huecos"
            return f"canal de {kind}"
        if d.state is Conduction.UNKNOWN:
            return "canal incierto"
        return "sin canal"

    def _carriers(self, p: QPainter, d: Device, channel: QRectF, sign: str) -> None:
        """Portadores en la capa de inversión. Se desplazan solo si hay corriente."""
        p.setPen(Qt.PenStyle.NoPen)
        n = 9
        direction = 0.0
        if self.flowing and d.source_value != d.drain_value:
            # La corriente va del nodo en 1 al nodo en 0; los electrones, al revés.
            current_right = d.source_value is Logic.ONE
            moves_right = current_right if d.pmos else not current_right
            direction = 1.0 if moves_right else -1.0
        for k in range(n):
            f = (k / n + direction * self._phase) % 1.0
            jitter = 0.6 * ((k * 37) % 5 - 2) * (0.5 if direction == 0 else 0)
            x = channel.left() + 6 + f * (channel.width() - 12) + jitter
            y = channel.center().y()
            p.setBrush(QBrush(QColor("#ffffff")))
            p.drawEllipse(QPointF(x, y), 2.4, 2.4)
            p.setBrush(QBrush(QColor("#1b1d22")))
            if sign == "−":
                p.drawRect(QRectF(x - 1.4, y - 0.4, 2.8, 0.8))
            else:
                p.drawRect(QRectF(x - 1.4, y - 0.4, 2.8, 0.8))
                p.drawRect(QRectF(x - 0.4, y - 1.4, 0.8, 2.8))

    def _terminal(
        self,
        p: QPainter,
        t: th.Theme,
        x: float,
        tag: str,
        name: str,
        value: Logic,
        font: QFont,
    ) -> None:
        color = t.logic(value)
        text = f"{tag}: {name} = {logic_text(value)}"
        fm = QFontMetricsF(font)
        w = fm.horizontalAdvance(text) + 10
        x = min(max(x, w / 2 + 2), self.width() - w / 2 - 2)
        box = QRectF(x - w / 2, 0, w, 17)
        p.setPen(pen(color, 1.2))
        p.setBrush(QBrush(alpha(color, 30)))
        p.drawRoundedRect(box, 4, 4)
        p.setFont(font)
        p.setPen(pen(color, 1))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


def explain(d: Device) -> str:
    """Texto que explica el estado del transistor en términos físicos y lógicos."""
    kind = "pMOS" if d.pmos else "nMOS"
    on_value = "0" if d.pmos else "1"
    g = logic_text(d.gate_value)
    if d.state is Conduction.UNKNOWN:
        return (
            f"La compuerta vale {g}: no se sabe si el canal se forma, así que el simulador "
            "marca el transistor como incierto."
        )
    if d.state is Conduction.OFF:
        return (
            f"Un {kind} conduce con la compuerta en {on_value}; aquí vale {g}. No se forma "
            "canal: fuente y drenador quedan aislados (interruptor abierto)."
        )
    field = (
        "La compuerta está a VDD y atrae electrones bajo el óxido"
        if not d.pmos
        else "La compuerta está a GND, por debajo del cuerpo (VDD), y atrae huecos bajo el óxido"
    )
    if d.source_value == d.drain_value:
        rest = (
            f"Fuente y drenador valen {logic_text(d.source_value)}: no hay diferencia de "
            "potencial, así que en reposo no circula corriente."
        )
    else:
        rest = "Fuente y drenador tienen valores distintos: circula corriente por el canal."
    return f"{field}: se forma el canal y el transistor conduce (interruptor cerrado). {rest}"


__all__ = ["CrossSection", "Device", "explain"]
