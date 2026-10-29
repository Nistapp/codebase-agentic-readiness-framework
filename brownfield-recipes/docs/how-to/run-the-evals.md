# How to Run the Evals

> **Goal:** Run the recipes headlessly on fixtures and real repos and score the results.
> **Audience:** Operators / Engineers
> **Status:** Partial. The corpus, the expected-results format (S4.1.1), the scorer (`tools/eval/score.py`,
> S4.1.2), the Claude Code runner (`tools/eval/run-claude.sh`, S4.1.3), and the fixture sweep and its
> published results (S4.2) are Live. Runners for other harnesses (`run-opencode.sh`, `run-codex.sh`) and
> real-repo runs (S4.3) are Planned.

> [!NOTE]
> Planned. Step 2 below covers `run-claude.sh` only; a runner for another harness is filled in when one
> exists.

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

- **The engine's own one-defect fixtures** (`brownfield-recipes/deterministic-audit/tests/fixtures/`), 89
  of them — each fails exactly one catalogue check by construction, so the expected verdict is known
  without a human re-deriving it. Their expected files are already generated and committed at
  `schema/examples/eval-expected/fixtures/<fixture>.json`; regenerate with
  `tools/eval/generate_fixture_expected.py` after a matrix change (S4.2.1).
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

`<target>` must be the root of a git repository with at least one commit: `report.py init` only records
`git_sha` for a target that is its own repo's root (`git rev-parse HEAD`), and the scorer (Step 3) treats a
run with no `git_sha`, or one that does not match the expected file's `repo_sha`, as not comparable — every
ground-truth metric then comes back `null`. For one of the one-defect fixtures, copy it out and commit it
exactly as `tools/eval/generate_fixture_expected.py` does (`materialise`'s fixed author/committer identity
and date), so the run's `git_sha` matches the committed expected file's `repo_sha`.

Run `tools/eval/run-claude.sh <target> <out-dir> [<repo-label>]`. `<target>` is the repository to audit,
as an absolute path; `<out-dir>` is where the recipe's own report files land, and must already exist; an
intake file, `<out-dir>/audit-intake.<repo-label>.json`, must already exist with `"eval_mode": true` and a
fixed `confirmation_policy` so Stage 0 never has to ask a question. The script runs
`claude -p --dangerously-skip-permissions` unattended and writes, in `<out-dir>`:

- `<repo-label>.harness-run.<stamp>.json` — harness, model, `started_at`, `duration_s`, cost/tokens
  (best-effort, from Claude Code's own `--output-format json`), and the exit code.
- `<repo-label>.harness-transcript.<stamp>.jsonl` — the harness's raw `--output-format json` line, unparsed.

The recipe writes its usual output files (the draft, the engine report, `facts.json`) into the same
`<out-dir>`, found by the file names `SCHEMA.md`'s [Output files](../../schema/SCHEMA.md#output-files)
section gives them. Score the draft with Step 3 below.

Runners for other harnesses (`run-opencode.sh`, `run-codex.sh`) are Planned: writing an unattended,
auto-approving runner script was refused by Claude Code's own safety classifier in the session that
otherwise did this work (not a `permissions.allow` rule — adding one had no effect), and `codex` was not
installed in that environment to verify its headless flags against. Carried to a session or environment
where either is possible.

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

Results live in [Evaluation Results](../reference/eval-results.md) (D59 places them under `docs/reference/`,
not the literal `docs/eval/` the roadmap originally named — `STYLE_GUIDE.md` has no `eval/` category and a
results table is reference-shaped data; extends D54's precedent). The fixture sweep (S4.2) is there now;
real-repo results (S4.3) are added the same way once those runs exist.

---

## Verification

- [x] An expected-results file validates against `eval-expected.schema.json`
      (`validate_report.py` does not yet cover this schema; validate with the reference `jsonschema`
      package via `make crosscheck`, or by hand with `_jsonschema_subset.SubsetValidator`).
- [x] `tools/eval/score.py` prints all five metrics for a comparable report
      (`python3 brownfield-recipes/tools/eval/score.py <report> <expected> --target <repo>`).
- [x] A headless runner completes a fixture end to end, unattended (`run-claude.sh` on
      `tests/fixtures/cmd-02-weak-check`, S4.1.3: `schema_valid: true`, `comparable: true`,
      `blocker_recall: 1.0`, `evidence_validity: 1.0`).
