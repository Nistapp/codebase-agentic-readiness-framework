# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/); dates are UTC. This page covers the
framework as a whole: the documents, the requirements and the repository's own gates. The components keep their own
histories:

- The recipes (audit and implement): [`audit/CHANGELOG.md`](audit/CHANGELOG.md).
- The deterministic engine's ruleset revisions (which verdicts moved and why):
  [`audit/engine/docs/reference/changelog.md`](audit/engine/docs/reference/changelog.md).

Paths in entries before v0.3.0 use the old layout. The v0.3.0 entry has a "Moved" table from each old path to its new
one.

## [Unreleased]

### Repository

- Two protected branches ([ADR 0002](docs/architecture/adrs/0002-dev-integrates-main-releases.md)). `dev` is the
  integration branch and the default branch: it accepts pull requests from any branch and no direct commits. `main` is
  the release branch: it accepts pull requests from `dev` only. The rulesets are declared in `.github/rulesets/`.
- The quick start in `README.md` clones `--branch main`, so a user gets the latest release, not `dev`.
- New required check on pull requests into `main`: `Check source branch`
  (`.github/workflows/pr-source-branch.yml`).
- CI runs on pushes to `dev` as well as `main`. Dependabot version updates target `dev`.
- `release.yml` refuses a tag whose commit is not on `main`.
- `lefthook.yml` stops a local commit on `dev` or `main`.
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
