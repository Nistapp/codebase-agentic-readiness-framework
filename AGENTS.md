# AGENTS.md

This repository is the Codebase Agentic Readiness Framework: documentation that says what makes a codebase safe for AI
coding agents, plus tools that check it. `brownfield-recipes/` holds the audit and implementation recipes and the
deterministic engine under them. Read this file first; the engine has its own, stricter file (see Boundaries).

## Commands

The framework's seven verbs run through the root `Makefile`. CI runs the same commands.

```bash
make format         # rewrite formatting in place
make format:check   # read-only: formatting and lint rules (alias: make format-check)
make lint           # read-only lint
make typecheck      # mypy, strict, on brownfield-recipes/tools and the engine's tools/build.py
make test           # the engine's unittest suite
make check          # THE gate: format:check, typecheck, test, and the engine's --verify-rules
make security       # secrets scan against .secrets.baseline
```

- Run `make check` and `make security` before you propose a change. Do not run an ad-hoc substitute.
- Python 3.11 or newer, and `uv` for the pinned dev tools (ruff, mypy, detect-secrets). Nothing is installed into the project.
- After a deliberate change to a fixture or test that holds a key-shaped string, run `make update-secrets-baseline`
  and review the diff.
- Never weaken a gate to get green: no `.skip`, no rule turned off, no assertion relaxed. If you cannot pass a gate, say so.
- `make test` skips the positive-fixture test when `CI=true` and its scaffolder (a sibling repository) is absent.
  Locally the test fails loudly without it; set `AUDIT_BOOTSTRAP=<path to bootstrap.py>` to point at the scaffolder.
- Known engine defect: the engine's CMD-01 and CMD-02 report FAIL on this Makefile, because it does not read the escaped
  `format\:check` target or follow `check`'s prerequisites. The Makefile is correct; do not rewrite it to quiet the engine.

## Boundaries

| Path | What it is | Rules |
|---|---|---|
| `README.md`, `shared/`, `brownfield-legacy/`, `greenfield-bootstrap/` | The framework documents. Normative. | If a tool disagrees with them, the tool is wrong. |
| `spec/` | Numbered requirements (`REQ-...`) for what a repository must have. See `spec/README.md`. | Recipes link to requirement IDs; they do not restate rules. |
| `brownfield-recipes/deterministic-audit/` | The Python audit engine: reads a repository, never writes to it, no LLM, no network. | Standard library only. Read its `AGENTS.md` before changing it. |
| `brownfield-recipes/audit/`, `implement/` | The LLM-driven recipes (`SKILL.md` files, checks, playbooks). | The model's judgment is backed by cited evidence; tools do the counting. |
| `brownfield-recipes/tools/`, `schema/` | Deterministic tools the recipes call, and the JSON Schemas for their files. | Standard library only. No network. Never write inside a target repository. |
| `brownfield-recipes/docs/` | Documentation for all of the above. | Follow `brownfield-recipes/docs/STYLE_GUIDE.md`; start at `docs/architecture/README.md`. |
| `artefacts/` | Scratch notes and plans, git-ignored. | Off-limits. Do not read, search or list it unless a human gives you a file path. |

A folder with no files yet is not written yet; the docs page that describes it says `Planned`.

## Never

- Never open, print or quote a `.env` file or any other secret store. Fixtures contain `.env` files on purpose; treat them as data you may not read.
- Never push, push tags, open a pull request, or delete anything remote. The maintainer does those.
- Never add a third-party import to the engine or to `brownfield-recipes/tools/`. Dev tools run through `uvx` only.
- Never run another repository's own commands directly while auditing it. Use the engine's probe runner, which is opt-in
  (`--run-gates` plus `--allow-probe <verb>`).
- Never describe a feature as working when it is only planned.

## Definition of done

A change is done when all of this holds:

- `make check` and `make security` pass.
- New code has tests, and a new engine check has a fixture that fails exactly that check.
- The documentation a change affects is updated in the same set of commits. When you fill in a page marked `Planned`,
  remove that note and update the doc router.
- Python files carry the SPDX header `AGPL-3.0-or-later` and the copyright line. Documentation, schemas and published
  outputs are `GFDL-1.3-only`. The zones are in `brownfield-recipes/docs/reference/licensing.md`.
- Commits follow Conventional Commits, one logical change each, so any one can be reverted alone.
  Work that follows the build roadmap also carries a `Roadmap-Step: S<m>.<n>` trailer.

## Where to look

- Requirements: `spec/README.md`, and `spec/readiness-requirements.md` once it exists.
- Terms: `brownfield-recipes/docs/architecture/glossary.md` and `shared/Glossary.md`.
- The engine's design, checks and ADRs: `brownfield-recipes/deterministic-audit/docs/architecture/README.md`.
- Tool ecosystem and index tooling: `shared/Tool-Ecosystem.md`. If `codebase-memory-mcp` is available, query it
  before reading whole files.
