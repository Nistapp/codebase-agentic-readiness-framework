# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna
#
# The framework's command surface for this repository: seven verbs, the same names a human, an agent
# and CI run. The runtime code is standard-library Python; the dev tools below are pinned in dev/tools/ and run
# through uvx or `go tool`, so nothing is installed into the project. Needs make, git, python3 (3.11+), uv and Go
# (1.27+, for actionlint and osv-scanner); `make security` also needs the network.
#
#   make format         rewrite formatting in place
#   make format:check   read-only: formatting and lint rules, and the ruff count against .quality-baseline.json
#                       (alias: make format-check)
#   make lint           read-only lint
#   make typecheck      mypy, strict, on the typed scope below
#   make test           the engine's unittest suite, then the recipe tools' (the catalogue checks), then the dev checks'
#   make check          THE gate: format:check -> typecheck -> test, plus the engine's rule check, the schema
#                       cross-check, the recipe linter, the master-list freshness check,
#                       the workflow lint and the spell check
#   make security       secrets scan against the committed baseline, then the dependency audit (osv-scanner) of
#                       the dev tools' lockfiles; needs Go and the network
#   make coverage       (extra) both unittest suites under coverage.py; fails below the floor in .coveragerc
#   make self-audit     (extra) the engine on this repository, read-only, against .audit-baseline.json; exit 2 on a regression
#
# `format:check` has a colon, which make reads as a rule separator. The target is spelled `format\:check`
# and `format-check` is the alias; the unescaped form `format:check:` would define a different rule.

PYTHON ?= python3

# Every dev tool version lives in one of two manifests, so that Dependabot sees it (.github/dependabot.yml):
# dev/tools/pyproject.toml (Python tools, one `"name==version",` line each, locked in uv.lock) and
# dev/tools/package.json (Node tools, locked in package-lock.json). `pin` and `npm_pin` read a version from them;
# make stops with an error when a pin is missing.
TOOL_PINS := dev/tools/pyproject.toml
NODE_PINS := dev/tools/package.json
pin = $(or $(shell sed -n 's/^ *"$(1)==\([^"]*\)".*/\1/p' $(TOOL_PINS)),$(error no pin for $(1) in $(TOOL_PINS)))
npm_pin = $(or $(shell sed -n 's|^ *"$(1)": *"\([^"]*\)".*|\1|p' $(NODE_PINS)),$(error no pin for $(1) in $(NODE_PINS)))

RUFF := uvx ruff@$(call pin,ruff)
MYPY := uvx mypy@$(call pin,mypy)
DETECT_SECRETS := uvx --from detect-secrets==$(call pin,detect-secrets) detect-secrets
DETECT_SECRETS_HOOK := uvx --from detect-secrets==$(call pin,detect-secrets) detect-secrets-hook
# The reference JSON Schema package is installed for one run, in a throwaway environment. The tools never import it.
CROSSCHECK := PYTHONPATH=audit/tools uv run --no-project --with jsonschema==$(call pin,jsonschema) python
# The Agent Skills spec's own reference validator (agentskills.io); its CLI entry point is `agentskills`,
# installed for one run, in a throwaway environment. Not the tools' or the engine's dependency.
SKILLS_REF := uvx --from skills-ref==$(call pin,skills-ref) agentskills
# Markdown lint (rules in .markdownlint-cli2.jsonc) and the Mermaid check need Node; neither is part of `check`.
MARKDOWNLINT := npx --yes markdownlint-cli2@$(call npm_pin,markdownlint-cli2)
# The compare step of the quality baseline (.quality-baseline.json): fails when a tool's full-tree count goes up.
QUALITY_BASELINE := $(PYTHON) dev/quality_baseline.py check
# The lockfiles that `make security` audits: every dev tool, Python, Node and Go.
DEP_LOCKFILES := dev/tools/uv.lock dev/tools/package-lock.json dev/tools/osv/go.mod dev/tools/actionlint/go.mod
COVERAGE := uvx coverage@$(call pin,coverage)
# Workflow and GitHub-config checks: actionlint (syntax, expressions, shellcheck on run: blocks), zizmor (workflow
# and Dependabot security, offline, at the pedantic persona: its help-level findings fail too) and check-jsonschema
# (the SchemaStore schemas it bundles, offline).
# actionlint is a Go `tool` in dev/tools/actionlint/go.mod: the Go module proxy serves it, go.sum checks it, and
# Dependabot (gomod) sees the version. `go -C` runs it in that folder, so the workflows are passed by full path.
ACTIONLINT := go -C dev/tools/actionlint tool actionlint
ZIZMOR := uvx zizmor@$(call pin,zizmor)
# The spell check: typos reads _typos.toml (the word list and the excluded data paths) from the repository root,
# and walks the tracked files that .gitignore does not hide.
TYPOS := uvx typos@$(call pin,typos)
CHECK_JSONSCHEMA := uvx --from check-jsonschema==$(call pin,check-jsonschema) check-jsonschema
# The coverage data stays under the git-ignored build output; settings (the floor) are in .coveragerc.
COVERAGE_DATA := $(CURDIR)/dev/dist/coverage/.coverage

# The Markdown that `docs-lint` holds to zero violations. A ratchet: a path joins once it is clean, and the list
# only grows. Everything else is reported by `docs-lint-all` and never fails.
DOCS_LINT_PATHS := 'implement/SKILL.md' 'implement/state.md' 'implement/playbooks/*.md' 'implement/prompts/*.md' \
	'docs/README.md' 'docs/STYLE_GUIDE.md' 'docs/architecture/**/*.md' 'docs/reference/branch-protection.md' 'docs/reference/dev-tooling.md' 'docs/reference/audit-master.md' 'docs/reference/implement-master.md' 'docs/how-to/contribute-a-change.md' 'docs/how-to/set-up-agent-tools.md' 'docs/COMMUNICATION_RULES.md' 'CONTRIBUTING.md' 'CHANGELOG.md' 'RELEASE_PROCESS.md' 'SECURITY.md' \
	'docs/explanation/user-overview/03-trust-and-safety.md' 'docs/explanation/contributor-deep-dive/04-stack-profiles.md' 'docs/explanation/contributor-deep-dive/05-evaluation.md' 'docs/how-to/add-a-stack-profile.md' 'docs/reference/harness-notes.md' \
	'audit/engine/docs/how-to/read-the-report.md'

# The prose check (dev/prose_check.py, the plain-language rules of docs/COMMUNICATION_RULES.md) is advisory: it
# reports warnings and notices and never fails a target. `make docs-prose` runs it; CI annotates changed Markdown.
PROSE_CHECK := $(PYTHON) dev/prose_check.py
# The tracked Markdown `make docs-prose` reads when FILES is not set: the markdownlint scope, without fixtures,
# test data and the worked example's copied reports.
PROSE_SCOPE := git ls-files -z -- '*.md' ':(exclude,glob)**/fixtures/**' ':(exclude,glob)**/testdata/**' \
	':(exclude,glob)**/server-worked-example/digital-assistant-server[-.]*.md'

ENGINE := audit/engine

# Mypy covers the recipe tools, the dev-only checks and the engine's build script. The engine's own code joins
# later, through a ratchet. The find picks up every Python file under audit/tools, implement/tools and
# dev, tests included, except the toy repositories under testdata/ (eval data).
TYPED_SOURCES := $(shell find audit/tools implement/tools dev -name '*.py' -not -path '*/testdata/*' -not -path '*/dist/*' 2>/dev/null | sort) $(ENGINE)/build.py

.DEFAULT_GOAL := help
.NOTPARALLEL:
.PHONY: help setup format format-check format\:check lint typecheck test coverage verify-rules crosscheck recipe-lint masters-check update-masters check security update-secrets-baseline self-audit update-audit-baseline validate-skills docs-lint docs-lint-all docs-prose docs-mermaid changelog-fix workflow-lint commit-lint spell spell-fix

help:
	@echo "verbs: format  format:check (format-check)  lint  typecheck  test  check  security"
	@echo "extra: setup (checks prerequisites, installs nothing)  coverage  self-audit  update-audit-baseline  verify-rules  crosscheck  recipe-lint  masters-check  update-masters  workflow-lint  commit-lint  spell  spell-fix  update-secrets-baseline  validate-skills"
	@echo "docs:  docs-lint  docs-lint-all  docs-prose [FILES=...]  docs-mermaid FILES=...  changelog-fix"

# There is nothing to install into the project: the runtime code is standard-library Python and the dev tools run
# through uvx and npx at pinned versions. This target checks the prerequisites without a prompt, exits 1 naming the
# first one that is missing, and writes nothing.
setup:
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "setup: Python 3.11 or newer is required (see .python-version)")'
	@command -v uv >/dev/null || { echo "setup: uv is required (https://docs.astral.sh/uv/)" >&2; exit 1; }
	@command -v git >/dev/null || { echo "setup: git is required" >&2; exit 1; }
	@command -v go >/dev/null || { echo "setup: Go 1.27 or newer is required for make check and make security (https://go.dev/doc/install)" >&2; exit 1; }
	@echo "setup: prerequisites present (python, uv, git, go); nothing to install"

format:
	$(RUFF) format audit implement dev

format-check:
	$(RUFF) format --check audit implement dev
	$(RUFF) check audit implement dev
	$(QUALITY_BASELINE) ruff -- $(RUFF) check audit implement dev --output-format json

format\:check: format-check

lint:
	$(RUFF) check audit implement dev

typecheck:
	$(MYPY) --config-file mypy.ini $(TYPED_SOURCES)
	$(QUALITY_BASELINE) mypy -- $(MYPY) --config-file mypy.ini $(TYPED_SOURCES)

test:
	cd $(ENGINE) && $(PYTHON) -m unittest discover -s tests
	$(PYTHON) -m unittest discover -s audit/tools/tests
	$(PYTHON) -m unittest discover -s implement/tools/tests
	$(PYTHON) -m unittest discover -s dev/tests

# Runs the engine's suite and the recipe tools' suite under coverage.py and fails when the total drops below the
# floor in .coveragerc (`fail_under`). Not part of `check`; CI runs it as its own job. Needs uv.
coverage:
	mkdir -p $(dir $(COVERAGE_DATA))
	rm -f $(COVERAGE_DATA)
	cd $(ENGINE) && COVERAGE_FILE=$(COVERAGE_DATA) $(COVERAGE) run --rcfile=$(CURDIR)/.coveragerc -m unittest discover -s tests
	COVERAGE_FILE=$(COVERAGE_DATA) $(COVERAGE) run --rcfile=.coveragerc --append -m unittest discover -s audit/tools/tests
	COVERAGE_FILE=$(COVERAGE_DATA) $(COVERAGE) run --rcfile=.coveragerc --append -m unittest discover -s implement/tools/tests
	COVERAGE_FILE=$(COVERAGE_DATA) $(COVERAGE) report --rcfile=.coveragerc

# The engine on this repository, read-only. Reports go under dist/self-audit/ (git-ignored); only artefacts/ and dist/
# are left out. --baseline is the ratchet (ADR-0001): exit 2 when a finding appears that .audit-baseline.json did not
# have, exit 0 otherwise. --no-user-config keeps the verdict the same on every machine. Publication:
# docs/reference/self-audit.md.
SELF_AUDIT_OUT := $(CURDIR)/dist/self-audit
SELF_AUDIT_FLAGS := --out $(SELF_AUDIT_OUT)/ --force --format both --no-user-config --exclude 'artefacts/*' --exclude 'dist/*'

self-audit:
	mkdir -p $(SELF_AUDIT_OUT)
	cd $(ENGINE) && $(PYTHON) -m audit $(CURDIR) $(SELF_AUDIT_FLAGS) --baseline $(CURDIR)/.audit-baseline.json

# Accepts today's findings as the new baseline: a deliberate act, never run to get green. Review the diff; the
# baseline only shrinks.
update-audit-baseline:
	mkdir -p $(SELF_AUDIT_OUT)
	cd $(ENGINE) && $(PYTHON) -m audit $(CURDIR) $(SELF_AUDIT_FLAGS)
	cp $(SELF_AUDIT_OUT)/audit-report.json .audit-baseline.json

# Every framework anchor the engine cites must still resolve in this repository.
verify-rules:
	cd $(ENGINE) && $(PYTHON) -m audit --verify-rules

# The subset validator that the tools use must agree with the reference JSON Schema package on every example
# and on thousands of one-defect mutants of them. About half a minute; needs uv and, the first time, the network.
crosscheck:
	$(CROSSCHECK) dev/crosscheck_jsonschema.py

# Lints the recipe Markdown and checks that audit/tools/CATALOGUE.md matches every tool's own --describe output.
recipe-lint:
	$(PYTHON) dev/recipe_lint.py .

# The audit and implement master lists (docs/reference/*-master.md) are generated from the catalogue, the check files
# and the playbooks. masters-check fails when either page is stale; update-masters rewrites them.
masters-check:
	$(PYTHON) dev/build_masters.py --check

update-masters:
	$(PYTHON) dev/build_masters.py --write

# Lints the GitHub Actions workflows and checks .github/dependabot.yml. All three tools run offline.
# Read-only: report each misspelling with its file and line. `make spell-fix` writes the suggested fixes; review them.
spell:
	$(TYPOS)

spell-fix:
	$(TYPOS) --write-changes

workflow-lint:
	$(ACTIONLINT) $(CURDIR)/.github/workflows/*.yml
	$(ZIZMOR) --offline --persona pedantic .github
	$(CHECK_JSONSCHEMA) --builtin-schema vendor.github-workflows .github/workflows/*.yml
	$(CHECK_JSONSCHEMA) --builtin-schema vendor.dependabot .github/dependabot.yml

# Checks that each commit subject in RANGE follows Conventional Commits; merge commits are skipped. CI runs it on
# the commits of a pull request. Locally: `make commit-lint` checks what this branch adds on top of origin/dev.
RANGE ?= origin/dev..HEAD
commit-lint:
	$(PYTHON) dev/commit_lint.py --range $(RANGE)

check: format-check typecheck test verify-rules crosscheck recipe-lint masters-check workflow-lint spell

# No third-party runtime dependencies exist to audit, so the gate is a secrets scan. The baseline
# lists the deliberate key-shaped strings in the fixtures and tests; a new hit fails the scan.
# The dependency audit: osv-scanner, pinned in dev/tools/osv/go.mod (a Go `tool` directive, so Dependabot sees it),
# reads the dev tools' lockfiles and fails on a known vulnerability that no osv-scanner.toml accepts. Without
# --config, osv-scanner reads the osv-scanner.toml next to each lockfile, the same file OpenSSF Scorecard reads.
# --no-call-analysis=go: the module holds no Go code of its own, so govulncheck has nothing to analyse.
# The audit engine's TOOL-04 reads this recipe and needs the tool name written out, not hidden in a variable.
security:
	git ls-files -z | xargs -0 $(DETECT_SECRETS_HOOK) --baseline .secrets.baseline
	go -C dev/tools/osv tool osv-scanner scan source --no-call-analysis=go $(foreach f,$(DEP_LOCKFILES),--lockfile=$(CURDIR)/$(f))

# Run this after a deliberate change to a fixture or test that holds a key-shaped string, then review the diff.
update-secrets-baseline:
	$(DETECT_SECRETS) scan --baseline .secrets.baseline

# Builds the agentic-readiness-audit and agentic-readiness-implement skill bundles fresh and validates both
# against the Agent Skills specification (S4.5.2). Not part of `check`: it is not one of the framework's seven verbs, and the
# validator needs the network the first time, same as `crosscheck`'s reference package.
validate-skills:
	$(PYTHON) dev/build_skills.py
	$(SKILLS_REF) validate dev/dist/skills/agentic-readiness-audit
	$(SKILLS_REF) validate dev/dist/skills/agentic-readiness-implement

# Lints the Markdown in DOCS_LINT_PATHS; fails on any violation. Then compares the full-tree count with
# .quality-baseline.json. The prose check is not part of it: see docs-prose. Needs Node (npx); the first run
# fetches the pinned CLI. CI runs it in the `docs` job when a Markdown file changed.
docs-lint:
	$(MARKDOWNLINT) $(DOCS_LINT_PATHS)
	$(QUALITY_BASELINE) markdownlint -- sh -c "git ls-files -z '*.md' | xargs -0 $(MARKDOWNLINT)"

# Reports violations in every tracked Markdown file (fixtures excluded by the config). Never fails: the debt
# outside DOCS_LINT_PATHS is recorded, not gated.
docs-lint-all:
	-git ls-files -z '*.md' | xargs -0 $(MARKDOWNLINT)

# Reports the prose check's warnings and notices (docs/COMMUNICATION_RULES.md) in FILES, or in all tracked Markdown
# when FILES is not set. Advisory: the check exits 0 whatever it finds. Add PROSE_ARGS=--min-severity=warning to
# hide the notices.
docs-prose:
ifdef FILES
	$(PROSE_CHECK) $(PROSE_ARGS) $(FILES)
else
	$(PROSE_SCOPE) | xargs -0 $(PROSE_CHECK) $(PROSE_ARGS)
endif

# Rewrites CHANGELOG.md in place with the markdownlint fixes (release-please writes `*` bullets and double blank
# lines). release-please.yml runs it on the release pull request; it fails when a violation is left that --fix
# cannot fix.
changelog-fix:
	$(MARKDOWNLINT) --fix CHANGELOG.md

# Renders every Mermaid block in FILES with the pinned mermaid-cli; fails on a block that does not render.
docs-mermaid:
	$(PYTHON) dev/mermaid_check.py $(MERMAID_FLAGS) $(FILES)
