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
make typecheck      # mypy, strict, on brownfield-recipes/tools and dev, and the engine's tools/build.py
make test           # the engine's unittest suite, then the recipe tools' (the catalogue checks), then the dev checks'
make check          # THE gate: format:check, typecheck, test, the engine's --verify-rules, the schema cross-check, recipe-lint
make security       # secrets scan against .secrets.baseline
```

One test, without the whole suite (the first from `brownfield-recipes/deterministic-audit/`, the second from the
repository root):

```bash
python3 -m unittest tests.test_cmd_pack -k verbs
python3 -m unittest discover -s brownfield-recipes/tools/tests -k catalogue
```

This file is read by Claude Code, opencode, Codex, Gemini CLI, Cursor and any other harness that reads `AGENTS.md`;
no vendor-specific instruction file exists beside it.

- Run `make check` and `make security` before you propose a change. Do not run an ad-hoc substitute.
- When you change Markdown, also run `make docs-lint` (needs Node; lints the ratchet path list in the
  `Makefile`) and validate every Mermaid block you add (`make docs-mermaid FILES=<file.md>`).
- Python 3.11 or newer (pinned in `.python-version`), and `uv` for the pinned dev tools (ruff, mypy, detect-secrets). Nothing is installed into the project.
- After a deliberate change to a fixture or test that holds a key-shaped string, run `make update-secrets-baseline`
  and review the diff.
- Never weaken a gate to get green: no `.skip`, no rule turned off, no assertion relaxed. If you cannot pass a gate, say so.
- `make test` skips the positive-fixture test when `CI=true` and its scaffolder (a sibling repository) is absent.
  Locally the test fails loudly without it; set `AUDIT_BOOTSTRAP=<path to bootstrap.py>` to point at the scaffolder.

## Boundaries

| Path | What it is | Rules |
|---|---|---|
| `README.md`, `shared/`, `brownfield-legacy/`, `greenfield-bootstrap/` | The framework documents. Normative. | If a tool disagrees with them, the tool is wrong. |
| `spec/` | Numbered requirements (`REQ-...`) for what a repository must have. See `spec/README.md`. | Recipes link to requirement IDs; they do not restate rules. |
| `brownfield-recipes/deterministic-audit/` | The Python audit engine: reads a repository, never writes to it, no LLM, no network. | Standard library only. Read its `AGENTS.md` before changing it. |
| `brownfield-recipes/audit/`, `implement/` | The LLM-driven recipes (`SKILL.md` files, checks, playbooks). | The model's judgment is backed by cited evidence; tools do the counting. |
| `brownfield-recipes/tools/`, `schema/` | Deterministic tools the recipes call, and the JSON Schemas for their files. | Standard library only. No network. Never write inside a target repository, except `progress.py` writing the target's two state files (ADR 0002 in `brownfield-recipes/docs/architecture/adrs/`). |
| `brownfield-recipes/dev/` | Checks that run in CI and are not shipped. Today: the cross-check of the tools' schema validator against the reference `jsonschema` package, and the Mermaid render check. | May import dev packages, which `uv run --with` installs for one run. Nothing in `tools/` or the engine may import them. |
| `brownfield-recipes/docs/` | Documentation for all of the above. | Follow `brownfield-recipes/docs/STYLE_GUIDE.md`; start at `docs/architecture/README.md`. |
| `artefacts/` | Scratch notes and plans. The folder is tracked, its contents are git-ignored. | Off-limits. Do not read, search or list it unless a human gives you a file path. |

A folder with no files yet is not written yet; the docs page that describes it says `Planned`.

## Never

- Never open, print or quote a `.env` file or any other secret store. Fixtures contain `.env` files on purpose; treat them as data you may not read.
- Never push, push tags, open a pull request, or delete anything remote. The maintainer does those.
- Never add a third-party import to the engine or to `brownfield-recipes/tools/`. Dev tools run through `uvx` only; the one place for dev-only imports is `brownfield-recipes/dev/`.
- Never run another repository's own commands directly while auditing it. Use the engine's probe runner, which is opt-in
  (`--run-gates` plus `--allow-probe <verb>`).
- Never describe a feature as working when it is only planned.
- Never edit, skip or delete a test to make a failing test pass, in `brownfield-recipes/deterministic-audit/tests/` or
  `brownfield-recipes/tools/tests/`. A fixture is data: change one only with the test that needs the change.

## Definition of done

A change is done when all of this holds:

- `make check` and `make security` pass.
- `make docs-lint` passes when Markdown changed, and a new Markdown file under a ratchet path is clean.
- New code has tests, and a new engine check has a fixture that fails exactly that check.
- When a change alters a public interface, observable behaviour, the architecture or a decision, update the
  affected documentation and the decision records in the same change set. When you fill in a page marked `Planned`,
  remove that note and update the doc router.
- Python files carry the SPDX header `AGPL-3.0-or-later` and the copyright line. Documentation, schemas and published
  outputs are `GFDL-1.3-only`. The zones are in `brownfield-recipes/docs/reference/licensing.md`.
- Commits follow Conventional Commits, one logical change each, so any one can be reverted alone.
  Work that follows a build roadmap or track also carries a `Roadmap-Step: <step id>` trailer
  (for example `S4.6`, `IR07.3` or `MR02`).

## Where to look

- Requirements: `spec/README.md`, and `spec/readiness-requirements.md`.
- Terms: `brownfield-recipes/docs/architecture/glossary.md` and `shared/Glossary.md`.
- The engine's design, checks and ADRs: `brownfield-recipes/deterministic-audit/docs/architecture/README.md`.
- Tool ecosystem and index tooling: `shared/Tool-Ecosystem.md`. If `codebase-memory-mcp` is available, query it
  before reading whole files.
