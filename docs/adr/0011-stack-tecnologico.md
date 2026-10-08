# ADR-0011 · Stack tecnológico

- **Estado:** Aceptada
- **Fecha:** 2026-10-08

## Contexto

Seis integrantes con experiencia distinta deben trabajar en paralelo, en sus propios
equipos, durante pocos días. El stack debe ser conocido, instalable sin privilegios de
administrador y con herramientas de calidad que se ejecuten igual en local y en la
integración continua.

## Decisión

| Necesidad | Herramienta | Instalación |
|---|---|---|
| Lenguaje | Python 3.12 | sistema |
| Empaquetado y metadatos | `pyproject.toml` (backend hatchling) | — |
| Entorno | `venv` + `pip` (uv es opcional) | `make install` |
| Pruebas | pytest + hypothesis (pruebas basadas en propiedades) | extra `dev` |
| Oráculo de pruebas | numpy (aritmética float16/float32 del hardware) | extra `dev` |
| Estilo | ruff (lint y formato) | extra `dev` |
| Tipos | mypy, estricto en `core/`, `fpu/` y `reference/` | extra `dev` |
| Ganchos | pre-commit | extra `dev` |
| CLI | Typer (comando `transim`) | dependencia base |
| GUI de escritorio | PySide6 | extra `gui` |
| Ejecutable final | PyInstaller | extra `dist` |
| Adaptador de IA remoto (opcional) | `anthropic` | extra `ai` |
| Adaptador de IA local | API HTTP de Ollama con `urllib` de la biblioteca estándar | ninguna |

1. La única dependencia obligatoria en tiempo de ejecución es **Typer**. Las demás se
   agrupan en *extras* opcionales para que `make install` sea rápido y no descargue la
   GUI ni el empaquetador si no se necesitan.
2. **numpy solo se usa en las pruebas**, como oráculo; ningún módulo de `src/` lo
   importa para calcular.
3. **Ninguna dependencia nueva sin un ADR** que la justifique.

## Consecuencias

- La integración continua (GitHub Actions) ejecuta ruff, mypy y las pruebas rápidas en
  cada push y pull request con exactamente las mismas versiones mínimas.
- Python es lento para simular transistores; el motor `cached` (ADR-0008) compensa en
  las operaciones grandes.

## Alternativas descartadas

- **C++ o Rust.** Simulación más rápida, pero la curva de aprendizaje del equipo y el
  plazo lo hacen inviable.
- **Tkinter para la GUI.** Incluido en Python, pero con widgets limitados para mostrar
  campos de bits y tablas de métricas.
- **Poetry.** Agrega una herramienta más sin beneficio frente a `pip` con `pyproject`.
