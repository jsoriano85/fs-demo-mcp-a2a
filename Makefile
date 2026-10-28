ifeq ($(OS),Windows_NT)
  VENV := .venv/Scripts/python
else
  VENV := .venv/bin/python
endif

.PHONY: format lint test docs

PY := src tests docs data mcp_server diagnosis_agent repair_agent coordinator_agent fetch_agent

format:
	$(VENV) -m black $(PY)
	$(VENV) -m ruff check --fix $(PY)

lint:
	$(VENV) -m ruff check $(PY)
	$(VENV) -m black --check $(PY)
	$(VENV) -m mypy

test:
	$(VENV) -m pytest

docs:
	$(VENV) -m docs.build_guide
