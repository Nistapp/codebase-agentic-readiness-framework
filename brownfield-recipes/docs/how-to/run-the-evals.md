# How to Run the Evals

> **Goal:** Run the recipes headlessly on fixtures and real repos and score the results.
> **Audience:** Operators / Engineers
> **Status:** Partial. The corpus, the expected-results format (S4.1.1) and the scorer (`tools/eval/score.py`,
> S4.1.2) are Live. The headless runners (`tools/eval/run-*.sh`, S4.1.3) are Planned.

> [!NOTE]
> Planned. Step 2 below cannot run yet: the headless runners do not exist. Filled in by roadmap step S4.1.3.

---

## Prerequisites

- [ ] Claude Code (Sonnet) or another harness with headless mode
- [ ] The engine fixtures (`brownfield-recipes/deterministic-audit/tests/fixtures/`) and, for a real repo, a
      written expected-results file
- [ ] Python 3.11+ on `PATH`

---

## Step-by-Step Instructions

### Step 1: Choose the corpus, and write its expected results

The corpus is two kinds of repository (DP §11, review R-07):

- **The engine's own one-defect fixtures** (`brownfield-recipes/deterministic-audit/tests/fixtures/`),
  about 70 of them — each fails exactly one catalogue check by construction, so the expected verdict is
  known without a human re-deriving it.
- **Real repositories**, hand-picked for stack coverage and for the properties DP §11 asks the corpus to
  exercise: a repo that already passes, a monorepo, a tiny repo, a repo with no tests or CI, a repo with a
  planted hostile file (an injection test).

For either kind, the ground truth a run is scored against is one JSON file matching
[`eval-expected.schema.json`](../../schema/eval-expected.schema.json) — see
[`eval-expected.example-service.json`](../../schema/examples/eval-expected.example-service.json) for a
worked example. It maps each check the corpus has ground truth for to its acceptable verdict(s) (more than
one when the ground truth genuinely is not sharper than that), the evidence paths a correct run must cite,
and a note explaining why. A check the file is silent on is not scored for that repository. Pin `repo_sha`
to the exact commit the file was written against; a run against a different commit is not comparable, and
the scorer (once it exists) records that mismatch rather than silently comparing anyway.

Write the file by hand for a small fixture, or derive a first draft from the deterministic engine's own
report on the repository and then correct it by reading the actual target — the same engine-first,
verify-independently method the audit recipe itself uses (`SKILL.md`, Stage 2).

### Step 2: Run a harness runner

- Planned (S4.1.3): `tools/eval/run-claude.sh` and siblings for other harnesses, each recording tokens,
  cost and time wherever the harness reports them.

### Step 3: Score

Run `tools/eval/score.py <report> <expected> [--target <repo>]`. It computes, each against the
expected-results file from Step 1:

- `schema_valid`: whether the report validates against `audit-report.schema.json`.
- `blocker_recall`: of the expected checks that are ground-truth blockers (catalogue severity `BLOCKER`,
  `PASS` not an acceptable verdict), the share the report also reports as an open blocker.
- `false_positive_candidates`: expected checks whose only acceptable verdict is `PASS` but whose report
  verdict is not.
- `override_precision`: of the report's checks that carry `override_reason` and that the expected file has
  ground truth for, the share whose resulting verdict is acceptable.
- `evidence_validity`: with `--target` only, the share of the report's `kind: file` evidence citations
  whose path exists in the target at the recorded commit, and whose `lines` (when given) fit the file.

A report whose `provenance.target.label`/`git_sha` does not match the expected file's `repo_label`/`repo_sha`
is recorded as not comparable rather than scored anyway, and every ground-truth metric comes back `null`.
A ratio is `null`, not `0`, when there was nothing of that kind to score (no expected blockers, no overrides,
and so on) — a run's own stderr summary line shows all four ratios.

### Step 4: Publish

- Planned (S4.1.4 and later): a results table under `docs/eval/` with model names and dates.

---

## Verification

- [x] An expected-results file validates against `eval-expected.schema.json`
      (`validate_report.py` does not yet cover this schema; validate with the reference `jsonschema`
      package via `make crosscheck`, or by hand with `_jsonschema_subset.SubsetValidator`).
- [x] `tools/eval/score.py` prints all five metrics for a comparable report
      (`python3 brownfield-recipes/tools/eval/score.py <report> <expected> --target <repo>`).
- [ ] Planned (S4.1.3): a headless runner completes a fixture end to end, unattended.
