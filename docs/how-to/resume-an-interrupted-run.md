# How to Resume an Interrupted Run

> **Goal:** Continue an audit or an implementation after a crash, a closed session or context exhaustion.
> **Audience:** Operators / Engineers
> **Status:** Live for audits (S3.5) and for implementations, which use `progress.py` and `check_drift.py`.

---

## Prerequisites

- [ ] The draft report from the interrupted audit, `<label>.audit-draft.<stamp>.json`, in the output directory the
  intake named
- [ ] Python 3.11+ on `PATH`
- [ ] For an implementation, the workspace: the folder of the final audit report, which holds the state file
  `<label>-agentic-readiness-state.json` (see the [state contract](../../implement/state.md)). A run started with
  an earlier release keeps it in the target instead; see
  [Move a run that keeps its state in the repository](#move-a-run-that-keeps-its-state-in-the-repository)

---

## Step-by-Step Instructions

### Step 1: Inspect the saved state

An audit keeps everything it has recorded in its draft, and the draft is written atomically after every change, so a
crash leaves the last complete state and never half of one. Find the newest draft for the repository (the stamp in its
name is the start time), then ask the builder where the audit stands:

```bash
python3 audit/tools/report.py status <output-dir>/<label>.audit-draft.<stamp>.json
```

Read these fields of `data`:

| Field | What it tells you |
|---|---|
| `families_done`, `families_remaining` | Which families of checks are finished, and the IDs of the checks still to record in the others. |
| `findings_pending`, `blockers_pending`, `pending` | The findings that wait for a person's decision. |
| `ready_to_finalise`, `blocking` | Whether `finalise` can run now, and if not, why. |

`report.py status` exits 2 when the draft does not validate. That means the file was edited by hand or by another
program. Fix what `data.errors` names, or start again with `report.py init`, which creates a new draft and leaves this
one alone. A draft from a release with another report schema gets a message that starts `the report has schema`:
start a new draft with `report.py init`.

For an implementation, the state file in the workspace plays this part. Summarise it with:

```bash
python3 implement/tools/progress.py show --workspace <workspace> [--label <label>]
```

Pass `--label` only when the workspace holds more than one state; add `--json` to print the state itself. Read
the skipped items, the preferences and the theme progress, and respect every skip and preference before
changing anything. `data.versions` names the framework that created the state (`created`), the one that last
wrote it (`last`) and the one you run now (`tools`). When `tools` differs from `last`, the next write logs
`Framework moved from ... to ...` in the state; that is expected.

The state lives only in the workspace, so every branch sees the same one. A theme in progress keeps its code on a
branch of its own. Look for one:

```bash
git -C <repo> branch --list 'agentic-readiness/*'
git -C <repo> worktree list
```

If a theme branch exists, continue on its worktree. Re-create one with
`git -C <repo> worktree add <dir> <branch>` when only the branch is left. Never start a
second branch for the same theme.

### Step 2: Restart the agent with the same kickoff prompt

For an implementation, paste [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md) again with
the same fill-ins, including the report path: its folder is the workspace. It runs `progress.py show` first and
resumes from the state. The recipe's [Resuming](../../implement/SKILL.md#resuming) section says what the agent does
with each case below.

For an audit:

Paste [`audit/prompts/kickoff.md`](../../audit/prompts/kickoff.md) again, naming the same output
directory. Its third line is exactly this: run `report.py status` on an existing draft before anything
else, and resume from what it reports — `families_remaining`, `pending` — instead of starting over. See
[`SKILL.md`'s "Resuming"](../../audit/SKILL.md#resuming) for which stage each reading of `status` points
back to. Recording a check again replaces it, so a check that was recorded just before the crash does no
harm when it is recorded twice.

### Step 3: Check for drift

For an audit, the target may have changed since the interruption. `status` does not compare; run
`validate_report.py <draft> --target <repo>` to see which cited files are no longer in the target at the
commit the draft recorded.

- For implementations, run `python3 implement/tools/check_drift.py <report> <repo>` before continuing: it lists the
  findings whose cited files changed since the audited commit. It exits 0 whatever it finds, so read `data.status`
  (`current`, `drifted`, `sha_missing` or `no_sha`). If `data.report_changed` is true, the report was edited after
  the state was created: stop and ask the owner; the text is no longer the audit's.
- `data.versions` compares the report's framework release with the tools'. A report from an older release, or from
  the same release at another commit, gives a warning. A newer report stops the tool with exit 2: install that
  release of both skills ([Versions](../reference/versions.md)).

### Step 4: Finish an item the interruption left open

An implementation item left `in_progress` may already have its commit. Before changing anything again, look for
it on the theme branch, so nothing is committed twice:

```bash
git -C <worktree> log --oneline origin/<integration branch>..HEAD
```

Then re-verify the item with its playbook's Verification row and end it with `progress.py set-status`: `done`,
`partial` with its debt, `failed` or `blocked` with a reason. An item already `partial` or `failed` goes back to
`in_progress` first; a `blocked` one goes back to `queued` (the [state contract](../../implement/state.md#item-statuses)
lists the allowed moves). Render the state with `--render` on the last write. The state is never committed.

## Move a run that keeps its state in the repository

A run started with framework release v0.3.4 or earlier keeps its state in the target, in `docs/agentic-readiness/`.
It keeps the report in `docs/agentic-readiness-report/`. The current tools read a state only from a workspace.
`progress.py adopt` moves it there. The agent does this in Stage 0 when it finds such a state, and you can run it
yourself.

1. Pick the branch with the newest state. A theme branch can be ahead of the integration branch. Compare the last
   commit that touched the state on each branch:

   ```bash
   git -C <repo> log -1 --format='%ci %h' <branch> -- docs/agentic-readiness/
   ```

2. Without a worktree for that branch, add a detached one: `git -C <repo> worktree add --detach <dir> <branch>`.
3. Adopt the state into the workspace, normally the first audit's output folder. `adopt` creates a missing folder:

   ```bash
   python3 implement/tools/progress.py adopt --target <dir> --workspace <workspace> \
     --phase <session id> [--label <label>]
   ```

4. Read `data.may_remove`. It lists the in-repo files you may now remove. They are the state folder, the report
   folder and the `AGENTS.md` line that points at the state. Remove them as a normal change, in the next theme
   branch or a small `chore` branch.
5. Remove the detached worktree: `git -C <repo> worktree remove <dir>`.
6. Resume as in [Step 1](#step-1-inspect-the-saved-state), with `progress.py show --workspace <workspace>`.

`adopt` reads the checkout and never writes or deletes anything in it. It copies each report and the Markdown
beside it into the workspace, and appends one log entry. It refuses a state of another schema version, and a report
whose SHA-256 differs from the recorded one. It also refuses a missing report, a workspace inside the target, and a
workspace that already holds the label.

---

## Verification

- `report.py status` shows `checks_recorded` and `findings_pending` no lower than before the interruption, and a
  family does not move back from `families_done` to `families_remaining`.
- For an implementation, `progress.py show --workspace <workspace>` lists no item of that theme as `in_progress`
  once the item is finished, and `git log` on the branch shows each change once.
- `report.py finalise` writes `<label>.audit-report.<stamp>.json` and `<label>.audit-report.<stamp>.md`, and
  `validate_report.py` exits 0 on the JSON.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `another report command has held the lock on ...` | A `report.py` command is still running on a draft in the same folder. Wait for it. A crashed command leaves no lock behind. |
| A hidden file like `.<label>.audit-draft.<stamp>.json.xxxx.tmp` in the output directory | The interrupted run died while writing. The draft is intact and the file is safe to delete. |
| `the draft is not valid before the change` | The draft changed outside the builder. See Step 1. |
| `the state has schema '0.2' (made by framework v0.3.2); these tools read schema '0.3'. ...` | The state comes from a release with another state schema. The tools read only their own. Move the two old state files aside and run `progress.py init` again from a final report. Or resume with the release that made the state. |
| `the report was made by framework vX; these tools are vY. Update the framework ...` | The report is newer than the tools. Install release vX or later of both skills. |
