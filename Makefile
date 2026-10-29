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
#   make test           the engine's unittest suite, then the recipe tools' (the catalogue checks), then the dev checks'
#   make check          THE gate: format:check -> typecheck -> test, plus the engine's rule check, the schema
#                       cross-check and the recipe linter
#   make security       secrets scan against the committed baseline
#
# `format:check` has a colon, which make reads as a rule separator. The target is spelled `format\:check`
# and `format-check` is the alias; the unescaped form `format:check:` would define a different rule.

PYTHON ?= python3

RUFF := uvx ruff@0.16.10
MYPY := uvx mypy@2.4.0
DETECT_SECRETS := uvx --from detect-secrets==1.5.0 detect-secrets
DETECT_SECRETS_HOOK := uvx --from detect-secrets==1.5.0 detect-secrets-hook
# The reference JSON Schema package is installed for one run, in a throwaway environment. The tools never import it.
CROSSCHECK := PYTHONPATH=brownfield-recipes/tools uv run --no-project --with jsonschema==4.23.0 python
# The Agent Skills spec's own reference validator (agentskills.io); its CLI entry point is `agentskills`,
# installed for one run, in a throwaway environment. Not the tools' or the engine's dependency.
SKILLS_REF := uvx --from skills-ref==0.1.1 agentskills
# Markdown lint (rules in .markdownlint-cli2.jsonc) and the Mermaid check need Node; neither is part of `check`.
MARKDOWNLINT := npx --yes markdownlint-cli2@0.24.0

# The Markdown that `docs-lint` holds to zero violations. A ratchet: a path joins once it is clean, and the list
# only grows. Everything else is reported by `docs-lint-all` and never fails.
DOCS_LINT_PATHS := 'brownfield-recipes/implement/**/*.md'

ENGINE := brownfield-recipes/deterministic-audit

# Mypy covers the recipe tools, the dev-only checks and the engine's build script. The engine's own code joins
# later, through a ratchet. The find picks up every Python file under brownfield-recipes/tools and
# brownfield-recipes/dev, tests included.
TYPED_SOURCES := $(shell find brownfield-recipes/tools brownfield-recipes/dev -name '*.py' 2>/dev/null | sort) $(ENGINE)/tools/build.py

.DEFAULT_GOAL := help
.NOTPARALLEL:
.PHONY: help format format-check format\:check lint typecheck test verify-rules crosscheck recipe-lint check security update-secrets-baseline validate-skills docs-lint docs-lint-all docs-mermaid

help:
	@echo "verbs: format  format:check (format-check)  lint  typecheck  test  check  security"
	@echo "extra: verify-rules  crosscheck  recipe-lint  update-secrets-baseline  validate-skills"
	@echo "docs:  docs-lint  docs-lint-all  docs-mermaid FILES=..."

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
	$(PYTHON) -m unittest discover -s brownfield-recipes/tools/tests
	$(PYTHON) -m unittest discover -s brownfield-recipes/dev/tests

# Every framework anchor the engine cites must still resolve in this repository.
verify-rules:
	cd $(ENGINE) && $(PYTHON) -m audit --verify-rules

# The subset validator that the tools use must agree with the reference JSON Schema package on every example
# and on thousands of one-defect mutants of them. About half a minute; needs uv and, the first time, the network.
crosscheck:
	$(CROSSCHECK) brownfield-recipes/dev/crosscheck_jsonschema.py

# Lints the recipe Markdown and checks that tools/CATALOGUE.md matches every tool's own --describe output.
recipe-lint:
	$(PYTHON) brownfield-recipes/tools/recipe_lint.py .

check: format-check typecheck test verify-rules crosscheck recipe-lint

# No third-party runtime dependencies exist to audit, so the gate is a secrets scan. The baseline
# lists the deliberate key-shaped strings in the fixtures and tests; a new hit fails the scan.
security:
	git ls-files -z | xargs -0 $(DETECT_SECRETS_HOOK) --baseline .secrets.baseline

# Run this after a deliberate change to a fixture or test that holds a key-shaped string, then review the diff.
update-secrets-baseline:
	$(DETECT_SECRETS) scan --baseline .secrets.baseline

# Builds the agentic-readiness-audit skill bundle fresh and validates it against the Agent Skills
# specification (S4.5.2). Not part of `check`: it is not one of the framework's seven verbs, and the
# validator needs the network the first time, same as `crosscheck`'s reference package.
validate-skills:
	$(PYTHON) brownfield-recipes/tools/build_skills.py
	$(SKILLS_REF) validate brownfield-recipes/dist/skills/agentic-readiness-audit

# Lints the Markdown in DOCS_LINT_PATHS and fails on any violation. Needs Node (npx); the first run fetches the
# pinned CLI. CI runs it in the `docs` job when a Markdown file changed.
docs-lint:
	$(MARKDOWNLINT) $(DOCS_LINT_PATHS)

# Reports violations in every tracked Markdown file (fixtures excluded by the config). Never fails: the debt
# outside DOCS_LINT_PATHS is recorded, not gated.
docs-lint-all:
	-git ls-files -z '*.md' | xargs -0 $(MARKDOWNLINT)

# Renders every Mermaid block in FILES with the pinned mermaid-cli; fails on a block that does not render.
docs-mermaid:
	$(PYTHON) brownfield-recipes/dev/mermaid_check.py $(MERMAID_FLAGS) $(FILES)
