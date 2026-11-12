# State contract

The [implement recipe](SKILL.md) keeps one state per run, in the audit workspace, outside the target repository.
The state is what lets a run stop after any theme and resume another day, and it is where the owner's skips and
preferences live. This
page is an agent directive: MUST and MUST NOT are used in the RFC 2119 sense.

> [!NOTE]
> The rules on this page bind every session. The schema and every `progress.py` command are live. A session
> changes an existing state only with `set-status`, `skip`, `unskip`, `defer`, `undefer`, `pref` and `theme`,
> which check the whole state, append a log entry and refuse a move the diagram below does not allow.

## Files and paths

The state lives in the **workspace**: the folder that holds the final audit report, normally the audit run's
output folder. The workspace is outside the target. Nothing of the state goes into the target, and nothing of it is
committed or pushed ([ADR 0004](docs/architecture/adrs/0004-implement-state-lives-in-the-audit-workspace.md)).

| File | Role |
|---|---|
| The final report, `.json` and `.md` | Written by the audit and never edited; the state names it by file name |
| `<label>-agentic-readiness-state.json` | The source of truth |
| `<label>-agentic-readiness-STATE.md` | Rendered from the JSON; its header says it is generated and not to be edited |

`<label>` is the audit report's `provenance.target.label`.

- The JSON MUST be the only file a session changes by intent; the Markdown view MUST be re-rendered from it,
  never edited by hand.
- The workspace MUST be kept until the run ends. The skips, the deferrals and the preferences live only there, so a
  lost workspace loses the run.
- A session MUST NOT copy the state or the report into the target, and MUST NOT commit either of them.

[`progress.py`](tools/progress.py) is the only writer of the JSON and the renderer of the Markdown view. No tool
writes inside a target: `init` takes the workspace from the report's folder and refuses one inside the target.

```bash
python3 implement/tools/progress.py init --report <workspace>/<final report>.json --target <target>
python3 implement/tools/progress.py show --workspace <workspace> [--json]
python3 implement/tools/progress.py render --workspace <workspace>
```

The transitions (`set-status`, `skip`, `unskip`, `defer`, `undefer`, `pref`, `theme`) take `--workspace` too.
`init` records the report's file name in `source_reports[].path` and its SHA-256 in `source_reports[].sha256`.
`check_drift.py <workspace>/<final report>.json <target>` recomputes the digest and reports `report_changed` when
the file was edited since.

`init` records the framework that created the state in `framework`: the release, the commit and how it was
installed, in the shape of the report's `provenance.framework`. Every later write sets `last_framework` to the
framework that wrote it, and logs `Framework moved from v0.3.2 at <commit> to v0.3.3 at <commit>.` when that
changed. `progress.py show` gives all three in `data.versions`: `created`, `last` and `tools`. The commit is read
with `git` from the folder above the tools, but only when that folder is the top of a git working tree. From an
installed skill it is not, even when the skills folder sits inside another repository, so `init` records `null`.
Pass `--framework-rev <commit>` with the framework release's commit when you know it; `init` keeps its first 12
digits.

`init` refuses a report that is not final or that `validate_report.py` rejects, and a report from a newer framework
release than the tools. It also refuses a report whose folder is inside the target, and an existing state. A report
from an older release gives a warning; `data.versions` holds both releases and commits. It queues confirmed and
edited findings (an edited finding's note goes into `notes`), imports a finding the owner deferred during the audit
as `deferred` with the owner's note as its reason, and lists rejected findings as `not_queued`. Each item gets the
theme of its check from the table in the tool.

## Move a state kept in the target

A run started with an earlier framework release keeps its state in the target's `docs/agentic-readiness/`
folder, with the report in `docs/agentic-readiness-report/`. `adopt` moves that state into a workspace:

```bash
python3 implement/tools/progress.py adopt --target <checkout> --workspace <workspace> --phase <step> [--label <label>]
```

- `adopt` reads the checkout and never writes or deletes anything in it. It copies each source report and the
  Markdown beside it into the workspace. It rewrites the report paths to the file names, appends one log entry and
  writes both state files.
- It refuses a state of another schema version and a report whose SHA-256 differs from the recorded one. It also
  refuses a missing report, a workspace inside the target, and a workspace that already holds the label.
- Theme branches can hold a newer state than the integration branch. A session MUST adopt from the checkout whose
  state has the newest log entry, and MUST tell the owner which branch it chose. The tool does not merge states.
- Its envelope lists the in-repo files the owner may now remove, in `data.may_remove`. They are the state folder,
  the report folder and the `AGENTS.md` line that points at the state. A session removes them only with the owner's
  consent, as a normal change in the next theme branch or a small `chore` branch.

## Item statuses

Every confirmed finding is one item. An item has exactly one status:

| Status | Meaning |
|---|---|
| `queued` | Confirmed in the report and waiting for its theme |
| `in_progress` | A session is applying its playbook |
| `done` | The mechanism is in and the check's verification passes |
| `partial` | The mechanism is in, the repository does not pass it yet, and the debt is recorded |
| `failed` | The playbook could not be applied; the reason is recorded |
| `blocked` | Needs an owner decision or another theme first |
| `deferred` | The owner chose to leave it for later, with a reason |
| `skipped` | The owner chose not to do it, with a reason. Final until the owner unskips it |

A finding the audit marked `rejected` is never an item; the Markdown view lists it as `not_queued`.

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> in_progress
    queued --> skipped: owner, with reason
    queued --> deferred: owner, with reason
    deferred --> queued
    in_progress --> done: verified
    in_progress --> partial: mechanism in, debt recorded
    in_progress --> failed: could not apply
    in_progress --> blocked: needs owner or another theme
    partial --> in_progress
    failed --> in_progress
    blocked --> queued
    skipped --> queued: owner unskips
```

Allowed next states, from each status (`progress.py set-status` refuses anything else and its message names them):

| From | May go to | Notes |
|---|---|---|
| `queued` | `in_progress`; `skipped`, `deferred` (owner) | |
| `in_progress` | `done`, `partial`, `failed`, `blocked` | |
| `partial`, `failed` | `in_progress` | never straight to `done`: go back to `in_progress`, then end it again |
| `blocked` | `queued` | never straight to `in_progress`: unblock to `queued` first |
| `deferred`, `skipped` | `queued` (owner) | `undefer`, `unskip` |
| `done` | nothing | final |

`set-status` to the status an item already has is not a transition: with `--note` (and any `--commit`) it appends
the note and logs "note added"; without `--note` it is refused.

- A transition not in the diagram MUST NOT be recorded.
- Every transition MUST record who made it (`owner` or `agent`), the date and, for `skipped`, `deferred`,
  `failed` and `blocked`, a reason.

## Skip, defer and preferences

- **Skip.** Only the owner skips. A session MUST NOT skip a finding on its own judgment, and MUST NOT propose
  a skipped finding again in any stage or session. The close-out re-audit lists skipped findings as
  owner-accepted, not as new gaps.
- **Defer.** Only the owner defers. A deferred item goes back to `queued` when the owner says so; a session
  MAY remind the owner of deferred items at the start of a theme.
- **Preferences.** Every owner choice (a tool, a style, a scope limit such as "no mass reformat") MUST be
  recorded as a preference with a key, a value, a reason, who decided, the date and the step. A session MUST
  read every preference before it plans a theme. A playbook step that conflicts with a preference MUST stop
  and ask; it MUST NOT override the preference. Keys are lower case (`node.version-file`: letters, digits, dot,
  underscore, hyphen). When the owner was asked and has no preference, record the value `none` with the owner's
  words as the reason (`pref set tool.formatter none --reason "..." --by owner`), so the question is not asked
  again.

## Continue on error

A theme's job is to install the mechanism: the formatter, the linter, the test verb, the coverage floor, the
CI step. When the repository does not pass it yet (unformatted code, lint debt, missing tests):

1. Count the debt and record it on the item: what, how many, and the baseline file if one exists.
2. Wire the check so the debt cannot grow: a ratchet, a baseline file, or a step marked report-only.
3. Mark the item `partial` and continue with the next item.

A session MUST NOT mass-fix, suppress rules or lower a gate unless the owner chooses that, and MUST NOT
record `done` for an item that is `partial`.

## JSON shape

The schema is [`schema/readiness-state.schema.json`](../audit/schema/readiness-state.schema.json), `schema_version`
`0.3`; the tools read no other, and refuse an older state with a message that names both versions. Field notes are in
[the schema reference](../audit/schema/SCHEMA.md#readiness-state). Two examples are in the framework repository, under
`audit/schema/examples/`:
`readiness-state.example-service.json`, which `init` writes for the framework's example report, and
`readiness-state.example-service.in-progress.json`, a state some themes later. Each has its rendered Markdown
beside it.

The schema subset cannot express these rules, so `progress.py` checks them on every read and write:

- `skipped`, `deferred`, `failed` and `blocked` need a `reason`; `skipped` and `deferred` need `by: owner`.
- An item with `debt` is never `done`.
- A finding appears once, in `items` or in `not_queued`.
- `themes` holds T1 to T8, each once, in order; preference keys and source report paths are unique.

The tools write the framework commits (`framework.revision`, `last_framework.revision`) and each source report's
`git_sha` as 12 lower-case hex digits, as the report does: a full id has the shape secret scanners read as a token.
`progress.py` cuts `commits` and `merged_sha` to 12 digits too; a shorter id given (7 to 11 digits) is kept as it is.
