"""Interfaz gráfica de escritorio con PySide6 (responsable: Yenny). ADR-0011.

Requiere el extra ``gui`` (``make install-gui``). Ver ``ui/gui/GUIA.md``.
"""

from __future__ import annotations


def create_window() -> object:
    """Construye la ventana principal (``QMainWindow``) sin mostrarla.

    El título contiene "TranSim754". Separar la construcción de ``main`` permite
    probarla sin bucle de eventos (``QT_QPA_PLATFORM=offscreen``).
    """
    raise NotImplementedError("pendiente: #25")


def main() -> int:
    """Abre la ventana principal y entra al bucle de eventos; devuelve el código de salida.

    Ventana: entrada de dos operandos (decimal o hex) y del formato; operación; vista de
    bits signo/exponente/fracción de operandos y resultado; flags; etapas de la
    operación (buses ``dbg_``); conteo de transistores y conmutaciones; pestaña para
    cargar y ejecutar programas ``.t754`` paso a paso.
    """
    raise NotImplementedError("pendiente: #25")
