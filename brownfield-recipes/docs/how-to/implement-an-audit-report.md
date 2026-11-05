# How to Implement an Audit Report

> **Goal:** Apply confirmed findings to a branch of the target, one reviewed commit per item.
> **Audience:** Operators / Engineers
> **Status:** Partial (placeholder steps).

> [!NOTE]
> Partial. The [implementation recipe](../../implement/SKILL.md) runs Stages 0 and 1 (intake and triage)
> today; start it with [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md). Step 1 below
> (the handoff from the audit) is written in MR04, and the remaining steps in IR12.

---

## Prerequisites

- [ ] A final, validated audit report
- [ ] A clean working tree in the target
- [ ] Python 3.11+ on `PATH`

---

## Step-by-Step Instructions

### Step 1: Start the agent with the implementation kickoff prompt

- TBD: point it at the report.

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
