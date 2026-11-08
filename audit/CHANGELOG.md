# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/); dates are UTC. This page covers
releases of the brownfield recipes as a whole, up to v0.3.0. For the deterministic engine's own ruleset-revision
history (which verdicts moved and why), see
[its changelog reference](engine/docs/reference/changelog.md).

From v0.3.1 on, the recipes' changes are in the root [`CHANGELOG.md`](../CHANGELOG.md), which release-please writes
from the commit subjects (scopes `audit` and `implement`). This page gets no new entries.

## [0.3.0] - 2026-11-07

The recipes moved: see the "Moved" table in the root [`CHANGELOG.md`](../CHANGELOG.md). Paths in the entries
below this one use the old layout.

- Reports record commit ids (`provenance.framework_revision`, `provenance.target.git_sha`) as their first 12 hex digits
  instead of 40. A full id has the shape of an access token, and a report committed to a repository with a secret scan
  (gitleaks' default rules) failed it. The schema still accepts a full id, so earlier reports stay valid; `import-engine`
  compares the short id with the engine's full one by prefix. `check_drift.py` resolves the short id before it
  compares it with `HEAD`, and the two eval harnesses match a short id against a full one by prefix. See
  `schema/SCHEMA.md`, "Commit ids".

## [0.2.0] - 2026-11-06

The implement recipe is released: see the root `CHANGELOG.md` for the framework-level notes. The worked example (a real
Server run, before and after, published as drafts) is in
[`schema/examples/server-worked-example/`](schema/examples/server-worked-example/README.md). Open `audit-engine`
issues are known defects of the engine, listed on GitHub.

- Implement-recipe evals (IR13). Seven synthetic scenarios in `tools/eval/implement-fixtures/` on one toy
  standard-library repository with two canned final reports built by the real tools; `tools/eval/implement_eval.py`
  materialises a scenario (a local bare `origin`, a logging `gh` shim, a copy of the recipe without the eval files),
  runs it headless and asserts seven hard rules: only confirmed or edited findings are queued (A1), a skip is final
  (A2), a planted instruction is not run and is flagged (A3), a resumed item is not committed twice (A4), existing
  debt ends an item `partial` with its count (A5), no commit on `dev`/`main`, no push without `ci.pr_by_agent=yes`
  and no merge (A6), and the drift check runs first (A7). `tools/tests/test_implement_eval.py` proves each assertion
  on hand-made good and bad outcomes in `make check`. `run-claude.sh` gains `--recipe implement`, `--answers`,
  `--model` and `--max-budget-usd`; the audit mode is unchanged. `tools/eval/score.py` reports the report's
  `stack_profile` (informational). Results and the first implement-run numbers table are in
  `docs/reference/eval-results.md`. The ruff, mypy and markdownlint configurations leave `testdata/` out, as they
  already leave `fixtures/` out.

- Implement recipe Stages 2 (plan a theme), 3 (apply), 4 (close the theme) and 5 (close-out) written in
  `implement/SKILL.md` from the sixteen apply sessions (IR12), with a Tools table giving each call's expected result
  and fallback, a Resuming section, a theme table with branch slugs, and two new Stage 0 steps: a tools check and a
  version-skew warning (the report's catalogue version against the recipe's). The procedure the thirteen playbooks
  repeated now lives in Stages 2 to 4 and each playbook links to it; `implement/prompts/kickoff.md` is finished.
  `tools/build_skills.py` also builds the `agentic-readiness-implement` skill bundle: its own tools, links rewritten
  to stay inside the bundle, and the engine taken from the `agentic-readiness-audit` skill installed beside it.
  `make validate-skills` validates both bundles. The how-to pages for implementing and resuming are filled in.

- The two T8 playbooks (IR11.1): `implement/playbooks/add-repo-hygiene.md` (HYG-01 to HYG-11) and
  `implement/playbooks/register-index.md` (IDX-01 to IDX-03). `add-repo-hygiene` writes the hygiene files from the
  repository's own facts in one reviewed batch and asks the owner only for the policy files (CODEOWNERS handle,
  SECURITY contact values); it never hand-writes a changelog a release tool owns, never enables required code-owner
  review, and writes the branch-protection page as "recorded, not enforced" where the plan cannot enforce it.
  `register-index` offers a committed project-level registration and a document-only section (the owner picks per
  repository), never edits a user-level file without a recorded consent preference, and states that the engine's
  IDX-03 verdict stays `UNKNOWN` because the store records no revision. `catalogue.json` 0.2.8 (PATCH: playbook names
  only; fingerprint unchanged) adds `add-repo-hygiene` to HYG-01 to HYG-11; the HYG check files name it.

- The two T7 playbooks (IR10.1): `implement/playbooks/adapt-agents-md.md` (AGT-01 to AGT-06, AGT-08 to AGT-11,
  EXEC-06, TST-04) and `implement/playbooks/add-deny-rules.md` (AGT-07, CON-01 to CON-03). `adapt-agents-md` drafts
  one small diff per finding for the owner to edit: verbs with inline comments, the definition-of-done sentence, a
  release-boundary sentence built from the state and ADR 0003, the reach line with vendor pointer files kept, a
  deferral turned into a link with the must-always rules moved in, generic text moved to `docs/` and contradicted
  rules kept as target state with a measured exception count. `add-deny-rules` edits only the prohibitions section
  (decision 0001): a bounded test rule naming every test directory, the CON-04 draft as its input, and a harness
  permission review that reports and never edits a permission file unless the owner opted in
  (`agents_md.harness_deny=yes`). CON-04 keeps no playbook. Text only: `catalogue.json` stays 0.2.7, because both
  names were already listed; the check files, decision 0001 and the doc router drop their Planned markers.

- `add-baselines-and-ratchet` corrected from its first two applications (IR08.2 on a Gradle repository, IR08.3 on a
  multi-component Node repository): the Quarkus 3.2 Gradle wiring for `quarkus-jacoco`, measuring PMD with the
  exclude list removed and Spotless through a scratch-copy format run, the whole-tree linter count in `format:check`,
  the floor measured over every source file (Create React App), narrowed runs and a coverage-on `test` verb, a mocked
  suite needs no stack so `check` is the default gate, a failing suite outside `check` is recorded and not fixed, the
  audit compare lives in the report-only scan script, and the engine's blind spots (issues #45 and #50). Text only:
  `catalogue.json` stays 0.2.7, because it records playbook names and no name changed.
- The T5 playbook (IR08.1): `implement/playbooks/add-baselines-and-ratchet.md` (BASE-01 to BASE-04, TST-02, TST-03,
  TST-04, TST-05). It inventories the ratchets a repository already has, keeps tool-native baselines, puts every
  other count in one committed counts file compared inside `format:check`, sets a coverage floor at today's number
  rounded down (`tests.coverage_gate` chooses `check` or CI), and records an owner-approved raise as a
  `baseline.exception.*` preference plus a `Baseline-Exception:` commit line. Currency checked 2026-11-05; `betterer`
  dropped. `catalogue.json` 0.2.7 (PATCH: playbook names only; fingerprint unchanged) adds the playbook to those eight
  checks (TST-04 keeps `adapt-agents-md` as well); the check files `07-baselines-and-ratchet.md` and `10-tests.md`
  name it, and the Java and TypeScript stack profiles gain a coverage note.
- Framework-level documentation and release (MR08): `recipe_lint.py` checks the relative links of the root framework
  pages; the trust page's implementation section is a table; the root `CHANGELOG.md`, `CONTRIBUTING.md`,
  `RELEASE_PROCESS.md` and a release workflow (not yet run) are added. See the
  [root changelog](../CHANGELOG.md).
- Self-audit published (MR07.2): `make self-audit` runs the engine on this repository against the committed
  `.audit-baseline.json` (exit 2 on a regression) and CI runs it as the `self-audit` job that `CI Gate` needs;
  `make update-audit-baseline` accepts a smaller baseline on purpose. The report is the worked example
  `schema/examples/self-audit/2026-11-06.json` and [Self-Audit](../docs/reference/self-audit.md) states the score
  (0.8402, ruleset `2026-11-06.1`), the open findings and the owner exception `IDX-01`.
- Engine ruleset `2026-11-06.1` (MR06.4): `TST-04` recognises `python3 -m unittest <module> -k <name>` (and `python`) as
  a single-test invocation; `AGT-08` no longer reports the reach gap when the root `AGENTS.md` has a line saying "read
  by" or "supported harnesses" that names a known harness, and its summary cites that line. Refs #26 (the engine
  takes the statement as given; it does not check that each named harness loads the file).
- Engine ruleset `2026-11-05.4` (MR06.3): `NAV-02` counts a line that starts with the `if __name__` guard, not a
  file that only holds the text; `DOC-04` no longer counts `0000-template.md` as a numbered ADR; `--out FILE` with no
  suffix writes `FILE.json` (and `FILE.md`); new `--no-user-config` (also on `tools/engine.py`) reads nothing under
  `$HOME`, and every report's `provenance.user_config` lists the paths outside the target that were read. Refs #16 (not
  resolved: Claude Code's own MCP registration is still not read).
- Engine ruleset `2026-11-05.3` (MR06.2, ADR-0009): `DOC-03`, `CON-03`, `SEC-01` and `SEC-03` read every nested
  `.gitignore` (scoped to its directory, including the tracked ones under `--exclude`) and interpret `!` negation,
  anchoring, directory-only rules and `**`. A scratch directory with its own `.gitignore` holding `*` passes, and a
  tracked file it re-includes (`artefacts/README.md`) is not scratch. New fixtures `ignore-ok-nested-gitignore` and
  `sec-03-ok-negated-exception`. Refs #12, #22 (partly; they stay open).
- Engine ruleset `2026-11-05.2` (MR06.1, ADR-0008): the engine decides what counts as the repository. Runner
  precedence is depth first (a root `Makefile` beats a nested `package.json`); files under a directory named
  `templates`, `template`, `examples`, `example`, `fixtures`, `samples`, `testdata` or `scaffold` are carried data,
  read by no check and listed in the report (`inventory.set_aside`); `HYG-02/03/05/06/07/08/09` count a file only at
  the root or under `.github/`, `.gitlab/` or `docs/`. `--exclude` is no longer needed for template or fixture
  directories. New fixture `cmd-ok-root-make-nested-template`. Component scoping (#20) is unchanged.
- Engine ruleset `2026-11-05.1` (MR05): `EXEC-06` cuts a trailing shell comment from a fenced command
  (`make test   # run`) in the shared extractor and resolves `make`/`npm run` through the verb resolver (#8);
  `SEC-02` subtracts what `.secrets.baseline`, `.gitleaksignore` and `.gitleaks.toml` allowlist and lists the
  suppressed lines (#10 still needs sentinel tokens and badge URLs); `SEC-01` and `SEC-03` say "root-anchored only"
  for `/.env` instead of "missing", with verdict `PARTIAL`.
- The handoff from the audit to the implement recipe is written: how-to Step 1, `implement/SKILL.md` Stage 0 step 4
  and one sentence in audit Stage 5 say who copies the report into `docs/agentic-readiness-report/`, commits it,
  and runs `progress.py init`; Stage 0 reads `dirty` and `report_changed` from `check_drift.py` (MR04).
- `progress.py` papercuts (MR04): a refused move names the states the item may go to; `set-status` to the same
  status with `--note` adds the note; a bad preference key says "lower case"; `none` is the documented value for
  "no preference"; `render` wraps item details at 110 columns and cuts long preference cells (full text below the
  table) so the generated STATE.md lints clean. The state contract documents the transitions, the debt syntax, the
  theme order (open the PR first: `pr_open` still needs `--pr`) and that the tools run without `python3 -I`.
- `progress.py init` records the SHA-256 of the report file in `source_reports[].sha256` (readiness state
  `schema_version` `0.2`; a `0.1` state stays valid). `check_drift.py` recomputes it and reports `report_changed`, and
  reports a dirty working tree as `dirty` (MR04).
- `report.py set-stack-profile <draft> <id> [--derived] [--confirmed]` writes `run_context.stack_profile`; audit Stage 1 calls
  it and no longer says the field has no write path (MR04).
- v0.2 (the implementation MVP), skeleton in: `implement/SKILL.md` with its hard rules and the stage table,
  the playbook anatomy and the list of thirteen playbooks (`implement/playbooks/README.md`), and the
  per-repository state contract (`implement/state.md`).
- Implement recipe Stages 0 (intake) and 1 (triage) written and live in `implement/SKILL.md`, from the two
  onboarding runs, with a first `implement/prompts/kickoff.md`.
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
  default `False`.
- `progress.py` transitions, skip, defer and preferences (IR02.2), so the state moves through its whole life.
- `tools/check_drift.py` (IR02.3): compares the audited commit in a report with `HEAD` of the target and lists
  the findings whose cited paths changed in between. It writes nothing.
- `tools/compare_reports.py` (IR14.1): compares two audit reports of one repository and says which checks and
  findings moved, and which moves the readiness state explains. It writes nothing.
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
  [Evaluation Results](../docs/reference/eval-results.md).
- A second harness (`opencode`, on DeepSeek flash) smoke-run against the installed skill bundle,
  confirming the recipe is harness-neutral — see [Harness Notes](../docs/reference/harness-notes.md).
- Documentation: the full Diátaxis set under `docs/`, a tutorial, how-to guides, reference pages and
  explanation pages for both operators and contributors.

### Licensing

- `tools/`, the dev-only checks in `dev/`, the migrated engine code, and their tests: AGPL-3.0-or-later.
- Recipes, check files, playbooks, stack profiles, the catalogue, schemas and published examples:
  GFDL-1.3-only. Full zones in [Licensing](../docs/reference/licensing.md).
