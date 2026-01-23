.PHONY: help build clean test lint format typecheck check install install-dev venv

SYS_PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
PROJECT_NAME := $(shell $(SYS_PYTHON) -c "import tomllib; from pathlib import Path; data=tomllib.load(open(Path('pyproject.toml'),'rb')); print(data['project']['name'])")
PROJECT_VERSION := $(shell $(SYS_PYTHON) -c "import tomllib; from pathlib import Path; data=tomllib.load(open(Path('pyproject.toml'),'rb')); print(data['project']['version'])")
PACKAGE_DIR := $(shell $(SYS_PYTHON) -c "import tomllib; from pathlib import Path; data=tomllib.load(open(Path('pyproject.toml'),'rb')); print(data['project']['name'].replace('-', '_'))")

help:
	@echo "$(PROJECT_NAME) $(PROJECT_VERSION)"
	@echo "Targets: venv, build, test, lint, format, typecheck, check, install, install-dev, clean"

venv:
	@test -x "$(VENV_PYTHON)" || $(SYS_PYTHON) -m venv "$(VENV)"

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

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
