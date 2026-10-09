# How to Implement an Audit Report

> **Goal:** Apply confirmed findings to a branch of the target, one reviewed commit per item.
> **Audience:** Operators / Engineers
> **Status:** Planned (placeholder).

> [!NOTE]
> Planned. The implementation recipe does not exist yet. Filled in by roadmap step S5.4.

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
