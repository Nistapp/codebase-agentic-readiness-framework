# Playbooks

A playbook says **how** to close one class of finding. The [implement recipe](../SKILL.md) picks the playbooks
for a theme; each playbook is an agent directive and follows the anatomy below, section for section, so an
agent can read any of them the same way.

> [!NOTE]
> Partly written. The two T1 playbooks (IR04.1), the two T2 playbooks (IR05.1), the T3 playbook (IR06.1) and
> the T6 playbook (IR09.1) are drafted. They are applied and corrected in IR04.2, IR04.3, IR05.2, IR05.3,
> IR06.2, IR06.3, IR09.2 and IR09.3. The other seven are Planned: each is written in the roadmap step named in
> the table (`IRnn.1` drafts it, `IRnn.2` and `IRnn.3` apply and correct it). The anatomy below is fixed.

## Anatomy

Every playbook file, `<name>.md` in this folder, has these sections in this order:

| Section | What it holds |
|---|---|
| Goal | One or two sentences: what the repository has when the playbook is done |
| Checks resolved | The catalogue check IDs this playbook closes |
| Preconditions | The state preferences it reads, the earlier themes it needs, and what must already be true in the repository |
| Inputs to ask | The tool-choice step: detect what the repository already has (manifests, build plugins, configs, the code index) and use it; if nothing is there, offer two to four current options with pros and cons and a recommendation, in a table. Every other question for the owner |
| Steps | Generic steps first, then one subsection per stack that points at the stack profile in [`stacks/`](../../stacks/README.md) instead of restating it |
| Continue on error | What counts as existing debt for this playbook, how it is counted and recorded, and how the check is wired so the debt cannot grow (ratchet, baseline file, or a report-only step) |
| Verification | One observable done-criterion per check resolved: the command to run or the file to read, and the expected result |
| Rollback | How to undo the change: which commits to revert, which files to delete |
| Do-not-do | What this playbook never does (for example, no mass reformat, no rule turned off) |
| State updates | The status, debt, preference and log entries the playbook records in the state file (see the [state contract](../state.md)) |

Rules for every playbook:

- A playbook never restates a check's rubric or a requirement; it links to the check file in
  [`audit/checks/`](../../audit/checks/README.md) and to `spec/`.
- Templates come from `greenfield-bootstrap/templates/` by reference, never copied verbatim into the playbook.
- A new playbook name is added to the `playbooks` list of each check it resolves in `catalogue.json`, in the
  same change that writes the file; the recipe linter rejects a playbook name the catalogue does not know.

## Playbook list

Thirteen playbooks, grouped by theme in dependency order. "In catalogue" says whether `catalogue.json`
already names the playbook; the new ones are added there by the step that writes them (`configure-quality-tools`
in IR04.1, `untrack-generated` in IR05.1, `establish-docs-contract` in IR09.1).

| Playbook | Theme | Checks | In catalogue | Status |
|---|---|---|---|---|
| [`define-command-surface`](define-command-surface.md) | T1 Command surface and quality tools | CMD-01, CMD-02, CMD-03, CMD-04, EXEC-03, TST-01 | yes | Drafted (IR04.1); applied in IR04.2, IR04.3 |
| [`configure-quality-tools`](configure-quality-tools.md) | T1 Command surface and quality tools | TOOL-01, TOOL-02, TOOL-03, TOOL-04 | yes | Drafted (IR04.1); applied in IR04.2, IR04.3 |
| [`pin-execution-environment`](pin-execution-environment.md) | T2 Execution determinism | EXEC-01, EXEC-02 | yes | Drafted (IR05.1); applied in IR05.2, IR05.3 |
| [`untrack-generated`](untrack-generated.md) | T2 Execution determinism | EXEC-05, EXEC-07 | yes | Drafted (IR05.1); applied in IR05.2, IR05.3 |
| [`env-inventory-and-secrets`](env-inventory-and-secrets.md) | T3 Secrets and env | EXEC-04, SEC-01, SEC-02, SEC-03 | yes | Drafted (IR06.1); applied in IR06.2, IR06.3 |
| `add-ci-parity` | T4 CI parity, hooks, commits | CI-01, CI-02, CI-03, CI-04 | yes | Planned (IR07.1) |
| `add-hooks-and-commit-rules` | T4 CI parity, hooks, commits | TOOL-05, TOOL-06 | no | Planned (IR07.1) |
| `add-baselines-and-ratchet` | T5 Tests and baselines | BASE-01, BASE-02, BASE-03, BASE-04, TST-02, TST-03, TST-05 | no | Planned (IR08.1) |
| [`establish-docs-contract`](establish-docs-contract.md) | T6 Docs and navigation | DOC-01, DOC-02, DOC-03, DOC-04, NAV-01, NAV-02, NAV-03, NAV-04, NAV-05 | yes | Drafted (IR09.1); applied in IR09.2, IR09.3 |
| `adapt-agents-md` | T7 AGENTS.md and governance | AGT-01, AGT-02, AGT-03, AGT-04, AGT-05, AGT-06, AGT-08, AGT-09, AGT-10, AGT-11, EXEC-06, TST-04 | yes | Planned (IR10.1) |
| `add-deny-rules` | T7 AGENTS.md and governance | AGT-07, CON-01, CON-02, CON-03 | yes | Planned (IR10.1) |
| `add-repo-hygiene` | T8 Hygiene and index | HYG-01 to HYG-11 | no | Planned (IR11.1) |
| `register-index` | T8 Hygiene and index | IDX-01, IDX-02, IDX-03 | yes | Planned (IR11.1) |

The checks of the new playbooks are the plan, not yet the catalogue: the step that writes a playbook confirms
its list against the check files and records it in `catalogue.json`. CON-04 (the draft allow and deny list)
is emitted by the audit engine and has no playbook in this plan.
