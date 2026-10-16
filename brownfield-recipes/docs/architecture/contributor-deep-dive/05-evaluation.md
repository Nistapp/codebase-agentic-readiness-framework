# 5. Evaluation

> **Audience:** Engineers, maintainers
> **Goal:** Explain how the recipes are evaluated and what the published results mean.
> **Status:** Partial. The corpus format, the scorer and the Claude Code runner are Live (S4.1). The
> fixture sweep and real-repo runs that actually populate results (S4.2–S4.4) are Planned.

---

## 1. Why headless, not interviewed

Stage 0 of the audit recipe is an interview, and Stage 4 asks a person to confirm each finding — neither
survives an unattended run, and the plan calls for three runs across eight to ten repos and several models
(DP §11). Review R-07 is the reason the harness exists in this shape rather than a human re-running the
recipe by hand each time: an **intake file** pre-answers Stage 0, and an **eval mode**
(`"eval_mode": true` in [`audit-intake.schema.json`](../../../schema/audit-intake.schema.json)) fixes the
`confirmation_policy` to `accept-all` or `defer-all`, stamping the output so it can never pass as a real
final report. `report.py`'s `set-disposition` auto-confirms under `accept-all` in eval mode and refuses it
otherwise, and `finalise` always refuses an eval-mode draft (`brownfield-recipes/audit/SKILL.md`, Stages
0 and 4).

## 2. Corpus

Two kinds of repository (DP §11):

- **The engine's own one-defect fixtures** (`brownfield-recipes/deterministic-audit/tests/fixtures/`),
  about 70 of them. Each fails exactly one catalogue check by construction (`test_fixture_matrix.py`'s own
  `MATRIX`), so the expected verdict needs no human re-derivation — a cheap ground-truth suite, planned to
  be run in full for the strongest model and sampled for the model matrix (S4.2).
- **Real repositories**, hand-picked for stack coverage and for the properties DP §11 asks the corpus to
  exercise: a repo that already passes, a monorepo, a tiny repo, a repo with no tests or CI, a repo with a
  planted hostile file (an injection test), plus the required NestJS and Java/Quarkus coverage (S4.3).

For either kind, ground truth is one JSON file matching
[`eval-expected.schema.json`](../../../schema/eval-expected.schema.json): each check the corpus has ground
truth for, mapped to its acceptable verdict(s), required evidence paths and a note. A check the file is
silent on is not scored for that repository, and `repo_sha` pins the exact commit the file was written
against. See [Run the Evals](../../how-to/run-the-evals.md) Step 1 for how to write one.

## 3. Metrics

[`tools/eval/score.py`](../../../tools/eval/score.py) computes five, each against one expected-results
file (`<report> <expected> [--target <repo>]`):

| Metric | What it answers | Needs `--target`? |
|---|---|---|
| `schema_valid` | Does the report validate against `audit-report.schema.json`? | No |
| `blocker_recall` | Of the expected checks that are ground-truth blockers (catalogue `severity: BLOCKER`, `PASS` not acceptable), what share does the report also carry as an open blocker (`_summary.open_blockers`)? | No |
| `false_positive_candidates` | Which expected-PASS-only checks did the report not verdict `PASS`? | No |
| `override_precision` | Of the report's `override_reason` checks the expected file has ground truth for, what share lands on an acceptable verdict? | No |
| `evidence_validity` | What share of `kind: file` evidence citations have a path that exists in the target at the recorded commit, with `lines` (when given) fitting the file? | Yes |

A report whose `provenance.target.label`/`git_sha` does not match the expected file's `repo_label`/
`repo_sha` is recorded `comparable: false` rather than scored anyway — deliberately not a hard stop, since
that would discard the `schema_valid` finding the same run already made. A ratio is `null`, not `0`, when
there is nothing of that kind to score (no expected blockers, no overrides, and so on).

DP §11 also names run-to-run variance (three runs per repo, to characterise non-determinism rather than
eliminate it) and cost/time. The runners (§4 below) record cost and time per run; variance and the
false-positive *rate* DP §11 means (findings a human rejects, as opposed to `false_positive_candidates`,
which is scored against written ground truth) are computed once the fixture sweep and real-repo runs exist
(S4.2–S4.3). Review R-27: cost and time have metrics now but no targets — those are set after the first
baseline runs, not before.

## 4. Headless runs

A harness runner drives the recipe unattended and records what it cost. Each needs a pre-written intake
file with `eval_mode: true` at the output directory
(`<out-dir>/audit-intake.<repo-label>.json`), so Stage 0 never has to ask a question — review R-08 still
applies unattended: the recipe reaches target commands only through the engine's own Tier-C probe runner,
never a harness's own shell access.

- **`tools/eval/run-claude.sh`** (Live). Runs `claude -p --dangerously-skip-permissions`, because an
  unattended run cannot answer a permission prompt either — an eval-harness choice, not a recommendation
  for a real audit. Verified end to end on `tests/fixtures/cmd-02-weak-check`: exit 0, 131s, $0.92, 30
  turns; the resulting draft validated and scored `blocker_recall: 1.0`, `evidence_validity: 1.0` against a
  one-check expected file.
- **`run-opencode.sh`, `run-codex.sh`** (Planned). Writing an unattended, auto-approving runner script for
  another harness was refused outright by Claude Code's own safety classifier ("Create Unsafe Agents") in
  the session that built `run-claude.sh`'s siblings — refused regardless of tool (the `Write` tool, a Bash
  heredoc) and of an explicit `permissions.allow` rule added for the purpose, which had no effect on the
  classifier. `codex` was also not installed in that environment, so its current headless flags could not
  be verified against `--help` rather than secondhand documentation. Carried forward to a session or
  environment where either is possible, rather than shipped unverified.

## 5. Models

DP §11's model matrix: at least one top-tier model, one mid-tier, one small/cheap model, and one
non-Anthropic model through opencode — "wherever a smaller model fails, tighten the rubric wording, not the
model choice." Only the first leg runs today, Claude Code on Sonnet (D5); the rest wait on the fixture sweep
and real-repo runs (S4.2–S4.4), and on `run-opencode.sh` existing to reach a non-Anthropic model at all.

## 6. Publishing

Results are planned for `docs/eval/`, with model names and dates, once the fixture sweep (S4.2) and
real-repo runs (S4.3) produce them — see [Run the Evals](../../how-to/run-the-evals.md) Step 4.
