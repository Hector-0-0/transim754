"""Ensamblador de texto ``.t754`` a binario (responsable: Héctor). ADR-0010, docs/04 §5."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from transim.cpu import isa
from transim.cpu.isa import Instruction, Opcode
from transim.fpu.format import BINARY32, FloatFormat
from transim.reference.fpu import from_decimal

WORD_BYTES = isa.WORD_BITS // 8
_REGISTRO = re.compile(r"^[fF]([0-9]+)$")


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


@dataclass(frozen=True)
class _Token:
    text: str
    column: int  # 1-based


def _operandos(n: int) -> str:
    return "1 operando" if n == 1 else f"{n} operandos"


def _sin_comentario(linea: str) -> str:
    """Corta la línea en el primer ``;`` o ``#``."""
    cortes = [i for i in (linea.find(";"), linea.find("#")) if i >= 0]
    return linea[: min(cortes)] if cortes else linea


def _tokens(linea: str) -> tuple[_Token, list[_Token]] | None:
    """Separa el mnemónico y los operandos (separados por comas) con sus columnas."""
    texto = _sin_comentario(linea)
    m = re.match(r"\s*(\S+)", texto)
    if m is None:
        return None
    mnemonico = _Token(m.group(1), m.start(1) + 1)
    resto = texto[m.end(1) :]
    base = m.end(1)
    if not resto.strip():
        return mnemonico, []
    operandos: list[_Token] = []
    inicio = 0
    for parte in resto.split(","):
        sin_izq = parte.lstrip()
        columna = base + inicio + (len(parte) - len(sin_izq)) + 1
        operandos.append(_Token(sin_izq.rstrip(), columna))
        inicio += len(parte) + 1
    return mnemonico, operandos


class _Ensamblador:
    def __init__(self, filename: str, fmt: FloatFormat) -> None:
        self.filename = filename
        self.fmt = fmt
        self.linea = 0

    def error(self, columna: int, mensaje: str) -> AssemblyError:
        return AssemblyError(self.filename, self.linea, columna, mensaje)

    def registro(self, tok: _Token) -> int:
        m = _REGISTRO.match(tok.text)
        if not tok.text:
            raise self.error(tok.column, "falta un operando")
        if m is None or int(m.group(1)) >= isa.N_REGS:
            raise self.error(
                tok.column, f"registro desconocido {tok.text!r} (se esperaba F0–F{isa.N_REGS - 1})"
            )
        return int(m.group(1))

    def literal(self, tok: _Token) -> int:
        texto = tok.text
        if not texto:
            raise self.error(tok.column, "falta el literal de LI")
        if texto.lower().startswith("0x"):
            try:
                valor = int(texto, 16)
            except ValueError:
                raise self.error(tok.column, f"literal hexadecimal inválido {texto!r}") from None
            if valor >> self.fmt.width:
                raise self.error(tok.column, f"{texto} no cabe en {self.fmt.width} bits")
            return valor
        cuerpo = texto.lstrip("+-").lower()
        if cuerpo not in ("inf", "infinity", "nan"):
            try:
                Fraction(cuerpo)
            except (ValueError, ZeroDivisionError):
                raise self.error(tok.column, f"literal inválido {texto!r}") from None
        return from_decimal(self.fmt, texto).bits

    def instruccion(self, mnemonico: _Token, operandos: list[_Token]) -> list[int]:
        try:
            opcode = Opcode[mnemonico.text.upper()]
        except KeyError:
            raise self.error(
                mnemonico.column, f"instrucción desconocida {mnemonico.text!r}"
            ) from None
        esperados = isa.OPERANDS[opcode]
        if len(operandos) < len(esperados):
            raise self.error(
                mnemonico.column,
                f"{opcode.name} requiere {_operandos(len(esperados))} ({', '.join(esperados)}); "
                f"se dieron {len(operandos)}",
            )
        if len(operandos) > len(esperados):
            extra = operandos[len(esperados)]
            raise self.error(
                extra.column,
                f"{opcode.name} requiere {_operandos(len(esperados))}; sobra {extra.text!r}",
            )
        campos: dict[str, int] = {}
        literal: int | None = None
        for nombre, tok in zip(esperados, operandos, strict=True):
            if nombre == "lit":
                literal = self.literal(tok)
            else:
                campos[nombre] = self.registro(tok)
        palabras = [isa.encode(Instruction(opcode, **campos))]
        if literal is not None:
            palabras.append(literal)
        return palabras


def assemble(source: str, *, filename: str = "<entrada>", fmt: FloatFormat = BINARY32) -> list[int]:
    """Ensambla un programa ``.t754`` en palabras de 32 bits.

    Reglas (docs/04 §5): una instrucción por línea; comentarios con ``;`` o ``#``;
    mayúsculas y minúsculas indistintas; operandos separados por comas; el literal de
    ``LI`` es decimal o fracción exacta (``1.5``, ``-2e-3``, ``1/3``, ``inf``, ``nan``),
    redondeado con RNE mediante ``reference.fpu.from_decimal``, o hexadecimal ``0x…``
    (bits tal cual).

    Raises:
        AssemblyError: ante el primer error, con línea y columna.
    """
    ens = _Ensamblador(filename, fmt)
    palabras: list[int] = []
    for numero, linea in enumerate(source.splitlines(), 1):
        ens.linea = numero
        partes = _tokens(linea)
        if partes is None:
            continue
        palabras.extend(ens.instruccion(*partes))
    return palabras


def to_bytes(words: list[int]) -> bytes:
    """Serializa palabras de 32 bits en big-endian."""
    return b"".join(w.to_bytes(WORD_BYTES, "big") for w in words)


def from_bytes(data: bytes) -> list[int]:
    """Inversa de :func:`to_bytes`.

    Raises:
        ValueError: si la longitud no es múltiplo de 4.
    """
    if len(data) % WORD_BYTES:
        raise ValueError(f"la longitud ({len(data)} bytes) no es múltiplo de {WORD_BYTES}")
    return [
        int.from_bytes(data[i : i + WORD_BYTES], "big") for i in range(0, len(data), WORD_BYTES)
    ]


def disassemble(words: list[int]) -> list[str]:
    """Una línea de ensamblador por instrucción (``LI`` muestra el literal en hex)."""
    lineas: list[str] = []
    i = 0
    digitos = isa.WORD_BITS // 4
    while i < len(words):
        instr = isa.decode(words[i])
        if instr.opcode is Opcode.LI:
            literal = words[i + 1] if i + 1 < len(words) else 0
            lineas.append(f"LI F{instr.rd}, 0x{literal:0{digitos}X}")
        else:
            lineas.append(str(instr))
        i += instr.words
    return lineas
