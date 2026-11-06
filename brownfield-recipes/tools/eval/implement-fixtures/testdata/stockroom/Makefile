PYTHON ?= python3

.PHONY: setup lint typecheck test

setup:
	@echo "nothing to install: standard library only"

lint:
	$(PYTHON) tools/style_check.py src tests

typecheck:
	$(PYTHON) -m compileall -q src tests

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -t .
