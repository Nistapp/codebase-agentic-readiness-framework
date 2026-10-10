# Tools CLI Reference

> **Audience:** Everyone
> **Source of truth:** each tool's `--describe` output; generated `tools/CATALOGUE.md` (planned, S2.8)
> **Status:** Live for `engine.py`, `validate_report.py`, `report.py`, except its `import-engine` subcommand (S2.5), and `render_report.py`. The other tools are planned.

> [!NOTE]
> Planned. Only `engine.py`, `validate_report.py`, `report.py` and `render_report.py` exist. The sections for the other tools are filled in by roadmap steps S2.5 to S2.8 and S5.1, and the generated `tools/CATALOGUE.md` by S2.8.

---

## Summary

| Item | Description | Status |
|---|---|---|
| [`engine.py`](#enginepy) | Runs the deterministic engine from any directory | Live |
| [`validate_report.py`](#validate_reportpy) | Validates a report against schema and semantic rules | Live |
| [`report.py`](#reportpy) | Builds and updates the audit report; the only writer | Live, except `import-engine`: Planned (S2.5) |
| [`render_report.py`](#render_reportpy) | Renders a report to Markdown | Live |
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

Builds the audit report. It is the only writer of the draft: the agent calls a subcommand and never edits the JSON by hand. The draft's path may be a link: the draft it points to is changed, and the link stays a link. Every file it writes is validated first with the checks of [`validate_report.py`](#validate_reportpy), and the readiness summary is computed by the tool, never taken from a caller. The source is [`report.py`](../../tools/report.py).

The subcommands are `init`, `add-check`, `add-finding`, `set-disposition`, `status` and `finalise`. `import-engine`, which brings in the engine's checks, is planned (S2.5).

Every subcommand but `init` and `status` changes the draft it is given, in place. A change is one step: the draft is read and validated, the change is made, the summary is recomputed, the result is validated, and only then is it written, atomically, so a crash or a refusal leaves the previous draft as it was. Commands that change drafts in one folder take turns, through a lock on the folder that the system releases when the process ends; run them one at a time anyway, because a command that cannot get the lock in 30 seconds exits with 1. A final report is never changed.

**Synopsis**

```text
python3 brownfield-recipes/tools/report.py init <intake>
python3 brownfield-recipes/tools/report.py add-check <draft> --from FILE|-
python3 brownfield-recipes/tools/report.py add-finding <draft> --from FILE|-
python3 brownfield-recipes/tools/report.py set-disposition <draft> --via VIA
        (--finding ID --disposition DISPOSITION [--note TEXT] | --from FILE|-)
python3 brownfield-recipes/tools/report.py status <draft>
python3 brownfield-recipes/tools/report.py finalise <draft>
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

### add-finding

Records an issue that a check raised.

```text
python3 brownfield-recipes/tools/report.py add-finding <draft> --from -
```

```json
{
  "check": "SEC-02",
  "scope": "src/config/constants.ts",
  "statement": "An agent cannot tell a credential from a placeholder because a live-looking key sits in constants.ts.",
  "evidence": [{ "kind": "file", "path": "src/config/constants.ts", "lines": "12" }],
  "remediation": { "summary": "Move the key to the environment and rotate it.", "playbook": "env-inventory-and-secrets", "effort": "S" }
}
```

| Fragment field | Meaning |
|---|---|
| `check`, `statement`, `remediation` | Required. The check the finding belongs to, which must already be in the draft; the statement, always "An agent cannot X because Y."; and the remediation (`summary`, and optionally `playbook`, `effort`, `depends_on` and `touches`). A playbook must be one the catalogue names. |
| `scope` | Optional. A path or component that tells two findings of one check apart. |
| `severity` | Optional. The check's severity by default. It may be lower, never higher. |
| `evidence`, `searches` | Optional. As for `add-check`. |

The tool computes what the agent must not write:

- **`key`** is the check ID, then `:` and the scope when there is one: `SEC-02:src/config/constants.ts`. A re-audit matches findings by key, so the tool writes the scope in one spelling: backslashes become `/`, `./` and `//` and `..` segments are resolved, and a scope of `.` means the whole check. A scope that is absolute, climbs out of the target, is empty or holds whitespace is refused.
- **`id`** is the next `F-nnn` after the highest in the draft. It is for display, and it is never reused.
- **`disposition`** is `pending` until a person decides. Under the `accept-all` policy (evaluation runs only) it is `confirmed`, with `confirmed_via: policy`.

Recording a finding again with the same key replaces it in place and keeps its `id`, as long as it is `pending`. A finding that has a decision is not the agent's to rewrite: the command exits 2 and names it. A finding on a check whose verdict is `PASS` is refused, because a passing check has no issue to raise (rule 7).

**Outputs.** `data` holds `draft`, `finding` (the id), `key`, `action` (`added` or `replaced`), `check`, `severity`, `disposition`, `findings` and `findings_pending`. Warnings list each cited file that is not in the target at the recorded commit, for this finding only.

**Exit codes** are those of `add-check`. A check that is not in the draft, a scope that is not usable and a finding that already has a decision are exit 2.

**Errors**

| Message | Fix |
|---|---|
| `<ID> is not a check in this draft` | Record the check first with `add-check`, or import the engine's report. |
| `fragment: /scope: ...` | Use a path inside the target, or a component name without whitespace; or leave `scope` out. |
| `<F-id> (<key>) already has a decision, so the agent cannot rewrite it` | A person decided. Set the finding back to `pending` with `set-disposition` to record it again, or give the new finding another scope. |
| `rule 7: ... is higher than <ID>'s <severity>` | A finding is never more severe than its check. |
| `rule 7: ... is PASS, so its finding must be rejected` | The check passes, so it raises no finding. Record the check as failing first, if it fails. |
| `rule 2: ... the catalogue names no playbook ...` | Use a playbook named in [`catalogue.json`](../../catalogue.json), or leave `playbook` out. |
| `rule 1: ... is not a finding in this report` | A `depends_on` entry must be the id of a finding already recorded. |

### set-disposition

Records what a person decided about findings, and how the decision was made. The agent asks the person and then calls this command; the tool never decides. It changes one finding or a list in a single write: if any decision in a list is refused, none is applied.

```text
python3 brownfield-recipes/tools/report.py set-disposition <draft> --via interactive \
    --finding F-003 --disposition rejected --note "Placeholders in a unit test."
python3 brownfield-recipes/tools/report.py set-disposition <draft> --via batch --from -
```

A list is a JSON array, each item with `finding` and `disposition` and, optionally, a `note`:

```json
[
  { "finding": "F-004", "disposition": "confirmed" },
  { "finding": "F-005", "disposition": "rejected", "note": "Not an issue here." }
]
```

| Argument | Meaning |
|---|---|
| `--via` | How the decision was made: `interactive` (the person answered for this finding), `batch` (the person answered for a group, which cannot include a `BLOCKER`) or `policy` (the run's `accept-all` policy decided; evaluation runs only). It is recorded as `confirmed_via`. Not needed to take a decision back. |
| `--finding`, `--disposition`, `--note` | One decision: the finding's id, `pending`, `confirmed`, `rejected`, `deferred` or `edited`, and the person's reason. |
| `--from FILE`, or `--from -` for stdin | A list of decisions, instead of `--finding`, `--disposition` and `--note`. |

`pending` takes a decision back: the finding loses its `confirmed_via` and its note. Setting any other disposition replaces the old note with the new one, or with none. The tool does not edit a finding's text. To change what a decided finding says, set it back to `pending`, record it again with `add-finding`, and ask the person again.

The tool refuses a decision that would claim something false about who made it:

| Refused | Because |
|---|---|
| `--via batch` for a finding of severity `BLOCKER` | A person decides on a blocker alone; a final report needs `confirmed_via: interactive` for each (rule 8). |
| `--via interactive` or `batch` in an eval-mode run | An evaluation run has no person. |
| `--via policy` unless the policy is `accept-all` | Only that policy decides anything. Under `defer-all` every finding stays `pending` until a person decides later, with `--via interactive`. |
| A decision on a finding of a passing check that is not `rejected` | A passing check has no standing finding (rule 7). |

**Outputs.** `data` holds `draft`, `updated` (the number of decisions), `by_disposition` (a count for each), `findings`, `findings_pending` and `blockers_pending`.

**Exit codes**

| Code | When |
|---|---|
| `0` | The decisions were recorded. |
| `1` | A bad argument: no decision given, both `--from` and `--finding`, a missing `--via`, a value outside the choices; or the draft or file is missing, the draft is final, or the file could not be written. |
| `2` | A list that fails its schema; a finding that is not in the draft or appears twice; a refused decision; a draft that was invalid or would be. Nothing is written. |
| `3` | Internal error. |

**Errors**

| Message | Fix |
|---|---|
| `--via is required when a finding gets a decision` | Say how the decision was made. |
| `<F-id> is a BLOCKER, so a person decides on it alone: use --via interactive` | Ask the person about the blocker, and call the command for it on its own. |
| `this is an eval-mode run, which has no person to decide: only --via policy is allowed` | An evaluation run's findings are decided by the policy, or stay pending. |
| `--via policy needs the 'accept-all' confirmation policy ...` | Use `--via interactive` or `batch`, for a person's decision. |
| `<F-id> is not a finding in this draft` | Use an id from `status`. |
| `fragment: /N/...` | Fix the item the pointer names. |

### status

Says where an audit stands: which families of checks are done, which are not, and which findings still wait for a decision. It is what to run first when a session resumes after a crash or after the agent's context ran out, because the draft holds everything and the tool reads it. It reads the draft and writes nothing, and it does not wait for the lock.

```text
python3 brownfield-recipes/tools/report.py status <draft>
```

The draft may be final: `status` then reports it and says it is already final. A draft that fails validation is exit 2, with the errors.

**Outputs.** The envelope is at most **40 lines** on stdout, so a report of 70 checks costs a few hundred tokens and not a page. `data` holds:

| Key | Meaning |
|---|---|
| `draft`, `status` | The path as given, and `draft` or `final`. |
| `eval_mode`, `confirmation_policy` | The run's answers, which say who may decide. |
| `checks_recorded`, `checks_expected` | The checks in the draft, and the phase-1 checks of the catalogue. |
| `families_done` | The families whose checks are all recorded, in the order the audit works through them (the catalogue's). |
| `families_remaining` | For each family with a check not yet recorded, the IDs of those checks. |
| `findings`, `findings_pending`, `blockers_pending` | The findings, those waiting for a decision, and the `BLOCKER` ones among them. |
| `ready_to_finalise`, `blocking` | Whether `finalise` has nothing to stop it, and if not, why in a sentence: an eval-mode run, checks not recorded, findings pending, a `BLOCKER` not decided interactively, or a report that is already final. `finalise` has the last word: it validates the final report. |
| `pending` | The findings waiting for a decision, one line each as `<id> <severity> <key>`, blockers first, as many as fit in the line budget (at most 8). |
| `pending_omitted` | How many pending findings are not listed, when some are left out. The envelope then has `truncated: true`. |

**Exit codes**

| Code | When |
|---|---|
| `0` | The state was reported. |
| `1` | A bad argument, or the draft is missing or too large. |
| `2` | The draft is not valid JSON, or fails its schema or a rule: it was edited by hand or by another tool. |
| `3` | Internal error. |

### finalise

Writes the final report from a finished draft. It checks that nothing stands in the way, validates the result, renders its Markdown with [`render_report.py`](#render_reportpy), and creates `<label>.audit-report.<stamp>.json` and `<label>.audit-report.<stamp>.md` beside the draft. The two files share one name apart from the extension: if either name is taken, both take `-2` after the stamp. The draft is left exactly as it was, and no earlier file is touched: a second `finalise` writes a second pair.

```text
python3 brownfield-recipes/tools/report.py finalise <draft>
```

The final report is the draft with `status: final` and `provenance.finalised_at`, and nothing else. The stamp in the name is the `finalised_at` time. The Markdown is the rendering of that report, made before anything is written, so a failure leaves no file of either kind. A final report is never changed afterwards: every other subcommand refuses it.

A draft can be finalised only when all of this holds, and each problem that does not is one line in `data.errors`:

| Condition | Why |
|---|---|
| The run is not an eval-mode run. | An evaluation run has no person to decide, so its report is never final. |
| Every phase-1 check of the catalogue is recorded, in every family. | A final report that leaves checks out would show a score over fewer checks than the audit has, with nothing to say so. A check that could not be evaluated is recorded as `UNKNOWN` with a summary that says why. |
| No finding is `pending`. | Each finding has been confirmed, rejected, deferred or edited by a person. |
| Every `BLOCKER` finding was decided with `--via interactive`. | A person decides on a blocker alone (rule 8). |
| The final report passes [`validate_report.py`](#validate_reportpy). | The same schema and rules, applied to the file before it is written. |

`status` reports the same conditions as `ready_to_finalise` and `blocking`, without writing anything.

**Outputs.** `data` holds `report` (the path of the new JSON file), `markdown` (the path of the Markdown file beside it), `draft`, `status` (`final`), `finalised_at`, `checks`, `findings` and `summary` (the readiness summary: score, scored checks, blockers remaining and the two qualifiers). Warnings list each cited file that is not in the target at the recorded commit, for the whole report, bounded.

**Exit codes**

| Code | When |
|---|---|
| `0` | The final report and its Markdown were written. |
| `1` | A bad argument; the draft is missing or too large, or is already a final report; its folder is inside the target; the lock could not be taken; the file could not be written. Nothing is written, and no partial file of either kind is left. |
| `2` | The draft cannot be finalised (`data.errors` lists every problem), the draft was already invalid, or the final report would be. Nothing is written. |
| `3` | Internal error. |

**Errors**

| Message | Fix |
|---|---|
| `the draft cannot be finalised: N problems` | Read `data.errors`: record the checks it lists, ask the person about the findings it lists, then run `status` and `finalise` again. |
| `checks not recorded in <FAMILY>: ...` | Record each check: `add-check` for an agent check, `import-engine` (S2.5) for the engine's. |
| `N findings still pending: F-001 ...` | Ask the person, and record the answers with `set-disposition`. The list shows the first 20. |
| `BLOCKER findings not decided interactively: ...` | Ask the person about each blocker, and record it with `--via interactive`. |
| `this is an eval-mode run, and its report is never final` | An evaluation run writes drafts only. |
| `the final report would not be valid, so nothing was written` | `data.errors` names the rule. This is a defect in the draft's state that `status` could not see, or a bug in the tool: report it. |

---

## render_report.py

Renders an audit report to Markdown. The Markdown is a pure function of the JSON report: one report gives the same bytes every time, whatever order its keys come in, and nothing in the Markdown is absent from the JSON apart from the words that explain a verdict or a severity. The readiness summary is computed with [`_summary.py`](../../tools/_summary.py), the code that the validator and the report builder use, and never taken from the file. The source is [`render_report.py`](../../tools/render_report.py). [`report.py finalise`](#finalise) calls it to write the Markdown beside the final report, and it is a command of its own for a draft, or for a report written earlier.

**Synopsis**

```text
python3 brownfield-recipes/tools/render_report.py <report> --out <md>
python3 brownfield-recipes/tools/render_report.py --describe
```

**Inputs**

| Argument | Meaning |
|---|---|
| `<report>` | An audit report, draft or final: a JSON file of at most 32 MiB. It must be valid. The tool applies the checks of [`validate_report.py`](#validate_reportpy) and renders nothing when one fails, because it reads fields that only a valid report guarantees. |
| `--out <md>` | The Markdown file to create. It must not exist, its folder must, and the folder must be outside the audited target. The tool never replaces a file. |

**What the Markdown holds**

| Section | What it shows |
|---|---|
| Title and banners | The repository, the commit, and when the report was finalised or started. A warning banner for an evaluation run, and a note banner for a draft, which counts the findings that await a decision. |
| Readiness summary | The headline of [`spec/readiness-summary.md`](../../../spec/readiness-summary.md) and no other number: the phase-1 score to two places, the blockers remaining by state, and the unattested requirements, then the two qualifiers. |
| Blockers remaining | Each scored BLOCKER check that is not PASS, with its verdict and summary. |
| Overrides of the engine's verdicts | Each check whose verdict differs from the engine's, with both verdicts and the reason. |
| Checks | How many checks have each verdict, what each verdict and severity means, and a table with a row for every check. |
| Check details | A block for each check that is not met, was overridden, was judged by the agent or raised a finding, in order of severity. It shows who captured each piece of evidence, each quote in a fenced block, the searches, and the check's findings with their fix and the decision on them. |
| Coverage, Stack and components, Provenance, Run context | What the audit examined and skipped, what was detected, where the report came from, and the intake answers the run used. |

A check that is `FAIL` or `UNKNOWN` and shows no evidence and no search, on the check or on any of its findings, says "We did not find any evidence." A check that passed and was settled by a tool has only its row in the table: its evidence and the engine's payloads are in the JSON report. A finding whose evidence equals its check's says so and does not print it twice.

The words of a report come from the audited repository, through a model, so the tool treats them as untrusted. Free text has every Markdown special character escaped, so that it cannot become a link, an image, a tag or a heading. A path or a command is in a code span, and a quote or an output tail in a fenced block, each with a delimiter longer than any run of backticks inside it. A control character, and a character that reorders or hides text, is written out as `{U+XXXX}`. A `|` cannot add a column to a table.

**Outputs**

`data` holds `markdown` (the path written), `report` (the path as given), `status` (`draft` or `final`), `lines` and `bytes`. Warnings are the validator's, bounded like every list.

**Exit codes**

| Code | When |
|---|---|
| `0` | The Markdown was written. |
| `1` | A bad argument, a report that is missing, not a file or over the size limit, an `--out` that exists or has no folder, a folder inside the target, or a file that could not be written. Nothing is written, and no partial file is left. |
| `2` | The report was read and is not valid: it fails the schema or a rule, or the file is not JSON. `data.errors` lists every error. Nothing is written. |
| `3` | Internal error. |

**Errors**

| Message | Fix |
|---|---|
| `the report is not valid, so it was not rendered: N errors in the S stage` | Run [`validate_report.py`](#validate_reportpy) on the report and fix what it names. A report that `report.py` wrote is valid, so this means it was edited by hand. |
| `<path> already exists, and a tool never replaces a file` | Choose another `--out`. To refresh a golden file on purpose, delete it first and read the diff. |
| `the folder for --out does not exist: <folder>` | Create the folder, or choose one that exists. The tool creates files and never folders. |
| `refusing to write inside the target: <folder>` | Choose a folder outside the audited repository. The tools never write inside it. |
| `cannot write <path>: <reason>` | The system's reason, such as a full disk or a missing permission. No partial file is left. |
