"""Ensamblador de texto ``.t754`` a binario (responsable: Héctor). ADR-0010, docs/04 §5."""

from __future__ import annotations

from dataclasses import dataclass

from transim.fpu.format import BINARY32, FloatFormat


@dataclass
class AssemblyError(ValueError):
    """Error de ensamblado con posición exacta.

    ``str(error)`` produce ``"archivo:línea:columna: mensaje"``.
    """

    filename: str
    line: int
    column: int
    message: str

    def __str__(self) -> str:
        return f"{self.filename}:{self.line}:{self.column}: {self.message}"


def assemble(source: str, *, filename: str = "<entrada>", fmt: FloatFormat = BINARY32) -> list[int]:
    """Ensambla un programa ``.t754`` en palabras de 32 bits.

    Reglas (docs/04 §5): una instrucción por línea; comentarios con ``;`` o ``#``;
    mayúsculas y minúsculas indistintas; operandos separados por comas; el literal de
    ``LI`` es decimal (redondeado con RNE mediante ``reference.fpu.from_decimal``) o
    hexadecimal ``0x…`` (bits tal cual).

    Raises:
        AssemblyError: ante el primer error, con línea y columna.
    """
    raise NotImplementedError("pendiente: #29")


def to_bytes(words: list[int]) -> bytes:
    """Serializa palabras de 32 bits en big-endian."""
    raise NotImplementedError("pendiente: #29")


def from_bytes(data: bytes) -> list[int]:
    """Inversa de :func:`to_bytes`.

    Raises:
        ValueError: si la longitud no es múltiplo de 4.
    """
    raise NotImplementedError("pendiente: #29")


def disassemble(words: list[int]) -> list[str]:
    """Una línea de ensamblador por instrucción (``LI`` muestra el literal en hex)."""
    raise NotImplementedError("pendiente: #29")
