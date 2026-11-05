# How to Implement an Audit Report

> **Goal:** Apply confirmed findings to a branch of the target, one reviewed commit per item.
> **Audience:** Operators / Engineers
> **Status:** Partial (Step 1 is written; Steps 2-5 are placeholders).

> [!NOTE]
> Partial. The [implementation recipe](../../implement/SKILL.md) runs Stages 0 and 1 (intake and triage)
> today; start it with [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md). Step 1 below
> (the handoff from the audit) is written; the remaining steps are written in IR12.

---

## Prerequisites

- [ ] A final audit report: the `.json` and `.md` pair `report.py finalise` wrote, which sit outside the target
- [ ] A clean working tree in the target, on the integration branch (for example `dev`)
- [ ] Python 3.11+ on `PATH`

---

## Step-by-Step Instructions

### Step 1: Hand the report over to the target and create the state

The audit writes only outside the target, and the implement recipe reads the report from inside it, so the owner
moves it across. Nothing else copies it.

1. Copy the final report's two files into the target, named
   `docs/agentic-readiness-report/<label>-<kind>-audit-<ts>.json` and `.md` (the convention in the UDAN
   repositories: `<kind>` is `server`, `micro` and so on; `<ts>` is the stamp from the audit's file name). Use the
   target's own naming if it has one ([ADR 0003](../architecture/adrs/0003-push-and-pr-policy.md) records the
   push and PR policy that follows).
2. Commit the pair on the integration branch, and let it reach the branch the work will start from. The report is
   evidence; do not edit it afterwards. An edit is detected: `progress.py init` records the SHA-256 of the
   `.json`, and `check_drift.py` reports `report_changed` if the file differs.
3. From the framework checkout, create the state (it refuses a draft or an invalid report, a report outside the
   target, and an existing state):

   ```bash
   python3 brownfield-recipes/tools/progress.py init \
     --report <target>/docs/agentic-readiness-report/<label>-<kind>-audit-<ts>.json \
     --target <target> --default-branch <integration branch> --phase <session or step>
   ```

4. Commit the two state files `init` wrote (`docs/agentic-readiness/<label>-agentic-readiness-state.json` and
   `-STATE.md`) on the integration branch, then start the agent with
   [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md). Its Stage 0 does the drift check and
   resumes from the state.

### Step 2: Handle drift

- TBD: re-verify findings whose evidence changed since the audit.

### Step 3: Approve the work queue

- TBD: order, batches, items to drop.

### Step 4: Approve each change

- TBD: explanation, proposed diff, verification, commit.

### Step 5: Close out

- TBD: targeted re-assessment and the implementation summary.

---

## Verification

- TBD: `python3 brownfield-recipes/tools/progress.py show` lists every item as done, skipped or failed, and the target's tests still pass.
