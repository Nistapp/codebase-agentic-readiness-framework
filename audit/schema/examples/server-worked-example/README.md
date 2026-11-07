# Worked example: the Digital Assistant Server, audited twice

> **Audience:** Everyone
> **Status:** Live. A real run. The second audit is final: the owner decided every finding.

These files are the output of running the recipes on a real open-source repository, the
Digital Assistant Server (Quarkus/Java), before and after
the implement recipe closed its confirmed findings. They show what the audit recipe writes, what the implement
recipe keeps in the state, and what the comparison between two audits looks like. They are an example, not a
benchmark: the numbers belong to one repository on one day.

## The repository before and after

- **Before:** the first audit below is the report on the repository as it was on 2026-10-28.
- **After:** the public repository with the implement recipe's changes merged:
  [Digital-Assistant-Server at `aae557f76144`](https://github.com/Digital-Assistant/Digital-Assistant-Server/tree/aae557f76144)
  (branch `dev`, newest commit on 2026-11-07). Its state file is in `docs/agentic-readiness/`.

## Draft status

- The **first audit** is a final report (every finding has an owner disposition).
- The **second audit** is `"status": "final"`. The owner did Stage 4 on 2026-11-06: 10 findings rejected, 4 deferred,
  1 edited. The decisions do not change a check's verdict, so the score stays 0.7262. Both reports pass
  `validate_report.py`.
- The **state** is the implement recipe's record at close-out; it is as the Server repository holds it.
- The second audit's score (0.7262) is the engine's figure; the owner's decisions record which findings stand.
  Several verdicts moved because the engine changed between the two runs (user-level configuration is no longer
  read), not because the repository changed; the comparison annotates each such move.

## Files

| File | What it is |
| --- | --- |
| `digital-assistant-server-first-audit-20261028T131409Z.json` / `.md` | The first audit: report and rendered view (final) |
| `digital-assistant-server.audit-report.20261106T123400Z.json` / `.md` | The second audit after the implement run (final) |
| `digital-assistant-server-second-audit-comparison-20261106T091756Z.md` | `compare_reports.py` output with hand annotations on the unexplained moves |
| `digital-assistant-server-agentic-readiness-state.json` / `-STATE.md` | The implement recipe's state and its rendered view |

The file names are those of the Server repository (`docs/agentic-readiness-report/` and `docs/agentic-readiness/`
at its `dev` commit `cb12266`; the final second audit is in Server pull request 127 until that is merged). The
Server's other files there are not copied.

## What was edited in these copies

The copies are **not byte-identical** to the Server repository's files. One mechanical edit was applied, and the
originals in the Server repository were not touched:

| Replaced | With | Why |
| --- | --- | --- |
| the audited checkout's absolute path | `<target>` | A local path is not part of the example |
| the home directory prefix (`/home/<user>/`) | `<home>/` | Same |
| the scratch directories of the second run | `<target>` / `<work>` | Same |
| the lock file path under `/tmp` | `<lock-file>` | Same |
| the user prefix in the code-index project name | `<index-prefix>` | The name embedded a user name |

After the edit the reports were validated again (`validate_report.py`, and the state against
`readiness-state.schema.json`), and the files were searched for the user name and for `/home/` and `/tmp/` paths.
A report digest recorded anywhere refers to the Server repository's original file, not to these copies.

## Where it is used

- [Implement an audit report](../../../../docs/how-to/implement-an-audit-report.md): the walk-through points here.
- [Evaluation results](../../../../docs/reference/eval-results.md): the implement runs and the before/after numbers.
- [`compare_reports.py`](../../../../docs/reference/tools-cli.md): the comparison file is its output.
