PYTHON ?= $(shell command -v python3.12 || command -v python3)
VENV ?= .venv
BIN := $(VENV)/bin
STAGE ?= smoke
CONFIG ?= config.yaml

.PHONY: venv install lint_shadow test doctor run smoke_basic smoke_stage smoke_all_dev all

venv:
	$(PYTHON) -m venv --clear $(VENV)

install: venv
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	$(BIN)/pip install -e .

lint_shadow:
	PYTHONPATH=src $(BIN)/python scripts/check_shadowing.py

test:
	PYTHONPATH=src $(BIN)/pytest

doctor:
	PYTHONPATH=src $(BIN)/python -m landslide_inventory.doctor --config $(CONFIG) --minimal

run:
	PYTHONPATH=src $(BIN)/python -m landslide_inventory.run --stage $(STAGE) --config $(CONFIG)

smoke_basic:
	PYTHONPATH=src $(BIN)/python scripts/smoke.py --config $(CONFIG) --level basic

smoke_stage:
	PYTHONPATH=src $(BIN)/python scripts/smoke.py --config $(CONFIG) --level stage --stage $(STAGE)

smoke_all_dev: smoke_basic
	PYTHONPATH=src $(BIN)/python scripts/smoke.py --config $(CONFIG) --level stage --stage scrape
	PYTHONPATH=src $(BIN)/python scripts/smoke.py --config $(CONFIG) --level stage --stage normalize_dates
	PYTHONPATH=src $(BIN)/python scripts/smoke.py --config $(CONFIG) --level stage --stage lang
	PYTHONPATH=src $(BIN)/python scripts/smoke.py --config $(CONFIG) --level stage --stage extract
	PYTHONPATH=src $(BIN)/python scripts/smoke.py --config $(CONFIG) --level stage --stage dedup

all:
	@echo "Placeholder target. Run 'make install', 'make lint_shadow', 'make test', 'make doctor', 'make smoke_basic', 'make smoke_stage STAGE=scrape', or 'make run STAGE=smoke'."
