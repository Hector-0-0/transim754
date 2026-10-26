"""GUI de escritorio con PySide6 (ADR-0011, ADR-0015): operación, transistores y programas.

- ``app``: ventana principal, menús, tema y ``main``.
- ``operation_tab``, ``transistor_tab``, ``program_tab``: las tres pestañas.
- ``model``: cálculos y textos sin Qt (operaciones, ciclos, ejemplos).
- ``circuit``, ``schematic``, ``silicon``: análisis de celdas, esquema y layout, sin Qt.
- ``canvas``, ``cross_section``, ``widgets``, ``theme``, ``worker``: dibujo e interfaz.
"""
