# Tools CLI Reference

> **Audience:** Everyone
> **Source of truth:** each tool's `--describe` output; generated `tools/CATALOGUE.md` (planned, S2.8)
> **Status:** Live for `engine.py`, `validate_report.py` and, in part, `report.py` (`init` and `add-check`). The other tools are planned.

> [!NOTE]
> Planned. Only `engine.py` and `validate_report.py` exist, and `report.py` has its first two subcommands. The sections for the other tools are filled in by roadmap steps S2.3 to S2.8 and S5.1, and the generated `tools/CATALOGUE.md` by S2.8.

---

## Summary

| Item | Description | Status |
|---|---|---|
| [`engine.py`](#enginepy) | Runs the deterministic engine from any directory | Live |
| [`validate_report.py`](#validate_reportpy) | Validates a report against schema and semantic rules | Live |
| [`report.py`](#reportpy) | Builds and updates the audit report; the only writer | Live for `init` and `add-check`; the other subcommands: Planned (S2.3) |
| `render_report.py` | Renders a report to Markdown | Planned (S2.4) |
| `facts.py` | Emits stack and inventory facts, no verdicts | Planned (S2.7) |
| `recipe_lint.py` | Checks recipes for broken references and budgets | Planned (S2.8) |
| `progress.py` | Manages implementation progress | Planned (S5.1) |
| `check_drift.py` | Lists findings affected by changes since the audit | Planned (S5.1) |

## Every tool

Every tool follows the [tool contract](../../tools/README.md#the-contract): one JSON envelope on stdout, the exit codes below, `--describe`, bounded output, no network, no writes inside the target, and a Python 3.11 check first. The explanation is in [Tool Contract](../architecture/contributor-deep-dive/01-tool-contract.md).

| Exit code | Meaning |
|---|---|
| `0` | OK |
| `1` | Usage or input error, including a Python older than 3.11 |
| `2` | The input was read and failed validation |
| `3` | Internal error |

Run a tool as `python3 brownfield-recipes/tools/<tool>.py`, from any directory. Below Python 3.11 a tool prints how to run itself with `uv run --python 3.12`.

---

## engine.py

Runs the [deterministic engine](../../deterministic-audit/README.md) from any directory, writes its JSON report under a name that carries the repository's name, and never replaces a file. The decision to import the engine is [ADR 0001](../architecture/adrs/0001-tools-import-engine.md); the source is [`engine.py`](../../tools/engine.py).

**Synopsis**

```text
python3 brownfield-recipes/tools/engine.py <target> [--out-dir DIR] [--repo-label LABEL] [--phase N]
                                           [--exclude GLOB]... [--max-files N]
                                           [--run-gates --allow-probe VERB... [--timeout SECONDS]]
python3 brownfield-recipes/tools/engine.py --list-checks
python3 brownfield-recipes/tools/engine.py --describe
```

**Inputs**

| Argument | Meaning |
|---|---|
| `<target>` | The repository to scan. It must exist and be a directory. The engine only reads it. |
| `--out-dir DIR` | Where the report goes. It is created if it does not exist, and it must be outside the target. Default: the current directory, which is refused when it is inside the target. |
| `--repo-label LABEL` | The label in the file name: up to 32 of `a` to `z`, `0` to `9`, dot, underscore and hyphen, starting with a letter or digit. Default: derived from the target's directory name, as in [Output files](../../schema/SCHEMA.md#output-files). |
| `--phase N` | The highest framework phase to evaluate. The engine's default is 1. |
| `--exclude GLOB` | An extra path pattern to skip. May be repeated. |
| `--max-files N` | A hard cap on the files the engine inspects. |
| `--run-gates`, `--allow-probe VERB`, `--timeout SECONDS` | Let the engine run the target's own commands. Nothing runs unless `--run-gates` is given and every verb is named in an `--allow-probe`. `--timeout` is the limit per command. |
| `--list-checks` | Print the engine's checks and exit. It takes no other argument. |

The engine's `--force`, `--out`, `--format`, `--fail-on`, `--baseline` and `--emit-baseline` are not offered, and abbreviations of the options above are refused.

**Outputs**

A scan writes one file, `<label>.engine-report.<stamp>.json`, in the output directory. It is the engine's own JSON report, untouched. The envelope's `data` is:

| Key | Meaning |
|---|---|
| `report` | The path of the file written. |
| `label`, `stamp` | The two parts of the name. The stamp is the UTC launch time as `YYYYMMDDTHHMMSSZ`. |
| `target` | The target's resolved path. |
| `engine` | `version` and `ruleset_revision` of the engine that ran. |

`--list-checks` writes nothing. Its `data` holds `engine` (name, version, ruleset revision and hash), `checks` (the engine's list, one entry per check) and `omitted`, the number of checks left out to stay within the output budget, which is `0` today.

**Exit codes**

| Code | When |
|---|---|
| `0` | The report was written, or the checks were listed. |
| `1` | A bad argument, a missing target, an output directory inside the target, a bad label, or a refusal by the engine, whose reason is in `data.error`. |
| `3` | The engine exited with any other code, raised, or reported success without writing the report. |

**Errors**

| Message | Fix |
|---|---|
| `refusing to write inside the target` | Pass `--out-dir` with a directory outside the repository, or run from outside it. |
| `the engine refused the run: --run-gates requires at least one --allow-probe VERB` | Name each verb the engine may run with `--allow-probe`. |
| `the engine refused the run: ... exists; nothing was replaced, run the tool again` | Another run took the name in the same second. Run the tool again. |
| `repo_label ... is not allowed` | Use a label that matches the pattern above. |
| `--list-checks takes no other argument` | Run `--list-checks` on its own. |

---

## validate_report.py

Checks an audit report against [its schema](../../schema/audit-report.schema.json) and against the rules a schema cannot express, which are numbered in [`SCHEMA.md`](../../schema/SCHEMA.md#rules-beyond-the-schema). It reads the report and writes nothing. The source is [`validate_report.py`](../../tools/validate_report.py), and the schema checker it uses is [`_jsonschema_subset.py`](../../tools/_jsonschema_subset.py).

**Synopsis**

```text
python3 brownfield-recipes/tools/validate_report.py <report> [--target <repo>]
python3 brownfield-recipes/tools/validate_report.py --describe
```

**Inputs**

| Argument | Meaning |
|---|---|
| `<report>` | The report to check: a JSON file of at most 32 MiB. |
| `--target <repo>` | The audited repository. With it the tool also looks for each cited `file` path and warns about the ones that are missing (rule 12). It asks git whether the commit in `provenance.target.git_sha` holds the path, or looks in the working tree when no commit is recorded. It never writes to the target. |

**Outputs**

A valid report gives `data` with `valid` (`true`), `report` (the path as given), `schema_version`, `status`, the number of `checks` and `findings`, and `target_checked`. Warnings are in the envelope's `warnings`, bounded like every list; when some were left out, `truncated` is `true` and `data.warnings_omitted` says how many. Warnings come only once a report has no errors.

An invalid report gives `data.error`, which counts the errors and names the stage, and `data.errors`, one string for each error:

```text
rule 6: /checks/6: TOOL-03 overrides the engine's PARTIAL with PASS and gives no override_reason
schema: /checks/1/verdict: expected one of ["PASS", "PARTIAL", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]
```

The tool checks in two stages. The first applies the schema, and a report that fails it is returned with its schema errors alone, up to 500. The second applies the rules, only to a report that passed the first, because the rules read fields the schema guarantees. Errors come in rule order, then in the order of the document. An error names the place with a JSON Pointer and never repeats the value it found, so a credential in a quote does not travel into the list.

**Exit codes**

| Code | When |
|---|---|
| `0` | The report is valid. |
| `1` | A bad argument, a report that is missing, not a file or over the size limit, or a target that does not exist. |
| `2` | The report was read and is not valid: it fails the schema or a rule, or the file is not JSON, repeats a key, holds `NaN` or `Infinity`, is not UTF-8, or is nested too deeply. |
| `3` | Internal error. |

**Errors**

| Message | Fix |
|---|---|
| `rule 1: ...` to `rule 12: ...` | The rule is in [Rules beyond the schema](../../schema/SCHEMA.md#rules-beyond-the-schema). The message says which item to change. |
| `rule 10: /summary/...: the report says X and its checks and findings give Y` | The summary is stale. It is never edited by hand: the report builder (S2.3) writes it, and until it exists the number Y is the one to use. |
| `rule 11: ... it looks like a credential` | Shorten the quote or the output tail, or leave it out. The patterns are the engine's, so a line such as `token: abc` is flagged even when it is not a secret. |
| `schema: /path: ...` | The pointer names the field. The schema is [`audit-report.schema.json`](../../schema/audit-report.schema.json). |
| `the file is not a report: ...` | The file is not one JSON document that this tool accepts. |

---

## report.py

Builds the audit report. It is the only writer of the draft: the agent calls a subcommand and never edits the JSON by hand. Every file it writes is validated first with the checks of [`validate_report.py`](#validate_reportpy), and the readiness summary is computed by the tool, never taken from a caller. The source is [`report.py`](../../tools/report.py).

Only `init` and `add-check` exist so far. `add-finding`, `set-disposition`, `status` and `finalise` are planned in the same step (S2.3), and `import-engine` is S2.5.

Every subcommand but `init` changes the draft it is given, in place. A change is one step: the draft is read and validated, the change is made, the summary is recomputed, the result is validated, and only then is it written, atomically, so a crash or a refusal leaves the previous draft as it was. Commands that change drafts in one folder take turns, through a lock on the folder that the system releases when the process ends; run them one at a time anyway, because a command that cannot get the lock in 30 seconds exits with 1. A final report is never changed.

**Synopsis**

```text
python3 brownfield-recipes/tools/report.py init <intake>
python3 brownfield-recipes/tools/report.py add-check <draft> --from FILE|-
python3 brownfield-recipes/tools/report.py --describe
```

### init

Starts a draft from an intake file. It reads the intake (the answers to the audit's Stage 0 questions, [`audit-intake.schema.json`](../../schema/audit-intake.schema.json)), captures the target's provenance, and creates `<label>.audit-draft.<stamp>.json` in the intake's `output_dir`. A second run on the same repository starts a second draft with a new stamp; the earlier draft stays as it was, and a name that is taken gets `-2`, `-3`. The names are defined in [Output files](../../schema/SCHEMA.md#output-files).

**Inputs**

| Argument | Meaning |
|---|---|
| `<intake>` | The intake file, a JSON file of at most 32 MiB. Relative paths inside it, `target_path` and `output_dir`, are relative to the working directory. |

**What it records**

| Field | Source |
|---|---|
| `provenance.target.path` | The intake's `target_path`, resolved to an absolute path. |
| `provenance.target.git_sha`, `branch`, `dirty` | Read from git with read-only commands. Each is `null` when it cannot be known: the target is not a repository, the repository has no commit, `HEAD` is detached (no branch), or git is missing. A target that is a subfolder of a repository records nothing and gives a warning, because a commit id says nothing about a subfolder. |
| `provenance.target.label` | The intake's `repo_label`, or a label derived from the target directory's name. |
| `provenance.framework_revision` | The commit of the framework checkout the tools run from, or `null` when they are not in one. |
| `provenance.catalogue_version` | The version of [`catalogue.json`](../../catalogue.json). |
| `provenance.agent` | The intake's `harness` and `model`. |
| `provenance.started_at` | The UTC start time. Its `YYYYMMDDTHHMMSSZ` form is the stamp in the file name. |
| `run_context` | The intake's `eval_mode`, `confirmation_policy`, `provider_exposure_acknowledged`, `index` (without `allow_install`), `probes` (default: nothing allowed, 120 seconds), `excluded` and `known_components`. `allow_install` and `output_dir` are instructions to the run and are not in the report. |

The draft starts with no checks, no findings and a summary computed from them. The scan facts (`stack`, `components`) and the engine's checks arrive with `import-engine` (S2.5).

**Outputs**

`data` holds `draft` (the path written), `label`, `target` (`path`, `git_sha`, `branch`, `dirty`) and `status` (`draft`). Warnings are in the envelope.

**Exit codes**

| Code | When |
|---|---|
| `0` | The draft was written. |
| `1` | A bad argument, an intake that is missing or too large, a target that is missing or not a directory, or an `output_dir` inside the target, including through a symlink. Nothing is written. |
| `2` | The intake fails its schema or its rules, or is not valid JSON. `data.errors` lists every error. Nothing is written. |
| `3` | Internal error. |

**Errors**

| Message | Fix |
|---|---|
| `schema: /pointer: ...` | The pointer names the field of the intake that the schema refuses. |
| `intake rule: /confirmation_policy: 'accept-all' is allowed only with eval_mode set to true` | `accept-all` confirms every finding without a person, so it is for evaluation runs. Set `eval_mode` or choose another policy. |
| `intake rule: /confirmation_policy: an eval-mode run cannot be 'interactive'` | An evaluation run has no person to ask. Use `defer-all` or `accept-all`. |
| `intake rule: /index/name: ... the index needs a name` | Name the index tool, or set `index.kind` to `none`. |
| `target not found: ...` | Fix `target_path`. |
| `refusing to write inside the target: ...` | Choose an `output_dir` outside the repository. |

### Fragments

`add-check` and the subcommands after it take a **fragment**: a JSON object with the fields the agent decides, from a file (`--from FILE`) or from stdin (`--from -`, for example with a here-document). The tool fills in everything it can compute, so a fragment holds nothing it could get wrong.

- A field that the tool computes is refused as an unknown field, with its place: `fragment: /: unexpected property: 'title'`.
- Evidence is the agent's. Leave out `captured_by`, `tool` and `tool_version`; the tool writes `captured_by: agent`. A fragment that claims a tool captured something is refused, because the report must never show a deterministic source for text a model wrote.
- A fragment fails as a whole: every problem is listed in `data.errors`, each starting with `fragment:` and a JSON Pointer into the fragment.

A fragment that is valid on its own can still leave the draft invalid, for example by citing a path that leaves the target. The tool then refuses it with the rule that fails (`rule 3: ...`) and writes nothing.

### add-check

Records the result for one check.

```text
python3 brownfield-recipes/tools/report.py add-check <draft> --from -
```

```json
{
  "id": "AGT-11",
  "verdict": "PASS",
  "confidence": "high",
  "summary": "AGENTS.md states a release rule that the code does not reveal.",
  "evidence": [{ "kind": "file", "path": "AGENTS.md", "lines": "14-15", "quote": "Never run npm publish by hand." }],
  "searches": []
}
```

| Fragment field | Meaning |
|---|---|
| `id`, `verdict`, `summary` | Required. The check's ID in [`catalogue.json`](../../catalogue.json), the verdict, and one short sentence. |
| `confidence`, `evidence`, `searches` | Optional. As in the [report schema](../../schema/SCHEMA.md#evidence). |
| `override_reason` | Only when disputing a verdict the engine gave; see below. |

The tool adds the check's `title`, `phase`, `severity`, `scored` and `method` from the catalogue, so the agent cannot misstate them. The check is added at the end of `checks`; recording a check again replaces its verdict, summary, confidence, evidence and searches in place.

**A check only the engine can run.** `add-check` cannot add an `automated` check, whose verdict comes from the engine (the checks arrive with `import-engine`, S2.5). It can dispute one the engine already ran: the engine's verdict stays in `engine_verdict`, with the engine's evidence and `data`, and the agent's `verdict`, `summary`, `override_reason` and agent-captured evidence are recorded beside them. A dispute needs an `override_reason` and at least one evidence item (rule 6). Disputing the same check again replaces the agent's earlier evidence. A fragment whose verdict equals the engine's clears an earlier dispute (and has no `override_reason`). A check whose finding is still `pending` cannot be disputed to `PASS`: reject the finding first (rule 7).

**Outputs.** `data` holds `draft`, `check`, `action` (`added`, `replaced`, `overridden` or `agreed`), `verdict`, `engine_verdict` (for an engine check), `checks_recorded` and `checks_expected` (the phase-1 checks of the catalogue). Warnings list each cited file that is not in the target at the recorded commit, for this check only (rule 12).

**Exit codes**

| Code | When |
|---|---|
| `0` | The check was recorded. |
| `1` | A bad argument; the draft or the fragment file is missing or too large; the draft is a final report; the draft's folder is inside the target; the lock could not be taken; the file could not be written. |
| `2` | The fragment is not valid JSON or fails its schema; the check is unknown, or automated and not yet in the draft; the draft was already invalid; or the change would leave it invalid (`data.errors` has the rule). Nothing is written. |
| `3` | Internal error. |

**Errors**

| Message | Fix |
|---|---|
| `fragment: /pointer: ...` | Fix the field the pointer names. |
| `fragment: /evidence/N: the agent cannot record tool-captured evidence ...` | Leave out `captured_by`, `tool` and `tool_version`. |
| `<ID> is an automated check, so its verdict comes from the engine ...` | Import the engine's report first; then dispute the verdict if the evidence says it is wrong. |
| `the draft is not valid before the change` | The draft was edited by hand or by another tool. Fix it, or start a new draft with `init`. |
| `the change would leave the draft invalid, so nothing was written` | `data.errors` names the rule and the place. Change the fragment. |
| `rule 5: ... is an agent check with the verdict PASS and has no evidence` | Cite what shows the check passes, or record `FAIL` or `UNKNOWN` and say what was missing. |
| `another report command has held the lock on ...` | Another `report.py` command is still running on a draft in the same folder. Wait for it, and run commands one at a time. |
