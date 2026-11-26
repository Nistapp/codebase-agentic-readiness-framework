# AGENTS.md: implement/

This folder holds the implement recipe and its tools. The recipe closes the confirmed findings of a final audit
report in the audited repository. The root [`AGENTS.md`](../AGENTS.md) applies here too. This file adds the rules
for this folder.

To implement fixes from an audit report, follow [`SKILL.md`](SKILL.md). The rest of this file is for changes to this
folder.

## What is here

| Path | What it is |
|---|---|
| `SKILL.md`, `prompts/` | The LLM-driven implement recipe and its kickoff prompt |
| `playbooks/` | One playbook per class of finding. See [`playbooks/README.md`](playbooks/README.md) |
| `playbooks/templates/` | Code a playbook copies into a target, with tests in `tools/tests/`. A copy carries the target's own licence in place of this repository's |
| `state.md` | The state contract: the per-repository state that `progress.py` keeps |
| `tool-choice.md` | What a step does when a tool it needs is missing, or older than the repository's pin |
| `theme-checks.md` | The integration-branch check, the history check, the lost-pass check and the gates check that Stages 3 and 4 run, and when to stack a theme on an unmerged one |
| `tools/` | `progress.py`, `check_drift.py`, `compare_reports.py`, `check_regressions.py`, `check_gates.py`, and their tests in `tools/tests/` |
| `docs/architecture/adrs/` | Decisions for this folder (ADR 0003, ADR 0004, ADR 0005, ADR 0006, ADR 0007 and ADR 0008) |

## Rules

- Use the standard library only in `tools/`. Never add a third-party import.
- Text and code that a playbook generates or copies into a target take the target's own licence, even when copied
  word for word. Never offer the owner a list of licences, and never leave this repository's licence line on a copy.
  See [licensing](../docs/reference/licensing.md#what-an-implement-run-puts-into-your-repository) and
  [ADR 0008](docs/architecture/adrs/0008-copies-in-a-target-take-the-targets-licence.md).
- Text a playbook copies into a target comes from `greenfield/templates/` (MIT-0), never from `docs/` (GFDL 1.3).
  The rule, with its full wording, is in the [rules for every playbook](playbooks/README.md#anatomy).
- Code in `playbooks/templates/` is relicensed under the target's licence when a playbook copies it into a target.
  Only its copyright holder changes it, or a contributor who agrees in writing to that relicensing. Say so in the
  pull request.
- Every tool follows the tool contract in [`audit/tools/README.md`](../audit/tools/README.md).
- No tool writes inside a target. `progress.py` keeps the state in the workspace, the folder of the audit report,
  outside the target. See [ADR 0004](docs/architecture/adrs/0004-implement-state-lives-in-the-audit-workspace.md).
- The recipe stops at a local branch by default. It pushes and opens a pull request only when the owner opted in.
  It never merges, force-pushes or pushes tags. See [ADR 0003](docs/architecture/adrs/0003-push-and-pr-policy.md).
- Read [`playbooks/README.md`](playbooks/README.md) before you add or change a playbook. Keep the anatomy it fixes,
  section for section.
- A change to a playbook, or to the playbook list in `playbooks/README.md`, changes the generated
  [implement master list](../docs/reference/implement-master.md). Run `make update-masters` from the repository
  root and commit the result in the same change.
- A playbook does not repeat the shared procedure in `SKILL.md` (Stages 3 and 4). It does not restate a stack
  profile; it links to [`audit/stacks/`](../audit/stacks/README.md).
- The tools import the shared helpers (`_common.py` and others) from `audit/tools/`. Import
  `_audit_tools_path.py` first; it puts `audit/tools/` on `sys.path`.
- The implement folder may import from the audit folder. The audit folder never imports from the implement folder.
- A fixture is data. Change a fixture only together with the test that needs the change.

## Documentation

- The tool reference: [`docs/reference/tools-cli.md`](../docs/reference/tools-cli.md).
- All decisions: the root index, [`docs/architecture/adrs/README.md`](../docs/architecture/adrs/README.md).
- How to add, change or delete an ADR: [`docs/ADR_POLICY.md`](../docs/ADR_POLICY.md).

## Test this folder

Run from the repository root:

```bash
python3 -m unittest discover -s implement/tools/tests
python3 dev/recipe_lint.py .
```

Before you propose a change, run `make check` and `make security` from the repository root.
