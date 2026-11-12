# 0004. The Implement State Lives in the Audit Workspace, Outside the Target

## Context

The implement recipe keeps one state per run. It records which findings are queued, done, partial, skipped or
deferred. It also holds the owner's preferences and each theme's branch and pull request. It is a JSON file, the
source of truth, and a Markdown view rendered from it. A session that edits the state by hand can corrupt it, so
[`tools/progress.py`](../../../tools/progress.py) validates every write.

The audit writes its final report outside the target, to the output directory the owner names at intake
([`audit/SKILL.md`](../../../../audit/SKILL.md)). A state kept inside the target forces work on the owner before the
run can start: copy the report into the target, commit it and push it. It also puts the tool's own bookkeeping into
the target's history. That means the state files, a folder README and an `AGENTS.md` pointer line. It also means a
triage pull request and a state commit on every theme branch. Those commits make stacked theme branches conflict
after squash merges.

The owner's position: no artefact of this tool is forced into the target repository. The
[tool contract](../../../../audit/tools/README.md#6-never-write-inside-the-target) says a tool never writes inside
the target; this decision keeps that rule without exception.

## Decision

1. **The workspace is the folder of the final report given to `progress.py init`.** Normally that is the audit
   run's output directory. `init` takes no `--workspace` option. It refuses a workspace that resolves inside the
   target, after symlinks are followed.
2. **The state lives in the workspace**, under the same two names:
   `<label>-agentic-readiness-state.json` and `<label>-agentic-readiness-STATE.md`. `<label>` is the report's
   `provenance.target.label`.
3. **Every other `progress.py` command finds the state with `--workspace DIR`.** They take no `--target` and no
   alias for it ([ADR 0008](../../../../docs/architecture/adrs/0008-one-release-version-and-current-schemas-only.md):
   no backward compatibility before 1.0.0). `check_drift.py` reads the state from the report's folder.
4. **No tool writes inside a target.** `ToolInfo.writes_inside_target` stays in the manifest and is `false` for every
   tool, so the [tool catalogue](../../../../audit/tools/CATALOGUE.md) states the guarantee.
5. **The write rules guard the workspace.** Every write validates the whole state against
   [`readiness-state.schema.json`](../../../../audit/schema/readiness-state.schema.json) first. A state file that is a
   symlink is refused. Each file is replaced atomically, and `init` and `render` sweep only their own hidden
   temporary files. `init` never replaces a state.
6. **The state schema stays at version 0.3.** Its shape does not change. `source_reports[].path` is relative to the
   workspace. The state stores no absolute path.
7. **`progress.py adopt` moves a current-schema state out of a target.** It reads
   `<target>/docs/agentic-readiness/<label>-agentic-readiness-state.json`. It never writes or deletes in the target.
   It refuses a state of another schema version. It refuses a report whose SHA-256 differs from the recorded one.
   It refuses a workspace that already holds the label. It copies each report pair into the workspace and rewrites
   `path`. It logs one entry and lists the in-repo files the owner may remove. It is the one relocation path. It
   stays until the owner removes it.
8. **The recipe leaves the target's history alone.** It makes no handover copy of the report. It needs no triage
   worktree, branch or pull request. It writes no folder README and no `AGENTS.md` pointer line. It commits no
   state. Triage writes only to the workspace. Theme branches carry only the fixes.
9. **A close-out re-audit writes to its own run folder.** `compare_reports.py` reads both reports by path; the state
   stays in the first workspace.

Files the owner asked for as fixes (a baseline file, a deny list, `AGENTS.md` edits) are the run's output, not its
bookkeeping. They go into the target and follow the target's own naming conventions.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| Keep the state in the target's `docs/agentic-readiness/`, written by `progress.py` as the one exception to the tool contract | It forces the copy, commit and push before `init`, a triage pull request, and state commits on every theme branch. |
| `init` copies the report into the target | It still puts the tool's own files into the target's history. |
| Offer both: state in the target or in the workspace | Two code paths and two variants of every recipe step, for about four to five days of work. |
| Keep the state in the target's `.git/` folder | It still writes inside the target checkout, against the tool contract. |
| Keep the state on an orphan branch of the target | It still commits the tool's own files into the target repository. |
| An explicit `--workspace` on `init` | One more path to type and to get wrong; the report's folder already names the workspace. |
| Keep `--target` as an alias on the other commands | ADR 0008 rules out backward compatibility before 1.0.0. |
| Bump the state schema to 0.4 | Then `adopt` would convert an older state, which ADR 0008 forbids. |

## Consequences

### Positive

- The owner starts implement straight from the audit's output folder: no copy, commit or push.
- The tool contract's rule against writing inside the target has no exception.
- Theme branches hold only fixes, so stacked branches no longer conflict over state files.

### Negative / Trade-offs

- Losing the workspace loses the run: the skips and preferences live only there. The audit intake and the recipe
  say so.
- Agents that work in the target outside an implement run do not see the skips.
- Two people cannot share one run, because the workspace is a local folder.
- `adopt` is one more command to keep and test.
