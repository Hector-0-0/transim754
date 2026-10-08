"""Envoltorio de un circuito combinacional como unidad funcional.

Las unidades de alto nivel (ALU, FPU) se construyen como netlists de transistores; una
:class:`HardwareUnit` las simula con el motor elegido y traduce enteros de Python a
buses y de vuelta. Así las pruebas y la CPU usan una interfaz numérica, pero cada
resultado proviene de la evaluación de transistores.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from transim.core.engine_cached import CachedEngine
from transim.core.engine_switch import InputValue, SwitchEngine
from transim.core.netlist import Netlist

EngineName = Literal["switch", "cached"]


def make_engine(netlist: Netlist, engine: EngineName = "cached") -> SwitchEngine:
    """Crea el motor ``engine`` ("switch" o "cached") para ``netlist``."""
    if engine == "switch":
        return SwitchEngine(netlist, max_events=10 * len(netlist.nodes) + 1000)
    if engine == "cached":
        return CachedEngine(netlist, max_events=10 * len(netlist.nodes) + 1000)
    raise ValueError(f"motor desconocido {engine!r}; use 'switch' o 'cached'")


class HardwareUnit:
    """Unidad funcional respaldada por un netlist.

    Args:
        netlist: circuito combinacional con puertos y buses con nombre.
        engine: motor de simulación ("switch" exacto o "cached").
    """

    def __init__(self, netlist: Netlist, engine: EngineName = "cached") -> None:
        self.netlist = netlist
        self.engine_name = engine
        self.engine = make_engine(netlist, engine)

    def evaluate(self, inputs: Mapping[str, InputValue]) -> dict[str, int | None]:
        """Aplica ``inputs`` y devuelve todas las salidas como enteros.

        Los buses se leen como enteros sin signo (LSB = bit 0) y las salidas sueltas
        como 0/1. Un valor que no es 0/1 (X o Z) se devuelve como None.
        """
        self.engine.set_inputs(inputs)
        nl = self.netlist
        result: dict[str, int | None] = {}
        bus_bits = {n.id for bits in nl.output_buses.values() for n in bits}
        for name in nl.output_buses:
            result[name] = self.engine.read_int(name)
        for name, node in nl.outputs.items():
            if node.id in bus_bits:
                continue
            value = self.engine.value(node)
            result[name] = int(value) if value.is_known else None
        return result

    def transistor_count(self) -> int:
        """Número total de transistores del netlist."""
        return len(self.netlist.transistors)
