"""Pruebas de valores lógicos, fuerzas y resolución de señales."""

from __future__ import annotations

import pytest

from transim.core.signals import Logic, Signal, Strength, resolve, to_logic

S, D, C = Strength.SUPPLY, Strength.DRIVEN, Strength.CHARGE
L0, L1, X, Z = Logic.ZERO, Logic.ONE, Logic.X, Logic.Z


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [(0, L0), (1, L1), (True, L1), (False, L0), ("x", X), ("Z", Z), ("1", L1), (L0, L0)],
)
def test_to_logic(entrada: object, esperado: Logic) -> None:
    assert to_logic(entrada) is esperado  # type: ignore[arg-type]


@pytest.mark.parametrize("malo", [2, -1, "a", 0.5])
def test_to_logic_rechaza_valores_invalidos(malo: object) -> None:
    with pytest.raises(ValueError, match="inválido"):
        to_logic(malo)  # type: ignore[arg-type]


def test_str_y_conocidos() -> None:
    assert [str(v) for v in Logic] == ["0", "1", "X", "Z"]
    assert L0.is_known
    assert L1.is_known
    assert not X.is_known
    assert not Z.is_known


@pytest.mark.parametrize(
    ("senales", "esperado"),
    [
        ([], Signal(Z, Strength.NONE)),
        ([Signal(L1, C)], Signal(L1, C)),
        ([Signal(L1, C), Signal(L0, D)], Signal(L0, D)),  # la fuerza mayor domina
        ([Signal(L1, S), Signal(L0, D)], Signal(L1, S)),
        ([Signal(L1, S), Signal(L0, S)], Signal(X, S)),  # conflicto a igual fuerza
        ([Signal(L1, C), Signal(L0, C)], Signal(X, C)),  # reparto de carga distinta
        ([Signal(X, D), Signal(L1, C)], Signal(X, D)),
        ([Signal(L1, D), Signal(L1, D)], Signal(L1, D)),
    ],
)
def test_resolve(senales: list[Signal], esperado: Signal) -> None:
    assert resolve(senales) == esperado
