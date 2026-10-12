# Audit Report and Intake Schema Reference

> **Audience:** Everyone who reads, writes or validates an audit report
> **Source of truth:** [`audit-report.schema.json`](audit-report.schema.json) and [`audit-intake.schema.json`](audit-intake.schema.json). Where this page and a schema disagree, the schema wins and this page has a defect.
> **Status:** Live for the schemas, the examples, the validator, the report builder, with its `import-engine` subcommand (the engine adapter), and the renderer. The facts schema and its example are live; the tool that writes the file, [`facts.py`](../tools/facts.py), is in development.

---

## Summary

| Item | Description |
|---|---|
| [`audit-report.schema.json`](audit-report.schema.json) | The canonical result of an audit. JSON Schema 2020-12, `schema_version` `0.1`. |
| [`audit-intake.schema.json`](audit-intake.schema.json) | The answers to the audit's Stage 0 questions, given in a file. `intake_version` `0.1`. |
| [`catalogue.schema.json`](catalogue.schema.json) | The check catalogue, [`../catalogue.json`](../catalogue.json): every check in one ID namespace. |
| [`facts.schema.json`](facts.schema.json) | The file `facts.py` writes: counts and names that describe a repository, with no verdict. `facts_version` `0.1`. See [Facts file](#facts-file). |
| [`examples/minimal.json`](examples/minimal.json) | The smallest valid report: one agent check, no findings. |
| [`examples/facts.minimal.json`](examples/facts.minimal.json) | A valid facts file for a small made-up service. |
| [`examples/realistic/`](examples/realistic/) | The engine's real reports on three open-source repositories, each beside its conversion: `agentic-tdd`, `Digital-Assistant-SDK` and `Digital-Assistant-Server`. They were scanned on 2026-10-10 at the commits named in each report's `provenance.target`, with the engine at ruleset revision `2026-09-28.13`. A `*.engine-report.*.json` file is the engine's output, untouched. A `*.audit-draft.*.json` file is that report converted by the mapping below and nothing else: all 69 checks, every finding pending, no name anonymised and nothing invented, because the repositories are open source. In all three the recomputed phase-1 score equals the engine's (0.7311, 0.6513 and 0.4244). Each pair is the input and the expected output of the engine adapter: a test imports each raw report into a draft made from the golden draft's own `init` fields and requires the draft beside it, byte for byte. When the mapping changes, the drafts are regenerated from the raw reports and the raw reports are left alone. |
| [`examples/example-service.audit-report.20261010T094207Z.json`](examples/example-service.audit-report.20261010T094207Z.json) | A synthetic worked example of a finished report on a made-up service. It shows an override of the engine's verdict, an agent check with evidence, an agent `FAIL` that found nothing and says so, a dependency between findings, a finding less severe than its check, and confirmed, edited, rejected and deferred dispositions. It is documentation, not a measured result, and the ID of its agent-only checks, `AGT-11` and `CI-04`, is provisional until the check catalogue exists (S1.5). |
| [`examples/audit-intake.example-service.json`](examples/audit-intake.example-service.json) | A valid intake file. |
| [`examples/minimal.md`](examples/minimal.md) and [`examples/example-service.audit-report.20261010T094207Z.md`](examples/example-service.audit-report.20261010T094207Z.md) | What `render_report.py` writes for `minimal.json` and for the worked example, each beside its JSON under the same name. They are the golden files that the renderer's tests compare its output with, and the way to see what a finished report looks like. |

The Markdown report, which [`tools/render_report.py`](../tools/render_report.py) writes, is a pure function of the JSON report: nothing the Markdown shows is absent from the JSON. Editorial wording, such as what a verdict means, lives in the renderer and never in the JSON, as in the engine's [ADR-0007](../deterministic-audit/docs/architecture/adrs/0007-json-report-render-contract.md).

---

## Versioning

| Version | Where | Meaning |
|---|---|---|
| `schema_version` | the report | The shape of the report. `0.1` today. |
| `intake_version` | the intake file | The shape of the intake file. `0.1` today. |
| `facts_version` | the facts file | The shape of the facts file. `0.1` today. |
| `catalogue_version` | `provenance` | The check catalogue the report was built against, `MAJOR.MINOR.PATCH`, as in [`catalogue.json`](../catalogue.json). The bump rules are in [`catalogue.schema.json`](catalogue.schema.json). |
| `provenance.recipe.version` | `provenance` | The audit recipe that produced the report. |
| `provenance.engine.version`, `ruleset_hash` | `provenance` | The deterministic engine and its ruleset. |

Policy:

- A `0.x` schema may break between releases. The version is `1.0` once the audit recipe and the implementation recipe have both run end to end on two repositories. Until then nothing may rely on a field staying put.
- A consumer refuses a `schema_version` it does not know. It never guesses.
- A schema change that adds a field is a new `0.x`. So is every change to a field's meaning, even where the field name stays. `0.1` itself stays open until the first tool that reads it ships (S2.2), so edits before then do not bump the version.
- The schemas, the check catalogue, the check rubrics and the tools are one shared layer. A report records `catalogue_version` so that a later run can warn when its catalogue differs.

---

## Shape

```text
report
├── schema_version, status
├── provenance       recipe, framework_revision, catalogue_version, engine?, agent, target (label, path, …), started_at, finalised_at?
├── run_context      eval_mode, confirmation_policy, provider_exposure_acknowledged, index, probes, excluded, known_components, stack_profile?
├── stack            ecosystems, package_managers, ci_providers, test_frameworks, hook_managers, notes?
├── components[]     name, path, declared, declared_by?, manifest?, agents_md?
├── checks[]         one per check evaluated, passes included
│   ├── id, title, phase, severity, scored, method, verdict, summary
│   ├── engine_verdict?, override_reason?, confidence?
│   ├── evidence[], searches[]
│   └── data?        an engine payload, carried unchanged
├── findings[]       one per issue a check raised
│   ├── id, key, check, severity, statement
│   ├── evidence[], searches[], remediation
│   └── disposition, disposition_note?, confirmed_via?
├── summary          phase1_score, scored_checks, blockers_remaining, unknown_scored_checks, unconfirmed_agent_findings
├── unattested[]     requirement, method, property?, why
└── coverage         scopes_examined, scopes_skipped, inventory?
```

A `?` marks an optional field. Every object is closed: a field the schema does not name is an error.

---

## Fields

### Top level

| Field | Meaning |
|---|---|
| `status` | `draft` while the report is being built or any finding awaits a decision. `final` only after validation, with nothing pending, and never in eval mode. Only `report.py finalise` sets it. |

### `provenance`

| Field | Meaning |
|---|---|
| `recipe` | Name and version of the audit recipe. |
| `framework_revision` | Git SHA of the framework repository the recipe ran from. `null` when it was not a git checkout. |
| `catalogue_version` | See Versioning. |
| `engine` | Absent until an engine report is imported. `name`, `version`, `ruleset_revision`, `ruleset_hash`, and `scanned_at` as the engine reported them. |
| `agent` | `harness` and `model`. Self-reported by the operator or the agent and unverified. `none` for both when no agent took part, as in a report that only imports an engine run. |
| `target` | `label`, `path`, `git_sha`, `branch` and `dirty`. `label` is the short repository name used in output file names (see Output files). The last three are `null` when the target is not a git repository. `report.py init` records the path resolved to an absolute one, so that later calls from another directory find the target; anonymise it before sharing a report if the repository is private. |
| `started_at`, `finalised_at` | ISO 8601 with an offset. `finalised_at` is set with `status: final`. |

### `run_context`

The intake answers, as the run used them. [`report.py init`](#intake-file) copies them in.

| Field | Meaning |
|---|---|
| `eval_mode` | True for a headless evaluation run. The report is stamped, and can never be final. |
| `confirmation_policy` | `interactive`: the person decides on each finding. `defer-all`: every disposition stays pending. `accept-all`: every finding is confirmed; eval mode only. |
| `provider_exposure_acknowledged` | Always `true`. The operator confirmed in the intake that the model provider receives whatever the agent reads from the target, and the report keeps the record. |
| `index` | `kind` (`mcp`, `cli` or `none`), and the tool's `name` and `notes`. |
| `probes` | `allowed`: the verbs the engine's probe runner may execute on the target, each one of the seven in [`spec/command-surface.md`](../../spec/command-surface.md). `timeout_s`: the per-command limit. An empty `allowed` means nothing ran. |
| `excluded`, `known_components` | Paths the audit left out, and component roots the operator named. |
| `stack_profile` | The stack profile used: `id`, whether it was `shipped` or `derived`, and whether the user confirmed it. |

### `checks[]`

| Field | Meaning |
|---|---|
| `id` | The check ID, such as `AGT-01`: a family of two to five capital letters, a hyphen and two or three digits. The family is the ID's prefix. |
| `title`, `phase`, `severity` | As in the catalogue. `severity` is `BLOCKER`, `DEGRADER` or `COSMETIC`; `phase` is 1 to 7. |
| `scored` | Whether the check enters the Phase-1 score. False for informational checks and for checks the engine cannot evaluate yet. |
| `method` | How the verdict is established: `automated` (a tool) or `agent` (a model, with cited evidence). The words are those of the [verification methods](../../spec/README.md#verification-methods). A requirement verified by `human` or `attested` has no check; it appears in `unattested[]`. |
| `verdict` | `PASS`, `PARTIAL`, `FAIL`, `UNKNOWN` or `NOT_APPLICABLE`. This is the verdict that counts, after any override. `UNKNOWN` means the evidence could not be gathered and earns no credit. |
| `engine_verdict` | The engine's verdict for the same check, kept beside the report's. Absent for a check the engine does not run. |
| `override_reason` | Present exactly when `verdict` differs from `engine_verdict`. |
| `confidence` | `high`, `medium` or `low`. Meant for `agent` checks. |
| `summary` | One short sentence. |
| `evidence`, `searches` | See Evidence. |
| `data` | An engine payload (`verb_surface`, `path_list`, `credential_matrix` and the others in the engine's [payloads.py](../deterministic-audit/audit/rules/payloads.py#L25-L176)), carried unchanged. It is the only open object in the schema; its `kind` says what it holds. |

### Evidence

`evidence[]` holds cited facts. `searches[]` records what was looked for when the answer is "not found". Both appear on checks and on findings.

| Field | Used by | Meaning |
|---|---|---|
| `kind` | all | `file`, `command` or `index_query`. |
| `captured_by` | all | `tool`: a deterministic tool recorded it. `agent`: the model recorded it. A report always shows which. |
| `tool`, `tool_version` | `captured_by: tool` | The tool and its version. |
| `path`, `lines`, `quote`, `note` | `file` | A repository-relative path, an optional line or range such as `12-30`, a verbatim quote of at most 300 characters, and a note. |
| `command`, `exit_code`, `output_tail`, `timed_out`, `duration_s`, `redactions` | `command` | The command that ran, how it ended, the end of its output after redaction, and how many redactions were made. |
| `index_tool`, `query`, `result_summary` | `index_query` | The index function called, its query and a short summary of the result. |

A search has `tool` (`glob`, `grep` or `index`), the `pattern`, the `scope` and the number of `hits`. It records a search the agent actually ran. A check that found nothing and ran no search says so in its `summary`; nothing is made up to show effort.

### `findings[]`

| Field | Meaning |
|---|---|
| `id` | `F-001`, `F-002`, and so on. For display. The builder assigns the next number after the highest in the draft, and never reuses one. They may change when a report is rebuilt. |
| `key` | Stable across runs: the check ID, then an optional scope after a colon, such as `SEC-02:src/config/constants.ts`. A re-audit matches findings by `key`. The builder computes it. |
| `check`, `severity` | The check the finding came from, and its severity, which may be lower than the check's. |
| `statement` | Always "An agent cannot X because Y." |
| `remediation` | `summary`, and optionally the `playbook` that fixes it, an `effort` of `S`, `M` or `L`, the findings it `depends_on` and the paths it `touches`. |
| `disposition` | `pending`, `confirmed`, `rejected`, `deferred` or `edited`. |
| `disposition_note` | Why, in the person's words. |
| `confirmed_via` | Present once the disposition is not `pending`. `interactive`: the person answered for this finding. `batch`: for a group of non-blockers. `policy`: the confirmation policy set it, in eval mode. |

### `summary`

The readiness summary of [`spec/readiness-summary.md`](../../spec/readiness-summary.md). The tools compute it from `checks` and `findings` with [`_summary.py`](../tools/_summary.py); the model never writes it.

| Field | Meaning |
|---|---|
| `phase1_score` | `sum(weight × credit) / sum(weight)` over the scored checks of phase 1 that have a verdict, rounded to four places. Weights are BLOCKER 3, DEGRADER 2, COSMETIC 1; credit is PASS 1, PARTIAL 0.5, FAIL 0, UNKNOWN 0. `NOT_APPLICABLE` checks are left out. |
| `scored_checks` | How many checks the score covers. |
| `blockers_remaining` | Scored BLOCKER checks whose verdict is not PASS: `total`, and how many are `fail`, `partial` and `unknown`. It counts checks, not findings. |
| `unknown_scored_checks` | The first qualifier: how many scored checks are UNKNOWN. |
| `unconfirmed_agent_findings` | The second qualifier: findings on `agent` checks whose disposition is still `pending`. |

The report also shows the unattested list beside them. The spec defines no level, grade or pass mark, so the schema has none.

### `unattested[]`, `coverage`

| Field | Meaning |
|---|---|
| `unattested[]` | Each requirement verified by `human` or `attested`: `requirement` (an ID such as `REQ-SH-004`), the `method`, an optional short `property` name and `why`. Such a requirement has no verdict and earns no credit. A declaration or a person's outcome cannot be recorded in 0.1, so the item stays listed. |
| `coverage.scopes_examined`, `scopes_skipped` | What the audit looked at, and each scope it left out with the reason. |
| `coverage.inventory` | The engine's file counts: inspected, skipped, and whether the scan was cut short. |

---

## Intake file

[`audit-intake.schema.json`](audit-intake.schema.json) describes the intake file, named `audit-intake.<label>.json`, which answers the audit's Stage 0 questions so that a run needs no interview. A person fills it in once and reuses it for re-audits; an evaluation run reads it unattended.

| Field | Required | Meaning |
|---|---|---|
| `intake_version` | yes | `0.1`. |
| `target_path` | yes | The repository to audit. |
| `harness`, `model` | yes | Self-reported, as in `provenance.agent`. |
| `provider_exposure_acknowledged` | yes, `true` | The operator confirms that the model provider receives whatever the agent reads from the target. The schema accepts nothing else, so there is no way to start without it. |
| `index` | yes | `kind` (`mcp`, `cli`, `none`), `name`, `allow_install` (off when absent; an installed index lives outside the target) and `notes`. |
| `probes` | no | `allowed` verbs and `timeout_s`. Nothing runs when absent. A target's commands run its code. |
| `excluded`, `known_components` | no | Paths relative to the target. |
| `confirmation_policy` | yes | `interactive`, `defer-all` or `accept-all`. |
| `repo_label` | no | A short name for the repository, used in output file names. Derived from the target directory's name when absent. |
| `output_dir` | yes | Where the report is written. Outside the target. |
| `eval_mode` | no | False when absent. |

`report.py init` copies `eval_mode`, `confirmation_policy`, `provider_exposure_acknowledged`, `index` (without `allow_install`), `probes`, `excluded` and `known_components` into `run_context`, with `probes` defaulting to no verbs and 120 seconds. It copies `target_path` to `provenance.target.path`, the label to `provenance.target.label`, and `harness` and `model` to `provenance.agent`. `allow_install` and `output_dir` are instructions to the run, not results, so they are not in the report.

---

## Facts file

[`facts.schema.json`](facts.schema.json) describes `facts.json`, the file that `facts.py` writes for the audit's recon stage: counts and names that describe a repository, taken with the engine's own inventory and detection. It gives no verdict. Nothing in it says that a file is good, that a stack is right or that a repository is ready.

> [!NOTE]
> In development. [`tools/facts.py`](../tools/facts.py) writes `facts_version`, `label`, `git`, `inventory`, `caps` (the entry for `excludes`) and part of `stack` (`ecosystems`, `source_only`, `package_managers` and `notes`) so far; the rest of `stack` and the other sections arrive in roadmap steps S2.7.3.2 to S2.7.4.2. The schema and the example are live, and this section is the format the finished tool will write. Until it writes every section only `facts_version` and `label` are required; the schema then makes every section required.

| Section | Holds | Comes from | Cut |
|---|---|---|---|
| `facts_version`, `label` | The schema's version, and the repository's short name, which follows the rule that names output files | The tool | None |
| `git` | `sha` and `dirty`; `sha` is null when the target is not a repository or has no commit | The engine's `target` module | None |
| `inventory` | File and byte counts, files per kind, paths left out counted per reason, whether the walk was cut short, the cap it used, and the `--exclude` globs | `audit.scan.build_inventory` | 8 reasons, 10 globs |
| `stack` | Ecosystems, the ones recognised only from source, package managers, CI providers, test frameworks, hook managers, and the engine's notes | `audit.stack.detect_stack` | Bounded by the engine's tables; 4 notes |
| `instruction_files` | `path`, `variant` and `size_bytes` of each file of the variants table that is present | `audit.rules.variants` | 25 files |
| `components` | Declared components, candidate paths, and the engine's notes | `audit.components.detect_components` | 16 declared, 20 candidates, 4 notes |
| `size` | `class`, the counts it used, whether the walk was cut short, and the thresholds, so that a reader sees the rule | The tool, from the inventory | None |
| `caps` | The limit and `omitted` of each list that depends on the repository or on the operator | The tool | None |

What the file never holds: a time, an absolute path, a machine or user name, a branch name, or the content of any file. One repository state gives one file, byte for byte, in whichever directory it sits and whenever the tool runs. A time may sit in the envelope that names the file; it never sits in the file.

How a list is cut:

- Every list is sorted, except `inventory.excludes`, which keeps the operator's order. A list that depends on the repository or on the operator keeps its first entries up to its limit, and `caps` records the limit and `omitted`, the number of entries left out.
- A string that comes from the repository or the operator (a path, a name, a glob) is printable ASCII and of limited length: 128 characters for a path, 64 for a name, 100 for a glob. An entry whose string does not fit is left out and counted in `omitted`, as if it were over the limit. That is how the largest file the schema allows is known: about 27 KB, under the 30 KB bound, and a test builds it.
- The stack's lists have no cut. The engine's own tables bound them, and a test checks that each table fits its list.

The inventory is the engine's own walk, shaped by `--exclude` and `--max-files` as they shape `engine.py`'s. It holds counts and never a path: `skipped` counts the paths the walk left out for each reason, such as `ignored` and `symlink`. A walk that `--max-files` cut short has `truncated` true and `max_files` set to the cap that cut it, and the tool warns in its envelope. The engine records no skip reason for a cut, so `skipped` does not say it. `excludes` names the globs as given, up to 10; a glob that is not printable ASCII or is over 100 characters is left out and counted in `caps.excludes.omitted`, though the engine applied it.

The stack is the engine's `detect_stack` run on that same inventory, so `--exclude` and a cut walk shape it as they shape the engine's. Each list is sorted. `source_only` names the ecosystems recognised from source files because no manifest names them (Python is the only one today); such a project declares no dependencies, and the engine's note says so. A repository the engine does not recognise gives empty lists and the engine's note, and the tool adds no error and no wording of its own.

The size class is by the engine's file count: `small` below 1,000 files, `medium` below 10,000, `large` below 100,000, and `huge` from there on or when the walk was cut short. The file carries the thresholds it used, so a later change to them cannot mislead a reader of an older file.

---

## Output files

Every file a run writes carries the repository's name, so that runs on several repositories sit side by side. No run replaces another run's output.

> [!NOTE]
> The engine report is written under this rule today, by [`tools/engine.py`](../tools/engine.py), and so is the draft, by [`report.py init`](../tools/report.py), with the helpers in [`tools/_common.py`](../tools/_common.py). The final report and its Markdown are written by `report.py finalise`, which has [`render_report.py`](../tools/render_report.py) render the Markdown.

| File | Name | Written by |
|---|---|---|
| Draft report | `<label>.audit-draft.<stamp>.json` | `report.py init` |
| Final report | `<label>.audit-report.<stamp>.json`, and its Markdown, `<label>.audit-report.<stamp>.md` | `report.py finalise` |
| Engine report | `<label>.engine-report.<stamp>.json` | `tools/engine.py` |
| Intake | `audit-intake.<label>.json` | The operator. The recipe never writes it. |

- **`<label>`** is the intake's `repo_label`. When absent it is derived from the name of the target directory: lower case, each run of characters outside `a` to `z` and `0` to `9` becomes one hyphen, leading and trailing hyphens are dropped, and the result is cut to 24 characters with any trailing hyphen dropped. `repo` stands in if nothing is left. The derived label for `Digital-Assistant-SDK` is `digital-assistant-sdk`, and for `Digital_Assistant_microServices` it is `digital-assistant-micros`. Set `repo_label` for a better short name; it takes up to 32 characters of `a` to `z`, `0` to `9`, dot, underscore and hyphen. The label is recorded in `provenance.target.label`.
- **`<stamp>`** is the UTC time as `YYYYMMDDTHHMMSSZ`: `started_at` for a draft, `finalised_at` for a final report, and the scan time for an engine report.
- **Nothing is replaced.** A tool creates a file only if the name is free. If it is taken, which can happen when two runs start in the same second, the tool adds `-2`, `-3` and so on after the stamp. A final report's two files take one number together: if either name is taken, both take `-2`. No tool has an overwrite option. The engine's own `--force` is never passed.
- **One deliberate exception:** a run updates its own draft in place, atomically, as it works and when it resumes after an interruption. That file belongs to the run. A second run on the same repository starts a new draft with a new stamp, and `finalise` leaves the draft untouched and writes the final files new.
- **Eval-mode runs write drafts only**, because an eval-mode report is never final.
- **The output directory is outside the target.** It is the intake's `output_dir`.

The examples in this folder are documentation, not run outputs. Where one belongs to a repository it follows the same naming.

> [!WARNING]
> The engine on its own does not meet this yet. It refuses to replace a JSON report without `--force`, but it replaces the Markdown file beside the report, and the `CON-04` draft, without asking, and its default name `audit-report.json` has no label. The recipes avoid this by always going through `tools/engine.py`, which passes a full file name and asks for JSON only.

---

## The keyword subset

The four schemas use only the keywords below, so a small validator can check them. [`tools/_jsonschema_subset.py`](../tools/_jsonschema_subset.py) is that validator, and it lints a schema before it uses it: a keyword outside this list is an error, so a constraint can never be written and silently ignored. The lint also refuses a `$ref` that is not `#/$defs/<name>` or has no target, a chain of `$ref` that leads back to itself, a `required` name that `properties` does not define, a range nothing can satisfy, and a `pattern` that Python and ECMAScript read differently (lookbehind, named groups, inline flags, back-references, possessive quantifiers, `\A` and `\Z`).

| Keyword | Notes |
|---|---|
| `$schema`, `$id`, `title`, `description` | Annotations. They have no effect on validation. |
| `$defs`, `$ref` | `$ref` is local: `#/$defs/<name>`. It may sit beside annotations. |
| `type` | One of `object`, `array`, `string`, `integer`, `number`, `boolean`, `null`, or an array of those. |
| `properties`, `required`, `additionalProperties` | `additionalProperties` is `false` on every object except `data`, which is `true`. |
| `items` | One schema for every element. |
| `enum`, `const` | Compared by JSON equality. |
| `pattern` | Applies to strings only, and uses the subset of regular expressions that ECMAScript and Python share. It is not anchored unless it says so, and `$` means the end of the string, as in ECMAScript: a value that ends with a newline does not match `^...$`. The reference `jsonschema` package, which uses Python's `re`, would accept it. |
| `minLength`, `maxLength`, `minItems`, `maxItems`, `minimum`, `maximum` | Inclusive bounds. |

The subset has no `oneOf`, `anyOf`, `if` or `format`. What each evidence kind needs is therefore a rule below, not a schema branch.

---

## Rules beyond the schema

> [!NOTE]
> Live: [`tools/validate_report.py`](../tools/validate_report.py) applies all twelve rules, and [`tools/report.py init`](../tools/report.py) enforces the intake rules at the end of this section.

A report is valid when it meets the schema and every rule here. An error fails validation. A warning does not. The tool checks in two stages: the schema first, and the rules only for a report that passes it, because the rules read fields the schema guarantees. Warnings are reported once a report has no errors.

1. **Unique and resolved.** Check IDs, finding IDs and finding keys are each unique. A finding's `check` is a check in the report, its `key` starts with that check's ID, and every `depends_on` entry is a finding in the report. Dependencies have no cycle.
2. **Catalogue.** Each check is in [`catalogue.json`](../catalogue.json), and its `title`, `phase`, `severity`, `scored` and `method` agree with it. Each finding's `playbook` is one the catalogue names; a playbook may be named before its file is written, so the catalogue, not the folder of playbooks, is what "exists" means. A report built against another `catalogue_version` than the one the tool holds, in `MAJOR.MINOR`, is a warning.
3. **Evidence by kind.** `file` evidence has a `path`, and `lines` only with a `path`. `command` evidence has a `command`. `index_query` evidence has an `index_tool` and a `query`. A `path` is relative to the target and does not leave it.
4. **Who captured it.** Evidence with `captured_by: tool` names the `tool` and its `tool_version`. Evidence with `captured_by: agent` names neither.
5. **Methods.** A check with an `engine_verdict` has `method: automated`, and the report has `provenance.engine`. An `automated` check needs no evidence of its own: the tool's recorded output is the evidence. An `agent` check has no `engine_verdict`; its `PASS` or `PARTIAL` has at least one evidence item. Its `FAIL` needs neither evidence nor a search: when the agent found nothing, its `summary` says "we did not find any evidence", and the report invents no evidence and no search to fill the gap.
6. **Overrides.** When `verdict` differs from `engine_verdict`, the check has an `override_reason` and at least one agent-captured evidence item. When they agree there is no `override_reason`.
7. **Findings.** A finding's `severity` is not higher than its check's. A finding on a check whose verdict is `PASS` or `NOT_APPLICABLE` has the disposition `rejected`. `confirmed_via` is present if and only if the disposition is not `pending`.
8. **Final reports.** `status: final` needs `finalised_at`, no `pending` finding, `eval_mode` false, and `confirmed_via: interactive` on every finding of BLOCKER severity.
9. **Policy.** `accept-all` needs `eval_mode: true`, and `eval_mode: true` rules out `interactive`. `confirmed_via: policy` appears only when the policy is not `interactive`.
10. **Summary.** The validator recomputes `summary` with [`tools/_summary.py`](../tools/_summary.py) and fails on any difference, naming each number that differs. The score is compared exactly, as stored to four places. The same code writes the summary in the report builder and shows it in the renderer.
11. **No secrets.** No `quote` or `output_tail` holds a string shaped like a credential, judged by the engine's redaction patterns.
12. **Warnings.** A `file` path that does not exist in the target at `git_sha`, when the target can be reached. The tool reaches it only when given `--target`. It asks git (`git cat-file`, which writes nothing) whether the commit holds the path, and looks in the working tree when `git_sha` is `null`. When the target lacks the commit, or git is missing, the tool says so in one warning and checks nothing else.

The intake file has its own rules, which `report.py init` enforces: `accept-all` needs `eval_mode: true`, `eval_mode: true` rules out `interactive`, `index.name` is present unless `kind` is `none`, `target_path` is an existing directory, and `output_dir` is not inside it.

---

## Verdicts: engine to report

The engine's verdicts are in [findings.py](../deterministic-audit/audit/findings.py#L36-L47).

| Engine | Report |
|---|---|
| `PASS`, `PARTIAL`, `FAIL`, `UNKNOWN` | The same word, in `verdict` and in `engine_verdict`. |
| `ATTEST` | No verdict, so the check is not a check of the report. Each requirement the catalogue gives it is listed in `unattested[]`, with `method` `attested` and the check's ID in lower case as the `property`. A draft that lists a check there has not left it out, and `status` and `finalise` count it as dealt with. A finding on such a check is refused. No engine check emits it today. |
| a check ID in `not_applicable[]` | A check with `verdict: NOT_APPLICABLE` and `engine_verdict: NOT_APPLICABLE`. |
| (not run by the engine) | A check with `method: agent` and no `engine_verdict`. |

The engine's five fixed unattested items become `unattested[]` entries:

| Engine item | Requirement |
|---|---|
| `index-in-use` | `REQ-SH-004` |
| `baseline-adequacy` | `REQ-BF-004` |
| `suite-trustworthiness` | `REQ-SH-050` |
| `doc-accuracy` | `REQ-SH-020` |
| `gate-honoured` | `REQ-SH-026` |

---

## Engine schema v2 mapping

> [!NOTE]
> Live: `report.py import-engine` applies this mapping once to a draft ([`apply_import`](../tools/report.py#L585-L645)), and the conversion is [`convert`](../tools/_engine_adapter.py#L726-L739), a pure function of the engine's report. [`model.py`](../deterministic-audit/audit/report/model.py#L60-L158) builds the engine report.

Every field of the engine's schema v2 is either carried or named as not carried.

| Engine field | Report field |
|---|---|
| `schema_version` | Not carried. The adapter accepts `"2"` and refuses any other value. |
| `provenance.tool`, `version`, `ruleset_revision`, `ruleset_hash`, `scanned_at` | `provenance.engine.name`, `version`, `ruleset_revision`, `ruleset_hash`, `scanned_at` |
| `provenance.target`, `git_sha`, `git_branch`, `git_dirty` | Not copied. `init` recorded the target's facts from the directory itself, and the draft keeps them. The adapter requires the engine's `target` to be the same directory as the draft's, and its `git_sha` to equal the draft's when both are known, and refuses a report that differs in either. A commit that only one side knows is a warning. |
| `provenance.framework_revision` | Not carried. The report records its own `provenance.framework_revision`. |
| `provenance.phase` | Not carried. A 0.1 report covers Phase 1; the adapter refuses an engine report for another phase. |
| `provenance.probes_enabled` | Not carried. `run_context.probes.allowed` says it. |
| `summary.phase1_score` | `summary.phase1_score`, recomputed from the checks; the validator rejects a mismatch. The adapter compares the engine's number with the recomputed one and warns when they differ, and keeps the recomputed one. |
| `summary.checks_scoreable` | `summary.scored_checks` |
| `summary.blockers`, `degraders`, `cosmetic` | Not carried. They count findings. `summary.blockers_remaining` counts checks, as the spec defines it, so the two differ by design. |
| `summary.checks`, `checks_implemented`, `checks_applicable` | Not carried. Verdict counts are derivable, and implementation status is not a property of the audited repository. |
| `summary.coverage_note` | Not carried. Editorial wording belongs to the renderer; the facts are `scored_checks` and `unknown_scored_checks`. |
| `stack.ecosystems`, `package_managers`, `ci_providers`, `test_frameworks`, `hook_managers`, `notes` | The same names under `stack`. `notes` is left out when there are none. |
| `inventory.files_inspected`, `files_skipped`, `truncated` | `coverage.inventory.*`. A scan the engine cut short (`truncated`) is a warning. |
| `components[].name`, `path`, `declared`, `declared_by`, `manifest`, `agents_md` | The same names under `components[]`; `declared` is true |
| `candidate_components[]` | `components[]` with `declared: false`, `name` and `path` both the engine's path |
| `checks[].id`, `title`, `severity`, `phase`, `summary`, `data` | `checks[].id`, `title`, `severity`, `phase`, `summary`, `data`. A check must be one of the catalogue's automated checks. `data` is carried when it has content, and it must have a `kind`. |
| `checks[].verdict` | `checks[].verdict` and `checks[].engine_verdict` |
| `checks[].scored` | `checks[].scored`. A check the engine reports `blocked` did not run, so it takes the catalogue's flag, which the engine's own report cannot give |
| `checks[].pack` | Not carried. It is the ID's prefix. |
| `checks[].tier` | Not carried. It is the engine's evidence cost class; the report states `method` and `captured_by` instead. |
| `checks[].status` | Not carried. `planned` and `blocked` checks arrive as `UNKNOWN`. A `blocked` one also gets a summary that says the engine's ruleset did not evaluate it, and a warning; no engine check is blocked now, so only a report from a ruleset before `2026-10-11.1` has one (its `CON-01`). |
| `findings[].id` | `findings[].key`. The builder assigns `findings[].id`, one past the highest in use. The engine's id is the check ID plus an optional path or scope. It is unique within a report from ruleset `2026-10-11.1` on; before that `AGT-08` could raise two findings with no path, and the golden Server report holds two. The adapter keeps the first as it is and adds `:2`, `:3` and so on to later ones, in the engine's order, so that keys stay unique, among the engine's findings and those the draft already holds. A key may not hold whitespace, so each whitespace character in the path is written as `%` and its UTF-8 bytes in hexadecimal (`%20`), and a path too long for a key is cut. |
| `findings[].check`, `severity`, `statement` | `findings[].check`, `severity`, `statement` |
| `findings[].phase`, `verdict` | Not carried. The check's phase and verdict apply. |
| `findings[].remediation` (a string) | `findings[].remediation.summary`. A missing or empty one becomes "The engine gave no remediation for this finding." |
| `findings[].evidence[]` `path`, `line`, `note` | `evidence[]` with `kind: file`, `captured_by: tool`, `path`, `lines`, `note`; `line` becomes `lines` when it is a positive integer. The engine's `path` is not always a path, so each one goes through [`locate`](../tools/_engine_adapter.py#L249-L274). A text in parentheses (`(no example file)`) or in angle brackets (`<repository>`, the engine's mark for the repository as a whole) names no file and is dropped without a warning. A path that is absolute or climbs out of the target names a place outside the repository, such as the index store that `IDX-02` cites; it is dropped with a warning and counted, because evidence paths are inside the target (rule 3 below), and the finding's `statement` already says where the engine looked. A `file:key` form (`package.json:lint`) and a `file [tag]` form (`pyproject.toml [mypy/pyright]`) are split into the file and a `note` that is the key or the tag as the engine wrote it, and nothing more: the engine writes `file:key` for a key that is set (`BASE-01`) and for one that is not (`TOOL-03`), so the note does not say which. The same items are also gathered onto the check, in the order of its findings. |
| `probes[]` | `evidence[]` with `kind: command` and `captured_by: tool`, on the check that ran the probe, after the file evidence gathered from its findings: `command` (the engine's argument list, written as a shell would read it), `exit_code`, `output_tail` (when there is one), `timed_out`, `duration_s` and `redactions`. The engine's probe record does not name its check, so the adapter holds a table of verb to check, today `test` to `TST-02`, and a test fails if the engine gains another check that builds a probe plan. `verb` is not carried. A probe with a `refused_reason` ran nothing, and its check's summary says why, so it is not carried and needs no warning. A probe that ran, whose verb or check the adapter does not know, is a warning. |
| `unattested[]` | `unattested[]`, in the engine's order: each of the five fixed items as the requirement in the table above, with `method` `attested`, `property` the engine's item name and `why` the engine's own description of it (read from the engine, never copied). An item the table does not have is a warning and is not carried. Each requirement of a check the engine marks `ATTEST` follows; see the verdict table. |
| `not_applicable[]` | `checks[]` with `verdict: NOT_APPLICABLE` and `engine_verdict: NOT_APPLICABLE`, the title, phase, severity and `scored` flag from the catalogue and a `summary` that says the engine did not run it. They follow the engine's checks. |
| `ratchet` | Not carried. A re-audit compares reports by finding `key`. |
| (none) | `method: automated` and `disposition: pending`; everything under `run_context`; `provenance` other than the engine's and the target's; `coverage.scopes_examined` and `scopes_skipped`, which start empty because the engine reports no scopes |

**Limits.** The adapter reads each limit from the report schema and never copies it. A text over its limit is cut, with `…` as its last character, and a warning says so; a probe's output loses its start and not its end, because the end is what matters. A list over its limit (the evidence of a finding or a check, the names of the stack, the components) keeps its first items, and a warning says how many were left out. Nothing the engine said is dropped without a warning, except a placeholder and a probe the engine refused to run. An engine report that is not schema v2 for phase 1, that does not have the shape the mapping reads, or that holds a check the catalogue lacks or only an agent can judge is refused, with every problem listed, and nothing is written.

---

## Validating

The tools validate with their own standard-library code, [`_jsonschema_subset.py`](../tools/_jsonschema_subset.py). `make crosscheck`, which is part of `make check` and so of CI, holds it against the reference `jsonschema` package: both must accept the four schemas, every example, the catalogue, the intake example and the facts example, and both must report the same errors (the same place and keyword) on the raw engine reports and on thousands of one-defect mutants of the examples, including values one below, at and one above every bound. The script is [`dev/crosscheck_jsonschema.py`](../dev/crosscheck_jsonschema.py); the reference package is installed for that run alone, in a throwaway environment, so nothing is installed in the project.

The same reference package gives a quick manual check of the schemas, the examples and the catalogue:

```bash
uv run --no-project --with jsonschema==4.23.0 python - <<'EOF'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

root = Path("brownfield-recipes/schema")
catalogue = Path("brownfield-recipes/catalogue.json")
examples = root / "examples"
report_examples = [examples / "minimal.json", *sorted(examples.rglob("*.audit-*.json"))]
intake_examples = sorted(examples.glob("audit-intake.*.json"))

for schema_name, files in [
    ("audit-report.schema.json", report_examples),
    ("audit-intake.schema.json", intake_examples),
    ("catalogue.schema.json", [catalogue]),
    ("facts.schema.json", [examples / "facts.minimal.json"]),
]:
    schema = json.loads((root / schema_name).read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for path in files:
        errors = list(validator.iter_errors(json.loads(path.read_text())))
        print(path.name, "valid" if not errors else errors)
EOF
```

The command prints `valid` once for each file: the minimal report, the three drafts in `examples/realistic/`, the worked example, the intake example, the catalogue and the facts example. The raw engine reports are not reports of this schema and are skipped.
