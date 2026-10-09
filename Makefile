# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna
#
# The framework's command surface for this repository: seven verbs, the same names a human, an agent
# and CI run. The runtime code is standard-library Python; the dev tools below are pinned and run
# through uvx, so nothing is installed into the project. Needs make, git, python3 (3.11+) and uv.
#
#   make format         rewrite formatting in place
#   make format:check   read-only: formatting and lint rules (alias: make format-check)
#   make lint           read-only lint
#   make typecheck      mypy, strict, on the typed scope below
#   make test           the engine's unittest suite
#   make check          THE gate: format:check -> typecheck -> test, plus the engine's rule check
#   make security       secrets scan against the committed baseline
#
# `format:check` has a colon, which make reads as a rule separator. The target is spelled `format\:check`
# and `format-check` is the alias; the unescaped form `format:check:` would define a different rule.

PYTHON ?= python3

RUFF := uvx ruff@0.16.10
MYPY := uvx mypy@2.4.0
DETECT_SECRETS := uvx --from detect-secrets==1.5.0 detect-secrets
DETECT_SECRETS_HOOK := uvx --from detect-secrets==1.5.0 detect-secrets-hook

ENGINE := brownfield-recipes/deterministic-audit

# Mypy covers the recipe tools and the engine's build script. The engine's own code joins later,
# through a ratchet. brownfield-recipes/tools has no Python yet (S2.1), so the find may match nothing.
TYPED_SOURCES := $(shell find brownfield-recipes/tools -name '*.py' 2>/dev/null | sort) $(ENGINE)/tools/build.py

.DEFAULT_GOAL := help
.NOTPARALLEL:
.PHONY: help format format-check format\:check lint typecheck test verify-rules check security update-secrets-baseline

help:
	@echo "verbs: format  format:check (format-check)  lint  typecheck  test  check  security"
	@echo "extra: verify-rules  update-secrets-baseline"

format:
	$(RUFF) format brownfield-recipes

format-check:
	$(RUFF) format --check brownfield-recipes
	$(RUFF) check brownfield-recipes

format\:check: format-check

lint:
	$(RUFF) check brownfield-recipes

typecheck:
	$(MYPY) --config-file mypy.ini $(TYPED_SOURCES)

test:
	cd $(ENGINE) && $(PYTHON) -m unittest discover -s tests

# Every framework anchor the engine cites must still resolve in this repository.
verify-rules:
	cd $(ENGINE) && $(PYTHON) -m audit --verify-rules

check: format-check typecheck test verify-rules

# No third-party runtime dependencies exist to audit, so the gate is a secrets scan. The baseline
# lists the deliberate key-shaped strings in the fixtures and tests; a new hit fails the scan.
security:
	git ls-files -z | xargs -0 $(DETECT_SECRETS_HOOK) --baseline .secrets.baseline

# Run this after a deliberate change to a fixture or test that holds a key-shaped string, then review the diff.
update-secrets-baseline:
	$(DETECT_SECRETS) scan --baseline .secrets.baseline
