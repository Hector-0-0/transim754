"""Cálculos de la GUI sin Qt: textos de valores, operandos, ejemplos y programas."""

from __future__ import annotations

import random

import pytest

from transim.cpu.assembler import assemble
from transim.fpu.format import BINARY16, BINARY32, FloatFormat
from transim.ui.gui import model


@pytest.mark.parametrize("fmt", [BINARY32, BINARY16])
def test_el_texto_de_un_valor_vuelve_a_los_mismos_bits(fmt: FloatFormat) -> None:
    """``value_text`` da los dígitos justos: al volver a leerlo se obtienen los mismos bits."""
    rnd = random.Random(754)
    casos = [fmt.zero(0), fmt.zero(1), fmt.inf(0), fmt.inf(1), fmt.max_finite(), 1, 2, 3]
    casos += [rnd.getrandbits(fmt.width) for _ in range(1500)]
    for bits in casos:
        if fmt.classify(bits).is_nan:
            continue
        texto = model.value_text(fmt, bits).replace(model.MINUS, "-")
        assert model.parse_operand(texto, fmt) == bits, (hex(bits), texto)


def test_textos_legibles() -> None:
    f = BINARY32
    assert model.value_text(f, model.parse_operand("0.1", f)) == "0.1"
    assert model.value_text(f, 0x80000000) == "−0"
    assert model.value_text(f, f.inf(1)) == "−∞"
    assert model.value_text(BINARY16, BINARY16.max_finite()) == "65504"
    assert model.exact_text(f, model.parse_operand("0.1", f)) == "0.100000001490116119384765625"
    assert "2^0" in model.decode_text(f, 0x3FC00000)
    assert "subnormal" in model.decode_text(f, 1)


@pytest.mark.parametrize("texto", ["", "abc", "1..2", "1/0", "0x1FFFFFFFF", "-0x1"])
def test_operandos_invalidos(texto: str) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - los mensajes se muestran tal cual
        model.parse_operand(texto, BINARY32)


def test_operandos_validos() -> None:
    f = BINARY32
    assert model.parse_operand("1/3", f) == 0x3EAAAAAB
    assert model.parse_operand("−2,5", f) == model.parse_operand("-2.5", f)
    assert model.parse_operand("∞", f) == f.inf(0)
    assert model.parse_operand(" 0x3fc00000 ", f) == 0x3FC00000


@pytest.mark.parametrize("fmt", [BINARY32, BINARY16])
@pytest.mark.parametrize("ejemplo", model.EXAMPLES, ids=lambda e: e.title)
def test_los_ejemplos_coinciden_con_la_referencia(fmt: FloatFormat, ejemplo: model.Example) -> None:
    a, b = ejemplo.operands(fmt)
    calc = model.calculate(
        fmt, ejemplo.op, model.parse_operand(a, fmt), model.parse_operand(b, fmt), "cached"
    )
    assert calc.matches, calc.expression


def test_ejemplos_muestran_cada_flag() -> None:
    vistos = set()
    for ej in model.EXAMPLES:
        a, b = ej.operands(BINARY32)
        calc = model.calculate(
            BINARY32,
            ej.op,
            model.parse_operand(a, BINARY32),
            model.parse_operand(b, BINARY32),
            "cached",
        )
        vistos |= set(str(calc.result.flags).split("|"))
    assert {"NV", "DZ", "OF", "UF", "NX"} <= vistos


def test_lineas_de_cada_instruccion() -> None:
    fuente = "; comentario\nLI F1, 1.5\n\nLI F2, 2\nFADD F3, F1, F2  ; suma\nHALT\n"
    palabras = assemble(fuente)
    assert model.instruction_lines(fuente, palabras) == {0: 2, 2: 4, 4: 5, 5: 6}
