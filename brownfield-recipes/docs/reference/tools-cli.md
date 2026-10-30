# Tools CLI Reference

> **Audience:** Everyone
> **Source of truth:** each tool's `--describe` output; generated [`tools/CATALOGUE.md`](../../tools/CATALOGUE.md)
> **Status:** Live for `engine.py`, `validate_report.py`, `report.py`, `render_report.py`, `facts.py`, `recipe_lint.py` (all eight rules, including the generated catalogue) `build_skills.py`, `progress.py` (all commands), and `check_drift.py`.

---

## Summary

| Item | Description | Status |
|---|---|---|
| [`engine.py`](#enginepy) | Runs the deterministic engine from any directory | Live |
| [`validate_report.py`](#validate_reportpy) | Validates a report against schema and semantic rules | Live |
| [`report.py`](#reportpy) | Builds and updates the audit report; the only writer | Live |
| [`render_report.py`](#render_reportpy) | Renders a report to Markdown | Live |
| [`facts.py`](#factspy) | Emits inventory, stack, instruction-file and component facts, no verdicts | Live |
| [`recipe_lint.py`](#recipe_lintpy) | Checks recipe Markdown for broken links, bad SKILL.md frontmatter, oversize files, missing tools, unknown check, requirement or playbook IDs, and a stale tool catalogue | Live |
| [`build_skills.py`](#build_skillspy) | Builds the agentic-readiness-audit skill bundle under `dist/skills/` | Live |
| [`progress.py`](#progresspy) | Creates, shows and renders the implement recipe's per-repository state; the only tool that writes inside a target | Live |
| [`check_drift.py`](#check_driftpy) | Lists the audit findings whose cited files changed between the audited commit and `HEAD` | Live |

## Every tool

Every tool follows the [tool contract](../../tools/README.md#the-contract): one JSON envelope on stdout, the exit codes below, `--describe`, bounded output, no network, no writes inside the target (`progress.py` writes the target's two state files, the one exception), and a Python 3.11 check first. The explanation is in [Tool Contract](../architecture/contributor-deep-dive/01-tool-contract.md).

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
                                           [--emit-baseline]
python3 brownfield-recipes/tools/engine.py --list-checks
python3 brownfield-recipes/tools/engine.py --describe
```

**Inputs**

| Argument | Meaning |
|---|---|
| `<target>` | The repository to scan. It must exist and be a directory. The engine only reads it. |
| `--out-dir DIR` | Where the report goes. It is created if it does not exist, and it must be outside the target. Default: the current directory, which is refused when it is inside the target. |
| `--repo-label LABEL` | The label in the file name: up to 32 of `a` to `z`, `0` to `9`, dot, underscore and hyphen, starting with a letter or digit. Default: derived from the target's directory name, as in [Output files](../../schema/SCHEMA.md#output-files). |
| `--phase N` | The phase recorded in the report's provenance. The engine implements phase 1 only, so a higher value changes nothing else; the engine's default is 1. |
| `--exclude GLOB` | An extra path pattern to leave out of the audit, matched against the whole path from the target's root, so `vendor-samples/*` covers every file under that directory. It applies to the checks that read git's tracked files as well as to the walk. May be repeated. |
| `--max-files N` | A hard cap on the files the engine inspects. |
| `--run-gates`, `--allow-probe VERB`, `--timeout SECONDS` | Let the engine run the target's own commands. Nothing runs unless `--run-gates` is given and every verb is named in an `--allow-probe`. `--timeout` is the limit per command. |
| `--emit-baseline` | Forwarded to the engine's own `--emit-baseline` (D51): also writes `do-not-do.draft.md` beside the report, the CON-04 remediation draft. |
| `--list-checks` | Print the engine's checks and exit. It takes no other argument. |

The engine's `--force`, `--out`, `--format`, `--fail-on` and `--baseline` are not offered, and abbreviations of the options above are refused.

**Outputs**

A scan writes one file, `<label>.engine-report.<stamp>.json`, in the output directory, and, with `--emit-baseline`, `do-not-do.draft.md` beside it. Both are the engine's own output, untouched. The envelope's `data` is:

| Key | Meaning |
|---|---|
| `report` | The path of the file written. |
| `label`, `stamp` | The two parts of the name. The stamp is the UTC launch time as `YYYYMMDDTHHMMSSZ`. |
| `target` | The target's resolved path. |
| `baseline_draft` | The draft's path, when `--emit-baseline` was given; `null` otherwise. |
| `engine` | `version` and `ruleset_revision` of the engine that ran. |

`--list-checks` writes nothing. Its `data` holds `engine` (name, version, ruleset revision and hash), `checks` (the engine's list, one entry per check) and `omitted`, the number of checks left out to stay within the output budget, which is `0` today.

**Exit codes**

| Code | When |
|---|---|
| `0` | The report was written, or the checks were listed. |
| `1` | A bad argument, a move the state diagram or the owner-only rules refuse, an unknown or rejected finding, a missing target, an output directory inside the target, a bad label, or a refusal by the engine, whose reason is in `data.error`. |
| `3` | The engine exited with any other code, raised, or reported success without writing the report or (with `--emit-baseline`) the draft. |

**Errors**

| Message | Fix |
|---|---|
| `refusing to write inside the target` | Pass `--out-dir` with a directory outside the repository, or run from outside it. |
| `the engine refused the run: --run-gates requires at least one --allow-probe VERB` | Name each verb the engine may run with `--allow-probe`. |
| `the engine refused the run: ... exists; nothing was replaced, run the tool again` | Another run took the report's name in the same second, or `do-not-do.draft.md` already exists in `--out-dir` from an earlier `--emit-baseline` run. Run the tool again, or point `--out-dir` elsewhere. |
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

The subcommands are `init`, `import-engine`, `add-check`, `add-finding`, `set-disposition`, `status` and `finalise`.

Every subcommand but `init` and `status` changes the draft it is given, in place. A change is one step: the draft is read and validated, the change is made, the summary is recomputed, the result is validated, and only then is it written, atomically, so a crash or a refusal leaves the previous draft as it was. Commands that change drafts in one folder take turns, through a lock on the folder that the system releases when the process ends; run them one at a time anyway, because a command that cannot get the lock in 30 seconds exits with 1. A final report is never changed.

**Synopsis**

```text
python3 brownfield-recipes/tools/report.py init <intake>
python3 brownfield-recipes/tools/report.py import-engine <draft> <engine report>
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

The draft starts with no checks, no findings and a summary computed from them. The scan facts (`stack`, `components`) and the engine's checks arrive with [`import-engine`](#import-engine).

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

### import-engine

Brings the engine's report into a draft: its checks and findings, the stack and components it detected, its file counts, the probes it ran and its unattested items. The report is the JSON that [`engine.py`](#enginepy) wrote. The rules of the conversion are in [Engine schema v2 mapping](../../schema/SCHEMA.md#engine-schema-v2-mapping). The conversion is [`convert`](../../tools/_engine_adapter.py#L726-L739), a pure function of the engine's report, and [`apply_import`](../../tools/report.py#L585-L645) applies its result to the draft in one validated step, as every other change is applied.

```text
python3 brownfield-recipes/tools/report.py import-engine <draft> <engine report>
```

It runs once for a draft. A draft that already holds an engine report is refused, because a second import would replace the first one's checks and the decisions made on them: start a new draft with `init` to audit again. It also runs for the draft's own repository only: the engine report's `target` must be the draft's target, and its commit the draft's commit when both are known, otherwise the report is refused. The draft's own target facts are kept, because `init` read them from the directory.

**Inputs**

| Argument | Meaning |
|---|---|
| `<draft>` | The draft to change. A final report is refused. |
| `<engine report>` | The engine's JSON report, schema v2 and phase 1, as `engine.py` wrote it: a file of at most 32 MiB. It is only read. |

**What it records**

| In the draft | From the engine's report |
|---|---|
| `provenance.engine` | The engine's name, version, ruleset revision and hash, and the scan time. |
| `checks[]` | Each engine check with `method: automated` and the engine's verdict in both `verdict` and `engine_verdict`, after any check the agent has already recorded. A check the engine left out as not applicable has the verdict `NOT_APPLICABLE`. |
| `checks[].evidence` | The evidence of the check's findings, gathered, then the probes the engine ran for it, as `command` evidence. |
| `findings[]` | Each engine finding, with a `key` (the engine's id, and `:2`, `:3` after a repeat) and an `id` one past the highest in use. It is `pending`, or `confirmed` by policy under `accept-all`. |
| `unattested[]` | The engine's five fixed items as the requirements they stand for, in the engine's words, and each requirement of a check the engine marks `ATTEST`. |
| `stack`, `components`, `coverage.inventory` | The engine's own. A path that looks like a component and that nothing declares is a component with `declared: false`. |

An engine evidence path is not always a path. A placeholder (`(no example file)`, `<repository>`) names no file and is dropped. A path outside the repository (the index store that `IDX-02` cites) is dropped with a warning. `package.json:lint` becomes the file `package.json` with the note `lint`, and the note does not say what it means, because the engine writes that form for a key that is set and for one that is not. [`locate`](../../tools/_engine_adapter.py#L249-L274) holds the rules.

**Outputs**

`data` holds `draft`, `engine_report` (the path read), `engine` (what was recorded in `provenance.engine`), `checks_imported`, `by_verdict` (a count for each verdict, including `NOT_APPLICABLE`), `findings_imported`, `unattested_listed`, `probes_carried`, `evidence_not_carried` (evidence items dropped with a warning), and the counts `checks_recorded`, `checks_expected`, `findings` and `findings_pending` of the draft as it now is. When the warnings are too many for the envelope, `warnings_omitted` says how many were left out and `truncated` is true.

Nothing the engine said is dropped without a warning, except a placeholder and a probe the engine refused to run (the check's own summary says why).

| Warning | Meaning |
|---|---|
| `<ID>: the evidence path 'P' is not carried: the path is absolute, so it is outside the repository` | The engine cited a place outside the repository. The finding's statement says where the engine looked. |
| `<ID>: the <field> is N characters and the report allows M, so it was cut` | A text over the report schema's limit was cut, and ends in `…`. |
| `<ID>: N evidence items, and the report allows M, so the rest are left out` | A list over its limit kept its first items. |
| `probe <verb>: ...` | A probe that ran has no known check, no command, or output over the limit. A probe whose check the report does not hold says `probe: <ID> ran it, and the report holds no such check`. |
| `the engine's scan was cut short, so what it did not reach is not in the report` | The engine's `inventory.truncated` is true. |
| `the engine's phase-1 score is X and the report's is Y; ...` | The score the engine computed and the score the report computes from its checks differ. The report's is kept. |
| `only the engine knows the target's commit, so the draft's cannot be compared` | One side recorded no commit, so the two could not be compared. The message says which side has one. |
| `the engine lists the unattested item 'X', which maps to no requirement, so it is not carried` | The engine lists an item the adapter has no requirement for. |
| `/checks/N/evidence/M: the file P is not in the target at C` | The validator's rule 12, for the imported checks, when the target is on this machine. |

**Exit codes**

| Code | When |
|---|---|
| `0` | The engine's report was imported. |
| `1` | A bad argument; the draft or the engine report is missing, a directory or too large; the draft is a final report; the draft's folder is inside the target; the lock could not be taken; the file could not be written. |
| `2` | The engine report is not valid JSON, is not schema v2 for phase 1, lacks a field the mapping reads, holds a check the catalogue lacks or only an agent can judge, or is of another repository or commit than the draft's; the draft already holds an engine report; the draft was already invalid; or the change would leave it invalid (`data.errors` has the rule). Nothing is written. |
| `3` | Internal error. |

**Errors**

| Message | Fix |
|---|---|
| `the engine report has schema_version X, and the adapter reads only '2'` | Scan again with [`engine.py`](#enginepy). |
| `the engine report is for phase N, and a 0.1 report covers phase 1` | Scan again without `--phase`. |
| `the engine report has the wrong shape: N errors` | Each error starts `engine report: /pointer:` and names the field. The file is not an engine report, or was edited. |
| `the engine report cannot be imported: N problems` | A check is not in [`catalogue.json`](../../catalogue.json), or only an agent can judge it, or appears twice, or a finding names a check the report does not hold. The engine and the catalogue are from different revisions of the framework. |
| `the engine report is not of this draft's target` | `data.errors` names both directories, or both commits. Scan the draft's own repository at its commit, or start a new draft with `init`. |
| `this draft already holds an engine report (ruleset H)` | Start a new draft with `init`. |
| `the draft already records X` | The draft holds a check the engine reports. Start a new draft. |
| `the change would leave the draft invalid, so nothing was written` | `data.errors` names the rule and the place, for example an engine finding more severe than its check (rule 7). |

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

**A check only the engine can run.** `add-check` cannot add an `automated` check, whose verdict comes from the engine (the checks arrive with [`import-engine`](#import-engine)). It can dispute one the engine already ran: the engine's verdict stays in `engine_verdict`, with the engine's evidence and `data`, and the agent's `verdict`, `summary`, `override_reason` and agent-captured evidence are recorded beside them. A dispute needs an `override_reason` and at least one evidence item (rule 6). Disputing the same check again replaces the agent's earlier evidence. A fragment whose verdict equals the engine's clears an earlier dispute (and has no `override_reason`). A check whose finding is still `pending` cannot be disputed to `PASS`: reject the finding first (rule 7).

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
| `checks not recorded in <FAMILY>: ...` | Record each check: `add-check` for an agent check, [`import-engine`](#import-engine) for the engine's. |
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
| Title and banners | The repository's name. A warning banner for an evaluation run, a note banner for a draft that counts the findings awaiting a decision, and a note that the audit reports and does not gate. |
| Provenance | A field and value table, straight after the title: the target, the commit (a bold flag for a dirty working tree), the status, when the audit started and finished, the recipe and catalogue, the engine and ruleset, the framework revision, the agent (self-reported) and the probes. |
| Readiness summary | The headline of [`spec/readiness-summary.md`](../../../spec/readiness-summary.md) and no other number: the phase-1 score to two places, the blockers remaining by state, and the unattested requirements, then the two qualifiers. |
| Checks by verdict and severity | How many checks have each verdict and what each earns, and for each severity its weight, its scored checks and how many are not met. |
| Checks that need attention | A table for each severity, with the columns Check, Verdict, What we found, Evidence, Fix and Decision. A row is a finding, or a check that has none. A check is listed when it is not met, was overridden, was judged by the agent, or raised a finding. |
| Overrides of the engine's verdicts | Each check whose verdict differs from the engine's, with both verdicts and the reason. |
| Evidence in full | Each quote and each command's output, in a fenced block, under the check that cites it. Left out when nothing is quoted. |
| Coverage, Stack and components, Run context | What the audit examined and skipped, what was detected, and the intake answers the run used. |
| Appendix — all checks | Every check, grouped by family: its severity, method, whether it is scored, its verdict, the engine's verdict and its summary. |

In the tables of checks that need attention, evidence is grouped by who captured it, so each item says whether a tool or the agent recorded it, and a tool is named only when it is not the engine that the provenance names. A cell shows at most eight items for each group and counts the rest, which are in the JSON report. A quote or output is not in a cell: the cell says where it is. A check that is `FAIL` or `UNKNOWN` and shows no evidence and no search, on the check or on any of its findings, has "We did not find any evidence." in its Evidence cell. A later finding of a check whose fix is the same as an earlier one's says "Same as" and the finding, instead of printing it again. A passing check that a tool settled is in the appendix and nowhere else, and the engine's structured payloads are in the JSON report.

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

---

## facts.py

Describes a repository with counts and names and no verdicts, in a file the audit recipe reads before its assessment stage: inventory, stack, instruction files, components and a size class, taken with the engine's own `scan`, `stack`, `components`, `target` and `rules/variants` modules by [ADR 0001](../architecture/adrs/0001-tools-import-engine.md). It gives no verdict, and nothing in it says that a file is good, that a stack is right or that a repository is ready. The source is [`facts.py`](../../tools/facts.py); the format is [`facts.schema.json`](../../schema/facts.schema.json), described in [Facts file](../../schema/SCHEMA.md#facts-file).

**Synopsis**

```text
python3 brownfield-recipes/tools/facts.py <target> --out FILE [--repo-label LABEL] [--exclude GLOB]... [--max-files N]
python3 brownfield-recipes/tools/facts.py --describe
```

**Inputs**

| Argument | Meaning |
|---|---|
| `<target>` | The repository to describe. It must exist and be a directory. The tool only reads it. |
| `--out FILE` | The file to create. It must not exist, its folder must, and the folder must be outside the target. The tool never replaces a file. |
| `--repo-label LABEL` | The label in the file: up to 32 of `a` to `z`, `0` to `9`, dot, underscore and hyphen, starting with a letter or digit. Default: derived from the target's directory name, as in [Output files](../../schema/SCHEMA.md#output-files). |
| `--exclude GLOB` | An extra path pattern to leave out of the inventory, spelled as `engine.py`'s is, so the facts describe the inventory the engine sees. Up to 10 are named in the file; the rest still apply. May be repeated. |
| `--max-files N` | A cap on the files the walk inspects. Default: the engine's own cap. A walk the cap stops is `truncated`, which pushes the size class to `huge` whatever the count. |

**Outputs**

A run writes one file, the one `--out` names, in `facts.schema.json`'s format: `facts_version`, `label`, `git` (`sha`, `dirty`), `inventory`, `stack`, `instruction_files`, `components`, `size` and `caps`, every section required. The file holds no time, no absolute path and no machine or user name, so one repository state gives one file. `data` holds `file` (the path written), `bytes` and `facts_version`. A walk `--max-files` cut short gives a warning, and every count in the file is then a lower bound.

**Exit codes**

| Code | When |
|---|---|
| `0` | The file was written. |
| `1` | A bad argument, a missing or non-directory target, a filesystem root, a bad `--out` or label, or a write the system refused. |
| `3` | The facts do not fit `facts.schema.json`, or are over the 30 KB bound: a bug in this tool. Nothing is written. |

**Errors**

| Message | Fix |
|---|---|
| `target not found: ...`, `target is not a directory: ...`, `refusing to scan a filesystem root` | Point `<target>` at an existing repository directory. |
| `the folder for --out does not exist: ...` | Create the folder, or choose one that exists. |
| `refusing to write inside the target: ...` | Choose a folder outside the audited repository. |
| `<path> already exists, and a tool never replaces a file` | Choose another `--out`. To refresh a golden file on purpose, delete it first and read the diff. |
| `cannot write <path>: <reason>` | The system's reason, such as a full disk or a missing permission. |
| `repo_label ... is not allowed` | Use a label that matches the pattern above. |
| `--max-files must be at least 1, not ...` | Pass a whole number of at least 1. |
| `the facts do not fit facts.schema.json, which is a bug in the tool` | Report it; `data.errors` names each place. Nothing written. |

## recipe_lint.py

Checks the Markdown under `brownfield-recipes/` so that a recipe does not silently rot: every relative link and anchor resolves, a `SKILL.md`'s frontmatter is valid, a `SKILL.md` or a check-family file (`audit/checks/NN-*.md`) stays inside its 500-line budget (R-10), every `brownfield-recipes/tools/<name>.py` the Markdown names exists and answers `--describe`, every check, requirement and playbook ID named is one `catalogue.json` or `spec/readiness-requirements.md` actually has, and the generated [`tools/CATALOGUE.md`](../../tools/CATALOGUE.md) matches what every tool's own `--describe` would produce today. It reads only, apart from running each tool's own `--describe`, which the contract guarantees does no work; nothing is written, unless `--write-catalogue` is given. The source is [`recipe_lint.py`](../../tools/recipe_lint.py).

**Synopsis**

```text
python3 brownfield-recipes/tools/recipe_lint.py <root>
python3 brownfield-recipes/tools/recipe_lint.py <root> --write-catalogue
```

**Inputs**

| Argument | Meaning |
|---|---|
| `<root>` | The repository that holds `brownfield-recipes/`. It must exist and be a directory. A link may resolve anywhere under it, even outside `brownfield-recipes/` (a check file citing `brownfield-legacy/Phased-Approach.md` does); a link that resolves outside `<root>` is an error. |
| `--write-catalogue` | Regenerate `brownfield-recipes/tools/CATALOGUE.md` from every tool's own `--describe` output and exit; none of the other rules run in this mode. |

**Outputs**

Nothing is written by a plain `recipe_lint.py <root>`; a clean run's `data` holds `root` and `files`, the count of Markdown files checked. `--write-catalogue` atomically replaces `brownfield-recipes/tools/CATALOGUE.md` (the second documented exception to "a tool never replaces a file", alongside the draft report; `tools/README.md` rule 7) and its `data` holds `file`, `bytes` and `tools`, the count of tools described.

**Exit codes**

| Code | When |
|---|---|
| `0` | Every file is clean, or (with `--write-catalogue`) the catalogue was written. |
| `1` | A bad argument, or `<root>` has no `brownfield-recipes/` directory. |
| `2` | A link does not resolve, an anchor matches nothing, a `SKILL.md`'s frontmatter is invalid, a file is over its line budget, a named tool is missing or fails `--describe`, a named check, requirement or playbook ID does not exist, or `tools/CATALOGUE.md` is missing, stale or could not be generated. `data.errors` lists every one; the markdown rules give `path:line: message`. |

**Errors**

| Message | Fix |
|---|---|
| `<root> has no brownfield-recipes/ directory` | Point `<root>` at the repository root, not at `brownfield-recipes/` itself. |
| `the link '...' does not resolve: no such file or directory` | Fix the path, or remove the link. A placeholder link under `docs/templates/` is exempt. |
| `the link '...' leaves <root>` | A relative link climbed out of the repository; point it at a path inside `<root>`. |
| `the anchor #... in '...' matches no heading` | The target file's heading changed, or the anchor was typed wrong; GitHub's slug is lower case with one hyphen per removed space. |
| `'...': the anchor #... is out of range` | A `#L<n>-L<n>` line-range anchor outgrew the file it points at; update the range. |
| `a SKILL.md must open with '---' frontmatter and a closing '---'` | Add the frontmatter block. |
| `name '...' must be lowercase letters, digits and hyphens, at most 64 characters` | Fix `name` to match the pattern. |
| `name '...' must match its folder, '...'` | Rename `name` or the folder so they agree. |
| `description is N characters; at most 1024 are allowed` | Shorten `description`. |
| `<file> has N lines; the budget is 500` | Split the file, or move content on demand into a file it links to. |
| `the tool brownfield-recipes/tools/<name>.py does not exist` | Fix the name, or write the tool; mark the line `TBD:` if it is only planned. |
| `brownfield-recipes/tools/<name>.py --describe exited N: ...` | `--describe` must not run any work; fix the tool so it only prints its manifest. |
| `brownfield-recipes/tools/<name>.py --describe did not finish within Ns` | The tool hung or is slow; fix it, or raise the budget in `recipe_lint.py`. |
| `brownfield-recipes/tools/<name>.py --describe printed no valid JSON envelope on stdout` | The tool wrote something other than the envelope to stdout. |
| `brownfield-recipes/tools/<name>.py --describe printed ok: False` | `--describe` must always succeed; fix the tool. |
| `the check '...' is not in catalogue.json` | Fix the ID, or add the check to `catalogue.json`. Never checked inside `deterministic-audit/`, which has its own registry. |
| `the requirement '...' is not in spec/readiness-requirements.md` | Fix the ID, or add the requirement to the spec. |
| `the catalogue names no playbook '...'` | Fix the name, or add it to a check's `playbooks` in `catalogue.json`; the file under `implement/playbooks/` may not exist yet (`schema/SCHEMA.md`, rule 2). |
| `brownfield-recipes/tools/CATALOGUE.md is missing; regenerate it with 'recipe_lint.py <root> --write-catalogue'` | Run `--write-catalogue` and commit the result. |
| `brownfield-recipes/tools/CATALOGUE.md is stale; regenerate it with 'recipe_lint.py <root> --write-catalogue'` | A tool's manifest changed since the file was last generated; run `--write-catalogue` and commit the result. |
| `N tool(s) could not be described` (with `--write-catalogue`) | Fix the tool named in each error so `--describe` succeeds, then try again; nothing is written while any tool fails. |

---

## build_skills.py

Builds the `agentic-readiness-audit` skill bundle: a self-contained copy of the audit recipe, under
`dist/skills/` (gitignored), that a harness installs and runs with no checkout of this repository. The
bundle has three parts — `SKILL.md` (the recipe's own file, with its frontmatter `name` rewritten from
`audit`, the source folder's name, to the bundle's own name), `references/` (the check files, stack profiles
and schema docs, read by the model) and `scripts/` (the tools the recipe calls, the schema files and
`catalogue.json` they read at a fixed path next to themselves, the engine's `audit` package mirroring the one
folder level `engine.py` expects, and `audit.pyz`, the engine's single-file build). It is replaced whole on
every run, so a stale file from an earlier build can never survive. The source is
[`build_skills.py`](../../tools/build_skills.py). `make validate-skills` builds the bundle and validates it
with [`skills-ref`](https://agentskills.io/specification#validation), the Agent Skills specification's own
reference validator (PyPI package `skills-ref`, CLI entry point `agentskills`; a dev-only tool, run through
`uvx` and pinned in the Makefile, never imported by the tools or the engine). An install smoke-run (S4.5.3)
acts on the bundle too; some of `SKILL.md`'s own links point outside what the bundle carries (found, not
fixed, by this tool — see its own module docstring; confirmed not something `skills-ref` itself checks, since
it validates only the frontmatter and the directory-name match), which the smoke run may need to account for.

**Synopsis**

```text
python3 brownfield-recipes/tools/build_skills.py [--out-dir DIR]
```

**Inputs**

| Argument | Meaning |
|---|---|
| `--out-dir` | Where to build `skills/` itself (default: `brownfield-recipes/dist/skills`). The bundle always lands at `<out-dir>/agentic-readiness-audit/`. |

**Outputs**

`data` holds `bundle`, the bundle's path, and `files`, how many files it has.

**Exit codes**

| Code | When |
|---|---|
| `0` | The bundle was built. |
| `1` | The engine's own `deterministic-audit/tools/build.py` failed to produce `audit.pyz`; `data.errors` carries its stderr. |

## progress.py

Creates the implement recipe's state for a target from a final audit report, summarises it, renders its
Markdown view, and applies the validated changes to it: status transitions, skip and defer, preferences and
theme progress. It is the one tool that writes inside a target, and only the two state files, by
[ADR 0002](../architecture/adrs/0002-progress-writes-state-in-target.md). The source is
[`progress.py`](../../tools/progress.py); the format is
[`readiness-state.schema.json`](../../schema/readiness-state.schema.json), described in
[Readiness state](../../schema/SCHEMA.md#readiness-state); the rules are the [state contract](../../implement/state.md).

**Synopsis**

```text
python3 brownfield-recipes/tools/progress.py init --report REPORT --target REPO [--default-branch BRANCH] [--phase PHASE] [--date YYYY-MM-DD] [--framework-rev SHA]
python3 brownfield-recipes/tools/progress.py show --target REPO [--label LABEL] [--json]
python3 brownfield-recipes/tools/progress.py render --target REPO [--label LABEL]
python3 brownfield-recipes/tools/progress.py set-status FINDING STATUS --target REPO --phase PHASE [--commit SHA] [--verification-command CMD --verification-result TEXT] [--debt what=TEXT,count=N[,baseline=FILE]] [--clear-debt] [--reason TEXT] [--note TEXT] [--by owner|agent] [--date YYYY-MM-DD] [--label LABEL] [--render]
python3 brownfield-recipes/tools/progress.py skip|defer FINDING --reason TEXT --by owner --target REPO --phase PHASE [--render]
python3 brownfield-recipes/tools/progress.py unskip|undefer FINDING --by owner --target REPO --phase PHASE [--reason TEXT] [--render]
python3 brownfield-recipes/tools/progress.py pref set KEY VALUE --reason TEXT --by owner --target REPO --phase PHASE [--render]
python3 brownfield-recipes/tools/progress.py pref unset KEY --reason TEXT --by owner --target REPO --phase PHASE [--render]
python3 brownfield-recipes/tools/progress.py theme THEME --status branch_open|pr_open|merged [--branch B] [--pr N] [--merged-sha SHA] --target REPO --phase PHASE [--render]
python3 brownfield-recipes/tools/progress.py --describe
```

**Inputs**

| Argument | Meaning |
|---|---|
| `--report` | `init`: the final audit report (JSON). It must be inside the target, so the state can point at it, and `validate_report.py` must accept it. |
| `--target` | The repository. The state is `docs/agentic-readiness/<label>-agentic-readiness-state.json` in it, and its view `<label>-agentic-readiness-STATE.md`. |
| `--default-branch` | `init`: the branch the theme PRs go into. Default: the report's `provenance.target.branch`, else `main`. |
| `--phase` | `init`: the step recorded in the first log entry. Default: `init`. |
| `--date` | `init`: the date recorded on the items and the log, `YYYY-MM-DD`. Default: today, UTC. |
| `--framework-rev` | `init`: the framework commit to record. Default: `git rev-parse HEAD` of the framework checkout, or null. |
| `--label` | Every command but `init`: which state to use when the folder holds more than one. |
| `FINDING STATUS` | `set-status`: the item and the status to move it to. The move must be in the state diagram of the [state contract](../../implement/state.md#item-statuses). `skipped`, `deferred` and the moves back out of them have their own commands. |
| `--commit` | `set-status`: a commit SHA to add to the item (repeatable). |
| `--verification-command`, `--verification-result` | `set-status`: the verification and what it gave; given together. `done` needs one. |
| `--debt`, `--clear-debt` | `set-status`: record debt (repeatable; same `what` replaces) or drop it. `partial` needs debt; `done` needs none. |
| `--reason` | The reason. Required by `failed`, `blocked`, `skip`, `defer` and `pref`. |
| `--note` | `set-status`: text appended to the item's notes. |
| `--by` | Who decided, `owner` or `agent` (default `agent`). `skip`, `unskip`, `defer`, `undefer` and `pref` refuse anything but `owner`: the agent relays the owner's answer; the tool cannot see who is typing. |
| `--phase` | Every write: the step recorded in the log entry and on the item or preference. |
| `--render` | Every write: also replace the Markdown view. Without it the tool warns that the view is out of date. |
| `--status`, `--branch`, `--pr`, `--merged-sha` | `theme`: the theme's new status (it only moves forward) and the data that status needs: a branch, then a PR, then the merge SHA. |
| `--json` | `show`: print the state itself instead of the summary. Long lists are cut to fit the output and `truncated` is set; the log keeps its newest entries. |

**Outputs**

`init` writes the JSON and the Markdown and puts their paths, the label, the item count, the count per status and
the `not_queued` count in `data`. `show` puts the summary in `data`: counts per status and per theme (`items` and
`open`, which is neither `done` nor `skipped`), the skipped finding ids, and the number of preferences, debt
entries and log entries. `show --json` puts the state under `data.state`. `render` writes the Markdown and puts
its path and size in `data`. Every other command checks the changed state whole, appends one log entry, replaces
the JSON and puts the path and the count per status in `data`. A refused command changes nothing. Each write is atomic; a temporary file a killed write left behind is removed, with a
warning.

**Exit codes**

| Code | When |
|---|---|
| `0` | Done. |
| `1` | A bad argument, a missing report or target, a report outside the target, an existing state for `init`, no state for `show` or `render`, a state folder that leaves the target, or a state file that is a symlink. |
| `2` | The report is invalid, not final, or has a finding on a check with no theme; or the state fails the schema or its rules. `data.errors` lists what to fix. |
| `3` | Internal error, including a write the system refused. The old file is left whole. |

**Errors**

| Message | Fix |
|---|---|
| `the report is a draft, not final` | Finalise it with `report.py finalise` and pass the final report. |
| `the report must be inside the target, so the state can point at it` | Commit the report folder to the target and pass that path. |
| `a state already exists: ...; init never replaces one` | Use `show`, `render` and the transition commands. |
| `F-nnn is done and done is final` | A regression is a new finding in the next audit. |
| `F-nnn is skipped and only the owner can bring it back` | Ask the owner, then `unskip --by owner`. |
| `F-nnn is queued and must be in_progress before it can be ...` | Move it to `in_progress` first. |
| `F-nnn: ... has its own command` | Use `skip`, `defer`, `unskip` or `undefer` with `--by owner`. |
| `... is an owner decision` | Ask the owner and pass `--by owner`. |
| `F-nnn cannot be done without a verification` / `... still has N debt entries` / `... cannot be partial without debt` | Give the verification, use `partial`, or record the debt. |
| `theme Tn is ... and a theme only moves forward` | Themes go `not_started`, `branch_open`, `pr_open`, `merged`. |
| `the report has findings on checks with no theme: ...` | Add the checks to `THEMES` in `progress.py`. |
| `no state in ...` | Run `init` first. |
| `N states in ...; pick one with --label` | Pass `--label`. |
| `the state is not valid: N errors` | Fix each entry in `data.errors`; `schema:` errors come from the schema, `rule:` errors from the rules above. |
| `refusing a state file that is a symlink` | Replace the link with the real file. |

## check_drift.py

Tells which audit findings the target has moved under since the audit. It reads the report's
`provenance.target.git_sha`, compares it with `HEAD` of the target using read-only git, and lists the paths that
changed and the findings whose cited `file` evidence or `remediation.touches` intersect them. A changed path
matches a cited path when they are equal or the changed path is below a cited directory. It judges nothing: a
listed finding is one to re-check before acting on the report's text. It writes nothing. The source is
[`check_drift.py`](../../tools/check_drift.py).

**Synopsis**

```text
python3 brownfield-recipes/tools/check_drift.py REPORT REPO [--json]
python3 brownfield-recipes/tools/check_drift.py --describe
```

`--json` is accepted for symmetry; the output is always the JSON envelope.

**Output**

`data.status` is one of:

| Status | Meaning |
|---|---|
| `current` | `HEAD` is the audited commit. |
| `drifted` | `HEAD` differs. `changed_count`, `changed_paths` and `findings` (each with `id`, `check`, `changed_paths`) are set, and `drifted` is `true`. |
| `sha_missing` | The audited commit is not in the target's history (rewritten or not fetched). Nothing is compared; a warning says to re-check every finding. |
| `no_sha` | The report recorded no `git_sha`. A warning says to re-check every finding. |

`audited_sha` and `head_sha` are always present. When the audited commit is not an ancestor of `HEAD`, the diff is
between the two trees and a warning says so. Long lists are bounded: `changed_paths_omitted` and
`findings_omitted` count what was left out, and `truncated` is `true`.

**Exit codes**

| Code | When |
|---|---|
| `0` | Done, whatever the status. Read `data.status`. |
| `1` | A bad argument, a missing report or target, or a target that is not a git repository. |
| `2` | The report is not valid; `data.errors` lists what to fix. |
| `3` | Internal error. |
