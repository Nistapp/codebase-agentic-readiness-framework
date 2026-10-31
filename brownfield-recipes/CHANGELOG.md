# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/); dates are UTC. This page covers
releases of the brownfield recipes as a whole. For the deterministic engine's own ruleset-revision
history (which verdicts moved and why), see
[its changelog reference](deterministic-audit/docs/reference/changelog.md).

## [Unreleased]

- v0.2 (the implementation MVP), skeleton in: `implement/SKILL.md` with its hard rules and the stage table,
  the playbook anatomy and the list of thirteen playbooks (`implement/playbooks/README.md`), and the
  per-repository state contract (`implement/state.md`). Stages, playbooks, the state schema and its tools
  are still Planned.
- Implement recipe Stages 0 (intake) and 1 (triage) written and live in `implement/SKILL.md`, from the two
  onboarding runs, with a first `implement/prompts/kickoff.md`. Stages 2 to 5 are still Planned.
- The two T1 playbooks: `implement/playbooks/define-command-surface.md` (CMD-01 to CMD-04, EXEC-03, TST-01) and
  `implement/playbooks/configure-quality-tools.md` (TOOL-01 to TOOL-04, with a tool-currency table checked
  2026-10-30). `catalogue.json` 0.2.3 (PATCH: playbook names only; fingerprint unchanged) adds
  `configure-quality-tools` to TOOL-01 to TOOL-04, and `audit/checks/05-tooling.md` names it as their
  remediation.
- The two T2 playbooks: `implement/playbooks/pin-execution-environment.md` (EXEC-01, EXEC-02; EXEC-03 as a
  check only) and `implement/playbooks/untrack-generated.md` (EXEC-05, EXEC-07), with tool-currency tables
  checked 2026-10-30 (Volta dropped: its README says it is unmaintained). `catalogue.json` 0.2.4 (PATCH: playbook
  names only; fingerprint unchanged) adds `untrack-generated` to EXEC-05 and EXEC-07, and
  `audit/checks/09-execution-determinism.md` names it as their remediation.
- The T3 playbook: `implement/playbooks/env-inventory-and-secrets.md` (EXEC-04, SEC-01, SEC-02, SEC-03): a
  key-names-only variable inventory, example-file rules, tracked secret-file handling that never prints or
  rotates, and the ignore-shape step with a negation check. Scanner currency table checked 2026-10-30.
  `catalogue.json` is unchanged (the four checks already list the playbook).
- The T6 playbook: `implement/playbooks/establish-docs-contract.md` (DOC-01 to DOC-04, NAV-01 to NAV-05): a docs
  index, a one-page style guide named from the instruction file, an ADR directory with template, index and
  `proposed` first records, an architecture page from the code index with a validated Mermaid diagram, a
  census-and-document step for NAV-03, and a ratcheted docs lint with `mmdc` in a separate CI job. Tool currency
  checked 2026-10-30. `catalogue.json` 0.2.5 (PATCH: playbook names only; fingerprint unchanged) adds the
  playbook to DOC-01 to DOC-04 and NAV-01 to NAV-05.
- The two T4 playbooks: `implement/playbooks/add-ci-parity.md` (CI-01 to CI-04: wrappers call the verbs, no green
  no-op, report-only steps named as such, a committed branch-protection record) and
  `implement/playbooks/add-hooks-and-commit-rules.md` (TOOL-05, TOOL-06: lefthook default, husky dropped on
  currency, three commit-rule options with the engine blind spot). Currency checked 2026-10-31.
  `catalogue.json` 0.2.6 (PATCH: playbook names only; fingerprint unchanged) adds the second playbook to TOOL-05
  and TOOL-06, and `audit/checks/05-tooling.md` names it as their remediation.
- The readiness state: `schema/readiness-state.schema.json` (`schema_version` `0.1`) with two examples and their
  rendered Markdown, and `tools/progress.py` `init`, `show` and `render`. `progress.py` is the one tool that
  writes inside a target, and only its two state files (ADR 0002); `ToolInfo` gains `writes_inside_target`,
  default `False`. Transitions, skip, defer and preferences are still Planned (IR02.2).
- Docs tooling for this repository: `.markdownlint-cli2.jsonc`, `make docs-lint` (gating, on a path list that
  only grows) and `make docs-lint-all` (report-only), and a CI `docs` job that lints and renders every
  Mermaid block in changed Markdown (`brownfield-recipes/dev/mermaid_check.py`).

## [0.1.0] — 2026-10-19

The audit MVP: a repository can be audited for Phase 1 agentic readiness, end to end, by any coding agent
with shell access, with no installation beyond Python 3.11+.

### Added

- The deterministic audit engine, migrated into this repository with its history
  (`deterministic-audit/`) — a read-only, standard-library-only Python scanner with no LLM and no
  network.
- Phase 1 and shared readiness requirements (`spec/`), traced to the check catalogue.
- The report, intake, facts, catalogue and eval-expected JSON Schemas (`schema/`), each cross-checked
  against the reference `jsonschema` validator.
- The check catalogue (`catalogue.json`, catalogue version 0.2.2): 71 checks across thirteen families,
  all tested against one-defect fixtures.
- Three stack profiles: `typescript-node` (with NestJS), `java` (with Quarkus on Gradle), `python`.
- The tools the recipe calls: `engine.py`, `validate_report.py`, `report.py`, `render_report.py`,
  `facts.py`, `recipe_lint.py` and `build_skills.py`.
- The audit recipe (`audit/SKILL.md`), its kickoff prompt and its intake schema, with an eval mode for
  unattended, scored runs.
- `tools/build_skills.py`, which builds the self-contained `agentic-readiness-audit` skill bundle
  (`dist/skills/`) that a harness installs with no checkout of this repository; validated against the
  Agent Skills specification's own reference validator (`make validate-skills`).
- An eval harness (`tools/eval/`): the corpus format, `score.py`'s five metrics, and `run-claude.sh`.
- Published evaluation results: a 89-fixture sweep (98.9% expected-verdict rate) and real-repo runs
  against three pinned repositories, one Node/TypeScript, one Java/Quarkus, one Python — see
  [Evaluation Results](docs/reference/eval-results.md).
- A second harness (`opencode`, on DeepSeek flash) smoke-run against the installed skill bundle,
  confirming the recipe is harness-neutral — see [Harness Notes](docs/reference/harness-notes.md).
- Documentation: the full Diátaxis set under `docs/`, a tutorial, how-to guides, reference pages and
  explanation pages for both operators and contributors.

### Licensing

- `tools/`, the dev-only checks in `dev/`, the migrated engine code, and their tests: AGPL-3.0-or-later.
- Recipes, check files, playbooks, stack profiles, the catalogue, schemas and published examples:
  GFDL-1.3-only. Full zones in [Licensing](docs/reference/licensing.md).
