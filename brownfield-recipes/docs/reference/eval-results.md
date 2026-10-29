# Evaluation Results

> **Audience:** Everyone
> **Source of truth:** `artefacts/audit-runs/fixture-sweep/batch{1,2,3}.results.jsonl` (git-ignored run
> artifacts; this page is the durable, published summary). See [Run the Evals](../how-to/run-the-evals.md)
> for the method and [5. Evaluation](../architecture/contributor-deep-dive/05-evaluation.md) for what the
> metrics mean.
> **Status:** Live for the fixture sweep (S4.2) and the real-repo runs (S4.3, one run per repo under
> `D61`). A second harness/model (`S4.3.4`) stays Planned, deferred per `D57`.

---

## Fixture sweep — Claude Code on Sonnet 5.5, 2026-10-17/18

All 89 of the engine's one-defect fixtures (`brownfield-recipes/deterministic-audit/tests/fixtures/`), the
full corpus named in review R-07, not a sample.

### Headline numbers

| Metric | Result |
|---|---|
| Fixtures run | 89 / 89 |
| Schema-valid reports | 89 / 89 (100%) |
| Comparable reports (`git_sha` matched the expected file's `repo_sha`) | 89 / 89 (100%) |
| Fixtures with ground-truth blockers (`blocker_recall` scored) | 31 / 89 |
| Fixtures that caught their expected blocker | 30 / 31 (96.8%) |
| **Fixtures hitting their expected verdict overall** | **88 / 89 (98.9%)** |
| `evidence_validity` (citations whose path/lines check out against the target) | 1,741 / 1,768 (98.5%) |
| Total cost | $86.71 (clean final runs); $86.90 including $0.19 spent on 14 attempts that were discarded and retried |
| Total wall time | 16,665.5s (~4.6h) for the clean final runs |
| Average per fixture | ~$0.97, ~187s (3.1 min); range 119.1s–309.0s |

The v0.1 exit criterion (§2.1 of the roadmap) asks for "at least 90% of fixtures get the expected verdict on
their defect check" — **98.9% clears it.**

### Per-family breakdown

| Family | Fixtures | Schema-valid / comparable | Blocker recall | Misses |
|---|---|---|---|---|
| AGT | 15 | 15/15 | 1.0 (15/15 scored) | none |
| BASE | 5 | 5/5 | n/a (no scored blockers) | none |
| CI | 4 | 4/4 | 1.0 (4/4 scored) | none |
| CMD | 13 | 13/13 | 1.0 (13/13 scored) | none |
| CON | 10 | 10/10 | 1.0 (scored subset) | none |
| DOC | 5 | 5/5 | n/a | none |
| EXEC | 10 | 10/10 | 1.0 (scored subset) | none |
| GOVERNED | 1 | 1/1 | n/a | none |
| HYG | 3 | 3/3 | n/a | none |
| **IDX** | 2 | 2/2 | **0.5 (1/2 scored)** | **`idx-01-no-mcp-config` missed `IDX-01`** |
| NAV | 3 | 3/3 | n/a | none |
| SEC | 7 | 7/7 | 1.0 (scored subset) | none |
| TOOL | 7 | 7/7 | n/a | none |
| TST | 4 | 4/4 | 1.0 (scored subset) | none |

### The one miss

`idx-01-no-mcp-config` expected `IDX-01` to `FAIL` (no project-level MCP config exists in the fixture) and
got `PASS`. Triaged in `S4.2.4`: not a model or engine defect — `IDX-01` is specified to check both
project-level AND user-level MCP configs, and the machine this sweep ran on has a genuine user-level
`codebase-memory-mcp` registration (`~/.config/opencode/opencode.jsonc`), which the engine correctly finds
and reports on every fixture run regardless of fixture content. This is an eval-harness environment-isolation
gap (the harness runs fixtures under the real, unmodified `$HOME`), not a rubric or engine problem — **KC
review requested** on whether to isolate `$HOME` for future sweeps or accept this as a known limitation of
running on a dogfooding machine. Full detail in `phase-M4-evaluate-release.md`'s `S4.2.4` log entry.

### Evidence-validity shortfall, found but not fixed

27 of 1,768 `file` evidence citations (1.5%) did not check out against the target. Investigated rather than
left unexplained; two distinct, unrelated causes, neither a model defect:

- **Absence-proof citations the scorer doesn't recognise as such.** Several checks' own specs call for
  citing the searched *location* when nothing was found there (`CI-04` citing `.github`, `AGT-11` citing
  `.` when no instruction file exists) — correct per the check's own rubric, but `tools/eval/score.py`'s
  `evidence_validity` metric checks every `kind: file` citation for a real path via `git cat-file`, so a
  deliberate non-path (a directory standing in for "I looked here and found nothing") is flagged invalid.
  Likely a scorer gap, not a report defect: `score.py` has no special case for absence-proof evidence.
  Affects `agt-10-deferred`, `ci-01-no-pr-trigger`, `ci-03-ci-only-step`, `exec-01-unpinned`,
  `exec-05-generated`, `tool-03-nonstrict-ts`, `tst-01-no-suite` (one or two citations each, all `CI-04` or
  `AGT-11`).
- **A genuine candidate evidence-path defect in a monorepo-shaped fixture.** `exec-02-nested-lockfile`
  (package manifest at `packages/app/package.json`, not the repo root) has 14 invalid citations across six
  checks (`CMD-01`, `TOOL-01`, and others), all `captured_by: tool`, all citing a bare `package.json` —
  the engine's own evidence, not the agent's, pointing at a path that doesn't exist at this fixture's root.
  Worth a closer look as a possible engine defect (the manifest-citing code may not be using the manifest's
  actual discovered path) rather than deriving a new placeholder.

Neither was fixed here — `S4.2.5`'s own scope is the results table, not engine or scorer changes. Carried
forward as candidates for `S4.4` (the rubric-tightening loop) or a standalone fix.

### Anomalies during the run

Two separate rounds of the operator's own Claude usage-quota exhaustion mid-sweep (not an engine or recipe
defect): batch 1's last 2 fixtures and batch 3's last 12 fixtures each hit `api_error_status: 429` before
producing a draft. Both resolved by waiting for the quota's own reset and retrying the same fixtures
unchanged, once the stale `work/<fixture>/repo/` directory from the failed attempt was cleared first
(`run_one.py`'s `materialise()` needs that, or it raises `FileExistsError` on a rerun — found, not fixed,
since it's scratch tooling for this leaf, not shipped). Full detail in `phase-M4-evaluate-release.md`'s
`S4.2.3` log entries.

### Cost and time budgets (R-27)

Review R-27 asked for cost/time targets to be set after the first baseline run rather than guessed in
advance. This sweep is that baseline. Proposed targets for future sweeps of this size (89 fixtures, this
model):

| Budget | Target | Basis |
|---|---|---|
| Per-fixture cost | $1.50 | ~1.5x the observed $0.97 average, to cover fixtures with more checks/findings than the average |
| Per-fixture time | 6 min | ~2x the observed 3.1 min average, generous headroom for a slower run |
| Total sweep cost (89 fixtures) | $135 | matches this sweep's approved $150 budget, used at 58% ($86.71) |
| Total sweep time, three batches | 8h | observed 4.6h; headroom for quota-retry overhead |

These are proposed, not yet KC-confirmed; raise or lower them once a second baseline (a different model, or
a re-run after rubric fixes) exists to compare against.

---

## Real-repo runs — Claude Code on Sonnet 5.5, 2026-10-19 (S4.3)

One run each against three real repositories (`S4.3.3`), scored with `tools/eval/score.py --target` against
a hand-corrected expected-findings sheet per repo (`S4.3.2`). **One run per repo, not three** (`D61`,
2026-10-19): KC decided this after the first run, trading the roadmap's and the DP's original "three runs
for each repo" plan for a faster calibration pass — this round's purpose was real cost/time numbers and a
first read on quality, not a statistically firm per-repo average. A second harness/model (`S4.3.4`) stays
deferred per `D57`.

### Real-repo headline numbers

| Metric | Result |
|---|---|
| Repos run | 3 / 3 (Digital-Assistant-SDK, Digital-Assistant-Server, the engine repo at `dev`) |
| Schema-valid, comparable reports | 3 / 3 (100%) |
| Total cost | $6.83 (including $0.66 spent on the engine repo's superseded run 1); $6.17 for the three final scored runs alone |
| Total wall time | 1,420s (~23.7 min) including the superseded run; 1,249s (~20.8 min) for the three final runs |
| `blocker_recall` (per repo) | SDK 1.0 (4/4); Server 1.0 (5/5); engine repo 1.0 (10/10) |
| `evidence_validity` (aggregate) | 257 / 275 (93.5%) |
| `false_positive_candidates` (aggregate) | 5 / 87 (5.7%) |

The v0.1 exit criterion (§2.1 of the roadmap) asks for `blocker_recall` ≥ 0.9, ≥ 98% valid citations, and
KC rejecting at most 10% of findings, each **across three runs per repo** — not yet measured that way under
`D61`'s one-run-per-repo plan, so none of the boxes below are ticked against that criterion yet. Read
individually, against this single data point per repo:

- **`blocker_recall` is 1.0 on every repo** — Digital-Assistant-Server's first score (0.7143) was revised
  after `S4.3.6`'s triage (`D62`) accepted four of the agent's own evidence-backed overrides as correct and
  updated the sheet to match; see "Ground truth corrected" below.
- **93.5% evidence validity is below the 98% target**, driven almost entirely by one known, already-
  diagnosed defect (the engine repo's fixture bleed, 18 of 18 total invalid citations), not by the model
  misreading the target.
- **5.7% of findings would need KC's rejection, within the 10% target in aggregate** — but the engine
  repo alone is at 15.4% (4/26), again the same fixture-bleed defect.

### Per-repo breakdown

| Repo | Cost | Time | Turns | `blocker_recall` | `evidence_validity` | `false_positive_candidates` | `override_precision` |
|---|---|---|---|---|---|---|---|
| Digital-Assistant-SDK | $1.91 | 302s | 54 | 1.0 (4/4) | 1.0 (92/92) | 0.0278 (1/36) | null (0 overrides) |
| Digital-Assistant-Server | $3.02 | 679s | 80 | 1.0 (5/5) | 1.0 (69/69) | 0.0 (0/25) | 1.0 (4/4) |
| Engine repo (`dev`), final run | $1.24 | 268s | 45 | 1.0 (10/10) | 0.8421 (96/114) | 0.1538 (4/26) | null (0 overrides) |

### Ground truth corrected: Digital-Assistant-Server's four overrides

The agent's four overridden verdicts (`AGT-07`, `CON-01`, `CON-02`, `EXEC-04`) first scored as "incorrect"
against the sheet, driving both the apparent missed-blocker count and `override_precision: 0.0` — but read
individually, they were a substantive, evidence-backed disagreement with a judgment call this same
evaluation round had made, not a quality defect. The agent's own `EXEC-04` override reasoned that four
flagged "missing env vars" (`GREEN`, `YELLOW`, `RED`, `NC`) are local ANSI-colour shell variables, never
read from the process environment — the *exact* diagnosis this round had already surfaced for KC during
`S4.3.2.2`'s sheet-building, where KC had chosen to keep the engine's literal `FAIL` as ground truth rather
than correct it. The agent independently re-derived the same finding and, unlike the sheet, acted on it.
`AGT-07`'s override was a new, separate finding: the engine's heading-word match requires a trigger word in
the prohibitions section's own heading, but AGENTS.md's section is headed "Security & Safety Guardrails"
with no such word, despite being a real prohibitions section in substance — a candidate `AGT-07` detector
gap, carried to `S4.4`. `CON-01`/`CON-02`'s overrides build on that same corrected reading. Put to KC during
`S4.3.6`'s triage, who accepted all four overrides as correct (`D62`, 2026-10-19) and had the sheet revised
to match, reversing `S4.3.2.2`'s original `EXEC-04` call — the table above reflects the corrected sheet.

### Found, not fixed: a real `SKILL.md` forwarding defect

The engine repo needed two runs. Run 1 (no `excluded` field in its intake, $0.66, 171s) reproduced a fixture-
bleed bug already found and excluded when building its sheet (`S4.3.2.3`): `tests/fixtures/**` holds the
engine's own one-defect-per-check synthetic fixtures (tiny Node/TS repos used to test the checks), and the
engine's scan of its own repository was citing fixture files as if they were the real root's configuration
(for example `SEC-02` citing `tests/fixtures/sec-02-key-shaped/config.py`, the engine's own synthetic-secret
fixture, as a third "credential-shaped line" beyond the sheet's two real ones). Run 2 added
`excluded: ["tests/fixtures/**"]` to the intake ($1.24, 268s) and got the *identical* four false positives
anyway. Traced to the actual cause: `brownfield-recipes/audit/SKILL.md` line 111 tells the agent to forward
the intake's `excluded` paths to `facts.py`; its Stage 2 instructions for running `engine.py` never mention
forwarding `excluded` at all, so the field reaches `facts.json` but never the engine scan that produces
checks and findings. **This is a real recipe-text defect, not specific to this repo or this round** — any
audit that relies on `intake.excluded` to keep the scan off some path gets it honoured for `facts.py` only.
KC chose to record it rather than spend a third run (2026-10-19); carried to `S4.4` or a dedicated leaf to
fix `SKILL.md`'s Stage 2 so it forwards `excluded` to `engine.py` the same way it already does for
`facts.py`.

### KC's triage and the licence check (S4.3.6)

Of the findings across the three runs that the agent did not itself dispute, KC rejected eight as false
positives, all driven by the two defects above: Digital-Assistant-SDK's four `SEC-02` findings (mock
credential literals in test code) and the engine repo's `AGT-01`/`EXEC-05`/`NAV-03`/`SEC-02` findings (the
fixture bleed). Digital-Assistant-Server's four overrides were accepted, not rejected — see "Ground truth
corrected" above. Licences: Digital-Assistant-SDK carries no `LICENSE` file (`package.json` declares `ISC`,
not actually present as a file); Digital-Assistant-Server and the engine repo are both `AGPL-3.0`. KC
confirmed on 2026-10-19 that all three repositories are their own, clearing the gate to publish findings
about them.

Full detail in `phase-M4-evaluate-release.md`'s `S4.3.2.1`–`S4.3.6` log entries.
