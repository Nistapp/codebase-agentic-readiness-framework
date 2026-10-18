# Evaluation Results

> **Audience:** Everyone
> **Source of truth:** `artefacts/audit-runs/fixture-sweep/batch{1,2,3}.results.jsonl` (git-ignored run
> artifacts; this page is the durable, published summary). See [Run the Evals](../how-to/run-the-evals.md)
> for the method and [5. Evaluation](../architecture/contributor-deep-dive/05-evaluation.md) for what the
> metrics mean.
> **Status:** Live for the fixture sweep (S4.2). Real-repo results (S4.3) are Planned.

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

## Real-repo runs (S4.3)

Planned. Three repositories (the Digital-Assistant-SDK, the Digital-Assistant-Server, and the engine repo
at `dev`), three runs each with the primary model plus one run with a second harness, per the roadmap's
`S4.3`.
