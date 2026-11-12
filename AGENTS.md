# AGENTS.md

This repository is the Codebase Agentic Readiness Framework: documentation that says what makes a codebase safe for AI
coding agents, plus tools that check it. `audit/` holds the audit recipe, its tools and the deterministic engine.
`implement/` holds the recipe that closes the findings of an audit. Read this file first. Three folders have their own
rules: `audit/AGENTS.md`, `implement/AGENTS.md` and `audit/engine/AGENTS.md` (the strictest). Read the file for a
folder before you change it.

**Before you edit any file in this repository**, run `python3 dev/mcp_config.py status --harness <your harness>`.
If it prints `not asked`, first make the one-time offer in `docs/how-to/set-up-agent-tools.md` ("For agents").
`python3 dev/mcp_config.py detect` helps you name your harness. Skip this for an audit or implement run on another
repository. Never install a server or write a harness config without the person's consent.

## Users: audit or implement a repository

- When asked to audit a repository, follow `audit/SKILL.md` from this repository's root.
- When asked to implement fixes from an audit report, follow `implement/SKILL.md`.

The rest of this file is for changes to this repository.

## Commands

The framework's seven verbs run through the root `Makefile`. CI runs the same commands.

```bash
make setup          # check the prerequisites (Python 3.11+, uv, git, Go); nothing is installed
make format         # rewrite formatting in place
make format:check   # read-only: formatting and lint rules (alias: make format-check)
make lint           # read-only lint
make typecheck      # mypy, strict: audit/tools, implement/tools, the playbook templates, dev, the engine build.py
make test           # the engine's, the audit tools', the implement tools' and the dev checks' suites (at once on Linux)
make check          # THE gate: format:check, typecheck, test, the engine's --verify-rules, the schema
                    # cross-check, recipe-lint, adr-lint, masters-check, eval-expected-check, workflow-lint (actionlint,
                    # zizmor, check-jsonschema), spell (typos)
make security       # secrets scan, then the dependency audit (osv-scanner; needs Go and the network)
make commit-lint    # Conventional Commits subjects on this branch (RANGE=origin/dev..HEAD); CI runs it on each PR
make update-masters # regenerate docs/reference/audit-master.md and implement-master.md (check runs masters-check)
```

One test, without the whole suite. Run the engine's tests from `audit/engine/`:

```bash
python3 -m unittest tests.packs.cmd.test_cmd_pack -k verbs
```

Run the tools' tests from the repository root:

```bash
python3 -m unittest discover -s audit/tools/tests -k catalogue
python3 -m unittest discover -s implement/tools/tests
```

This file is read by Claude Code, opencode, Codex, Gemini CLI, Cursor and any other harness that reads `AGENTS.md`.
No vendor-specific instruction file exists beside it.

- Run `make check` and `make security` before you propose a change. Do not run an ad-hoc substitute.
- A misspelling fails `make spell` (in `make check`). Fix it, or run `make spell-fix` and review the diff. Add a word
  to `_typos.toml` only for a project term or a code token.
- When you change Markdown, also run `make docs-lint` (needs Node; lints the ratchet path list in the
  `Makefile`) and validate every Mermaid block you add (`make docs-mermaid FILES=<file.md>`). Run
  `make docs-prose FILES=<file.md>` too, and fix its warnings on the lines you changed; it never fails.
- Prerequisites: Python 3.11 or newer (pinned in `.python-version`) and `uv` for the pinned dev tools (ruff, mypy,
  detect-secrets). Go 1.27 or newer runs actionlint (`make check`) and osv-scanner (`make security`).
  Each tool version is written once (ADR 0003): in `dev/tools/pyproject.toml`, in `dev/tools/package.json`, or in a
  Go tool module (`dev/tools/osv/go.mod`, `dev/tools/actionlint/go.mod`).
  Never write a version in the `Makefile`, a hook or a workflow. Nothing is installed into the project.
- The local hooks live in `lefthook.yml`. They stop commits to `dev` and `main` and check the formatting of staged
  Python. They run `make docs-lint` on staged ratchet Markdown and `make workflow-lint` on staged `.github/` files.
  They run typos on staged files, a secrets scan, and `dev/commit_lint.py` on the commit message.
  The developer runs `lefthook install` once per clone; an agent never does.
  Hooks do not replace the gate: CI runs `make check`, `make security` and `make docs-lint`.
- `make coverage` runs the engine's, the audit tools' and the implement tools' suites under coverage.py. It fails
  below the floor in `.coveragerc` (`fail_under`). CI runs it in parts (`coverage-<suite>` per job, then
  `coverage-combine` in the `coverage` job). Each suite runs as CI does (an empty `HOME` and `CI=true`), so a local
  pass means a CI pass. The floor is debt that only goes up: raise it when coverage rises, never lower it to get green.
- Quality baseline: existing lint debt is counted in `.quality-baseline.json` (ruff, mypy, Markdown lint outside the
  ratchet) and the secrets in `.secrets.baseline`. No new violations: `make format-check`, `make typecheck` and
  `make docs-lint` compare the live count with the baseline and fail when it went up (a ratchet). A baseline only goes
  down, a coverage floor only goes up; raising either needs the owner. When a count falls, lower the baseline in the
  same change.
- The audit and implement master lists (`docs/reference/audit-master.md`, `docs/reference/implement-master.md`) are
  generated from `audit/catalogue.json`, `audit/checks/` and `implement/playbooks/`. After you change one of those,
  run `make update-masters` and commit the pages in the same change. Never edit the pages by hand.
- After a deliberate change to a fixture or test that holds a key-shaped string, run `make update-secrets-baseline`
  and review the diff.
- Never weaken a gate to get green: no `.skip`, no rule turned off, no assertion relaxed. If you cannot pass a gate,
  say so.
- `make test` skips the positive-fixture test when `CI=true` and its scaffolder (a sibling repository) is absent.
  Locally the test fails loudly without it; set `AUDIT_BOOTSTRAP=<path to bootstrap.py>` to point at the scaffolder.

## How to write for people

Full rules: [`docs/COMMUNICATION_RULES.md`](docs/COMMUNICATION_RULES.md). They apply to chat replies, plans,
reports, commit messages, pull request descriptions and docs.

- Write for a new engineer who knows Git, Python and Markdown, but not this repository or its terms.
- Put the bottom line first: the answer, the result or the decision you need.
- Use short sentences (at most 25 words; 20 in a step), active voice and one term per meaning.
- Never leave a code alone. Write "T7 AGENTS.md and governance", not `T7`; "`IDX-01` codebase-memory-mcp
  registered", not `IDX-01`; "Discovery and Index (`IDX`)", not `IDX`; "F-020 style guide", not `F-020`.
- For a decision, give the context, two to four options with pros and cons, your recommendation and the default.
- Use a Mermaid diagram when a flow, a sequence or a state is easier to see than to read.
- Mark each claim as checked, inferred or assumed. Report failures and skipped steps plainly.

## Boundaries

| Path | What it is | Rules |
|---|---|---|
| `README.md`, `docs/`, `greenfield/` | The framework documents (`docs/framework/`), the Diátaxis docs for everything here, and the greenfield templates. Normative. | If a tool disagrees with them, the tool is wrong. Follow `docs/STYLE_GUIDE.md`; start at `docs/README.md`. |
| `spec/` | Numbered requirements (`REQ-...`) for what a repository must have. See `spec/README.md`. | Recipes link to requirement IDs; they do not restate rules. |
| `audit/` | The audit recipe (`SKILL.md`, `checks/`, `prompts/`, `catalogue.json`, `stacks/`), the JSON Schemas (`schema/`) and the deterministic tools (`tools/`). | Standard library only. No network. Never write inside a target repository. Read `audit/AGENTS.md`. |
| `audit/engine/` | The Python audit engine: reads a repository, never writes to it, no LLM, no network. | Standard library only. Read `audit/engine/AGENTS.md` before you change it. |
| `implement/` | The implement recipe (`SKILL.md`, `playbooks/`, `prompts/`, `state.md`) and its tools (`tools/`). | Standard library only. No tool writes inside a target; `progress.py` keeps the state beside the audit report (ADR 0004 in `implement/docs/architecture/adrs/`). Read `implement/AGENTS.md`. |
| `dev/` | Checks and builds that run in this repository and CI only, never shipped: the recipe linter, the schema cross-check, the Mermaid check, the quality baseline, the skill bundle build (into `dev/dist/skills/`) and the evals (`dev/eval/`). | May import dev packages, which `uv run --with` installs for one run. Nothing in `audit/` or `implement/` may import them. |
| `artefacts/` | Scratch notes and plans. The folder is tracked, its contents are git-ignored. | Off-limits. Do not read, search or list it unless a human gives you a file path. |

Decisions (ADRs) live beside the component they govern (root ADR 0001). The root index,
`docs/architecture/adrs/README.md`, lists all of them. **Every ADR you add, change or delete follows
`docs/ADR_POLICY.md`.** Git is the archive, so an ADR states only the current decision. Overwrite a changed
decision in place. Delete a superseded one, and never refer to it again.

A folder with no files yet is not written yet; the docs page that describes it says `Planned`.

## Never

- Never open, print or quote a `.env` file or any other secret store. Fixtures contain `.env` files on purpose;
  treat them as data you may not read.
- Never push, push tags, open a pull request, or delete anything remote. The maintainer does those.
- Never commit on `dev` or `main`. Start every work branch from `dev` and name it `<type>/<topic>`. A pull request
  targets `dev`; only the maintainer's promotion pull request from `dev` and release-please's release pull request
  target `main` (`RELEASE_PROCESS.md`).
- Never edit `CHANGELOG.md` or a version string (`.release-please-manifest.json`, the engine's `__version__`).
  release-please writes them from the commit subjects (ADR 0005).
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
- A change can alter a public interface, observable behaviour, the architecture or a decision. Then update the
  affected documentation and the decision records in the same change set. When you fill in a page marked `Planned`,
  remove that note and update the doc router.
- An ADR you added or changed follows `docs/ADR_POLICY.md` and has its row in the ADR index.
- Python files carry the SPDX header `AGPL-3.0-or-later` and the copyright line. Documentation, schemas and published
  outputs are `GFDL-1.3-only`. The zones are in `docs/reference/licensing.md`.
- Commits follow Conventional Commits, one logical change each, so any one can be reverted alone.
  Work that follows a build roadmap or track also carries a `Roadmap-Step: <step id>` trailer
  (for example `S4.6`, `IR07.3` or `MR02`).

## Where to look

- Setting up and contributing, for a person: `CONTRIBUTING.md`. It also holds the repository map.
  Branches, promotion and cutting a release (the maintainer only): `RELEASE_PROCESS.md`. One change, step by step:
  `docs/how-to/contribute-a-change.md`.
- How to write for people: `docs/COMMUNICATION_RULES.md`.
- Documentation index, style guide and decisions of record: `docs/README.md`, `docs/STYLE_GUIDE.md`,
  `docs/architecture/adrs/README.md`. The ADR rules: `docs/ADR_POLICY.md`.
- Requirements: `spec/README.md`, and `spec/readiness-requirements.md`.
- What an audit checks and what an implement run changes, for a reader: `docs/reference/audit-master.md` and
  `docs/reference/implement-master.md`.
- Terms: `docs/glossary.md` and `docs/framework/glossary.md`.
- The engine's design, checks and ADRs: `audit/engine/docs/architecture/README.md`.
- The tool contract and the tool catalogue: `audit/tools/README.md`, `audit/tools/CATALOGUE.md`.
- Tool ecosystem and index tooling: `docs/framework/tool-ecosystem.md`. If `codebase-memory-mcp` is available, query it
  before reading whole files. `.mcp.json` registers it; Claude Code and VS Code read that file. Another harness
  copies the entry into its own config. No gate needs an MCP server (`docs/reference/dev-tooling.md`).
