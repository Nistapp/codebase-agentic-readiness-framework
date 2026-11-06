# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/); dates are UTC. This page covers the
framework as a whole: the documents, the requirements and the repository's own gates. The components keep their own
histories:

- The brownfield recipes: [`brownfield-recipes/CHANGELOG.md`](brownfield-recipes/CHANGELOG.md).
- The deterministic engine's ruleset revisions (which verdicts moved and why):
  [`brownfield-recipes/deterministic-audit/docs/reference/changelog.md`](brownfield-recipes/deterministic-audit/docs/reference/changelog.md).

## [Unreleased]

### Framework pages (since v0.1)

- A quality baseline for this repository, by the `add-baselines-and-ratchet` playbook: `.quality-baseline.json` and a
  compare step that fails when the ruff, mypy or Markdown lint count goes up (MR08.3).

- The framework pages say the implement recipe is in development and no longer promise features that are only
  planned; the verb count is seven everywhere; the greenfield README and `AGENTS.md` template (now 1.1.1) state what
  the scaffold satisfies (MR01.3).
- Decisions of record: the push and pull request policy ([ADR 0003](brownfield-recipes/docs/architecture/adrs/0003-push-and-pr-policy.md)),
  `format:check` includes the lint rules ([spec decision 0002](spec/decisions/0002-lint-in-the-gate.md)), and a note
  that monorepo component scoping is v0.3 (MR03).
- The risk register names the risks the recipes introduce, R9-R14 (MR08).
- The trust page's implementation section is a table of what the implement recipe may and never does (MR08).

### This repository's own gates

- Phase 1 for this repository (MR07): `.python-version`, lefthook hooks, `make setup`, `make coverage` with a
  floor, a root `docs/` index with a branch-protection page, issue and pull request templates, and secret and key
  material ignored by shape.
- The self-audit is published and ratcheted: `make self-audit` against `.audit-baseline.json`, a `self-audit` job in
  `CI Gate`, and [Self-Audit](brownfield-recipes/docs/reference/self-audit.md) (MR07.2).
- `recipe_lint.py` checks the relative links of the root `README.md`, `shared/`, `spec/`, `greenfield-bootstrap/` and
  `brownfield-legacy/` as part of `make check` (MR08).
- `CONTRIBUTING.md`, this changelog, `RELEASE_PROCESS.md`, a Dependabot schedule for the workflow actions, and a
  release workflow that attaches `audit.pyz` and the skill bundle to a tagged release (MR08). The workflow has not
  run yet.
