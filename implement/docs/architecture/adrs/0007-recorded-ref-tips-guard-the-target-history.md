# 0007. Recorded Ref Tips Guard the Target's History

## Context

A hard rule of the [implement recipe](../../../SKILL.md#hard-rules) bans destructive commands. It names history
rewrites, deleted branches or data, and wiped local stacks, unless the person asks for that exact action. The paid
implement eval scores it, but only after a run ends. On a run, an agent can rebase, amend a pushed branch, delete
a branch or tag, or force a reset, and nothing notices.

Git damage of that kind leaves a trace in the refs. A ref is gone, or its tip no longer contains the commit it
held. Read the refs at the start of a run and again at each theme close, and the damage shows. The state lives in
the workspace, outside the target ([ADR 0004](0004-implement-state-lives-in-the-audit-workspace.md)), so the
record goes there too.

## Decision

1. **`progress.py init` and `adopt` record the target's ref tips.** They run `git for-each-ref` over `refs/heads`,
   `refs/tags` and `refs/remotes/origin` with read-only git. A symbolic ref such as `origin/HEAD` is left out. Each
   tip is cut to 12 hex digits, as every commit the state records.
2. **The record is a file of its own, beside the state:** `<label>-ref-tips.json`. The state schema does not
   change. `init` and `adopt` refuse a workspace that already holds one; they never replace it.
3. **Each theme close runs `progress.py verify-refs`**
   ([theme-checks.md](../../../theme-checks.md#keep-the-targets-history)). It writes nothing. It exits 2 when a
   recorded ref lost history, with one stderr line per ref. The ref is gone, or it is a tag that points elsewhere.
   Or it is a branch whose tip no longer contains its recorded tip (`git merge-base --is-ancestor`).
4. **A ref the run creates is not recorded, so it passes.** Theme branches and their worktrees are new refs.
5. **The owner accepts a rewrite made on purpose.** `progress.py accept-ref <ref> --reason ... --by owner` takes
   the ref's current tip as its recorded tip, or drops a ref that is gone. It logs one entry in the state, as
   `accept-lost` does ([ADR 0005](0005-a-lost-pass-stops-the-theme.md)). A later rewrite of the same ref is reported
   again.
6. **A state with no record is not checked.** A target that is not the top folder of a git work tree gets no
   record, and `init` warns. `verify-refs` then exits 1 and says the history check did not run.
   `progress.py record-refs` records the tips for such a state, from that moment on. It never replaces a record.
7. **The commands that read the refs take `--target`.** `record-refs`, `verify-refs` and `accept-ref` read the
   target with read-only git, because the state stores no path to it.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| Keep the ref tips as a field of the state | It needs a new state schema version and an `adopt` path for every older state; a separate file needs neither. |
| Leave it to the eval only | The eval scores a run after it ends, and only the paid scenarios. Nothing would stop a run that rewrites history. |
| Make `set-status ... done` and `theme --status merged` refuse a lost ref | A rewrite is not tied to one theme, and the stop belongs to the owner's decision at close. One command at close reports it plainly. |
| Accept a moved tag when the new tip contains the old one | Moving a tag rewrites what a release name means, even when the move is forward. |
| Record every ref, including other remotes and notes | Other remotes are not the run's to change, and their refs move with every fetch. |

## Consequences

### Positive

- The next theme close catches a deleted branch or tag, an amend, a rebase or a forced reset on a recorded ref.
  It does so on every run, not only in the eval.
- The record is outside the target, so the tool contract's rule against writing inside the target holds.

### Negative / Trade-offs

- It sees only damage to refs. It does not see an `rm -rf` of untracked data, a `git stash drop`, a `docker` stack
  wipe, or a change in a remote that was not fetched.
- It cannot tell a command the person asked for from one they did not. The owner says so with `accept-ref`.
- A `git fetch --prune` after someone else deleted a remote branch is reported too; the owner accepts it.
- A hand edit of the record or of the log could hide a rewrite. The tool cannot see who is typing, as for every
  `--by owner` move.
