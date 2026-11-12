# Implement

The implement recipe closes the confirmed findings of a final audit report in the audited repository. It works one
theme at a time, on one branch per theme. It respects each finding the owner skipped, and it records existing debt
instead of mass-fixing it. It never merges. It pushes and opens a pull request only when the owner opted in
([ADR 0003](docs/architecture/adrs/0003-push-and-pr-policy.md)). A state file in the target lets a run stop after any
theme and resume later. The report comes from the [audit recipe](../audit/README.md).

## Start implementing

1. Have a final, owner-confirmed audit report for the repository.
2. Open Claude Code at the root of this repository.
3. Say: "Start implementing the fixes on `<repo-path>` based on `<audit-json-path>`".
4. Answer the triage questions, one theme at a time. Say the same sentence again to resume; the state file tells the
   agent where it stopped.

The skill is [`SKILL.md`](SKILL.md) (`agentic-readiness-implement`). Another agent with shell access can run it from
[`prompts/kickoff.md`](prompts/kickoff.md). Full walkthrough:
[Implement an audit report](../docs/how-to/implement-an-audit-report.md).

To install the skill in another project, build the bundles with `python3 dev/build_skills.py` and copy
`dev/dist/skills/agentic-readiness-implement/` beside `agentic-readiness-audit/`, from the same build. The implement
skill runs the audit skill's engine.

## What is here

| Path | Contents |
| --- | --- |
| [`SKILL.md`](SKILL.md) | The recipe: hard rules, Stages 0 to 5, themes |
| [`prompts/`](prompts/kickoff.md) | The kickoff prompt, also used to resume |
| [`playbooks/`](playbooks/README.md) | Thirteen playbooks, one per class of finding, and their anatomy |
| [`state.md`](state.md) | The per-repository state contract: files, statuses, skip, preferences |
| [`tools/`](tools/) | The implement tools and their tests |
| [`docs/architecture/adrs/`](docs/architecture/adrs/0004-implement-state-lives-in-the-audit-workspace.md) | This recipe's decisions |

## Tools

Each tool is standard-library Python: `python3 implement/tools/<tool>.py <arguments>`. The tools import the shared
helpers from `audit/tools/`.

| Tool | Does |
| --- | --- |
| `progress.py` | Creates, shows and renders the state; the only tool that writes inside the target ([ADR 0004](docs/architecture/adrs/0004-implement-state-lives-in-the-audit-workspace.md)) |
| `check_drift.py` | Tells which findings the repository has moved under since the audit |
| `compare_reports.py` | Compares two audit reports of the same repository |

The full synopsis of each tool is in the [Tools CLI reference](../docs/reference/tools-cli.md).

## Documentation

Start at the root router, [`docs/README.md`](../docs/README.md). What the recipe may and never does to a repository is
in [Trust and safety](../docs/explanation/user-overview/03-trust-and-safety.md). A real run, before and after this
recipe, is in the [worked example](../audit/schema/examples/server-worked-example/README.md).
