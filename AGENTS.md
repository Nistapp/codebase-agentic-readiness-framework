# AGENTS.md

This repository is the Codebase Agentic Readiness Framework: documentation that says what makes a codebase safe for AI
coding agents, plus tools that check it. `audit/` holds the audit recipe, its tools and the deterministic engine.
`implement/` holds the recipe that closes the findings of an audit. Read this file first. Three folders have their own
rules: `audit/AGENTS.md`, `implement/AGENTS.md` and `audit/engine/AGENTS.md` (the strictest). Read the file for a
folder before you change it.

## Users: audit or implement a repository

- When asked to audit a repository, follow `audit/SKILL.md` from this repository's root.
- When asked to implement fixes from an audit report, follow `implement/SKILL.md`.

The rest of this file is for changes to this repository.

## Commands

The framework's seven verbs run through the root `Makefile`. CI runs the same commands.

```bash
make setup          # check the prerequisites (Python 3.11+, uv, git); nothing is installed
make format         # rewrite formatting in place
make format:check   # read-only: formatting and lint rules (alias: make format-check)
make lint           # read-only lint
make typecheck      # mypy, strict, on audit/tools, implement/tools and dev, and the engine's build.py
make test           # the engine's suite, then the audit tools', the implement tools' and the dev checks'
make check          # THE gate: format:check, typecheck, test, the engine's --verify-rules, the schema
                    # cross-check, recipe-lint
make security       # secrets scan against .secrets.baseline
```

One test, without the whole suite. Run the engine's tests from `audit/engine/`:

```bash
python3 -m unittest tests.test_cmd_pack -k verbs
```

Run the tools' tests from the repository root:

```bash
python3 -m unittest discover -s audit/tools/tests -k catalogue
python3 -m unittest discover -s implement/tools/tests
```

This file is read by Claude Code, opencode, Codex, Gemini CLI, Cursor and any other harness that reads `AGENTS.md`;
no vendor-specific instruction file exists beside it.

- Run `make check` and `make security` before you propose a change. Do not run an ad-hoc substitute.
- When you change Markdown, also run `make docs-lint` (needs Node; lints the ratchet path list in the
  `Makefile`) and validate every Mermaid block you add (`make docs-mermaid FILES=<file.md>`).
- Python 3.11 or newer (pinned in `.python-version`), and `uv` for the pinned dev tools (ruff, mypy, detect-secrets).
  Nothing is installed into the project.
- Local hooks are `lefthook.yml` (a stop on commits to `dev` and `main`, format check on staged Python,
  `make docs-lint` on staged ratchet Markdown, a secrets scan, a Conventional Commits check).
  The developer runs `lefthook install` once per clone; an agent never does.
  Hooks do not replace the gate: CI runs `make check`, `make security` and `make docs-lint`.
- `make coverage` runs the engine's, the audit tools' and the implement tools' suites under coverage.py. It fails
  below the floor in `.coveragerc` (`fail_under`). CI runs it as the `coverage` job. The floor is debt that only goes
  up: raise it when coverage rises, never lower it to get green.
- Quality baseline: existing lint debt is counted in `.quality-baseline.json` (ruff, mypy, Markdown lint outside the
  ratchet) and the secrets in `.secrets.baseline`. No new violations: `make format-check`, `make typecheck` and
  `make docs-lint` compare the live count with the baseline and fail when it went up (a ratchet). A baseline only goes
  down, a coverage floor only goes up; raising either needs the owner. When a count falls, lower the baseline in the
  same change.
- After a deliberate change to a fixture or test that holds a key-shaped string, run `make update-secrets-baseline`
  and review the diff.
- Never weaken a gate to get green: no `.skip`, no rule turned off, no assertion relaxed. If you cannot pass a gate,
  say so.
- `make test` skips the positive-fixture test when `CI=true` and its scaffolder (a sibling repository) is absent.
  Locally the test fails loudly without it; set `AUDIT_BOOTSTRAP=<path to bootstrap.py>` to point at the scaffolder.

## Boundaries

| Path | What it is | Rules |
|---|---|---|
| `README.md`, `docs/`, `greenfield/` | The framework documents (`docs/framework/`), the Diátaxis docs for everything here, and the greenfield templates. Normative. | If a tool disagrees with them, the tool is wrong. Follow `docs/STYLE_GUIDE.md`; start at `docs/README.md`. |
| `spec/` | Numbered requirements (`REQ-...`) for what a repository must have. See `spec/README.md`. | Recipes link to requirement IDs; they do not restate rules. |
| `audit/` | The audit recipe (`SKILL.md`, `checks/`, `prompts/`, `catalogue.json`, `stacks/`), the JSON Schemas (`schema/`) and the deterministic tools (`tools/`). | Standard library only. No network. Never write inside a target repository. Read `audit/AGENTS.md`. |
| `audit/engine/` | The Python audit engine: reads a repository, never writes to it, no LLM, no network. | Standard library only. Read `audit/engine/AGENTS.md` before you change it. |
| `implement/` | The implement recipe (`SKILL.md`, `playbooks/`, `prompts/`, `state.md`) and its tools (`tools/`). | Standard library only. `progress.py` writes only the target's two state files (ADR 0002 in `implement/docs/architecture/adrs/`). Read `implement/AGENTS.md`. |
| `dev/` | Checks and builds that run in this repository and CI only, never shipped: the recipe linter, the schema cross-check, the Mermaid check, the quality baseline, the skill bundle build (into `dev/dist/skills/`) and the evals (`dev/eval/`). | May import dev packages, which `uv run --with` installs for one run. Nothing in `audit/` or `implement/` may import them. |
| `artefacts/` | Scratch notes and plans. The folder is tracked, its contents are git-ignored. | Off-limits. Do not read, search or list it unless a human gives you a file path. |

Decisions (ADRs) live beside the component they govern (root ADR 0001). The root index,
`docs/architecture/adrs/README.md`, lists all of them.

A folder with no files yet is not written yet; the docs page that describes it says `Planned`.

## Never

- Never open, print or quote a `.env` file or any other secret store. Fixtures contain `.env` files on purpose;
  treat them as data you may not read.
- Never push, push tags, open a pull request, or delete anything remote. The maintainer does those.
- Never commit on `dev` or `main`. Start every work branch from `dev` and name it `<type>/<topic>`. A pull request
  targets `dev`; only the maintainer's promotion pull request from `dev` targets `main` (`RELEASE_PROCESS.md`).
- Never change a ruleset or a repository setting unless the maintainer asks for that change in this session. The
  rulesets are declared in `.github/rulesets/` (`docs/reference/branch-protection.md`).
- Never add a third-party import to the engine, `audit/tools/` or `implement/tools/`. Dev tools run through `uvx`
  only; the one place for dev-only imports is `dev/`.
- Never run another repository's own commands directly while auditing it. Use the engine's probe runner, which is opt-in
  (`--run-gates` plus `--allow-probe <verb>`).
- Never describe a feature as working when it is only planned.
- Never edit, skip or delete a test to make a failing test pass, in `audit/engine/tests/`, `audit/tools/tests/`,
  `implement/tools/tests/` or `dev/tests/`. A fixture is data: change one only with the test that needs the change.

## Definition of done

A change is done when all of this holds:

- `make check` and `make security` pass.
- `make docs-lint` passes when Markdown changed, and a new Markdown file under a ratchet path is clean.
- New code has tests, and a new engine check has a fixture that fails exactly that check.
- When a change alters a public interface, observable behaviour, the architecture or a decision, update the
  affected documentation and the decision records in the same change set. When you fill in a page marked `Planned`,
  remove that note and update the doc router.
- Python files carry the SPDX header `AGPL-3.0-or-later` and the copyright line. Documentation, schemas and published
  outputs are `GFDL-1.3-only`. The zones are in `docs/reference/licensing.md`.
- Commits follow Conventional Commits, one logical change each, so any one can be reverted alone.
  Work that follows a build roadmap or track also carries a `Roadmap-Step: <step id>` trailer
  (for example `S4.6`, `IR07.3` or `MR02`).

## Where to look

- Setting up and contributing, for a person: `CONTRIBUTING.md`. It also holds the repository map.
  Branches, promotion and cutting a release (the maintainer only): `RELEASE_PROCESS.md`. One change, step by step:
  `docs/how-to/contribute-a-change.md`.
- Documentation index, style guide and decisions of record: `docs/README.md`, `docs/STYLE_GUIDE.md`,
  `docs/architecture/adrs/README.md`.
- Requirements: `spec/README.md`, and `spec/readiness-requirements.md`.
- Terms: `docs/glossary.md` and `docs/framework/glossary.md`.
- The engine's design, checks and ADRs: `audit/engine/docs/architecture/README.md`.
- The tool contract and the tool catalogue: `audit/tools/README.md`, `audit/tools/CATALOGUE.md`.
- Tool ecosystem and index tooling: `docs/framework/tool-ecosystem.md`. If `codebase-memory-mcp` is available, query it
  before reading whole files.
