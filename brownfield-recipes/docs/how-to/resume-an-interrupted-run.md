# How to Resume an Interrupted Run

> **Goal:** Continue an audit or an implementation after a crash, a closed session or context exhaustion.
> **Audience:** Operators / Engineers
> **Status:** Planned (placeholder).

> [!NOTE]
> Planned. `tools/report.py status` and `tools/progress.py show` do not exist yet. Filled in by roadmap step S2.3 and S5.1.

---

## Prerequisites

- [ ] The draft report or the progress file from the interrupted run

---

## Step-by-Step Instructions

### Step 1: Inspect the saved state

- TBD: `report.py status` for audits, `progress.py show` for implementations.

### Step 2: Restart the agent with the same kickoff prompt

- TBD: the recipe detects the saved state and resumes.

### Step 3: Check for drift

- TBD: for implementations, `check_drift.py` before continuing.

---

## Verification

- TBD: the resumed run does not repeat completed families or items.
