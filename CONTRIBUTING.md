# Contributing

This repository is the Codebase Agentic Readiness Framework: documents that say what makes a codebase safe for AI
coding agents, and tools that check it. This page gets a new contributor to a green `make check` without reading
the Makefile. The rules an agent follows are in [`AGENTS.md`](AGENTS.md); they are the same rules.

## Prerequisites

| You need | For | Notes |
| --- | --- | --- |
| Python 3.11 or newer | Everything | Pinned in `.python-version`; CI runs 3.11 and 3.14 |
| `git` | Everything | |
| [`uv`](https://docs.astral.sh/uv/) | `make check`, `make security`, `make coverage` | The dev tools (ruff, mypy, detect-secrets, coverage.py) run through `uvx` at pinned versions; nothing is installed into the project |
| `make` | Every command below | Linux and macOS. On Windows use WSL |
| Node 22 | `make docs-lint` | The pinned `markdownlint-cli2` runs through `npx`; not needed for `make check` |
| Chrome, through Puppeteer | `make docs-mermaid` | Only when you add or change a Mermaid block; the pinned mermaid-cli fetches it on first use |
| The sibling scaffolder | One engine test, the positive fixture | Set `AUDIT_BOOTSTRAP=<path to bootstrap.py>`. With `CI=true` and no scaffolder the test is skipped; locally it fails without it |

`make setup` checks Python, `uv` and `git`, installs nothing, and names the first one that is missing.

## The gates

Run these before you propose a change. CI runs the same commands.

| Command | What it does |
| --- | --- |
| `make format` | Rewrites formatting in place. Run it before the first `make check` |
| `make check` | The gate: formatting and lint, `mypy` strict, the engine's, the tools' and the dev checks' tests, the engine's rule check, the schema cross-check and the recipe linter. It takes a couple of minutes |
| `make security` | A secrets scan against `.secrets.baseline` |
| `make docs-lint` | Markdown lint over the ratchet path list in the `Makefile`. Run it when Markdown changed |
| `make docs-mermaid FILES=<file.md>` | Renders every Mermaid block in the files. Run it when you added or changed one |
| `make coverage` | The engine's and the tools' suites under coverage.py; fails below the floor in `.coveragerc`. The floor only goes up |
| `make self-audit` | The engine on this repository against `.audit-baseline.json`; exit 2 on a regression. See [Self-Audit](docs/reference/self-audit.md) |

The seven verbs the framework asks of any repository (`format`, `format:check`, `lint`, `typecheck`, `test`,
`check`, `security`) are defined in [`spec/command-surface.md`](spec/command-surface.md).

One test, without the whole suite (the first from `audit/engine/`, the second from the
repository root):

```bash
python3 -m unittest tests.test_cmd_pack -k verbs
python3 -m unittest discover -s audit/tools/tests -k catalogue
```

A change to a fixture or a test that holds a key-shaped string needs `make update-secrets-baseline`; review the
diff. Use low-entropy fakes (`aaaabbbbcccc`) in examples so the baseline does not grow.

Never weaken a gate to get green: no skipped test, no rule turned off, no assertion relaxed, no lowered baseline or
floor. If you cannot pass a gate, say so in the pull request.

## Local hooks

[`lefthook.yml`](lefthook.yml) runs the format check on staged Python, `make docs-lint` on staged Markdown, a
secrets scan and a Conventional Commits check before a commit lands. Install it once per clone with
`lefthook install` ([lefthook.dev](https://lefthook.dev)). Hooks do not replace the gate.

## Commits and pull requests

- [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): subject`, for example
  `fix(engine): ...` or `docs(spec): ...`.
- One logical change per commit, so any one can be reverted alone.
- Work that follows a build roadmap or track carries a `Roadmap-Step: <step id>` trailer (for example `S4.6`,
  `IR07.3` or `MR02`).
- The pull request template lists what a reviewer expects: gates green, tests for new code (a new engine check has a
  fixture that fails exactly that check), and the documentation and decision records updated in the same change.

## Licence zones

Python files carry the SPDX header `AGPL-3.0-or-later` and the copyright line. Documentation, schemas and
published outputs are `GFDL-1.3-only`. The zones are in
[`docs/reference/licensing.md`](docs/reference/licensing.md).

## Documentation

Follow [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md) and start at the doc
router, [`docs/explanation/README.md`](docs/explanation/README.md). A page
describes what exists; a feature that is only planned is marked `Planned`. Decisions go in an ADR
([index](docs/architecture/adrs/README.md)).

## Reporting an engine defect

File an issue on the repository with the `audit-engine` label. Say which check gave the wrong verdict, the
repository or fixture where you saw it, and what the verdict should have been. A fix lands with a fixture that
reproduces it and a new ruleset revision in the engine's
[changelog](audit/engine/docs/reference/changelog.md).

## Releases

Only the maintainer tags a release. See [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md).
