# TranSim754 — tareas de desarrollo.
# Uso: make <objetivo>   (ver `make help`)

PY      ?= python3.12
VENV    ?= .venv
BIN     := $(VENV)/bin
PYTHON  := $(BIN)/python
M       ?=

.DEFAULT_GOAL := help
.PHONY: help install install-gui test test-all lint format typecheck validar metrics gui demo clean

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

$(PYTHON):
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip

install: $(PYTHON) ## Crea el venv e instala el paquete con dependencias de desarrollo
	$(PYTHON) -m pip install -e ".[dev]"
	$(BIN)/pre-commit install || true

install-gui: install ## Instala además PySide6 (GUI)
	$(PYTHON) -m pip install -e ".[dev,gui]"

test: ## Pruebas rápidas (excluye las marcadas slow)
	$(BIN)/pytest -m "not slow" -q

test-all: ## Todas las pruebas, incluidas las lentas
	$(BIN)/pytest -q

lint: ## ruff (lint + verificación de formato)
	$(BIN)/ruff check src tests scripts
	$(BIN)/ruff format --check src tests scripts

format: ## Aplica el formato de ruff
	$(BIN)/ruff format src tests scripts
	$(BIN)/ruff check --fix src tests scripts

typecheck: ## mypy (estricto en core/, fpu/ y reference/)
	$(BIN)/mypy

validar: ## Valida un módulo: make validar M=<modulo>
	@test -n "$(M)" || (echo "Uso: make validar M=<modulo>"; exit 2)
	$(PYTHON) scripts/validar.py $(M)

metrics: ## Genera las tablas de métricas (Markdown y CSV)
	$(BIN)/transim metrics --out docs/metricas

gui: ## Abre la interfaz gráfica
	$(BIN)/transim gui

demo: ## Demo de consola: 1.5 + 2.25 en binary32 con traza
	$(BIN)/transim calc 1.5 + 2.25 --format binary32 --trace

clean: ## Borra cachés y artefactos de compilación
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .hypothesis
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
