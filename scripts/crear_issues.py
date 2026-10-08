"""Crea en GitHub los labels, milestones e issues del proyecto (idempotente).

Lee las tareas de ``TODO.md`` (``#N · [Persona] ámbito: título — dependencias — hito``)
y crea los issues **en orden**, verificando que el número asignado por GitHub sea N:
las pruebas pendientes citan ``#N`` (``@pendiente(N)``). Si un issue con ese título ya
existe, no se vuelve a crear. Si la numeración no coincide, se detiene.

Uso::

    python scripts/crear_issues.py --dry-run     # muestra lo que haría
    python scripts/crear_issues.py               # crea lo que falte
    python scripts/crear_issues.py --asignar     # asigna cada issue a su responsable

Requiere ``gh`` autenticado con permiso de escritura sobre el repositorio.
"""

# ruff: noqa: E501  (tablas de datos de los issues)
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REPO = "Hector-0-0/transim754"

PERSONAS = {
    "Héctor": ("hector", "Hector-0-0"),
    "Jairo": ("jairo", "JairoHCh"),
    "Ronald": ("ronald", "devronaldaz"),
    "Daniel": ("daniel", "Sergiodam73"),
    "Fabricio": ("fabricio", "Fabrizzio-07"),
    "Yenny": ("yenny", "yennyestherchavez"),
}
HITOS = {
    "A": (
        "v0.1.0-avance",
        "2026-10-12T23:59:59Z",
        "Presentación del avance: FADD/FSUB en transistores y demo.",
    ),
    "P": (
        "v0.5.0-parcial",
        None,
        "Después del parcial: FMUL, FDIV, CPU completa, CLA y GUI completa.",
    ),
    "F": (
        "v1.0.0-final",
        None,
        "Exposición final: control en compuertas, métricas finales y ejecutable.",
    ),
}
AMBITOS = [
    "core", "cells", "blocks", "alu", "fpu-common", "fpu-addsub", "fpu-muldiv",
    "cpu", "metrics", "ai", "cli", "gui", "docs", "research", "repo", "reference",
]  # fmt: skip
GUIAS = {
    "cells": ("src/transim/cells/GUIA.md", "cells"),
    "blocks": ("src/transim/blocks/GUIA.md", "blocks"),
    "alu": ("src/transim/alu/GUIA.md", "alu"),
    "fpu-common": ("src/transim/fpu/GUIA_ADDSUB.md", "fpu-addsub"),
    "fpu-addsub": ("src/transim/fpu/GUIA_ADDSUB.md", "fpu-addsub"),
    "fpu-muldiv": ("src/transim/fpu/GUIA_MULDIV.md", "fpu-muldiv"),
    "metrics": ("src/transim/metrics/GUIA.md", "metrics"),
    "gui": ("src/transim/ui/gui/GUIA.md", "gui"),
    "cpu": ("src/transim/cpu/GUIA.md", "cpu"),
    "cli": ("src/transim/cpu/GUIA.md", "cli"),
    "ai": ("src/transim/assistant/GUIA.md", "ai"),
    "research": ("docs/investigacion/transistores_en_cpus.md", None),
    "docs": ("docs/00_propuesta.md", None),
    "repo": ("EQUIPO.md", None),
}
PRIORIDAD_ALTA = {1, 2, 3, 4, 7, 8, 11, 12, 15, 16, 17, 29, 31, 33}

CRITERIOS: dict[int, list[str]] = {
    1: [
        "AND2 y OR2 de 6 transistores (NAND2/NOR2 + INV).",
        "Tablas de verdad exhaustivas y equivalencia de motores.",
    ],
    2: [
        "XOR2 y XNOR2 de 12 transistores, entradas solo a compuertas.",
        "Tablas exhaustivas, conteo exacto, nMOS = pMOS.",
    ],
    3: [
        "MUX2 restaurador de 12 transistores (INV en entradas de datos y salida).",
        "Tabla exhaustiva de 8 combinaciones; celda tabulable.",
    ],
    4: [
        "HA de 18 T y FA espejo de 28 T como celda primitiva.",
        "Tablas exhaustivas y equivalencia switch/cached.",
    ],
    5: [
        "Latch transparente con clk = 1 y retención con clk = 0.",
        "DFF captura solo en flanco de subida durante 40 ciclos.",
    ],
    6: ["REG{N} con habilitación para 1, 4 y 8 bits.", "`make validar M=cells` → PASS."],
    7: [
        "RCA de `width` celdas FA (RCA8 = 224 T).",
        "Exhaustivo de 1 a 4 bits; 300 aleatorios en 8, 24 y 32 bits.",
    ],
    8: ["Salidas s, cout y ovf.", "Exhaustivo de 1, 3 y 4 bits; 300 aleatorios en 8 y 32 bits."],
    9: ["lt, eq y gt exhaustivos en 4 bits y 300 aleatorios en 10 bits."],
    10: ["MUX2×N y árbol MUX-N para N = 2, 4, 8; ValueError si N no es potencia de 2."],
    11: [
        "Izquierda y derecha con sticky, exhaustivos en 6 bits (incluido sh ≥ ancho).",
        "200 casos en 27 bits.",
    ],
    12: ["Exhaustivo en 1, 2, 5 y 8 bits; aleatorio en 24, 27 y 48 bits; count = ancho si a = 0."],
    13: [
        "49 pares de bordes × ADD/SUB y 500 aleatorios con C, V, Z, N.",
        "`make validar M=alu` → PASS.",
    ],
    14: [
        "Mismos puertos y pruebas que el RCA.",
        "Tabla de comparación RCA/CLA (transistores, profundidad, α).",
    ],
    15: [
        "Desempaquetado y clasificador en todos los bordes; clasificador exhaustivo en binary16.",
        "special_cases coincide con la referencia para add, mul y div.",
    ],
    16: [
        "Contrato de `reference.fpu.round_and_pack`: 300 y 10 000 casos por formato, 0 discrepancias."
    ],
    17: [
        "Ejemplos de docs/03.",
        "Todos los pares borde y 10 000 aleatorios en binary16 y binary32, suma y resta: 0 discrepancias bit a bit incluidos flags.",
        "`make validar M=fpu-addsub COMPLETO=1` → PASS.",
    ],
    18: ["Exhaustivo de 1 a 4 bits; 100 casos en 11 y 24 bits; width² celdas AND2."],
    19: [
        "Ejemplos 4 y 6 de docs/03.",
        "Bordes y 10 000 aleatorios en ambos formatos: 0 discrepancias incluidos flags.",
    ],
    20: ["Exhaustivo sobre mantisas normalizadas de 2 a 4 bits; 60 casos para p = 11 y 24."],
    21: [
        "Ejemplo 5 de docs/03 (1/3).",
        "Bordes y 10 000 aleatorios en ambos formatos: 0 discrepancias incluidos flags.",
    ],
    22: ["Cadena de 5 inversores, 4 estímulos: 18 conmutaciones y 30 eventos exactos."],
    23: ["Cadena de n inversores → n; ramas → la más larga; jerarquía → celdas primitivas."],
    24: [
        "8 archivos .md/.csv; CSV de transistores con columnas modulo, nmos, pmos, total.",
        "Subcomando `transim metrics`.",
    ],
    25: [
        "`create_window()` construye la ventana en modo offscreen.",
        "Vista de bits de operandos y resultado; flags.",
    ],
    26: ["Etapas (buses dbg_), métricas y pestaña de programas .t754 paso a paso."],
    27: ["Secciones del esqueleto completas, 8 a 12 páginas, APA 7, cifras con fuente y año."],
    28: ["Diapositivas e informe del avance en APA; tablas tomadas de `transim metrics`."],
    29: [
        "Los 4 programas de examples/ ensamblan al código esperado.",
        "Errores con archivo:línea:columna; binario big-endian; desensamblador.",
    ],
    30: [
        "Decodificador, banco de registros, control y máquina.",
        "Mismo estado final que `reference.machine.run` en los 4 programas.",
    ],
    31: ["`transim calc`, `asm` y `run` con las pruebas de tests/ui/test_cli.py."],
    32: ["Ollama contra servidor local de prueba; Anthropic exige ANTHROPIC_API_KEY."],
    33: [
        "FADD/FSUB en transistores integrada; `make demo` funciona.",
        "docs/00_propuesta.md final; tag v0.1.0-avance y release.",
    ],
}


@dataclass
class Tarea:
    numero: int
    persona: str
    ambito: str
    titulo: str
    dependencias: list[int]
    hito: str

    @property
    def titulo_issue(self) -> str:
        return f"[{self.persona}] {self.ambito}: {self.titulo}"


LINEA = re.compile(r"^- \[[ x]\] #(\d+) · \[([^\]]+)\] ([\w-]+): (.+?) — (.+?) — ([APF])\b")


def leer_todo() -> list[Tarea]:
    tareas = []
    for linea in (RAIZ / "TODO.md").read_text(encoding="utf-8").splitlines():
        m = LINEA.match(linea)
        if m:
            deps = [int(x) for x in re.findall(r"#(\d+)", m.group(5))]
            tareas.append(
                Tarea(int(m.group(1)), m.group(2), m.group(3), m.group(4), deps, m.group(6))
            )
    numeros = [t.numero for t in tareas]
    if numeros != list(range(1, len(tareas) + 1)):
        sys.exit(f"TODO.md: numeración no consecutiva: {numeros}")
    return tareas


def cuerpo(t: Tarea) -> str:
    guia, modulo = GUIAS.get(t.ambito, ("EQUIPO.md", None))
    deps = ", ".join(f"#{d}" for d in t.dependencias) if t.dependencias else "ninguna"
    criterios = "\n".join(f"- [ ] {c}" for c in CRITERIOS.get(t.numero, []))
    validar = f"`make validar M={modulo}` → PASS" if modulo else "Revisión de otro integrante"
    pendientes = (
        f"Las pruebas de esta tarea están marcadas `@pendiente({t.numero})`." if modulo else ""
    )
    return f"""## Descripción
{t.titulo}. Detalle técnico, interfaces y puntos de commit en [{guia}](../blob/main/{guia}).

## Responsable
{t.persona} (la asignación en GitHub corresponde a esta persona).

## Dependencias
Bloqueado por: {deps}

## Criterios de aceptación
{criterios}

## Validación
{validar}. {pendientes}

## Definition of Done
Ver [CONTRIBUTING.md](../blob/main/CONTRIBUTING.md#definition-of-done).
"""


def gh(*args: str, entrada: str | None = None) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True, input=entrada)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def labels(dry: bool) -> None:
    definidos = (
        [(f"modulo:{a}", "1d76db", f"Módulo {a}") for a in AMBITOS]
        + [
            ("tipo:tarea", "0e8a16", "Unidad de trabajo de un módulo"),
            ("tipo:bug", "d73a4a", "Resultado incorrecto o error"),
            ("tipo:docs", "c5def5", "Documentación"),
            ("tipo:investigacion", "bfdadc", "Investigación"),
            ("prioridad:alta", "b60205", "Bloquea el avance o a otros"),
            ("prioridad:media", "fbca04", "Necesaria para el hito"),
            ("prioridad:baja", "c2e0c6", "Mejora o hito posterior"),
        ]
        + [(f"persona:{slug}", "5319e7", nombre) for nombre, (slug, _) in PERSONAS.items()]
    )
    for nombre, color, desc in definidos:
        print(f"label {nombre}")
        if not dry:
            gh(
                "label",
                "create",
                nombre,
                "--color",
                color,
                "--description",
                desc,
                "--force",
                "-R",
                REPO,
            )


def milestones(dry: bool) -> dict[str, int]:
    existentes = {
        m["title"]: m["number"] for m in json.loads(gh("api", f"repos/{REPO}/milestones?state=all"))
    }
    for titulo, fecha, desc in HITOS.values():
        if titulo in existentes:
            continue
        print(f"milestone {titulo}")
        if not dry:
            args = [
                "api",
                f"repos/{REPO}/milestones",
                "-f",
                f"title={titulo}",
                "-f",
                f"description={desc}",
            ]
            if fecha:
                args += ["-f", f"due_on={fecha}"]
            existentes[titulo] = json.loads(gh(*args))["number"]
    return existentes


def issues(tareas: list[Tarea], dry: bool) -> None:
    existentes = {
        i["title"]: i["number"]
        for i in json.loads(
            gh(
                "issue",
                "list",
                "-R",
                REPO,
                "--state",
                "all",
                "--limit",
                "500",
                "--json",
                "title,number",
            )
        )
    }
    for t in tareas:
        if t.titulo_issue in existentes:
            if existentes[t.titulo_issue] != t.numero:
                sys.exit(
                    f"El issue '{t.titulo_issue}' existe como #{existentes[t.titulo_issue]}, no #{t.numero}"
                )
            continue
        etiquetas = [
            f"modulo:{t.ambito}",
            "tipo:investigacion"
            if t.ambito == "research"
            else "tipo:docs"
            if t.ambito == "docs"
            else "tipo:tarea",
            f"prioridad:{'alta' if t.numero in PRIORIDAD_ALTA else 'media' if t.hito == 'A' else 'baja'}",
            f"persona:{PERSONAS[t.persona][0]}",
        ]
        print(f"issue #{t.numero}: {t.titulo_issue}  [{', '.join(etiquetas)}] → {HITOS[t.hito][0]}")
        if dry:
            continue
        url = gh(
            "issue", "create", "-R", REPO, "--title", t.titulo_issue, "--body-file", "-",
            "--label", ",".join(etiquetas), "--milestone", HITOS[t.hito][0], entrada=cuerpo(t),
        ).strip()  # fmt: skip
        numero = int(url.rsplit("/", 1)[-1])
        if numero != t.numero:
            sys.exit(
                f"GitHub asignó #{numero} a la tarea #{t.numero}: numeración desalineada; deteniendo."
            )


def asignar(tareas: list[Tarea], dry: bool) -> None:
    """Asigna cada issue a su responsable y verifica que GitHub lo haya aplicado.

    GitHub ignora sin error la asignación a quien aún no aceptó la invitación de
    colaborador; por eso se comprueba el resultado y se listan los pendientes.
    """
    pendientes: dict[str, list[int]] = {}
    for t in tareas:
        usuario = PERSONAS[t.persona][1]
        if dry:
            print(f"asignar #{t.numero} → @{usuario}")
            continue
        gh("issue", "edit", str(t.numero), "-R", REPO, "--add-assignee", usuario)
        datos = json.loads(gh("issue", "view", str(t.numero), "-R", REPO, "--json", "assignees"))
        if usuario in {a["login"] for a in datos["assignees"]}:
            print(f"#{t.numero} asignado a @{usuario}")
        else:
            pendientes.setdefault(usuario, []).append(t.numero)
    for usuario, numeros in pendientes.items():
        lista = ", ".join(f"#{n}" for n in numeros)
        print(
            f"PENDIENTE @{usuario}: no aceptó la invitación aún ({lista}). Vuelva a ejecutar luego."
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--asignar", action="store_true", help="solo asigna los issues a sus responsables"
    )
    a = p.parse_args()
    tareas = leer_todo()
    if a.asignar:
        asignar(tareas, a.dry_run)
        return 0
    labels(a.dry_run)
    milestones(a.dry_run)
    issues(tareas, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
