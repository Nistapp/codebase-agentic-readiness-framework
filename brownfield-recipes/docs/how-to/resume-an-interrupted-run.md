# How to Resume an Interrupted Run

> **Goal:** Continue an audit or an implementation after a crash, a closed session or context exhaustion.
> **Audience:** Operators / Engineers
> **Status:** Live for audits (S3.5). The implementation half uses `progress.py` and `check_drift.py`.

> [!NOTE]
> Planned. `tools/progress.py` does not exist yet, so the implementation steps below are placeholders. Filled in by roadmap step S5.1.

---

## Prerequisites

- [ ] The draft report from the interrupted audit, `<label>.audit-draft.<stamp>.json`, in the output directory the intake named
- [ ] Python 3.11+ on `PATH`
- [ ] The progress file from the interrupted run (implementations only; Planned, S5.1)

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

For an implementation, `tools/progress.py show` plays this part.

### Step 2: Restart the agent with the same kickoff prompt

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

- For implementations, run `check_drift.py <report> <repo>` before continuing: it lists the findings whose cited files changed since the audited commit.

---

## Verification

- `report.py status` shows `checks_recorded` and `findings_pending` no lower than before the interruption, and a family does not move back from `families_done` to `families_remaining`.
- `report.py finalise` writes `<label>.audit-report.<stamp>.json` and `<label>.audit-report.<stamp>.md`, and `validate_report.py` exits 0 on the JSON.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `another report command has held the lock on ...` | A `report.py` command is still running on a draft in the same folder. Wait for it. A crashed command leaves no lock behind. |
| A hidden file like `.<label>.audit-draft.<stamp>.json.xxxx.tmp` in the output directory | The interrupted run died while writing. The draft is intact and the file is safe to delete. |
| `the draft is not valid before the change` | The draft changed outside the builder. See Step 1. |
