# How to Resume an Interrupted Run

> **Goal:** Continue an audit or an implementation after a crash, a closed session or context exhaustion.
> **Audience:** Operators / Engineers
> **Status:** Live for audits, as far as the tools go. The recipe that calls them (S3.5) and the implementation half (S5.1) are planned.

> [!NOTE]
> Planned. The audit recipe does not exist yet, so the agent step below says what the recipe will do. `tools/progress.py` does not exist yet, so the implementation steps are placeholders. Filled in by roadmap steps S3.5 and S5.1.

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

For an implementation, `tools/progress.py show` plays this part. It is Planned (S5.1).

### Step 2: Restart the agent with the same kickoff prompt

- TBD: the audit recipe's kickoff prompt tells the agent to run `report.py status` first and to continue from `families_remaining` and `pending`, without repeating a recorded check (Planned, S3.5).

Until the recipe exists, the agent can do the same by hand: record each remaining check with `report.py add-check`, ask the person about each pending finding and record the answer with `report.py set-disposition`, and then run `report.py finalise`. Recording a check again replaces it, so a check that was recorded just before the crash does no harm when it is recorded twice.

### Step 3: Check for drift

- TBD: for implementations, `check_drift.py` before continuing (Planned, S5.1). For an audit, the target may have changed since the interruption. `status` does not compare; run `validate_report.py <draft> --target <repo>` to see which cited files are no longer in the target at the commit the draft recorded.

---

## Verification

- `report.py status` shows `checks_recorded` and `findings_pending` no lower than before the interruption, and a family does not move back from `families_done` to `families_remaining`.
- `report.py finalise` writes `<label>.audit-report.<stamp>.json`, and `validate_report.py` exits 0 on it.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `another report command has held the lock on ...` | A `report.py` command is still running on a draft in the same folder. Wait for it. A crashed command leaves no lock behind. |
| A hidden file like `.<label>.audit-draft.<stamp>.json.xxxx.tmp` in the output directory | The interrupted run died while writing. The draft is intact and the file is safe to delete. |
| `the draft is not valid before the change` | The draft changed outside the builder. See Step 1. |
