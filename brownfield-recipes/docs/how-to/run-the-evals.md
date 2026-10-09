# How to Run the Evals

> **Goal:** Run the recipes headlessly on fixtures and real repos and score the results.
> **Audience:** Operators / Engineers
> **Status:** Planned (placeholder).

> [!NOTE]
> Planned. The eval harness does not exist yet. Filled in by roadmap step S4.1.

---

## Prerequisites

- [ ] Claude Code (Sonnet) or another harness with headless mode
- [ ] The engine fixtures and the expected-results files

---

## Step-by-Step Instructions

### Step 1: Choose the corpus

- TBD: fixtures, real repos, or both.

### Step 2: Run a harness runner

- TBD: `tools/eval/run-claude.sh` and siblings.

### Step 3: Score

- TBD: `tools/eval/score.py`.

### Step 4: Publish

- TBD: results table under `docs/eval/` with model names and dates.

---

## Verification

- TBD: the scorer prints metrics for every run and every report is schema-valid.
