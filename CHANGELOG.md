# Changelog

This page covers the whole repository: the framework documents, the requirements, the audit and implement recipes,
the engine and the repository's own gates. Dates are UTC.

From v0.3.1 on, release-please writes each entry from the Conventional Commit subjects of the release. Do not edit
this file by hand on `dev`: write a clear commit subject instead. How it works:
[`RELEASE_PROCESS.md`](RELEASE_PROCESS.md). Two older histories stay:

- The recipes up to v0.3.0: [`audit/CHANGELOG.md`](audit/CHANGELOG.md).
- The deterministic engine's ruleset revisions (which verdicts moved and why):
  [`audit/engine/docs/reference/changelog.md`](audit/engine/docs/reference/changelog.md).

Paths in entries before v0.3.0 use the old layout. The v0.3.0 entry has a "Moved" table from each old path to its new
one.

## [0.3.1](https://github.com/Nistapp/codebase-agentic-readiness-framework/compare/v0.3.0...v0.3.1) (2026-11-08)


### Bug fixes

* **engine:** report the released version 0.3.0 instead of 0.1.0 ([1214f59](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1214f5936befeb3a086d6828e691f00b500deea4))


### Documentation

* add a development tooling reference page ([7e19468](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7e194686fe0f2a7848a1a2c75905198fdc0dcda0))
* add a step-by-step guide to contribute a change through dev ([5806e9e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5806e9e6936e540128a96fed73d9c7946438fb11))
* add the harness disclaimer and the report steps to the README quick start ([7a8f4eb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7a8f4eba2a66a70e86cb9a13a79ba47b10171286))
* clone main in the README quick start ([f1d41a2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f1d41a22446ff135e1f7ba1e020ba49066fecde4))
* describe the dev and main branches in the README ([bdcbe3d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bdcbe3d516552fb17e1606cd8c77ae86635f688d))
* describe workflow-lint, commit-lint and CODEOWNERS ([2aa6632](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2aa66327cab3f602e1e1dd80bd0e74e494a787e6))
* fix the overview link and the skill list in the README ([00d4ffc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/00d4ffc604a04924a99b9ba27a73a0cfd57cb8a3))
* make dev the default branch in ADR 0002 and the process docs ([1a557dd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1a557dde90cb1fd7351aea972ce336b7dc7f96e2))
* recommend a fresh session before the implement step in the README ([0efe17c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0efe17c35fe5c515f5e66e4d04fe6271f663c837))
* record the Dependabot policy and the dev tool pins (ADR 0003) ([df049b5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/df049b59b6f3b9024274edef73776f2aec0454e2))
* record the dev and main branch model and the promotion release ([268ed75](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/268ed750943bd8489c89f84470733c4adb1ea45c))
* record the dev ruleset as active ([e417e1a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e417e1ac16870d0866be3cc3c8c3671fc02a2798))
* **release:** describe the release-please process ([ae0f2ed](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ae0f2ed89099011c79c4673383607e3ec7411fb7))
* reword the README introduction ([0fdcd4a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0fdcd4aa6413eccd40911790c1e7be07a435f31c))


### Build and dev tools

* **dev:** move the dev tool pins into manifests that Dependabot reads ([6002b89](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6002b894984a56847ef79f73d1908b5d41e6fcf0))


### CI and release

* **dependabot:** open security pull requests only, never for a major version ([0cfcc6c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0cfcc6c34cd46f2f870141e2f580e3c857751d29))
* lint the workflows and the commit subjects in the gate ([e83a10f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e83a10f0a3914ab776a7df63b511040bc29fd59d))
* **release:** automate versions and releases with release-please ([83f7d0c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/83f7d0ccbe85bce2d75ba59692df64f78c6b56bc))
* **release:** automate versions and releases with release-please ([be5d86f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/be5d86fd25e16d2e3f70fb796e51cc99d65178fc))
* **release:** CI checks, gates and automation - first phase. ([0c90c2d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0c90c2d4eddc45f104d8b9e2ecbcb702713fb989))
* **release:** publish only a tag whose commit is on main ([195d76b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/195d76b9fd4c4b680f1fa9d6d9d4ed3bc5315535))
* require pull requests into main to come from dev ([8c3c05a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8c3c05ad67fbc7333c7eeecc1d4659c13590cabe))
* run CI on pushes to dev and target Dependabot at dev ([58d65c1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/58d65c17f5838bb1097a4e2ce7b0b3752b816b14))

## [Notes written by hand since 0.3.0]

These notes were written by hand before release-please took over this file. They ship in the first release that
release-please makes: the entry above this one.

### Repository

- Releases are automated with release-please
  ([ADR 0005](docs/architecture/adrs/0005-release-please-cuts-releases.md)). A push to `main` opens or updates a
  release pull request that bumps the version and writes this file. Merging it tags `vX.Y.Z`, publishes the GitHub
  release with its files and opens a back-merge pull request from `main` into `dev`. `release.yml` no longer runs on
  a pushed tag; `release-please.yml` calls it. The engine's `__version__` (it said `0.1.0`) now follows the release.

- Two protected branches ([ADR 0002](docs/architecture/adrs/0002-dev-integrates-main-releases.md)). `dev` is the
  integration branch and the default branch: it accepts pull requests from any branch and no direct commits. `main` is
  the release branch: it accepts pull requests from `dev` only. The rulesets are declared in `.github/rulesets/`.
- The quick start in `README.md` clones `--branch main`, so a user gets the latest release, not `dev`.
- New required check on pull requests into `main`: `Check source branch`
  (`.github/workflows/pr-source-branch.yml`).
- CI runs on pushes to `dev` as well as `main`. Dependabot version updates target `dev`.
- `release.yml` refuses a tag whose commit is not on `main`.
- `lefthook.yml` stops a local commit on `dev` or `main`.
- Dependabot opens security pull requests only, and never for a major version
  ([ADR 0003](docs/architecture/adrs/0003-dependabot-security-pull-requests-only.md)). A fix that needs a major
  version stays an alert. The greenfield template and the test fixtures never get a pull request.
- The dev tool versions move from the `Makefile` and the workflows to `dev/tools/pyproject.toml` (with `uv.lock`)
  and `dev/tools/package.json` (with `package-lock.json`), so Dependabot sees them. The root `.nvmrc` pins Node for
  CI. `dev/tests/test_tool_pins.py` keeps each version in one place.
- New gate `make workflow-lint`, part of `make check`: actionlint, zizmor and check-jsonschema on `.github/`, all
  offline. Each Dependabot entry has a 7-day cooldown, which zizmor asks for.
- New CI job `commits`, required through `CI Gate`: `dev/commit_lint.py` checks that each commit subject a pull
  request adds follows Conventional Commits. The lefthook `commit-msg` hook runs the same script.
- `.github/CODEOWNERS` routes review requests to the maintainer.
- New reference page: [development tooling](docs/reference/dev-tooling.md), every tool, its command, its CI job and
  where its version is pinned.
- `dev/recipe_lint.py` also checks the links in `AGENTS.md`, `CONTRIBUTING.md`, `RELEASE_PROCESS.md` and
  `SECURITY.md`.
- New how-to: [contribute a change](docs/how-to/contribute-a-change.md). `RELEASE_PROCESS.md` and
  [branch protection](docs/reference/branch-protection.md) describe the promotion from `dev` to `main`.

## [0.3.0] - 2026-11-07

The first public release for developers. One layout, one way to start, and a protected `main`.

### Start in one minute

- Clone the repository, start Claude Code in it, and say "Audit `<repo>` and write the output to `<dir>`", then
  "Start implementing the fixes on `<repo>` based on `<report>.json`". Two tracked pointer skills in
  `.claude/skills/` start the recipes `audit/SKILL.md` and `implement/SKILL.md`; `dev/tests/test_pointer_skills.py`
  keeps them in step (V03.U1).
- The root `README.md` is short and user-first: the quick start, a table of other ways in, an honest platform
  statement (Linux tested; macOS tools tested in CI; Windows not tested) and the licences (V03.B1, V03.C2).
- New how-to: [install the skills from a release](docs/how-to/install-the-skills.md), with the checksum check.
- The worked example links the public Server repository at the commit after the fixes (V03.X1).

### Repository

- New layout (V03.C1): `docs/` (framework pages and the Diátaxis docs), `spec/` (unchanged), `greenfield/`,
  `audit/` (recipe, catalogue, schemas, stacks, tools, and the engine with its own docs), `implement/` (recipe, tools,
  its ADRs) and `dev/` (build, lint, eval and CI-only checks; never shipped). Moves are `git mv`, so
  `git log --follow` keeps each file's history.
- Licence files: `LICENSE` (GFDL-1.3, documents) and `LICENSE-CODE` (AGPL-3.0-or-later, code). Each skill bundle now
  carries `LICENSE` with the AGPL text.
- Skill bundles: the engine package moves from `scripts/deterministic-audit/audit/` to `scripts/engine/audit/`, the
  same shape as the clone. Unzip a new release over the old folders. Bundles build into `dev/dist/skills/`.
- `SECURITY.md`: report a vulnerability privately through GitHub, or by email to `udan-security@nistapp.com`;
  acknowledgement within 5 working days (V03.D2).
- `main` is protected by a ruleset (pull request, `CI Gate`, up to date, no force push or deletion, merge commit), and
  private vulnerability reporting, secret scanning, push protection and Dependabot security updates are on
  ([branch protection](docs/reference/branch-protection.md), V03.D1, V03.D3).
- The `register-index` playbook recommends `.mcp.json` at the repository root as the one MCP config (V03.A1).

### Moved

| Old path | New path |
| --- | --- |
| `brownfield-recipes/audit/`, `catalogue.json`, `stacks/`, `schema/` | `audit/`, `audit/catalogue.json`, `audit/stacks/`, `audit/schema/` |
| `brownfield-recipes/schema/examples/eval-expected/` | `dev/eval/expected/` |
| `brownfield-recipes/implement/` | `implement/` |
| `brownfield-recipes/tools/` (audit tools and shared helpers) | `audit/tools/` |
| `brownfield-recipes/tools/{progress,check_drift,compare_reports}.py` | `implement/tools/` |
| `brownfield-recipes/tools/{build_skills,recipe_lint}.py`, `tools/eval/`, `brownfield-recipes/dev/` | `dev/` |
| `brownfield-recipes/deterministic-audit/` | `audit/engine/` (`tools/build.py` → `audit/engine/build.py`; `LICENSE` → `LICENSE-CODE`) |
| `brownfield-recipes/docs/` | `docs/` (`architecture/user-overview/`, `contributor-deep-dive/` → `docs/explanation/`) |
| `brownfield-recipes/docs/architecture/adrs/0001-*` | `audit/docs/architecture/adrs/` |
| `brownfield-recipes/docs/architecture/adrs/0002-*`, `0003-*` | `implement/docs/architecture/adrs/` |
| `brownfield-recipes/README.md`, `CHANGELOG.md` | `audit/README.md`, `audit/CHANGELOG.md` |
| `shared/<Name>.md` | `docs/framework/<name>.md` (lowercase, for example `tool-ecosystem.md`) |
| `brownfield-legacy/Phased-Approach.md`, `README.md` | `docs/framework/phased-approach.md`, `brownfield-track.md` |
| `greenfield-bootstrap/` | `greenfield/` |
| `docs/branch-protection.md` | `docs/reference/branch-protection.md` |

## [0.2.0] - 2026-11-06

Release notes: the implement recipe (`brownfield-recipes/implement/`) is live with Stages 0-5, thirteen playbooks and
its own skill bundle, and the release workflow attaches both bundles. A real run is published as a
[worked example](audit/schema/examples/server-worked-example/README.md) with an owner-confirmed second
audit (IR15). The engine defects found
on the way are open `audit-engine` issues on GitHub (for example #45 and #49-#52); they are known, not fixed in 0.2.0.

### Framework pages (since v0.1)

- A quality baseline for this repository, by the `add-baselines-and-ratchet` playbook: `.quality-baseline.json` and a
  compare step that fails when the ruff, mypy or Markdown lint count goes up (MR08.3).

- The framework pages say the implement recipe is in development and no longer promise features that are only
  planned; the verb count is seven everywhere; the greenfield README and `AGENTS.md` template (now 1.1.1) state what
  the scaffold satisfies (MR01.3).
- Decisions of record: the push and pull request policy ([ADR 0003](implement/docs/architecture/adrs/0003-push-and-pr-policy.md)),
  `format:check` includes the lint rules ([spec decision 0002](spec/decisions/0002-lint-in-the-gate.md)), and a note
  that monorepo component scoping is v0.3 (MR03).
- The risk register names the risks the recipes introduce, R9-R14 (MR08).
- The trust page's implementation section is a table of what the implement recipe may and never does (MR08).

### This repository's own gates

- Phase 1 for this repository (MR07): `.python-version`, lefthook hooks, `make setup`, `make coverage` with a
  floor, a root `docs/` index with a branch-protection page, issue and pull request templates, and secret and key
  material ignored by shape.
- The self-audit is published and ratcheted: `make self-audit` against `.audit-baseline.json`, a `self-audit` job in
  `CI Gate`, and [Self-Audit](docs/reference/self-audit.md) (MR07.2).
- `recipe_lint.py` checks the relative links of the root `README.md`, `shared/`, `spec/`, `greenfield-bootstrap/` and
  `brownfield-legacy/` as part of `make check` (MR08).
- `CONTRIBUTING.md`, this changelog, `RELEASE_PROCESS.md`, a Dependabot schedule for the workflow actions, and a
  release workflow that attaches `audit.pyz` and the skill bundle to a tagged release (MR08). The workflow has not
  run yet.
