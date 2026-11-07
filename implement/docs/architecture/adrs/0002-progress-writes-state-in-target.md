# 0002. `progress.py` Writes the State Files Inside the Target

* **Status:** Accepted
* **Date:** 2026-10-29
* **Last reviewed:** 2026-10-29
* **Deciders:** [@nistapp]

---

## Context

The implement recipe keeps one state per target repository: which findings are queued, done, partial, skipped or
deferred, the owner's preferences, and each theme's branch and PR. The [state contract](../../../implement/state.md)
puts it in the target, in `docs/agentic-readiness/`, so it travels with the repository and every later session
reads it. It is a JSON file, the source of truth, and a Markdown view rendered from it.

The state is the only record of the owner's decisions across sessions and days. A session that edits it by hand can
corrupt it, drop a skip, or let a skipped finding be proposed again. A tool that validates every write prevents that,
but the [tool contract](../../../tools/README.md#6-never-write-inside-the-target) says a tool never writes inside
the target.

## Decision

[`tools/progress.py`](../../../tools/progress.py) is the one exception to rule 6. It writes inside the target, and
only these two files:

* `docs/agentic-readiness/<label>-agentic-readiness-state.json`
* `docs/agentic-readiness/<label>-agentic-readiness-STATE.md`

`<label>` is the audit report's `provenance.target.label`. The limits:

* Every write validates the whole state against [`readiness-state.schema.json`](../../../schema/readiness-state.schema.json)
  and the rules the schema cannot express, before anything is written.
* The folder must resolve inside the target, after symlinks are followed. A state file that is a symlink is refused,
  so a write never goes through a link.
* Each file is replaced atomically: a temporary file beside it, flushed to disk, then a rename. A reader sees the old
  file or the new one. A process killed between the two steps can leave a hidden `.<name>.*.tmp` file, never a
  half-written state; `init` and `render` remove such files for the two names and nothing else.
* `init` never replaces a state. Changes to an existing state come through validated transitions.
* `ToolInfo.writes_inside_target` is `False` by default and `True` for this tool alone, so `--describe` and the
  generated [tool catalogue](../../../tools/CATALOGUE.md) say so.

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Print the state on stdout, or write it to an `--out` path outside the target, and let the agent copy it in | Rule 6 would stay absolute, but the copy step is unvalidated. A session can skip it, copy a stale render, or edit the copy, which is the corruption the tool exists to stop. Every later transition would need a manual read-modify-write. |
| An explicit `--state <file>` that must end in one of the two names, wherever it is | The same exception in practice, with weaker path checks: the tool would not know which repository the file belongs to. |

## Consequences

### Positive

* Nothing hand-copies the state. Every write, including the last, is validated.
* The exception is narrow and visible: two fixed file names, one tool, a manifest flag and this ADR.

### Negative / Trade-offs

* Rule 6 is no longer absolute; a reader of the contract must know this exception.
* For a moment during each write a temporary file exists in the target's `docs/agentic-readiness/` folder.
* A later tool that wants the same exception needs its own ADR. This one does not extend to it.
