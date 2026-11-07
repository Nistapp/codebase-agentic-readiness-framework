# How to Resume an Interrupted Run

> **Goal:** Continue an audit or an implementation after a crash, a closed session or context exhaustion.
> **Audience:** Operators / Engineers
> **Status:** Live for audits (S3.5) and for implementations, which use `progress.py` and `check_drift.py`.

---

## Prerequisites

- [ ] The draft report from the interrupted audit, `<label>.audit-draft.<stamp>.json`, in the output directory the intake named
- [ ] Python 3.11+ on `PATH`
- [ ] For an implementation, the target repository with its state file, `docs/agentic-readiness/<label>-agentic-readiness-state.json` (see the [state contract](../../implement/state.md))

---

## Step-by-Step Instructions

### Step 1: Inspect the saved state

An audit keeps everything it has recorded in its draft, and the draft is written atomically after every change, so a crash leaves the last complete state and never half of one. Find the newest draft for the repository (the stamp in its name is the start time), then ask the builder where the audit stands:

```bash
python3 brownfield-recipes/tools/report.py status <output-dir>/<label>.audit-draft.<stamp>.json
```

Read these fields of `data`:

| Field | What it tells you |
|---|---|
| `families_done`, `families_remaining` | Which families of checks are finished, and the IDs of the checks still to record in the others. |
| `findings_pending`, `blockers_pending`, `pending` | The findings that wait for a person's decision. |
| `ready_to_finalise`, `blocking` | Whether `finalise` can run now, and if not, why. |

`report.py status` exits 2 when the draft does not validate. That means the file was edited by hand or by another program. Fix what `data.errors` names, or start again with `report.py init`, which creates a new draft and leaves this one alone.

For an implementation, the state file inside the target plays this part. Summarise it with:

```bash
python3 brownfield-recipes/tools/progress.py show --target <repo> [--label <label>]
```

Pass `--label` only when the target holds more than one state; add `--json` to print the state itself. Read
the skipped items, the preferences and the theme progress, and respect every skip and preference before
changing anything.

Read the state where it is newest. A theme in progress keeps its state on its own branch, which is ahead of the
integration branch until the theme is merged:

```bash
git -C <repo> branch --list 'agentic-readiness/*'
git -C <repo> worktree list
```

If a theme branch exists, run `progress.py show` on its worktree (re-create one with
`git -C <repo> worktree add <dir> <branch>` when only the branch is left) and continue there. Never start a
second branch for the same theme.

### Step 2: Restart the agent with the same kickoff prompt

For an implementation, paste [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md) again with
the same fill-ins. It runs `progress.py show` first and resumes from the state; the recipe's
[Resuming](../../implement/SKILL.md#resuming) section says what the agent does with each case below.

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

- For implementations, run `python3 brownfield-recipes/tools/check_drift.py <report> <repo>` before continuing: it lists the findings whose cited files changed since the audited commit. It exits 0 whatever it finds, so read `data.status` (`current`, `drifted`, `sha_missing` or `no_sha`). If `data.report_changed` is true, the report was edited after the state was created: stop and ask the owner; the text is no longer the audit's.

### Step 4: Finish an item the interruption left open

An implementation item left `in_progress` may already have its commit. Before changing anything again, look for
it on the theme branch, so nothing is committed twice:

```bash
git -C <worktree> log --oneline origin/<integration branch>..HEAD
```

Then re-verify the item with its playbook's Verification row and end it with `progress.py set-status`: `done`,
`partial` with its debt, `failed` or `blocked` with a reason. An item already `partial` or `failed` goes back to
`in_progress` first; a `blocked` one goes back to `queued` (the [state contract](../../implement/state.md#item-statuses)
lists the allowed moves). Render the state and commit it after the code commits.

---

## Verification

- `report.py status` shows `checks_recorded` and `findings_pending` no lower than before the interruption, and a family does not move back from `families_done` to `families_remaining`.
- For an implementation, `progress.py show` on the theme's worktree lists no item of that theme as `in_progress`
  once the item is finished, and `git log` on the branch shows each change once.
- `report.py finalise` writes `<label>.audit-report.<stamp>.json` and `<label>.audit-report.<stamp>.md`, and `validate_report.py` exits 0 on the JSON.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `another report command has held the lock on ...` | A `report.py` command is still running on a draft in the same folder. Wait for it. A crashed command leaves no lock behind. |
| A hidden file like `.<label>.audit-draft.<stamp>.json.xxxx.tmp` in the output directory | The interrupted run died while writing. The draft is intact and the file is safe to delete. |
| `the draft is not valid before the change` | The draft changed outside the builder. See Step 1. |
