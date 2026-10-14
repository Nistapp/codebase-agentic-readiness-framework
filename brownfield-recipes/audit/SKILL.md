---
name: audit
description: Audit a repository for agentic readiness against the framework's Phase-1 requirements. Runs the deterministic engine, verifies every blocker independently, resolves what the engine could not judge, and produces a schema-valid, evidence-cited report the user confirms before it is final. Use this when asked to audit, assess or score a repository's readiness for AI coding agents, or to run the agentic-readiness-audit.
---

# Audit

This skill assesses whether a repository is safe for an AI coding agent to work in, against the framework's
Phase-1 requirements (`spec/readiness-requirements.md`). It produces one JSON report and its Markdown
rendering. It never changes the audited repository. The implementation recipe (a separate skill, not yet
written) is what acts on the findings.

## When to use it

Use this skill when asked to audit, assess, score or evaluate a repository's readiness for AI coding agents,
or when asked to run the `agentic-readiness-audit`. Do not use it to fix anything it finds — that is the
implementation recipe's job once it exists.

## Hard rules

These apply through every stage, without exception:

- **Read-only against the target.** The audit never writes inside the repository it is assessing. Every
  tool below refuses an output path inside the target on its own, but say so to the user too.
- **Writes go only to the output directory** the intake names, outside the target.
- **Cite evidence for every verdict.** A check or finding with nothing in `evidence[]` or `searches[]` is
  not a verdict, it is a guess.
- **Absence claims list the searches.** A `FAIL` or a `0`-hit claim records what was searched and where,
  not just the conclusion.
- **Use `UNKNOWN` instead of guessing.** A check with no way to gather evidence is `UNKNOWN`, never a
  guessed `PASS` or `FAIL`.
- **Do not pad findings.** One finding per real issue; do not split one problem into several to look
  thorough, and do not invent minor findings to fill out a report.
- **Stop and ask when intake answers are ambiguous.** Guessing at Stage 0 compounds through every later
  stage.
- **Never hand-edit the report JSON.** Every change goes through `report.py`'s subcommands, which validate
  before they write. An agent that edits the draft directly breaks the one guarantee the tool gives.
- **Run target commands only through the engine's Tier-C runner** (`engine.py --run-gates --allow-probe
  <verb>`), and only for a verb the user allowed at intake. Never run a target's own command directly.
- **To override a check the engine already ran, reject its finding first**, then record the override with
  `add-check` and an `override_reason`. Recording `PASS` over a `pending` finding is refused (the finding
  must be rejected first); see [`report.py` CLI reference, `add-check`](../docs/reference/tools-cli.md#add-check).

## Stages

| Stage | Name | Written in |
|---|---|---|
| 0 | Intake | S3.5.2 |
| 1 | Recon | S3.5.2 |
| 2 | Assess | S3.5.3 |
| 3 | Synthesize | S3.5.4 |
| 4 | Confirm | S3.5.4 |
| 5 | Finalise | S3.5.4 |

Stage 2 works through the catalogue's thirteen families in order: `IDX`, `AGT`, `DOC`, `CMD`, `TOOL`, `CI`,
`BASE`, `CON`, `EXEC`, `TST`, `NAV`, `SEC`, `HYG`. Each family's check file is `audit/checks/NN-*.md`,
listed in [`audit/checks/README.md`](checks/README.md).

## Tools

Full detail, including every input, error message and exit code, is in the
[Tools CLI reference](../docs/reference/tools-cli.md). This table is what each call expects to happen and
what to do when it does not.

| Tool | Call | Expected result | Fallback |
|---|---|---|---|
| [`facts.py`](../docs/reference/tools-cli.md#factspy) | `facts.py <target> --out FILE` | Exit `0`; one JSON file with inventory, stack, instruction files, components and a size class. | Exit `1` on a bad target or path: fix the argument and retry. There is no facts-free path for Stage 1; a failure here is a reason to stop and ask, not to guess the stack. |
| [`engine.py`](../docs/reference/tools-cli.md#enginepy) | `engine.py <target> --out-dir DIR [--run-gates --allow-probe VERB]...` | Exit `0`; the engine's own JSON report written under `DIR`, named with the repository's label. | Exit `1` with `data.error` naming why (bad target, bad label, name already taken this second — rerun). Exit `3` means the engine itself failed; record that as `UNKNOWN` for every automated check and tell the user, never fabricate engine verdicts. |
| [`report.py init`](../docs/reference/tools-cli.md#init) | `report.py init <intake>` | Exit `0`; a new draft report, provenance filled in from the intake and git. | Exit `2` means the intake fails its schema: `data.errors` names each field; fix the intake and retry. Exit `1` means a bad path; fix and retry. |
| [`report.py import-engine`](../docs/reference/tools-cli.md#import-engine) | `report.py import-engine <draft> <engine report>` | Exit `0`; the engine's checks, findings, stack and components are now in the draft. Runs once per draft, straight after `init`. | Exit `2` with `data.error` naming the mismatch (wrong target, wrong schema version, already imported). Do not retry blindly — read the message; a draft that already holds an import needs a new draft via `init`, not a second `import-engine`. |
| [`report.py add-check`](../docs/reference/tools-cli.md#add-check) | `report.py add-check <draft> --from -` | Exit `0`; the check is recorded or its agent-side dispute is recorded beside the engine's own verdict. | Exit `2` means the fragment is malformed or the override is missing its `override_reason` or evidence (rule 6): fix the fragment from `data.errors` and resend. An automated check that is not yet in the draft (exit `2`, "comes from the engine") means `import-engine` has not run yet. |
| [`report.py add-finding`](../docs/reference/tools-cli.md#add-finding) | `report.py add-finding <draft> --from -` | Exit `0`; the finding is recorded against a check already in the draft. | Exit `2` if the check is not yet recorded (record it first) or the finding would outrank its check's severity (rule 7; lower the severity or fix the check). |
| [`report.py set-disposition`](../docs/reference/tools-cli.md#set-disposition) | `report.py set-disposition <draft> --via <via> --finding <id> --disposition <d>` | Exit `0`; the person's decision is recorded, never the tool's own. | Exit `2` on a disallowed combination (e.g. `--via batch` on a `BLOCKER`, or `--via policy` outside `accept-all`): read `data.errors` and ask the person the way the rule actually requires. |
| [`report.py status`](../docs/reference/tools-cli.md#status) | `report.py status <draft>` | Exit `0`; which families are done, which findings are pending, and whether `finalise` would succeed. | Run this first after any interruption (crash, a new session, context exhaustion) instead of guessing where the audit left off. |
| [`report.py finalise`](../docs/reference/tools-cli.md#finalise) | `report.py finalise <draft>` | Exit `0`; the final JSON report and its Markdown are written beside the draft. | Exit `2` lists every blocking condition in `data.errors` (checks not recorded, findings pending, a blocker not decided interactively). Fix each one, then run `status` to confirm, then retry `finalise`. |
| [`validate_report.py`](../docs/reference/tools-cli.md#validate_reportpy) | `validate_report.py <report> [--target <repo>]` | Exit `0`; the report is schema- and rule-valid. `report.py` already runs this before every write, so a direct call is for checking a report written earlier. | Exit `2` lists every rule and schema error with a JSON Pointer; fix the draft through `report.py`'s subcommands, never by hand. |
| [`render_report.py`](../docs/reference/tools-cli.md#render_reportpy) | `render_report.py <report> --out <md>` | Exit `0`; a Markdown file. `report.py finalise` already calls this for the final report; a direct call is for a draft or an earlier report. | Exit `1` if `--out` already exists (a tool never replaces a file): choose a new name, or delete the stale file first if refreshing it on purpose. |

If the harness offers no shell, none of the tools above can run. Say so to the user, mark the report
`validated: false` in the intake's eval settings where supported, and fall back to a manual, documented
self-check against `validate_report.py`'s own rules, listed in [`SCHEMA.md`](../schema/SCHEMA.md#rules-beyond-the-schema).
