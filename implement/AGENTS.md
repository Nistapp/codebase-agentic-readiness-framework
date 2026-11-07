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
| `state.md` | The state contract: the per-repository state that `progress.py` keeps |
| `tools/` | `progress.py`, `check_drift.py`, `compare_reports.py`, and their tests in `tools/tests/` |
| `docs/architecture/adrs/` | Decisions for this folder (ADR 0002 and ADR 0003) |

## Rules

- Use the standard library only in `tools/`. Never add a third-party import.
- Every tool follows the tool contract in [`audit/tools/README.md`](../audit/tools/README.md).
- `progress.py` is the one tool that writes inside a target. It writes only the target's two state files. See
  [ADR 0002](docs/architecture/adrs/0002-progress-writes-state-in-target.md). No other tool writes inside a target.
- The recipe stops at a local branch by default. It pushes and opens a pull request only when the owner opted in.
  It never merges, force-pushes or pushes tags. See [ADR 0003](docs/architecture/adrs/0003-push-and-pr-policy.md).
- Read [`playbooks/README.md`](playbooks/README.md) before you add or change a playbook. Keep the anatomy it fixes,
  section for section.
- A playbook does not repeat the shared procedure in `SKILL.md` (Stages 3 and 4). It does not restate a stack
  profile; it links to [`audit/stacks/`](../audit/stacks/README.md).
- The tools import the shared helpers (`_common.py` and others) from `audit/tools/`. Import
  `_audit_tools_path.py` first; it puts `audit/tools/` on `sys.path`.
- The implement folder may import from the audit folder. The audit folder never imports from the implement folder.
- A fixture is data. Change a fixture only together with the test that needs the change.

## Documentation

- The tool reference: [`docs/reference/tools-cli.md`](../docs/reference/tools-cli.md).
- All decisions: the root index, [`docs/architecture/adrs/README.md`](../docs/architecture/adrs/README.md).

## Test this folder

Run from the repository root:

```bash
python3 -m unittest discover -s implement/tools/tests
python3 dev/recipe_lint.py .
```

Before you propose a change, run `make check` and `make security` from the repository root.
