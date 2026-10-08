"""Valores lógicos y fuerzas del simulador switch-level (ADR-0007).

Un nodo del circuito tiene en cada instante un valor lógico de ``{0, 1, X, Z}``.
Cuando varias fuentes alcanzan un nodo, gana la de mayor fuerza:
``SUPPLY`` (rieles VDD/GND) > ``DRIVEN`` (entradas externas) > ``CHARGE`` (carga
retenida por un nodo aislado).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum


class Logic(IntEnum):
    """Valor lógico de un nodo."""

    ZERO = 0
    ONE = 1
    X = 2  # desconocido o en conflicto
    Z = 3  # alta impedancia: sin fuente y sin carga conocida

    @property
    def is_known(self) -> bool:
        """True si el valor es 0 o 1."""
        return self <= Logic.ONE

    def __str__(self) -> str:
        return "01XZ"[self]


class Strength(IntEnum):
    """Fuerza de una señal; un valor mayor domina a uno menor."""

    NONE = 0
    CHARGE = 1
    DRIVEN = 2
    SUPPLY = 3


@dataclass(frozen=True, slots=True)
class Signal:
    """Par (valor, fuerza) que aporta una fuente a un nodo."""

    value: Logic
    strength: Strength


LogicLike = Logic | int | bool | str
"""Tipos aceptados donde se espera un valor lógico: ``Logic``, 0/1, bool o '0'/'1'/'X'/'Z'."""

_POR_TEXTO = {"0": Logic.ZERO, "1": Logic.ONE, "X": Logic.X, "Z": Logic.Z}


def to_logic(value: LogicLike) -> Logic:
    """Convierte ``value`` a :class:`Logic`.

    Raises:
        ValueError: si el valor no representa un nivel lógico.
    """
    if isinstance(value, Logic):
        return value
    if isinstance(value, bool):
        return Logic.ONE if value else Logic.ZERO
    if isinstance(value, int):
        if value in (0, 1):
            return Logic(value)
        raise ValueError(f"valor lógico inválido: {value!r} (se esperaba 0 o 1)")
    if isinstance(value, str) and value.upper() in _POR_TEXTO:
        return _POR_TEXTO[value.upper()]
    raise ValueError(f"valor lógico inválido: {value!r}")


def resolve(sources: Iterable[Signal]) -> Signal:
    """Combina las señales que alcanzan un mismo grupo de nodos.

    Gana la fuerza máxima presente. Si todas las señales de esa fuerza tienen el mismo
    valor conocido, ese es el resultado; si hay 0 y 1, o alguna X, el resultado es X.
    Sin fuentes, el resultado es Z con fuerza ``NONE``.
    """
    top = Strength.NONE
    values: set[Logic] = set()
    for s in sources:
        if s.strength > top:
            top = s.strength
            values = {s.value}
        elif s.strength == top and top != Strength.NONE:
            values.add(s.value)
    if top == Strength.NONE:
        return Signal(Logic.Z, Strength.NONE)
    if len(values) == 1:
        (only,) = values
        if only.is_known:
            return Signal(only, top)
    return Signal(Logic.X, top)
