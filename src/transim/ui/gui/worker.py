"""Trabajo en segundo plano: los cálculos largos no congelan la ventana."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    """Ejecuta ``fn`` fuera del hilo de la interfaz y emite su resultado o su error.

    Las señales deben conectarse a métodos (no a funciones anónimas) para que Qt las
    entregue en el hilo de la interfaz.
    """

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:  # se informa en la interfaz
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.signals.done.emit(result)


__all__ = ["Task", "TaskSignals"]
