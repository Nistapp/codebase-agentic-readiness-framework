# Playbooks

A playbook says **how** to close one class of finding. The [implement recipe](../SKILL.md) picks the playbooks
for a theme; each playbook is an agent directive and follows the anatomy below, section for section, so an
agent can read any of them the same way.

> [!NOTE]
> All thirteen playbooks are written (IR04.1 to IR11.1) and were applied and corrected on two repositories (IR04.2 to
> IR11.3). The procedure they share (worktree and branch, drift first, per-item status, commits, the engine re-check,
> the ending) is in [`SKILL.md`](../SKILL.md#stage-3-apply), Stages 3 and 4, and is not repeated here (IR12). The
> anatomy below is fixed.

## Anatomy

Every playbook file, `<name>.md` in this folder, has these sections in this order. A step id in a header line
(`IR04.1` and the like) names the framework roadmap step that wrote or corrected the playbook; an agent needs
nothing from it.

| Section | What it holds |
|---|---|
| Goal | One or two sentences: what the repository has when the playbook is done |
| Checks resolved | The catalogue check IDs this playbook closes |
| Preconditions | The state preferences it reads, the earlier themes it needs, and what must already be true in the repository |
| Inputs to ask | The tool-choice step: detect what the repository already has (manifests, build plugins, configs, the code index) and use it; if nothing is there, offer two to four current options with pros and cons and a recommendation, in a table. Every other question for the owner |
| Steps | Generic steps first, then one subsection per stack that points at the stack profile in [`stacks/`](../../audit/stacks/README.md) instead of restating it. Only what is specific to the playbook: the shared procedure is `SKILL.md` Stage 3 |
| Continue on error | What counts as existing debt for this playbook, how it is counted and recorded, and how the check is wired so the debt cannot grow (ratchet, baseline file, or a report-only step) |
| Verification | One observable done-criterion per check resolved: the command to run or the file to read, and the expected result |
| Rollback | How to undo the change: which commits to revert, which files to delete |
| Do-not-do | What this playbook never does (for example, no mass reformat, no rule turned off) |
| State updates | The `done` and `partial` lines, debt texts and preference keys specific to the playbook (see the [state contract](../state.md)); the shared lines are in `SKILL.md` Stages 3 and 4 |

How to write the State updates section so each line runs as written:

- Debt goes on `set-status` as `--debt what=TEXT,count=N[,baseline=FILE]`, repeatable (the same `what` replaces
  its entry): `set-status F-001 partial --debt "what=unformatted files,count=212,baseline=.ruff-baseline"`.
- List only the lines specific to the playbook. The `in_progress` line, the transition rules and the theme rows
  are in [Stage 3](../SKILL.md#stage-3-apply); the ending (`pr_open` after the pull request exists, never merge)
  is in [Stage 4](../SKILL.md#stage-4-close-the-theme).

Rules for every playbook:

- A playbook never restates a check's rubric or a requirement; it links to the check file in
  [`audit/checks/`](../../audit/checks/README.md) and to `spec/`.
- Templates come from `greenfield/templates/` by reference, never copied verbatim into the playbook.
- A playbook does not restate the shared procedure of `SKILL.md` Stages 2 to 4; it links to the stage step.
- A new playbook name is added to the `playbooks` list of each check it resolves in `catalogue.json`, in the same change
  that writes the file; the framework's recipe linter (`recipe_lint.py`) rejects a playbook name the catalogue does not
  know.

## Playbook list

Thirteen playbooks, grouped by theme in dependency order. "In catalogue" says whether `catalogue.json`
already names the playbook; the new ones are added there by the step that writes them (`configure-quality-tools`
in IR04.1, `untrack-generated` in IR05.1, `establish-docs-contract` in IR09.1,
`add-hooks-and-commit-rules` in IR07.1, `add-baselines-and-ratchet` in IR08.1).

| Playbook | Theme | Checks | In catalogue | Status |
|---|---|---|---|---|
| [`define-command-surface`](define-command-surface.md) | T1 Command surface and quality tools | CMD-01, CMD-02, CMD-03, CMD-04, EXEC-03, TST-01 | yes | Drafted (IR04.1); applied in IR04.2, IR04.3 |
| [`configure-quality-tools`](configure-quality-tools.md) | T1 Command surface and quality tools | TOOL-01, TOOL-02, TOOL-03, TOOL-04 | yes | Drafted (IR04.1); applied in IR04.2, IR04.3 |
| [`pin-execution-environment`](pin-execution-environment.md) | T2 Execution determinism | EXEC-01, EXEC-02, EXEC-08 | yes | Drafted (IR05.1); applied and corrected in IR05.2, IR05.3 (T2 closed) |
| [`untrack-generated`](untrack-generated.md) | T2 Execution determinism | EXEC-05, EXEC-07 | yes | Drafted (IR05.1); applied and corrected in IR05.2, IR05.3 (T2 closed) |
| [`env-inventory-and-secrets`](env-inventory-and-secrets.md) | T3 Secrets and env | EXEC-04, SEC-01, SEC-02, SEC-03 | yes | Applied and corrected (IR06.1-IR06.3) |
| [`add-ci-parity`](add-ci-parity.md) | T4 CI parity, hooks, commits | CI-01, CI-02, CI-03, CI-04, CI-05 | yes | Drafted (IR07.1); applied and corrected in IR07.2, IR07.3 (T4 closed) |
| [`add-hooks-and-commit-rules`](add-hooks-and-commit-rules.md) | T4 CI parity, hooks, commits | TOOL-05, TOOL-06, TOOL-07 | yes | Drafted (IR07.1); applied and corrected in IR07.2, IR07.3 (T4 closed) |
| [`add-baselines-and-ratchet`](add-baselines-and-ratchet.md) | T5 Tests and baselines | BASE-01, BASE-02, BASE-03, BASE-04, TST-02, TST-03, TST-04, TST-05 | yes | Drafted (IR08.1); applied in IR08.2, IR08.3 |
| [`establish-docs-contract`](establish-docs-contract.md) | T6 Docs and navigation | DOC-01, DOC-02, DOC-03, DOC-04, NAV-01, NAV-02, NAV-03, NAV-04, NAV-05 | yes | Drafted (IR09.1); applied in IR09.2, IR09.3 |
| [`adapt-agents-md`](adapt-agents-md.md) | T7 AGENTS.md and governance | AGT-01, AGT-02, AGT-03, AGT-04, AGT-05, AGT-06, AGT-08, AGT-09, AGT-10, AGT-11, EXEC-06, TST-04 | yes | Drafted (IR10.1); applied in IR10.2, IR10.3 |
| [`add-deny-rules`](add-deny-rules.md) | T7 AGENTS.md and governance | AGT-07, CON-01, CON-02, CON-03 | yes | Drafted (IR10.1); applied in IR10.2, IR10.3 |
| [`add-repo-hygiene`](add-repo-hygiene.md) | T8 Hygiene and index | HYG-01 to HYG-11 | yes | Drafted (IR11.1); applied in IR11.2, IR11.3 |
| [`register-index`](register-index.md) | T8 Hygiene and index | IDX-01, IDX-02, IDX-03 | yes | Drafted (IR11.1); applied in IR11.2, IR11.3 |

Each playbook's check list matches `catalogue.json`, which the framework's recipe linter checks. CON-04 (the draft allow
and deny list) is emitted by the audit engine and has no playbook: [`add-deny-rules`](add-deny-rules.md) reads its draft
as an input, and the state keeps CON-04 in T7 for that reason.
