# TranSim754, rama de exposición.
# Uso: make <objetivo>   (ver `make help`)

PY      ?= python3.12
VENV    ?= .venv
BIN     := $(VENV)/bin
PYTHON  := $(BIN)/python

.DEFAULT_GOAL := help
.PHONY: help install-gui gui demo clean

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

$(PYTHON):
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip

install-gui: $(PYTHON) ## Instala el programa con su interfaz gráfica (una sola vez)
	$(PYTHON) -m pip install -e ".[gui]"

gui: ## Abre la interfaz gráfica en modo exposición
	$(BIN)/transim gui

demo: ## Demo de consola: 1.5 + 2.25 en binary32 con traza
	$(BIN)/transim calc 1.5 + 2.25 --format binary32 --trace

clean: ## Borra cachés y artefactos de compilación
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .hypothesis
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
