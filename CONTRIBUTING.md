# Contributing

This repository is the Codebase Agentic Readiness Framework: documents that say what makes a codebase safe for AI
coding agents, and tools that check it. This page gets a new contributor to a green `make check` without reading
the Makefile. The rules an agent follows are in [`AGENTS.md`](AGENTS.md); they are the same rules. The folders
`audit/`, `implement/` and `audit/engine/` each have their own `AGENTS.md` with the rules for that folder.

## Repository map

"Shipped" means the folder reaches users: in a skill bundle, or as the documents a user reads.

| Folder | What it is | Shipped |
| --- | --- | --- |
| `docs/` | The framework pages (`docs/framework/`), the Diátaxis docs and the root decision records | Yes, as documents |
| `spec/` | The numbered requirements (`REQ-...`) and the decisions about them | Yes, as documents |
| `greenfield/` | Templates for a new repository that starts ready | Yes, as documents |
| `audit/` | The audit recipe, its checks, prompts, catalogue, stack profiles, schemas and tools | Yes, in the audit skill bundle |
| `audit/engine/` | The deterministic audit engine, with its own docs and decision records | Yes, in the audit skill bundle |
| `implement/` | The implement recipe, its playbooks, prompts, state contract and tools | Yes, in the implement skill bundle |
| `dev/` | The recipe linter, the schema cross-check, the Mermaid check, the quality baseline, the skill bundle build and the evals | No: this repository and CI only |
| `artefacts/` | Scratch notes and plans; the contents are git-ignored | No, and off-limits to agents |

`make validate-skills` builds the two skill bundles into `dev/dist/skills/` and validates them.

## Prerequisites

| You need | For | Notes |
| --- | --- | --- |
| Python 3.11 or newer | Everything | Pinned in `.python-version`; CI runs 3.11 and 3.14 |
| `git` | Everything | |
| [`uv`](https://docs.astral.sh/uv/) | `make check`, `make security`, `make coverage` | The dev tools (ruff, mypy, detect-secrets, coverage.py) run through `uvx` at the versions pinned in `dev/tools/`; nothing is installed into the project |
| [Go](https://go.dev/doc/install) 1.27 or newer | `make check`, `make security` | Builds the pinned actionlint (`dev/tools/actionlint/go.mod`) and osv-scanner (`dev/tools/osv/go.mod`) on first use, through the Go module proxy. `make security` also needs the network |
| `make` | Every command below | Linux and macOS. On Windows use WSL |
| Node 22 | `make docs-lint` | The pinned `markdownlint-cli2` runs through `npx`; not needed for `make check` |
| Chrome, through Puppeteer | `make docs-mermaid` | Only when you add or change a Mermaid block; the pinned mermaid-cli fetches it on first use |
| `codebase-memory-mcp` (optional) | Faster code search for your coding agent | Listed in `.mcp.json`. Your agent offers to set it up once; see [Set up the agent tools](docs/how-to/set-up-agent-tools.md). No gate needs it |
| The sibling scaffolder | One engine test, the positive fixture | Set `AUDIT_BOOTSTRAP=<path to bootstrap.py>`. With `CI=true` and no scaffolder the test is skipped; locally it fails without it |

`make setup` checks Python, `uv` and `git`, installs nothing, and names the first one that is missing.

## The gates

Run these before you propose a change. CI runs the same commands: the steps of `make check` as separate jobs
that run at once ([The required checks](docs/reference/branch-protection.md#the-required-checks)).

| Command | What it does |
| --- | --- |
| `make format` | Rewrites formatting in place. Run it before the first `make check` |
| `make check` | The gate: formatting and lint, `mypy` strict, the engine's, the tools' and the dev checks' tests, the engine's rule check, the schema cross-check, the recipe linter and the workflow lint. It takes a couple of minutes. The steps run one by one, in the order the spec fixes. On Linux, `make test` runs its four suites at once (`TEST_JOBS`; `make test TEST_JOBS=` runs them one by one) |
| `make spell` | Part of `make check`. typos on the tracked text; the word list is `_typos.toml`. `make spell-fix` writes the suggested fixes |
| `make workflow-lint` | Part of `make check`. actionlint, zizmor and check-jsonschema on `.github/`: workflow mistakes, workflow security, and `dependabot.yml` against its schema. Offline |
| `make commit-lint` | Checks that each commit subject on your branch follows Conventional Commits (`RANGE=origin/dev..HEAD` by default). CI runs the same check on every pull request |
| `make security` | A secrets scan against `.secrets.baseline`, then a dependency audit of the dev tools (osv-scanner) |
| `make docs-lint` | Markdown lint over the ratchet path list in the `Makefile`. Run it when Markdown changed |
| `make docs-prose FILES=<file.md>` | The plain-language check from [`docs/COMMUNICATION_RULES.md`](docs/COMMUNICATION_RULES.md). Advisory: it prints warnings and notices and never fails. Fix the warnings on the lines you changed |
| `make docs-mermaid FILES=<file.md>` | Renders every Mermaid block in the files. Run it when you added or changed one |
| `make coverage` | The engine's and the tools' suites under coverage.py; fails below the floor in `.coveragerc`. The floor only goes up |
| `make self-audit` | The engine on this repository against `.audit-baseline.json`; exit 2 on a regression. See [Self-Audit](docs/reference/self-audit.md) |

The seven verbs the framework asks of any repository (`format`, `format:check`, `lint`, `typecheck`, `test`,
`check`, `security`) are defined in [`spec/command-surface.md`](spec/command-surface.md).

One test, without the whole suite (the first from `audit/engine/`, the second from the
repository root):

```bash
python3 -m unittest tests.packs.cmd.test_cmd_pack -k verbs
python3 -m unittest discover -s audit/tools/tests -k catalogue
```

A change to a fixture or a test that holds a key-shaped string needs `make update-secrets-baseline`; review the
diff. Use low-entropy fakes (`aaaabbbbcccc`) in examples so the baseline does not grow.

Never weaken a gate to get green: no skipped test, no rule turned off, no assertion relaxed, no lowered baseline or
floor. If you cannot pass a gate, say so in the pull request.

## Tool versions

Every tool, what it catches and where it runs: [Development tooling](docs/reference/dev-tooling.md).

Each dev tool version is written once: Python tools in `dev/tools/pyproject.toml`, Node tools in
`dev/tools/package.json`, each with a lockfile. The `Makefile`, the hooks and CI read the versions from there, and
Dependabot watches them for security fixes. To change a version, follow
[Change a tool version](RELEASE_PROCESS.md#change-a-tool-version).

## Local hooks

[`lefthook.yml`](lefthook.yml) stops a commit on `dev` or `main`. It also runs the format check on staged Python,
`make docs-lint` on staged Markdown, `make workflow-lint` on staged `.github/` files, the spell check on staged
files, a secrets scan and the Conventional Commits check (`dev/commit_lint.py`) before a commit lands. Install it
once per clone with `lefthook install` ([lefthook.dev](https://lefthook.dev)). Hooks do not replace the gate.

## Branches

Two branches are protected: `dev` and `main`. You cannot commit or push to them directly.

- Start each change on a work branch from `dev`. Name it `<type>/<topic>`, for example `fix/report-score`.
- Open the pull request into `dev`. The required check is `CI Gate`.
- Do not open a pull request into `main`. Only the maintainer does that, and only from `dev`, to make a release.
- Do not edit `CHANGELOG.md` or a version. release-please writes them from your commit subjects at release time.
- Merges use a merge commit. Do not squash or rebase. Into `dev`, the maintainer merges through the merge queue,
  which tests your branch merged onto the latest `dev` before it lands.

The step-by-step guide is [Contribute a change](docs/how-to/contribute-a-change.md). The rules and the release steps
are in [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md). The ruleset settings are in
[Branch protection](docs/reference/branch-protection.md).

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

Write in plain language ([`docs/COMMUNICATION_RULES.md`](docs/COMMUNICATION_RULES.md)). Follow
[`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md). Start at the documentation index,
[`docs/README.md`](docs/README.md). A page describes what exists; a feature that is only planned is marked
`Planned`. Decisions go in an ADR ([index](docs/architecture/adrs/README.md)).

## Reporting an engine defect

File an issue on the repository with the `audit-engine` label. Say which check gave the wrong verdict, the
repository or fixture where you saw it, and what the verdict should have been. A fix lands with a fixture that
reproduces it and a new ruleset revision in the engine's
[changelog](audit/engine/docs/reference/changelog.md).

## Releases

Only the maintainer promotes `dev` to `main`. release-please then opens the release pull request, and its merge tags
the release. See [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md).
