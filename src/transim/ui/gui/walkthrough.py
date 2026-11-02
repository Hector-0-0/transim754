"""Recorrido paso a paso de una operación: sus etapas en el orden del datapath.

Cada paso es una etapa de primer nivel de la unidad (desempaquetar, comparar, alinear…)
con los valores que la simulación dejó en sus entradas y salidas y una explicación en
palabras. La suma y la resta tienen textos propios con las cuentas de la operación; en
la multiplicación y la división los pasos son los bloques de primer nivel en orden de
flujo, con sus entradas y salidas.

El motor no tiene tiempo (ADR-0007): el orden de los pasos es el de la dependencia de
los datos, que es el orden del algoritmo de hardware (ADR-0009), no un orden temporal
medido. Los valores se copian al construir el recorrido; no cambian si la unidad calcula
otra cosa después. Nada de esto cambia la simulación.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from transim.core.netlist import Instance, Netlist
from transim.core.node import Node
from transim.core.signals import Logic
from transim.fpu.format import FloatFormat, FPClass
from transim.metrics.stages import STAGE_NAMES
from transim.ui.gui import model

SUB = "₂"
"""Subíndice de los números en binario."""

Reader = Callable[[Node], Logic]


# ---------------------------------------------------------------- puertos
@dataclass(frozen=True, slots=True)
class Port:
    """Entrada o salida de un bloque con los bits que tenía (el menos significativo primero)."""

    name: str
    bits: tuple[Logic, ...]

    @property
    def value(self) -> int | None:
        """Valor sin signo, o None si algún bit no es 0 ni 1."""
        if any(b not in (Logic.ZERO, Logic.ONE) for b in self.bits):
            return None
        return sum(1 << k for k, b in enumerate(self.bits) if b is Logic.ONE)

    def text(self) -> str:
        """``0`` o ``1`` para un bit; binario (hasta 16 bits) o hexadecimal para un bus."""
        v = self.value
        if v is None:
            return "X"
        n = len(self.bits)
        if n == 1:
            return str(v)
        if n <= 16:
            return format(v, f"0{n}b") + SUB
        return f"0x{v:0{(n + 3) // 4}X}"


def ports(inst: Instance, read: Reader) -> tuple[tuple[Port, ...], tuple[Port, ...]]:
    """Entradas y salidas de una instancia, con los buses agrupados y sus valores."""
    d = inst.definition
    ins: list[Port] = []
    outs: list[Port] = []
    for names, single, dest in (
        (d.input_buses, d.inputs, ins),
        (d.output_buses, d.outputs, outs),
    ):
        for bus in names:
            if bus in inst.buses:
                dest.append(Port(bus, tuple(read(n) for n in inst.buses[bus])))
        for port in single:
            if "[" not in port and port in inst.ports:
                dest.append(Port(port, (read(inst.ports[port]),)))
    return tuple(ins), tuple(outs)


# ---------------------------------------------------------------- grafo de bloques
@dataclass(frozen=True)
class Graph:
    """Bloques de primer nivel y qué bloque alimenta a cuál.

    Attributes:
        blocks: instancias de primer nivel que no son celdas sueltas.
        links: pares (origen, destino) de índices en ``blocks``.
        ranks: columna de cada bloque: el camino más largo desde una entrada del chip.
    """

    blocks: tuple[Instance, ...]
    links: tuple[tuple[int, int], ...]
    ranks: tuple[int, ...]


def _port_nodes(inst: Instance, outputs: bool) -> list[Node]:
    d = inst.definition
    buses = d.output_buses if outputs else d.input_buses
    single = d.outputs if outputs else d.inputs
    nodes = [n for bus in buses if bus in inst.buses for n in inst.buses[bus]]
    nodes += [inst.ports[p] for p in single if "[" not in p and p in inst.ports]
    return nodes


_GRAPHS: dict[int, tuple[Netlist, Graph]] = {}


def graph(netlist: Netlist) -> Graph:
    """Bloques de primer nivel y sus conexiones, también a través de las celdas sueltas."""
    hit = _GRAPHS.get(id(netlist))
    if hit is not None and hit[0] is netlist:
        return hit[1]
    top = netlist.top_instances()
    blocks = tuple(i for i in top if not i.is_leaf)
    # Dirección de la señal dentro de cada celda suelta: de sus entradas a sus salidas.
    succ: dict[int, set[int]] = {}
    for cell in (i for i in top if i.is_leaf):
        outs = {n.id for n in _port_nodes(cell, outputs=True)}
        for src in _port_nodes(cell, outputs=False):
            succ.setdefault(src.id, set()).update(outs)
    feeds: dict[int, set[int]] = {}
    for j, b in enumerate(blocks):
        for n in _port_nodes(b, outputs=False):
            feeds.setdefault(n.id, set()).add(j)
    links: set[tuple[int, int]] = set()
    for i, b in enumerate(blocks):
        seen: set[int] = set()
        stack = [n.id for n in _port_nodes(b, outputs=True)]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            for j in feeds.get(x, ()):
                if j != i:
                    links.add((i, j))
            if x not in feeds:  # la señal sigue por las celdas sueltas hasta un bloque
                stack.extend(succ.get(x, ()))
    ranks = [0] * len(blocks)
    for _ in blocks:  # acotado: un lazo no hace crecer el rango sin fin
        changed = False
        for u, v in links:
            if ranks[v] < ranks[u] + 1:
                ranks[v] = ranks[u] + 1
                changed = True
        if not changed:
            break
    g = Graph(blocks, tuple(sorted(links)), tuple(ranks))
    _GRAPHS[id(netlist)] = (netlist, g)
    return g


# ---------------------------------------------------------------- recorrido
@dataclass(frozen=True)
class Step:
    """Un paso del recorrido.

    Attributes:
        key: etapa (nombre de la instancia principal); da el color de la etapa.
        title: nombre del paso en palabras.
        paths: instancias de primer nivel que forman el paso.
        transistors: transistores de esas instancias.
        summary: el resultado del paso en pocas palabras, para su caja.
        text: qué hace el paso, con los valores de esta operación.
        detail: la cuenta, en líneas de ancho fijo.
        ins, outs: entradas y salidas de las instancias, con sus valores.
        sources, targets: índices de los pasos que lo alimentan y a los que alimenta.
    """

    key: str
    title: str
    paths: tuple[str, ...]
    transistors: int
    summary: str
    text: str
    detail: str
    ins: tuple[Port, ...]
    outs: tuple[Port, ...]
    sources: tuple[int, ...] = ()
    targets: tuple[int, ...] = ()


@dataclass(frozen=True)
class Walkthrough:
    """Los pasos de una operación.

    Attributes:
        expression: ``1.5 + 2.25 = 3.75``.
        unit: nombre de la unidad (``FADDSUB_binary32``).
        inputs: líneas de las entradas (``a = 1.5``).
        result: valor del resultado en decimal.
        steps: los pasos, en orden.
        narrated: True si los pasos tienen textos propios de la operación.
    """

    expression: str
    unit: str
    inputs: tuple[str, ...]
    result: str
    steps: tuple[Step, ...]
    narrated: bool


class _UnknownValueError(Exception):
    """Un valor que hace falta para narrar el paso vale X o Z."""


def _known(p: Port | None) -> int:
    if p is None or p.value is None:
        raise _UnknownValueError
    return p.value


def _sup(n: int) -> str:
    """Exponente en superíndice: ``2⁻³``."""
    table = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return str(n).translate(table)


def fixed(values: Sequence[int], width: int, int_bits: int) -> list[str]:
    """Números de ``width`` bits en binario con la coma tras ``int_bits`` bits.

    Se quitan los ceros finales que todos tienen en común, así quedan alineados.
    """
    texts = [format(v, f"0{width}b") for v in values]
    frac = width - int_bits
    common = min((len(t) - len(t.rstrip("0")) for t in texts), default=0)
    keep = max(1, frac - common)
    return [f"{t[:int_bits]}.{t[int_bits : int_bits + keep]}{SUB}" for t in texts]


def short(text: str, limit: int = 16) -> str:
    """Recorta un texto largo para la caja del paso."""
    return text if len(text) <= limit else text[: limit - 2] + "…" + SUB


class _Story:
    """Lee los puertos de las instancias de la suma/resta y arma los textos."""

    def __init__(self, calc: model.Calculation, read: Reader, netlist: Netlist) -> None:
        self.calc = calc
        self.fmt: FloatFormat = calc.fmt
        self.read = read
        self.inst = {i.path: i for i in netlist.top_instances()}
        self.cache: dict[str, tuple[dict[str, Port], dict[str, Port]]] = {}

    def io(self, path: str) -> tuple[dict[str, Port], dict[str, Port]]:
        if path not in self.cache:
            ins, outs = ports(self.inst[path], self.read)
            self.cache[path] = ({p.name: p for p in ins}, {p.name: p for p in outs})
        return self.cache[path]

    def get(self, path: str, name: str) -> int:
        ins, outs = self.io(path)
        return _known(outs.get(name) or ins.get(name))

    def width(self, path: str, name: str) -> int:
        ins, outs = self.io(path)
        p = outs.get(name) or ins.get(name)
        return 0 if p is None else len(p.bits)

    def power(self, e: int) -> str:
        """``2⁻³``, o una nota si el campo de exponente está todo en 1 (∞ o NaN)."""
        if e == self.fmt.exp_max_field:
            return "todo en 1 (∞ o NaN)"
        return f"2{_sup(e - self.fmt.bias)}"

    @property
    def is_special(self) -> bool:
        return bool(self.get("special", "special"))

    # ----------------------------------------------------------- pasos
    def unpack(self) -> tuple[str, str, str]:
        f = self.fmt
        lines = []
        exps = []
        for name, bits in (("a", self.calc.a), ("b", self.calc.b)):
            path = f"unpack_{name}"
            s, e, m = self.get(path, "sign"), self.get(path, "exp"), self.get(path, "mant")
            sf, ef, ff = f.fields(bits)
            field = f"{sf} {format(ef, f'0{f.exp_bits}b')} {format(ff, f'0{f.frac_bits}b')}"
            (mant,) = fixed([m], f.precision, 1)
            power = self.power(e)
            exps.append(power)
            lines.append(f"{name} = {field}")
            note = " (cero o subnormal: exponente mínimo)" if ef == 0 else ""
            lines.append(f"    signo {s}, exponente {e} → {power}{note}")
            lines.append(f"    mantisa {mant}")
        text = (
            "Separa el signo, el exponente y la fracción de cada operando, y agrega el 1 "
            "implícito a la izquierda de la fracción (0 si el número es cero o subnormal). "
            f"El exponente guardado tiene un sesgo de {f.bias}: el exponente real es el "
            f"guardado menos {f.bias}."
        )
        if self.calc.op == "sub":
            text += " En la resta se invierte el signo de b: a − b = a + (−b)."
        elif self.calc.op in ("mul", "div"):
            sa, sb = self.get("unpack_a", "sign"), self.get("unpack_b", "sign")
            text += " El signo del resultado es el XOR de los signos."
            lines.append(f"signo = {sa} ⊕ {sb} = {sa ^ sb}")
        return f"exponentes {exps[0]} y {exps[1]}", text, "\n".join(lines)

    def order(self) -> tuple[str, str, str]:
        f = self.fmt
        swap = self.get("order", "lt")
        mag = [model.value_text(f, x & ~f.sign_mask) for x in (self.calc.a, self.calc.b)]
        lines = [f"|a| = {mag[0]}", f"|b| = {mag[1]}"]
        if swap:
            lines.append("|a| < |b| → intercambia: X = b, Y = a")
            summary = "X = b (intercambia)"
        else:
            lines.append("|a| ≥ |b| → sin cambio: X = a, Y = b")
            summary = "X = a (sin cambio)"
        text = (
            "Compara las magnitudes (exponente y mantisa juntos, como un solo número sin "
            "signo). El mayor pasa a llamarse X y el menor Y; así la diferencia de "
            "exponentes nunca es negativa y siempre se corre la mantisa del menor. El "
            "intercambio lo hacen multiplexores controlados por la salida del comparador."
        )
        return summary, text, "\n".join(lines)

    def exp_diff(self) -> tuple[str, str, str]:
        ex, ey, d = self.get("exp_diff", "a"), self.get("exp_diff", "b"), self.get("exp_diff", "s")
        lines = [f"d = eX − eY = {ex} − {ey} = {d}"]
        span = self.width("align", "y")
        if d >= span:
            lines.append(f"d ≥ {span}: Y sale entera por la derecha")
        text = (
            "Resta los exponentes con un restador de complemento a 2. La diferencia d dice "
            "cuántos lugares hay que correr la mantisa de Y a la derecha para que X e Y "
            "tengan el mismo exponente."
        )
        return f"d = {d}", text, "\n".join(lines)

    def align(self) -> tuple[str, str, str]:
        n = self.width("align", "y")
        y_in, sh = self.get("align", "a"), self.get("align", "sh")
        y_out, lost = self.get("align", "y"), self.get("align", "sticky")
        y_al = y_out | lost
        before, after = fixed([y_in, y_al], n, 1)
        lines = [
            f"Y       = {before}",
            f"Y >> {sh:<3}= {after}",
            f"salió por la derecha: {'algún 1' if lost else 'todo 0'}",
            f"sticky = {lost}",
        ]
        text = (
            "Un desplazador de barril corre la mantisa de Y d lugares a la derecha. Lleva "
            "3 bits extra a la derecha (guarda, redondeo y sticky) para no perder lo que "
            "hace falta al redondear; si sale algún 1 por la derecha, el último bit (sticky) "
            "queda en 1."
        )
        return f"Y >> {sh}", text, "\n".join(lines)

    def addsub(self) -> tuple[str, str, str, str]:
        n = self.width("mant_addsub", "s")
        xa, yb = self.get("mant_addsub", "a"), self.get("mant_addsub", "b")
        eop, total = self.get("mant_addsub", "sub"), self.get("mant_addsub", "s")
        x_t, y_t, s_t = fixed([xa, yb, total], n, 2)
        sym = "−" if eop else "+"
        lines = [f"  X = {x_t}", f"{sym} Y = {y_t}", f"  = {s_t}"]
        if eop:
            title = "Restar mantisas"
            text = (
                "Los signos efectivos son distintos, así que se resta X − Y con el mismo "
                "sumador: Y entra invertida y con acarreo inicial 1 (complemento a 2). "
            )
        else:
            title = "Sumar mantisas"
            text = "Los signos efectivos son iguales, así que se suman las mantisas. "
        text += (
            "El sumador está hecho de celdas de suma completa (FA) en cadena; el bit extra "
            "de la izquierda recibe el acarreo."
        )
        return title, f"= {short(s_t)}", text, "\n".join(lines)

    def lzc(self) -> tuple[str, str, str]:
        n = self.width("lzc", "a")
        total, lz = self.get("lzc", "a"), self.get("lzc", "count")
        (t,) = fixed([total], n, 2)
        if total == 0:
            lines = [t, "→ el resultado es cero"]
        else:
            lines = [t, f"→ {lz} cero{'s' if lz != 1 else ''} antes del primer 1"]
        text = (
            "Cuenta los ceros a la izquierda del resultado. Como hay un bit extra para el "
            "acarreo, sin acarreo el primer 1 queda en la segunda posición (lz = 1), con "
            "acarreo en la primera (lz = 0), y si una resta canceló bits, lz es mayor."
        )
        return f"lz = {lz}", text, "\n".join(lines)

    def normalize(self) -> tuple[str, str, str]:
        n = self.width("normalize", "y")
        total, lz, norm = (self.get("normalize", k) for k in ("a", "sh", "y"))
        ex = self.get("exp_diff", "a")
        e_bits = self.width("round", "e")
        e = self.get("round", "e")
        if e >> (e_bits - 1):
            e -= 1 << e_bits  # complemento a 2
        (before,) = fixed([total], n, 2)
        (after,) = fixed([norm], n, 1)
        g, r, s = (self.get("round", k) for k in ("g", "r", "s"))
        (mant,) = fixed([self.get("round", "m")], self.fmt.precision, 1)
        if total == 0:
            lines = ["el resultado es cero: no hay un 1 que llevar adelante"]
            return "resultado 0", self.normalize_text(), "\n".join(lines)
        lines = [
            f"resultado = {before}",
            f"<< {lz:<8}= {after}",
            "exponente = eX + 1 − lz",
            f"          = {ex} + 1 − {lz} = {e}",
            f"mantisa   = {mant}",
            f"G = {g}, R = {r}, S = {s}",
        ]
        return f"<< {lz}, e = {e}", self.normalize_text(), "\n".join(lines)

    @staticmethod
    def normalize_text() -> str:
        return (
            "Un desplazador de barril corre el resultado lz lugares a la izquierda para "
            "dejar el primer 1 adelante (forma 1.xxx) y el exponente se ajusta en lo mismo. "
            "Los bits que quedan después de la mantisa son G (guarda), R (redondeo) y S "
            "(sticky, el OR de los que siguen)."
        )

    def round(self) -> tuple[str, str, str]:
        f = self.fmt
        g, r, s = (self.get("round", k) for k in ("g", "r", "s"))
        m = self.get("round", "m")
        y = self.get("round", "y")
        ovf, unf, inx = (self.get("round", k) for k in ("overflow", "underflow", "inexact"))
        lsb = m & 1
        up = bool(g and (r or s or lsb))
        if not g:
            why = "G = 0: lo que sobra es menos de medio ulp → se trunca"
        elif r or s:
            why = "G = 1 y R o S en 1: más de medio ulp → se suma 1"
        elif lsb:
            why = "empate exacto con el último bit en 1 → se suma 1 para dejarlo par"
        else:
            why = "empate exacto con el último bit en 0 → queda par, se trunca"
        sf, ef, ff = f.fields(y)
        lines = [
            f"G R S = {g} {r} {s}, último bit = {lsb}",
            why,
            "empaquetado:",
            f"  {sf} {format(ef, f'0{f.exp_bits}b')} {format(ff, f'0{f.frac_bits}b')}",
            f"  = {model.hex_text(f, y)} = {model.value_text(f, y)}",
        ]
        if ovf:
            lines.append("el exponente no cabe → OF, resultado ±∞")
        if unf:
            lines.append("diminuto e inexacto → underflow (UF)")
        lines.append("inexacto (NX): " + ("sí, se perdieron bits" if inx else "no"))
        text = (
            "Redondea al más cercano y, en empate, al par (ADR-0002): suma 1 a la mantisa "
            "si G = 1 y además R, S o el último bit valen 1. Después arma los bits del "
            "resultado: signo, exponente con sesgo y fracción sin el 1 implícito."
        )
        summary = "exacto" if not inx else ("redondea ↑" if up else "trunca")
        return summary, text, "\n".join(lines)

    def special(self) -> tuple[str, str, str]:
        f = self.fmt
        names = {
            "zero": FPClass.ZERO,
            "subnormal": FPClass.SUBNORMAL,
            "normal": FPClass.NORMAL,
            "inf": FPClass.INF,
            "qnan": FPClass.QNAN,
            "snan": FPClass.SNAN,
        }
        classes = []
        for tag in ("a", "b"):
            _, outs = self.io(f"class_{tag}")
            hit = [k for k in names if outs.get(k) is not None and outs[k].value == 1]
            classes.append(model.CLASS_NAMES[names[hit[0]]] if len(hit) == 1 else "X")
        special = self.get("special", "special")
        res = self.calc.result
        fl = res.flags
        raised = any((fl.invalid, fl.div_by_zero, fl.overflow, fl.underflow, fl.inexact))
        lines = [f"a: {classes[0]}, b: {classes[1]}"]
        cases = "NaN o ∞" if self.calc.op in ("add", "sub") else "NaN, ∞ o 0"
        if special:
            lines.append(f"caso especial ({cases}): manda la tabla")
        else:
            lines.append("sin caso especial: pasa el numérico")
        lines.append(f"resultado = {model.hex_text(f, res.bits)}")
        lines.append(f"          = {model.value_text(f, res.bits)}")
        lines.append(f"flags: {fl if raised else 'ninguno'}")
        example = {
            "add": "∞ − ∞ da NaN y levanta NV",
            "sub": "∞ − ∞ da NaN y levanta NV",
            "mul": "0 × ∞ da NaN y levanta NV; 0 × x da 0 con el signo del XOR",
            "div": "x ÷ 0 da ∞ y levanta DZ; 0 ÷ 0 e ∞ ÷ ∞ dan NaN y levantan NV",
        }[self.calc.op]
        text = (
            "En paralelo con todo lo anterior, un clasificador mira si cada operando es "
            f"cero, subnormal, normal, infinito o NaN. Si hay un caso especial ({cases}), "
            f"el resultado sale de una tabla (por ejemplo, {example}); si no, un "
            "multiplexor deja pasar el resultado numérico."
        )
        return f"= {model.value_text(f, res.bits)}", text, "\n".join(lines)

    # ----------------------------------------------------------- multiplicación
    def _signed(self, path: str, name: str) -> int:
        """Valor en complemento a 2 de un bus (para el exponente con signo)."""
        value, bits = self.get(path, name), self.width(path, name)
        return value - (1 << bits) if value >> (bits - 1) else value

    def mul_product(self) -> tuple[str, str, str]:
        f = self.fmt
        p = f.precision
        ma, mb, prod = (self.get("mant_mul", k) for k in ("a", "b", "p"))
        x_t, y_t = fixed([ma, mb], p, 1)
        (p_t,) = fixed([prod], 2 * p, 2)
        lines = [f"  X = {x_t}", f"× Y = {y_t}", f"  = {p_t}"]
        text = (
            f"Un multiplicador en arreglo: {p} × {p} = {p * p} compuertas AND forman los "
            "productos parciales X·yⱼ (X corrido j lugares si el bit j de Y es 1) y "
            f"{p - 1} filas de sumadores completos (FA) los van acumulando. El producto "
            f"tiene {2 * p} bits con dos bits enteros, porque dos mantisas en [1, 2) dan un "
            "producto en [1, 4)."
        )
        return f"= {short(p_t)}", text, "\n".join(lines)

    def mul_lzc(self) -> tuple[str, str, str]:
        n = self.width("lzc", "a")
        prod, lz = self.get("lzc", "a"), self.get("lzc", "count")
        (t,) = fixed([prod], n, 2)
        lines = (
            [t, "→ el producto es cero"] if prod == 0 else [t, f"→ {lz} ceros antes del primer 1"]
        )
        if prod and lz == 1:
            lines[1] = "→ 1 cero antes del primer 1"
        text = (
            "Cuenta los ceros a la izquierda del producto. Si el producto es ≥ 2, el primer 1 "
            "está en el primer bit (lz = 0); si es < 2, en el segundo (lz = 1). Con "
            "operandos subnormales puede haber más ceros."
        )
        return f"lz = {lz}", text, "\n".join(lines)

    def mul_normalize(self) -> tuple[str, str, str]:
        f = self.fmt
        n = self.width("normalize", "y")
        prod, lz, norm = (self.get("normalize", k) for k in ("a", "sh", "y"))
        ea, eb = self.get("unpack_a", "exp"), self.get("unpack_b", "exp")
        e = self._signed("round", "e")
        (before,) = fixed([prod], n, 2)
        (after,) = fixed([norm], n, 1)
        (mant,) = fixed([self.get("round", "m")], f.precision, 1)
        g, r, s_ = (self.get("round", k) for k in ("g", "r", "s"))
        if prod == 0:
            return "producto 0", self.normalize_text(), "el producto es cero"
        lines = [
            f"producto = {short(before, 30)}",
            f"<< {lz:<7}= {short(after, 30)}",
            "exponente = ea + eb − sesgo + 1 − lz",
            f"          = {ea} + {eb} − {f.bias} + 1 − {lz} = {e}",
            f"mantisa   = {mant}",
            f"G = {g}, R = {r}, S = {s_}",
        ]
        text = (
            "Un desplazador de barril deja el primer 1 adelante (forma 1.xxx). El exponente "
            "se calcula en paralelo con sumadores: los exponentes se suman y se resta un "
            "sesgo, porque cada uno ya lo traía; el 1 − lz ajusta la posición de la coma. "
            "Los bits que sobran dan G, R y S para redondear."
        )
        return f"<< {lz}, e = {e}", text, "\n".join(lines)

    # ----------------------------------------------------------------- división
    def div_normalize(self) -> tuple[str, str, str]:
        f = self.fmt
        p = f.precision
        lines = []
        shifts = []
        for tag in ("a", "b"):
            m, lz = self.get(f"lzc_{tag}", "a"), self.get(f"lzc_{tag}", "count")
            norm = self.get(f"normalize_{tag}", "y")
            before, after = fixed([m, norm], p, 1)
            shifts.append(lz)
            lines.append(f"{tag}: {short(before, 28)} << {lz}")
            lines.append(f"   = {short(after, 28)}")
        text = (
            "El divisor necesita mantisas que empiecen en 1. Si un operando es subnormal, su "
            "mantisa empieza con ceros: un contador de ceros y un desplazador la corren a la "
            "izquierda y su exponente baja en lo mismo. Con números normales no hay nada que "
            "correr (lz = 0)."
        )
        summary = "sin cambio" if not any(shifts) else f"<< {shifts[0]} y << {shifts[1]}"
        return summary, text, "\n".join(lines)

    def div_quotient(self) -> tuple[str, str, str]:
        f = self.fmt
        p = f.precision
        na, nb = self.get("mant_div", "a"), self.get("mant_div", "b")
        q, rest = self.get("mant_div", "q"), self.get("mant_div", "sticky")
        qb = self.width("mant_div", "q")
        x_t, y_t = fixed([na, nb], p, 1)
        (q_t,) = fixed([q], qb, 1)
        top = q >> (qb - 1)
        ea, eb = self.get("unpack_a", "exp"), self.get("unpack_b", "exp")
        e = self._signed("round", "e")
        lines = [
            f"  X = {short(x_t, 30)}",
            f"÷ Y = {short(y_t, 30)}",
            f"  = {short(q_t, 30)}",
            f"resto ≠ 0: {'sí' if rest else 'no'} → sticky = {rest}",
            f"bit alto = {top}: " + ("cociente ≥ 1" if top else "cociente < 1, se corre 1"),
            f"exponente = ea − eb + sesgo − 1 + {top}",
            f"          = {ea} − {eb} + {f.bias} − 1 + {top} = {e}",
        ]
        text = (
            f"Un divisor no restaurador de {qb} filas. Cada fila suma o resta el divisor al "
            "resto parcial según el signo del resto anterior (XOR + FA) y da un bit del "
            "cociente: 1 si el nuevo resto es ≥ 0. Si al final queda resto, el resultado no "
            "es exacto y eso va al bit sticky. El exponente es la resta de exponentes más el "
            "sesgo."
        )
        return f"= {short(q_t)}", text, "\n".join(lines)


MUL: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("unpack_a", ("unpack_a", "unpack_b"), "Desempaquetar"),
    ("mant_mul", ("mant_mul",), "Multiplicar mantisas"),
    ("lzc", ("lzc",), "Contar ceros"),
    ("normalize", ("normalize",), "Normalizar"),
    ("round", ("round",), "Redondear y empaquetar"),
    ("special", ("class_a", "class_b", "special"), "Casos especiales"),
)
"""Pasos de la multiplicación."""

DIV: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("unpack_a", ("unpack_a", "unpack_b"), "Desempaquetar"),
    (
        "normalize_a",
        ("lzc_a", "lzc_b", "normalize_a", "normalize_b"),
        "Normalizar operandos",
    ),
    ("mant_div", ("mant_div",), "Dividir mantisas"),
    ("round", ("round",), "Redondear y empaquetar"),
    ("special", ("class_a", "class_b", "special"), "Casos especiales"),
)
"""Pasos de la división."""

ADDSUB: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("unpack_a", ("unpack_a", "unpack_b"), "Desempaquetar"),
    ("order", ("order",), "Comparar magnitudes"),
    ("exp_diff", ("exp_diff",), "Restar exponentes"),
    ("align", ("align",), "Alinear mantisa"),
    ("mant_addsub", ("mant_addsub",), "Sumar mantisas"),
    ("lzc", ("lzc",), "Contar ceros"),
    ("normalize", ("normalize",), "Normalizar"),
    ("round", ("round",), "Redondear y empaquetar"),
    ("special", ("class_a", "class_b", "special"), "Casos especiales"),
)
"""Pasos de la suma/resta: etapa (color), instancias y título."""


def _generic_text(inst_ins: Sequence[Port], inst_outs: Sequence[Port]) -> str:
    lines = [f"entra {p.name} = {p.text()}" for p in inst_ins]
    lines += [f"sale  {p.name} = {p.text()}" for p in inst_outs]
    return "\n".join(lines)


def _title(path: str) -> str:
    name = STAGE_NAMES.get(path, path)
    return name[:1].upper() + name[1:]


def _generic_step(inst: Instance, read: Reader) -> Step:
    ins, outs = ports(inst, read)
    main = outs[0] if outs else None
    summary = f"{main.name} = {short(main.text(), 14)}" if main else ""
    text = (
        f"Bloque {inst.definition.name} ({inst.path}). Se muestran sus entradas y salidas "
        "tal como quedaron en la simulación."
    )
    return Step(
        inst.path,
        _title(inst.path),
        (inst.path,),
        len(inst.transistors),
        summary,
        text,
        _generic_text(ins, outs),
        ins,
        outs,
    )


def _with_links(steps: list[Step], g: Graph) -> tuple[Step, ...]:
    owner = {p: k for k, s in enumerate(steps) for p in s.paths}
    src: dict[int, set[int]] = {k: set() for k in range(len(steps))}
    dst: dict[int, set[int]] = {k: set() for k in range(len(steps))}
    for i, j in g.links:
        a, b = owner.get(g.blocks[i].path), owner.get(g.blocks[j].path)
        if a is not None and b is not None and a != b:
            dst[a].add(b)
            src[b].add(a)
    return tuple(
        replace(s, sources=tuple(sorted(src[k])), targets=tuple(sorted(dst[k])))
        for k, s in enumerate(steps)
    )


def build(calc: model.Calculation) -> Walkthrough:
    """Recorrido de la última operación de ``calc.unit`` (lee los valores ahora)."""
    netlist = calc.unit.netlist
    read: Reader = calc.unit.engine.value
    g = graph(netlist)
    by_path = {i.path: i for i in g.blocks}
    steps: list[Step] = []
    plan = {"add": ADDSUB, "sub": ADDSUB, "mul": MUL, "div": DIV}.get(calc.op, ())
    narrated = bool(plan) and all(p in by_path for _, paths, _ in plan for p in paths)
    if narrated:
        story = _Story(calc, read, netlist)
        methods = {
            "unpack_a": story.unpack,
            "order": story.order,
            "exp_diff": story.exp_diff,
            "align": story.align,
            "lzc": story.mul_lzc if calc.op == "mul" else story.lzc,
            "normalize": story.mul_normalize if calc.op == "mul" else story.normalize,
            "round": story.round,
            "special": story.special,
            "mant_mul": story.mul_product,
            "normalize_a": story.div_normalize,
            "mant_div": story.div_quotient,
        }
        for key, paths, title in plan:
            ins: list[Port] = []
            outs: list[Port] = []
            for p in paths:
                i, o = ports(by_path[p], read)
                ins += i
                outs += o
            count = sum(len(by_path[p].transistors) for p in paths)
            try:
                if key == "mant_addsub":
                    title, summary, text, detail = story.addsub()
                else:
                    summary, text, detail = methods[key]()
                if key not in ("unpack_a", "special") and story.is_special:
                    text += (
                        " En esta operación hay un caso especial: el resultado numérico de "
                        "este paso se calcula igual, pero al final se descarta."
                    )
            except _UnknownValueError:
                summary = "X"
                text = "Algún valor de este paso quedó sin definir (X o Z)."
                detail = _generic_text(ins, outs)
            steps.append(
                Step(key, title, paths, count, summary, text, detail, tuple(ins), tuple(outs))
            )
    else:
        order = sorted(range(len(g.blocks)), key=lambda k: (g.ranks[k], k))
        steps = [_generic_step(g.blocks[k], read) for k in order]
    f = calc.fmt
    return Walkthrough(
        expression=calc.expression,
        unit=netlist.name,
        inputs=(f"a = {model.value_text(f, calc.a)}", f"b = {model.value_text(f, calc.b)}"),
        result=model.value_text(f, calc.result.bits),
        steps=_with_links(steps, g),
        narrated=narrated,
    )


__all__ = [
    "ADDSUB",
    "DIV",
    "MUL",
    "Graph",
    "Port",
    "Step",
    "Walkthrough",
    "build",
    "fixed",
    "graph",
    "ports",
]
