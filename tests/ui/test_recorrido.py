"""Recorrido paso a paso (sin Qt): pasos, valores leídos de la simulación y textos."""

from __future__ import annotations

import pytest

from transim.fpu.format import BINARY16, BINARY32, FloatFormat
from transim.reference import fpu as ref
from transim.ui.gui import model
from transim.ui.gui import walkthrough as wt


def recorrido(fmt: FloatFormat, op: str, a: str, b: str) -> wt.Walkthrough:
    calc = model.calculate(
        fmt, op, model.parse_operand(a, fmt), model.parse_operand(b, fmt), "cached"
    )
    assert calc.matches
    return wt.build(calc)


def paso(w: wt.Walkthrough, key: str) -> wt.Step:
    return next(s for s in w.steps if s.key == key)


def test_suma_de_la_exposicion() -> None:
    w = recorrido(BINARY32, "add", "1.5", "2.25")
    assert w.narrated
    assert w.expression == "1.5 + 2.25 = 3.75"
    assert w.inputs == ("a = 1.5", "b = 2.25")
    assert w.result == "3.75"
    assert [s.title for s in w.steps] == [
        "Desempaquetar",
        "Comparar magnitudes",
        "Restar exponentes",
        "Alinear mantisa",
        "Sumar mantisas",
        "Contar ceros",
        "Normalizar",
        "Redondear y empaquetar",
        "Casos especiales",
    ]
    assert "mantisa 1.1₂" in paso(w, "unpack_a").detail
    assert "mantisa 1.001₂" in paso(w, "unpack_a").detail
    assert paso(w, "order").summary == "X = b (intercambia)"
    assert paso(w, "exp_diff").summary == "d = 1"
    alinear = paso(w, "align").detail
    assert "1.10₂" in alinear
    assert "0.11₂" in alinear
    assert paso(w, "mant_addsub").detail.splitlines()[-1] == "  = 01.111₂"
    assert paso(w, "lzc").summary == "lz = 1"
    assert "128 + 1 − 1 = 128" in paso(w, "normalize").detail
    assert paso(w, "round").summary == "exacto"
    assert "0x40700000" in paso(w, "special").detail
    assert "flags: ninguno" in paso(w, "special").detail


def test_resta_con_signos_distintos() -> None:
    w = recorrido(BINARY32, "sub", "1", "0.75")
    s = paso(w, "mant_addsub")
    assert s.title == "Restar mantisas"
    assert "− Y" in s.detail
    assert "se invierte el signo de b" in paso(w, "unpack_a").text
    assert paso(w, "lzc").summary == "lz = 3"  # la resta canceló bits


def test_redondeo_inexacto() -> None:
    w = recorrido(BINARY32, "add", "1/3", "0.1")
    r = paso(w, "round")
    assert r.summary in ("trunca", "redondea ↑")
    assert "inexacto (NX): sí" in r.detail
    assert "flags: NX" in paso(w, "special").detail


def test_resultado_cero() -> None:
    w = recorrido(BINARY32, "sub", "1", "1")
    assert paso(w, "lzc").detail.endswith("→ el resultado es cero")
    assert paso(w, "normalize").summary == "resultado 0"


def test_caso_especial_avisa_en_los_pasos_numericos() -> None:
    w = recorrido(BINARY32, "add", "inf", "-inf")
    assert "todo en 1 (∞ o NaN)" in paso(w, "unpack_a").detail
    assert "se descarta" in paso(w, "align").text
    assert "manda la tabla" in paso(w, "special").detail
    assert "flags: NV" in paso(w, "special").detail


def test_overflow() -> None:
    w = recorrido(BINARY32, "add", "3.4e38", "3.4e38")
    assert "OF" in paso(w, "round").detail


@pytest.mark.parametrize("fmt", [BINARY32, BINARY16])
def test_el_resultado_del_recorrido_es_el_de_la_referencia(fmt: FloatFormat) -> None:
    for ej in model.EXAMPLES:
        if ej.op not in ("add", "sub"):
            continue
        a, b = ej.operands(fmt)
        w = recorrido(fmt, ej.op, a, b)
        x, y = model.parse_operand(a, fmt), model.parse_operand(b, fmt)
        esperado = (ref.fadd if ej.op == "add" else ref.fsub)(fmt, x, y)
        assert w.result == model.value_text(fmt, esperado.bits)
        assert all(s.summary != "X" for s in w.steps), ej.title


def test_cada_bloque_esta_en_un_solo_paso() -> None:
    netlist = model.unit_for(BINARY32, "add", "cached").netlist
    bloques = {i.path for i in netlist.top_instances() if not i.is_leaf}
    pasos = [p for _, paths, _ in wt.ADDSUB for p in paths]
    assert sorted(pasos) == sorted(bloques)


def test_enlaces_entre_pasos_siguen_el_datapath() -> None:
    w = recorrido(BINARY32, "add", "1.5", "2.25")
    k = {s.key: n for n, s in enumerate(w.steps)}
    assert k["exp_diff"] in w.steps[k["order"]].targets
    assert k["align"] in w.steps[k["mant_addsub"]].sources
    assert w.steps[k["unpack_a"]].sources == ()


def test_multiplicacion_explicada() -> None:
    w = recorrido(BINARY32, "mul", "1.5", "2.25")
    assert w.narrated
    assert [s.title for s in w.steps] == [
        "Desempaquetar",
        "Multiplicar mantisas",
        "Contar ceros",
        "Normalizar",
        "Redondear y empaquetar",
        "Casos especiales",
    ]
    assert "signo = 0 ⊕ 0 = 0" in paso(w, "unpack_a").detail
    assert paso(w, "mant_mul").detail.splitlines()[-1] == "  = 01.1011₂"
    assert paso(w, "lzc").summary == "lz = 1"
    assert "127 + 128 − 127 + 1 − 1 = 128" in paso(w, "normalize").detail
    assert "0x40580000" in paso(w, "special").detail


def test_division_explicada() -> None:
    w = recorrido(BINARY32, "div", "1", "3")
    assert w.narrated
    assert [s.title for s in w.steps] == [
        "Desempaquetar",
        "Normalizar operandos",
        "Dividir mantisas",
        "Redondear y empaquetar",
        "Casos especiales",
    ]
    cociente = paso(w, "mant_div").detail
    assert "0.10101010" in cociente
    assert "sticky = 1" in cociente
    assert "127 − 128 + 127 − 1 + 0 = 125" in cociente
    assert paso(w, "round").summary == "redondea ↑"
    assert "0x3EAAAAAB" in paso(w, "special").detail


def test_division_por_cero_y_subnormal() -> None:
    w = recorrido(BINARY32, "div", "1", "0")
    assert "cero o subnormal" in paso(w, "unpack_a").detail
    assert "se descarta" in paso(w, "mant_div").text
    assert "flags: DZ" in paso(w, "special").detail
    m = recorrido(BINARY32, "mul", "1e-40", "2")
    assert int(paso(m, "lzc").summary.split("= ")[1]) > 1  # subnormal: más ceros


@pytest.mark.parametrize("fmt", [BINARY32, BINARY16])
def test_ejemplos_de_mul_y_div_sin_valores_indefinidos(fmt: FloatFormat) -> None:
    for ej in model.EXAMPLES:
        if ej.op not in ("mul", "div"):
            continue
        a, b = ej.operands(fmt)
        w = recorrido(fmt, ej.op, a, b)
        assert w.narrated
        assert all(s.summary != "X" for s in w.steps), ej.title
        netlist = model.unit_for(fmt, ej.op, "cached").netlist
        bloques = {i.path for i in netlist.top_instances() if not i.is_leaf}
        assert {p for s in w.steps for p in s.paths} == bloques


def test_los_valores_se_copian_al_construir() -> None:
    w = recorrido(BINARY32, "add", "1.5", "2.25")
    recorrido(BINARY32, "add", "100", "7")  # la misma unidad calcula otra cosa
    assert paso(w, "exp_diff").summary == "d = 1"


def test_texto_binario_alineado() -> None:
    assert wt.fixed([0b1100, 0b0110], 4, 1) == ["1.10₂", "0.11₂"]
    assert wt.fixed([0], 4, 2) == ["00.0₂"]
