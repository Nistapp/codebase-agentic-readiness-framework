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
#   make test           the four unittest suites: the engine's, the audit tools' (the catalogue checks), the
#                       implement tools' and the dev checks'; at once on Linux (TEST_JOBS), else one by one
#   make check          THE gate: format:check -> typecheck -> test, plus the engine's rule check, the schema
#                       cross-check, the recipe linter, the master-list freshness check,
#                       the workflow lint and the spell check
#   make security       secrets scan against the committed baseline, then the dependency audit (osv-scanner) of
#                       the dev tools' lockfiles; needs Go and the network
#   make coverage       (extra) the engine's and the tools' suites under coverage.py; fails below the floor in
#                       .coveragerc. CI runs it in parts: coverage-<suite> per job, then coverage-combine
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
	'audit/engine/docs/how-to/read-the-report.md' 'docs/reference/versions.md' 'docs/how-to/implement-an-audit-report.md' \
	'docs/how-to/resume-an-interrupted-run.md' 'docs/glossary.md' 'AGENTS.md'

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

# The suites of `test`. On Linux with GNU make 4 or newer, `make test` runs them at once, in a sub-make with
# TEST_JOBS: about 80 s on CI instead of 170 s, and about 200 MB of memory in all (measured 2026-11-09). Elsewhere
# they run one by one: macOS ships GNU make 3.81, which has no --output-sync. `make test TEST_JOBS=` runs them one by
# one on Linux too. --output-sync=target prints each suite's output in one piece, when that suite ends.
TEST_SUITES := test-engine test-audit-tools test-implement-tools test-dev
ifeq ($(shell uname -s 2>/dev/null)-$(filter 3.%,$(MAKE_VERSION)),Linux-)
TEST_JOBS ?= -j4 --output-sync=target
endif

# Everything else runs one target at a time, even under `make -j`: spec/command-surface.md fixes the order of
# `check` (format:check, then typecheck, then test). Only the sub-make that `test` starts for its suites is parallel.
# GNU make 4.3 (Ubuntu 24.04) reads any .NOTPARALLEL as "the whole file", so the sub-make leaves it out.
ifndef TEST_SUITES_SUBMAKE
.NOTPARALLEL:
endif
.PHONY: help setup format format-check format\:check lint typecheck test $(TEST_SUITES) test-engine-shard test-audit-tools-shard test-part coverage coverage-engine coverage-engine-shard coverage-audit-tools-shard coverage-part coverage-audit-tools coverage-implement-tools coverage-combine verify-rules crosscheck recipe-lint masters-check update-masters check security update-secrets-baseline self-audit update-audit-baseline validate-skills docs-lint docs-lint-all docs-prose docs-mermaid changelog-fix workflow-lint commit-lint spell spell-fix

help:
	@echo "verbs: format  format:check (format-check)  lint  typecheck  test  check  security"
	@echo "parts: test-engine  test-audit-tools  test-implement-tools  test-dev  coverage-engine  coverage-audit-tools  coverage-implement-tools  coverage-combine"
	@echo "ci:    test-part SHARD=<i>  coverage-part SHARD=<i>  coverage-combine SHARDED=1  (and test-<suite>-shard, coverage-<suite>-shard)"
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
	$(MAKE) --no-print-directory TEST_SUITES_SUBMAKE=1 $(TEST_JOBS) $(TEST_SUITES)

test-engine:
	cd $(ENGINE) && $(PYTHON) -m unittest discover -s tests

test-audit-tools:
	$(PYTHON) -m unittest discover -s audit/tools/tests

test-implement-tools:
	$(PYTHON) -m unittest discover -s implement/tools/tests

test-dev:
	$(PYTHON) -m unittest discover -s dev/tests

# CI splits the slow suites (SHARDED_SUITES) into TEST_SHARDS parts that run in separate jobs; SHARD=<i> picks one
# (1 to TEST_SHARDS). dev/test_shard.py finds the modules at run time and balances them by
# dev/test_shard_weights.json; every module is in exactly one shard, and a shard that selects no test fails. `test`
# and `coverage` never shard.
TEST_SHARDS := 2
SHARDED_SUITES := engine audit-tools
test_shard = $(CURDIR)/dev/test_shard.py --suite $(1) --shard $(SHARD)/$(TEST_SHARDS)
require_shard = @test -n "$(SHARD)" || { echo "$@: set SHARD to a number from 1 to $(TEST_SHARDS)" >&2; exit 1; }

test-engine-shard:
	$(require_shard)
	cd $(ENGINE) && $(PYTHON) $(call test_shard,engine)

test-audit-tools-shard:
	$(require_shard)
	$(PYTHON) $(call test_shard,audit-tools)

# Every suite of `test` in TEST_SHARDS parts, for CI's Python 3.14 jobs: part <i> is shard <i> of each sharded suite
# plus the targets in TEST_PART_<i>, run at once as `test` runs its suites. test-dev takes about as long as an engine
# shard, so it shares a part with no other whole suite. dev/tests/test_ci_parity.py fails when the parts leave out a
# suite of `test`.
TEST_PART_1 := test-implement-tools verify-rules
TEST_PART_2 := test-dev
test-part:
	$(require_shard)
	$(MAKE) --no-print-directory TEST_SUITES_SUBMAKE=1 $(TEST_JOBS) $(SHARDED_SUITES:%=test-%-shard) $(TEST_PART_$(SHARD))

# Runs the engine's suite and the tools' suites under coverage.py and fails when the total drops below the floor in
# .coveragerc (`fail_under`). Not part of `check`; needs uv. Each coverage-<suite> writes its own data file
# (.coverage.<suite>), so CI runs them in separate jobs; coverage-combine merges them and reports. It fails when a
# suite's file is missing, so a partial run cannot pass on a partial total. coverage.py does not measure dev/.
#
# Each suite runs as CI runs it, so the local number is CI's number. HOME is an empty directory, one per suite so
# that parallel jobs cannot clear each other's: the IDX checks read the user's index store and MCP configs from
# $HOME, which a CI runner does not have. CI=true lets the positive-fixture test skip as it does in CI (its
# scaffolder is found through $HOME). uv's own directories are resolved from the real home first, so uvx still
# finds its cache and tools and nothing is downloaded again.
COVERAGE_HOME := $(CURDIR)/dev/dist/coverage/home
coverage_env = env -u AUDIT_INDEX_STORE -u XDG_CONFIG_HOME -u XDG_CACHE_HOME HOME=$(COVERAGE_HOME)/$(1) CI=true \
	UV_CACHE_DIR="$$(uv cache dir)" UV_PYTHON_INSTALL_DIR="$$(uv python dir)" UV_TOOL_DIR="$$(uv tool dir)"
COVERAGE_SUITES := coverage-engine coverage-audit-tools coverage-implement-tools
coverage: coverage-engine coverage-audit-tools coverage-implement-tools coverage-combine

coverage-engine:
	mkdir -p $(dir $(COVERAGE_DATA))
	rm -f $(COVERAGE_DATA).engine
	rm -rf $(COVERAGE_HOME)/engine && mkdir -p $(COVERAGE_HOME)/engine
	cd $(ENGINE) && $(call coverage_env,engine) COVERAGE_FILE=$(COVERAGE_DATA).engine $(COVERAGE) run --rcfile=$(CURDIR)/.coveragerc -m unittest discover -s tests

coverage-audit-tools:
	mkdir -p $(dir $(COVERAGE_DATA))
	rm -f $(COVERAGE_DATA).audit-tools
	rm -rf $(COVERAGE_HOME)/audit-tools && mkdir -p $(COVERAGE_HOME)/audit-tools
	$(call coverage_env,audit-tools) COVERAGE_FILE=$(COVERAGE_DATA).audit-tools $(COVERAGE) run --rcfile=.coveragerc -m unittest discover -s audit/tools/tests

coverage-implement-tools:
	mkdir -p $(dir $(COVERAGE_DATA))
	rm -f $(COVERAGE_DATA).implement-tools
	rm -rf $(COVERAGE_HOME)/implement-tools && mkdir -p $(COVERAGE_HOME)/implement-tools
	$(call coverage_env,implement-tools) COVERAGE_FILE=$(COVERAGE_DATA).implement-tools $(COVERAGE) run --rcfile=.coveragerc -m unittest discover -s implement/tools/tests

# One shard of a sharded suite under coverage.py, in the same environment as coverage-<suite>, with its own HOME and
# data file (.coverage.<suite>-<i>).
coverage-engine-shard:
	$(require_shard)
	mkdir -p $(dir $(COVERAGE_DATA))
	rm -f $(COVERAGE_DATA).engine-$(SHARD)
	rm -rf $(COVERAGE_HOME)/engine-$(SHARD) && mkdir -p $(COVERAGE_HOME)/engine-$(SHARD)
	cd $(ENGINE) && $(call coverage_env,engine-$(SHARD)) COVERAGE_FILE=$(COVERAGE_DATA).engine-$(SHARD) $(COVERAGE) run --rcfile=$(CURDIR)/.coveragerc $(call test_shard,engine)

coverage-audit-tools-shard:
	$(require_shard)
	mkdir -p $(dir $(COVERAGE_DATA))
	rm -f $(COVERAGE_DATA).audit-tools-$(SHARD)
	rm -rf $(COVERAGE_HOME)/audit-tools-$(SHARD) && mkdir -p $(COVERAGE_HOME)/audit-tools-$(SHARD)
	$(call coverage_env,audit-tools-$(SHARD)) COVERAGE_FILE=$(COVERAGE_DATA).audit-tools-$(SHARD) $(COVERAGE) run --rcfile=.coveragerc $(call test_shard,audit-tools)

# The coverage suites in TEST_SHARDS parts, for CI's Python 3.11 jobs: part <i> is shard <i> of each sharded suite
# plus the targets in COVERAGE_PART_<i>, run at once. Each writes its own data file for coverage-combine SHARDED=1.
COVERAGE_PART_1 := coverage-implement-tools
COVERAGE_PART_2 :=
coverage-part:
	$(require_shard)
	$(MAKE) --no-print-directory TEST_SUITES_SUBMAKE=1 $(TEST_JOBS) $(SHARDED_SUITES:%=coverage-%-shard) $(COVERAGE_PART_$(SHARD))

# The data files coverage-combine needs: one per suite, or, with SHARDED=1 (CI), one per shard of each sharded suite
# in place of that suite's. `coverage combine` deletes the files it merges, so a later combine cannot reuse stale data.
COMBINE_PARTS = $(if $(SHARDED),$(foreach s,$(SHARDED_SUITES),$(foreach i,$(shell seq 1 $(TEST_SHARDS)),$(s)-$(i))) implement-tools,engine audit-tools implement-tools)
coverage-combine:
	@for part in $(COMBINE_PARTS); do \
		test -f $(COVERAGE_DATA).$$part || { echo "coverage-combine: no data file $(COVERAGE_DATA).$$part; run its coverage target first" >&2; exit 1; }; \
	done
	rm -f $(COVERAGE_DATA)
	COVERAGE_FILE=$(COVERAGE_DATA) $(COVERAGE) combine --rcfile=.coveragerc $(addprefix $(COVERAGE_DATA).,$(COMBINE_PARTS))
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
