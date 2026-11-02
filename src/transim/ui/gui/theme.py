"""Tema visual de la interfaz: paleta clara y oscura, hoja de estilo y colores del dibujo.

La interfaz usa el estilo Fusion con su propia paleta, así se ve igual en cualquier
escritorio. Arranca en oscuro (ADR-0019); en el modo completo, el menú Ver permite
cambiarlo. Los colores de los valores lógicos son los mismos en todas las vistas:
1 rojo, 0 azul, X ámbar, Z gris; un canal que conduce es verde.
"""

from __future__ import annotations

import atexit
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPalette, QPolygonF
from PySide6.QtWidgets import QApplication

from transim.core.signals import Logic
from transim.core.transistor import Conduction


@dataclass(frozen=True)
class Theme:
    """Colores con nombre de un tema."""

    name: str
    dark: bool
    window: str
    surface: str
    surface_alt: str
    border: str
    text: str
    muted: str
    accent: str
    accent_text: str
    hover: str
    # Valores lógicos y canales
    one: str
    zero: str
    unknown: str
    floating: str
    on: str
    off: str
    # Lienzo del esquema
    paper: str
    grid: str
    ink: str
    frame: str
    halo: str
    select: str
    # Bits de IEEE 754
    sign: str
    exponent: str
    fraction: str
    # Avisos
    good: str
    warn: str
    bad: str

    def logic(self, value: Logic) -> QColor:
        """Color de un valor lógico."""
        return QColor(
            {
                Logic.ONE: self.one,
                Logic.ZERO: self.zero,
                Logic.X: self.unknown,
                Logic.Z: self.floating,
            }[value]
        )

    def channel(self, state: Conduction) -> QColor:
        """Color del canal de un transistor según conduzca o no."""
        return QColor(
            {Conduction.ON: self.on, Conduction.OFF: self.off, Conduction.UNKNOWN: self.unknown}[
                state
            ]
        )


LIGHT = Theme(
    name="claro",
    dark=False,
    window="#f3f4f7",
    surface="#ffffff",
    surface_alt="#f7f8fa",
    border="#d8dce3",
    text="#1d2127",
    muted="#5d6673",
    accent="#4f46e5",
    accent_text="#ffffff",
    hover="#eceefe",
    one="#d93025",
    zero="#1a66d9",
    unknown="#d97706",
    floating="#8a929c",
    on="#16a34a",
    off="#aab1bb",
    paper="#ffffff",
    grid="#e8ebf0",
    ink="#2a2f37",
    frame="#cfd4dc",
    halo="#f8c51c",
    select="#4f46e5",
    sign="#e11d48",
    exponent="#2563eb",
    fraction="#059669",
    good="#15803d",
    warn="#b45309",
    bad="#b91c1c",
)

DARK = Theme(
    name="oscuro",
    dark=True,
    window="#16171b",
    surface="#1e2025",
    surface_alt="#24272d",
    border="#353943",
    text="#e7e9ed",
    muted="#a0a7b3",
    accent="#8b8cf7",
    accent_text="#101114",
    hover="#2a2c3d",
    one="#ff6a5c",
    zero="#5aa2ff",
    unknown="#ffb020",
    floating="#8f96a1",
    on="#3ddc84",
    off="#5b616c",
    paper="#121317",
    grid="#20232a",
    ink="#cfd4dc",
    frame="#3a3f49",
    halo="#f2c230",
    select="#a5a6ff",
    sign="#fb7185",
    exponent="#60a5fa",
    fraction="#34d399",
    good="#4ade80",
    warn="#fbbf24",
    bad="#f87171",
)

THEMES = {"claro": LIGHT, "oscuro": DARK}

_current: Theme = LIGHT


def current() -> Theme:
    """Tema activo."""
    return _current


def system_prefers_dark() -> bool:
    """True si el escritorio está en modo oscuro (Qt ≥ 6.5)."""
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    if scheme is None:
        return False
    return bool(scheme() == Qt.ColorScheme.Dark)


def apply(app: QApplication, theme: Theme) -> None:
    """Aplica ``theme`` a toda la aplicación (paleta Fusion y hoja de estilo)."""
    global _current
    _current = theme
    app.setStyle("Fusion")
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: theme.window,
        QPalette.ColorRole.WindowText: theme.text,
        QPalette.ColorRole.Base: theme.surface,
        QPalette.ColorRole.AlternateBase: theme.surface_alt,
        QPalette.ColorRole.Text: theme.text,
        QPalette.ColorRole.Button: theme.surface,
        QPalette.ColorRole.ButtonText: theme.text,
        QPalette.ColorRole.Highlight: theme.accent,
        QPalette.ColorRole.HighlightedText: theme.accent_text,
        QPalette.ColorRole.ToolTipBase: theme.surface,
        QPalette.ColorRole.ToolTipText: theme.text,
        QPalette.ColorRole.PlaceholderText: theme.muted,
        QPalette.ColorRole.Link: theme.accent,
        QPalette.ColorRole.Mid: theme.border,
        QPalette.ColorRole.Midlight: theme.surface_alt,
        QPalette.ColorRole.Dark: theme.border,
        QPalette.ColorRole.Light: theme.surface,
        QPalette.ColorRole.Shadow: theme.border,
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(theme.muted))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(theme))


ARROW_W, ARROW_H = 18, 12
"""Tamaño en píxeles de las flechas dibujadas (el doble del que se ve: nítidas en HiDPI)."""

_arrow_dir: Path | None = None


def arrow_images(color: str) -> tuple[str, str]:
    """Rutas de dos PNG con una flecha hacia arriba y otra hacia abajo de ``color``.

    La hoja de estilo reemplaza el dibujo nativo de los cuadros numéricos y de las listas
    desplegables: sin una imagen propia, sus flechas no se ven. Se dibujan una vez por
    color en una carpeta temporal que se borra al salir.
    """
    global _arrow_dir
    if _arrow_dir is None:
        _arrow_dir = Path(tempfile.mkdtemp(prefix="transim754-"))
        atexit.register(shutil.rmtree, _arrow_dir, True)
    paths = []
    for name, up in (("up", True), ("down", False)):
        path = _arrow_dir / f"{name}-{color.lstrip('#')}.png"
        if not path.exists():
            img = QImage(ARROW_W, ARROW_H, QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            top, bottom = (1.0, ARROW_H - 1.0) if up else (ARROW_H - 1.0, 1.0)
            p.drawPolygon(
                QPolygonF(
                    [QPointF(ARROW_W / 2, top), QPointF(ARROW_W - 1, bottom), QPointF(1, bottom)]
                )
            )
            p.end()
            img.save(str(path))
        paths.append(path.as_posix())
    return paths[0], paths[1]


def stylesheet(t: Theme) -> str:
    """Hoja de estilo de la aplicación para el tema ``t``."""
    up, down = arrow_images(t.text)
    return f"""
    QMainWindow, QDialog {{ background: {t.window}; }}
    QToolTip {{
        background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
        padding: 6px 8px; border-radius: 6px;
    }}
    QTabWidget::pane {{ border: 0; }}
    QTabBar::tab {{
        background: transparent; color: {t.muted}; padding: 9px 18px; margin-right: 2px;
        border: 0; border-bottom: 2px solid transparent; font-weight: 600;
    }}
    QTabBar::tab:hover {{ color: {t.text}; }}
    QTabBar::tab:selected {{ color: {t.text}; border-bottom: 2px solid {t.accent}; }}
    QTabWidget#subtabs QTabBar::tab {{ padding: 6px 12px; font-weight: 500; }}
    QFrame#card {{
        background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px;
    }}
    QLabel#cardTitle {{ color: {t.muted}; font-weight: 600; letter-spacing: 0.5px; }}
    QLabel#muted {{ color: {t.muted}; }}
    QLabel#bigResult {{ font-size: 22px; font-weight: 700; }}
    QLabel#statValue {{ font-size: 18px; font-weight: 700; }}
    QLabel#statLabel {{ color: {t.muted}; }}
    QLabel#hint {{ color: {t.muted}; font-size: 11px; }}
    QLabel#error {{ color: {t.bad}; font-size: 11px; }}
    QLabel#ok {{ color: {t.good}; font-weight: 600; }}
    QLabel#breadcrumb {{ color: {t.muted}; }}
    QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{
        background: {t.surface}; border: 1px solid {t.border}; border-radius: 7px;
        padding: 5px 8px; selection-background-color: {t.accent};
        selection-color: {t.accent_text};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
        border: 1px solid {t.accent};
    }}
    QLineEdit[invalid="true"] {{ border: 1px solid {t.bad}; }}
    QComboBox::drop-down {{ border: 0; width: 22px; }}
    QComboBox::down-arrow {{ image: url({down}); width: 9px; height: 6px; }}
    QSpinBox {{ padding-right: 24px; }}
    QSpinBox::up-button, QSpinBox::down-button {{
        subcontrol-origin: border; width: 22px; border: 0; background: transparent;
    }}
    QSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 7px; }}
    QSpinBox::down-button {{
        subcontrol-position: bottom right; border-bottom-right-radius: 7px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {t.hover}; }}
    QSpinBox::up-arrow {{ image: url({up}); width: 9px; height: 6px; }}
    QSpinBox::down-arrow {{ image: url({down}); width: 9px; height: 6px; }}
    QPushButton {{
        background: {t.surface}; border: 1px solid {t.border}; border-radius: 7px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{ background: {t.hover}; border-color: {t.accent}; }}
    QPushButton:pressed {{ background: {t.surface_alt}; }}
    QPushButton:disabled {{ color: {t.muted}; background: {t.surface_alt}; }}
    QPushButton#primary {{
        background: {t.accent}; color: {t.accent_text}; border: 0; font-weight: 700;
        padding: 9px 18px;
    }}
    QPushButton#primary:hover {{ background: {t.select}; }}
    QPushButton#primary:disabled {{ background: {t.border}; color: {t.muted}; }}
    QPushButton#segment {{ border-radius: 0; padding: 6px 12px; }}
    QPushButton#segment[position="first"] {{
        border-top-left-radius: 7px; border-bottom-left-radius: 7px;
    }}
    QPushButton#segment[position="last"] {{
        border-top-right-radius: 7px; border-bottom-right-radius: 7px;
    }}
    QPushButton#segment:checked {{
        background: {t.accent}; color: {t.accent_text}; border-color: {t.accent};
    }}
    QPushButton#tool {{ padding: 5px 10px; }}
    QPushButton#chip {{
        border-radius: 12px; padding: 3px 10px; font-size: 11px;
    }}
    QToolButton {{
        background: transparent; border: 1px solid transparent; border-radius: 6px;
        padding: 4px 8px;
    }}
    QToolButton:hover {{ background: {t.hover}; border-color: {t.border}; }}
    QToolButton:checked {{ background: {t.hover}; border-color: {t.accent}; }}
    QPushButton::menu-indicator, QToolButton::menu-indicator {{ image: none; width: 0px; }}
    QTableWidget, QTreeWidget, QListWidget {{
        background: {t.surface}; border: 1px solid {t.border}; border-radius: 8px;
        gridline-color: {t.border}; alternate-background-color: {t.surface_alt};
    }}
    QTreeWidget::item, QListWidget::item {{ padding: 3px 2px; }}
    QTreeWidget::item:hover, QListWidget::item:hover, QTableWidget::item:hover {{
        background: {t.hover};
    }}
    QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {{
        background: {t.accent}; color: {t.accent_text};
    }}
    QHeaderView::section {{
        background: {t.surface_alt}; color: {t.muted}; border: 0;
        border-bottom: 1px solid {t.border}; padding: 5px 6px; font-weight: 600;
    }}
    QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
    QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
    QScrollBar::handle {{ background: {t.border}; border-radius: 4px; min-height: 24px;
        min-width: 24px; }}
    QScrollBar::handle:hover {{ background: {t.muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QSplitter::handle {{ background: {t.window}; }}
    QSplitter::handle:hover {{ background: {t.border}; }}
    QStatusBar {{ background: {t.surface}; color: {t.muted}; border-top: 1px solid {t.border}; }}
    QStatusBar QLabel {{ color: {t.muted}; padding: 0 6px; }}
    QMenuBar {{ background: {t.surface}; border-bottom: 1px solid {t.border}; }}
    QMenuBar::item {{ padding: 5px 10px; background: transparent; border-radius: 5px; }}
    QMenuBar::item:selected {{ background: {t.hover}; }}
    QMenu {{ background: {t.surface}; border: 1px solid {t.border}; padding: 4px; }}
    QMenu::item {{ padding: 6px 22px 6px 22px; border-radius: 5px; }}
    QMenu::item:selected {{ background: {t.hover}; color: {t.text}; }}
    QMenu::separator {{ height: 1px; background: {t.border}; margin: 4px 8px; }}
    QCheckBox {{ spacing: 6px; }}
    QGroupBox {{ border: 0; margin-top: 0; }}
    """


__all__ = [
    "DARK",
    "LIGHT",
    "THEMES",
    "Theme",
    "apply",
    "arrow_images",
    "current",
    "stylesheet",
    "system_prefers_dark",
]
