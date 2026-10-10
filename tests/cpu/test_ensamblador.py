"""Ensamblador .t754 (responsable: Héctor). Issue #29."""

from __future__ import annotations

import pytest

from cpu.programas import EJEMPLOS, PROGRAMAS
from transim.cpu.assembler import AssemblyError, assemble, disassemble, from_bytes, to_bytes


@pytest.mark.parametrize("nombre", sorted(PROGRAMAS))
def test_ejemplos_ensamblan_al_codigo_esperado(nombre: str) -> None:
    fuente = (EJEMPLOS / f"{nombre}.t754").read_text(encoding="utf-8")
    assert assemble(fuente, filename=f"{nombre}.t754") == PROGRAMAS[nombre][0]


def test_mayusculas_comentarios_y_espacios() -> None:
    assert assemble("  fadd f3,f1 ,  F2   # comentario\n\n; otro\nhalt") == [0x10650000, 0xFF000000]


@pytest.mark.parametrize(
    ("literal", "bits"),
    [("1.5", 0x3FC00000), ("-0", 0x80000000), ("0x7F800001", 0x7F800001), ("-inf", 0xFF800000),
     ("nan", 0x7FC00000), ("0.1", 0x3DCCCCCD), ("1e-45", 0x00000001)],
)  # fmt: skip
def test_literales_de_li(literal: str, bits: int) -> None:
    assert assemble(f"LI F7, {literal}") == [0x01E00000, bits]


@pytest.mark.parametrize(
    ("fuente", "linea", "columna", "texto"),
    [
        ("NOP\n; c\nFADD F1, F9, F2\n", 3, 10, "F9"),
        ("FOO F1\n", 1, 1, "FOO"),
        ("HALT\nFADD F1, F2\n", 2, 1, "operandos"),
        ("MOV F1, F2, F3\n", 1, 13, "operandos"),
        ("LI F1, uno\n", 1, 8, "uno"),
        ("LI F1, 0x1FFFFFFFF\n", 1, 8, "32 bits"),
    ],
)
def test_errores_con_linea_y_columna(fuente: str, linea: int, columna: int, texto: str) -> None:
    with pytest.raises(AssemblyError) as info:
        assemble(fuente, filename="prog.t754")
    err = info.value
    assert (err.line, err.column) == (linea, columna)
    assert texto in err.message
    assert str(err).startswith(f"prog.t754:{linea}:{columna}: ")


def test_binario_big_endian_ida_y_vuelta() -> None:
    palabras = PROGRAMAS["horner"][0]
    datos = to_bytes(palabras)
    assert datos[:4] == bytes([0x01, 0x20, 0x00, 0x00])  # LI F1 en big-endian
    assert from_bytes(datos) == palabras
    with pytest.raises(ValueError, match="4"):
        from_bytes(b"\x00\x01\x02")


def test_desensamblado() -> None:
    lineas = disassemble(PROGRAMAS["suma_simple"][0])
    assert lineas[0] == "LI F1, 0x3FC00000"
    assert lineas[2] == "FADD F3, F1, F2"
    assert lineas[-1] == "HALT"
    assert assemble("\n".join(lineas)) == PROGRAMAS["suma_simple"][0]
