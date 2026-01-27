.PHONY: help build clean test lint format typecheck check install install-dev install-release install-pipx install-pipx-dev venv runtime-venv

SYS_PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
RUNTIME_VENV := $(HOME)/.music-ferry/venv
RUNTIME_PYTHON := $(RUNTIME_VENV)/bin/python
PROJECT_NAME := $(shell $(SYS_PYTHON) -c "import tomllib; from pathlib import Path; data=tomllib.load(open(Path('pyproject.toml'),'rb')); print(data['project']['name'])")
PROJECT_VERSION := $(shell $(SYS_PYTHON) -c "import tomllib; from pathlib import Path; data=tomllib.load(open(Path('pyproject.toml'),'rb')); print(data['project']['version'])")
PACKAGE_DIR := $(shell $(SYS_PYTHON) -c "import tomllib; from pathlib import Path; data=tomllib.load(open(Path('pyproject.toml'),'rb')); print(data['project']['name'].replace('-', '_'))")

help:
	@echo "$(PROJECT_NAME) $(PROJECT_VERSION)"
	@echo "Targets: venv, runtime-venv, build, test, lint, format, typecheck, check, install, install-dev, install-release, install-pipx, install-pipx-dev, clean"

venv:
	@test -x "$(VENV_PYTHON)" || $(SYS_PYTHON) -m venv "$(VENV)"

runtime-venv:
	@test -x "$(RUNTIME_PYTHON)" || $(SYS_PYTHON) -m venv "$(RUNTIME_VENV)"

build: venv
	$(VENV_PYTHON) -m build

test: venv
	$(VENV_PYTHON) -m pytest -v

lint: venv
	$(VENV_PYTHON) -m ruff check .

format: venv
	$(VENV_PYTHON) -m black .

typecheck: venv
	$(VENV_PYTHON) -m mypy $(PACKAGE_DIR)

check: lint typecheck test

install: venv
	$(VENV_PYTHON) -m pip install .

install-dev: venv
	$(VENV_PYTHON) -m pip install -e ".[dev]"

install-release: build runtime-venv
	@WHEEL=$$(ls -t dist/*.whl | head -n 1); \
	if [ -z "$$WHEEL" ]; then \
		echo "No wheel found in dist/"; exit 1; \
	fi; \
	$(RUNTIME_PYTHON) -m pip install --force-reinstall "$$WHEEL"

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
