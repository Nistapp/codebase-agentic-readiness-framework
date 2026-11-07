# Python

> Follows the anatomy in [`README.md`](README.md). Covers pip, uv and poetry. `shipped`, per
> `run_context.stack_profile` (DP §5.6).

---

## Detection signals

`facts.json`'s `stack` section reads `ecosystems: ["python"]` from `pyproject.toml`, `setup.py`,
`requirements*.txt` or `Pipfile` anywhere in the tree, or, with none of those present, from a bare `.py`
source file alone (D29 item 9) — the latter is `source_only`, and several checks below treat it
differently from a manifest-bearing project, never as a false `PASS`. `package_managers` reads the
lockfile at the repository root: `poetry.lock` → poetry, `uv.lock` → uv, `Pipfile.lock` → pipenv; a
plain `pip` project pinned only by `requirements.txt` has no lockfile signal at all (`requirements.txt`
is a manifest, not a lock, by the engine's own "manifest-as-lock" exclusion — see Pitfalls).

## Command-surface map

No `pyproject.toml` section plays npm's `scripts` role generically: the engine's own reader understands
only `[tool.poe.tasks]` (poethepoet) or `[tool.taskipy.tasks]` (taskipy) — a project on either tool
defines the seven verbs there directly; every other pip/uv/poetry project needs a `Makefile` or
`Taskfile` as the actual runner, with `uv run <verb>`/`poetry run <verb>` only invoking what that file
defines. Typical realisation: `format` → `ruff format`/`black .`, `format:check` → `ruff format --check`/
`black --check .`, `lint` → `ruff check`, `typecheck` → `mypy`/`pyright`, `test` → `pytest`, `check` →
the four above in sequence, `security` → `pip-audit`/`safety check`.

## Tooling defaults

Formatter: Ruff's own formatter, or Black. Linter: Ruff (replacing Flake8/Pylint in new projects) or
Flake8/Pylint on an older one; config in `pyproject.toml`'s `[tool.ruff]`/`[tool.black]` or standalone
`ruff.toml`/`.flake8`/`.pylintrc`. Type checker: mypy or Pyright, `[tool.mypy]`/`[tool.pyright]` or
`mypy.ini`'s `strict = true`. Test runner: pytest. Dependency scanner: `pip-audit` (works against any of
pip/uv/poetry's resolved environment) or `safety check`.

## Execution determinism

`.python-version` or `pyproject.toml`'s `requires-python` pins the interpreter (`EXEC-01`); uv and
poetry both honour `.python-version` directly, pip does not read it at all — say which the project
actually acts on, not just which file exists. The matching lockfile (`poetry.lock`/`uv.lock`/
`Pipfile.lock`) must be git-tracked at the root; `uv sync --frozen`/`poetry install --no-update`/
`pipenv sync` is the non-interactive install path, never a bare `install` that can resolve new versions.

## CI idiom

GitHub Actions is the common provider: `actions/checkout`, `actions/setup-python` with `python-version`
pinned to `requires-python`/`.python-version`, the matching manager's own cache (`setup-python`'s
`cache: pip`, or `astral-sh/setup-uv`/`cache: poetry` for the others), then the project's `check` target.

## Baseline / ratchet

Ruff and mypy both support an incremental-only invocation (changed files alone in CI) as the common
"no new violations" pattern; Ruff also reads a `[tool.ruff.lint]` `per-file-ignores` table to grandfather
existing files while a stricter rule set is phased in. Not verified against a real repository in this
leaf.

## Boundaries

A `src/<package>/` layout with internal-only modules under a leading underscore is the idiom; nothing in
pip/uv/poetry enforces an import boundary on its own — `import-linter` (a `[tool.importlinter]` contract)
is the closest analogue to `eslint-plugin-boundaries`. Not seen in the one repository checked (a single
flat `audit/` package, no sub-boundaries).

## Engine coverage

Reliable as the engine reads it: `EXEC-01` for `.python-version`/`requires-python`; `TOOL-01`–`TOOL-03`
for Ruff/Black/mypy/Pyright's fixed filename and `pyproject.toml` key lists. Needs independent agent
verification: `CMD-01` on a Makefile-less, poe/taskipy-less pip/uv/poetry project, where every verb reads
`UNKNOWN` rather than `FAIL` for lack of a recognised runner — confirm by reading whether the project
documents its commands in prose (a README) instead, which the engine cannot credit; `EXEC-02`, whose
`python` lockfile table omits `pip` entirely (the same "manifest-as-lock" exclusion as Detection signals)
— a plain `requirements.txt` project reads `FAIL` naming `poetry.lock`/`uv.lock`/`Pipfile.lock` as the
missing file, accurate ("no lockfile exists") but worth explaining to a user expecting its own manifest
to count; a `source_only` repository (D29 item 9: Python recognised from a bare `.py` file, no manifest
at all) reads `EXEC-02` `UNKNOWN`, correctly, since no dependency is declared to lock.

## Pitfalls

The one repository checked, the engine's own pre-migration tree, is `source_only`: no `pyproject.toml`,
`setup.py`, `requirements.txt`, `Pipfile` or `Makefile` anywhere, and no CI workflow at all — every
`CMD-01` verb and `EXEC-02` reads `UNKNOWN`, not `FAIL`, by the engine's own documented rule for a
manifest-less ecosystem, and genuinely so: the project's own README states "no install step, no
dependencies" as a deliberate design choice (stdlib-only, so the tool runs on a machine with nothing
installed), not an omission to flag. A local, untracked `.env` exists in the same checkout — confirmed
via `git ls-files` only, never opened, per the root `AGENTS.md` rule — and is correctly untracked, so
`SEC-01` reads `PASS`.

## Verified

2026-10-13, against the engine repo itself, pre-migration
(`/home/kc/Projects/Nistapp-agentic-frameworks/agentic-readiness-audit`, `dev` at `b8235a8`, matching the
§10 pin): no `pyproject.toml`/`setup.py`/`requirements*.txt`/`Pipfile`/`Makefile`/CI workflow anywhere in
the tree — a genuine `source_only` Python project, not a pip/uv/poetry one, so the pip/uv/poetry
conventions above are read from the engine's own source (`audit/rules/checks/tool.py`, `execution.py`,
`_common.py`) and D29 item 9's changelog entry, not exercised against a manifest-bearing repository —
that remains to do once one joins the corpus. Read via direct inspection of the checkout (`git ls-files`,
the root listing, `README.md`); no target command was run and `.env` was not opened.
