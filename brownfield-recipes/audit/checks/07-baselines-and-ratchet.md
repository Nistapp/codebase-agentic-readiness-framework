# Baselines and the Ratchet (`BASE`)

> Follows the anatomy in [`README.md`](README.md). Four checks, all `method: automated`. See
> [Why These Checks §8](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#8-baselines-and-the-ratchet-base)
> for the consequence behind this family: a brownfield repository arrives with debt, and the
> framework's answer is not "fix it" but "freeze it and do not add to it" — instrumentation
> (`BASE-01`/`BASE-02`) must land before enforcement (`BASE-03`/`BASE-04`) can exist. No MVP playbook
> covers this family yet (backlog: `add-baseline-and-ratchet`); each check's **Remediation** says what
> to commit directly in the meantime. [REQ-BF-004](../../../spec/readiness-requirements.md#req-bf-004--baseline-is-adequate)
> (the owner attests the baseline is adequate) has no check in this family or any other — it is
> verified `attested`, never `automated`, so no `BASE-*` check judges whether an existing baseline's
> content is itself acceptable, only whether one exists, is measured, and is guarded.

---

## BASE-01 — Baseline artifact exists

Why it matters   Gates cannot be turned on over existing debt without mass failure; instrumentation
                  that separates old debt from new debt must land first
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `BASE-01`. Matches a fixed set of baseline/suppression artifact names at any depth
                 (`.eslint-baseline*`, `.ruff-baseline*`, `.mypy-baseline*`, `baseline.json`,
                 `*baseline*.json`, `*baseline*.xml`, `coverage-baseline.*`, `*.baseline`,
                 `.secrets.baseline`, `.snyk`, `.gitleaksignore`), or a documented equivalent mechanism
                 in `AGENTS.md`/`CLAUDE.md` (a sentence matching "quality baseline", "no new
                 violations", "violation budget", or similar). Either is `PASS`. Neither, but a lint/
                 type-check/security tool is configured (so a baseline *could* be produced), is
                 `PARTIAL`. Neither, with a recognised ecosystem, is `FAIL`. Distrust a `FAIL` when the
                 project names its baseline artifact something this fixed list does not carry — verify
                 by reading the project's own documentation for how it tracks existing debt.
Method           automated
Look for         Any filename matching the fixed baseline-artifact glob list, at any depth; failing
                 that, `AGENTS.md`/`CLAUDE.md` for a documented equivalent mechanism.
Rubric           PASS: a baseline/suppression artifact is committed, or an equivalent mechanism is
                 documented in `AGENTS.md` or `CLAUDE.md`.
                 PARTIAL: no artifact or documented mechanism exists, but a lint, type-check or security
                 tool is configured (`BASE-01`'s own counting-tool reader) that could produce one.
                 FAIL: no artifact, documented mechanism, or counting tool exists and the repository has
                 a recognised ecosystem.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem or project configuration exists at all, so a
                 baseline cannot be ruled out.
Evidence to cite A `file` evidence item citing the baseline artifact's path, or the `AGENTS.md`/
                 `CLAUDE.md` file in which the documented mechanism was found; for `PARTIAL`, the
                 counting-tool config files found instead.
Absence proof    A FAIL cites `<repository>` as the evidence that no artifact of any name in the fixed
                 list, and no documented mechanism, was found — the glob list itself is the absence
                 search, since every pattern in it was checked.
Remediation      No MVP playbook yet (backlog: `add-baseline-and-ratchet`). Commit a baseline or
                 suppression artifact (for example `baseline.json`, an eslint/ruff baseline, or
                 `.gitleaksignore`), or document the equivalent mechanism in `AGENTS.md`.
Pitfalls         A filename match is not a content check — `baseline.json` existing is evidence the
                 mechanism exists, not that its content is current or adequate (that is
                 [REQ-BF-004](../../../spec/readiness-requirements.md#req-bf-004--baseline-is-adequate)'s
                 territory, and it has no automated check at all). Do not read a stale or empty baseline
                 file as grounds to downgrade this check's `PASS` — currency is out of scope here.

## BASE-02 — Current violation counts measured

Why it matters   The baseline must be a number, not an impression, or there is no way to tell whether
                  debt is growing or shrinking
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `BASE-02`. The audit never runs the target's own tools (that would be Tier C), so the
                 only count it can point at exactly is an explicit numeric budget already committed to
                 text: `--max-warnings N`, `max-issues`/`max-problems` with a number, or a `violation
                 budget` with a number, read from the runner manifests and the counting-tool configs.
                 A committed baseline artifact or a configured counting tool is a *mechanism*, not a
                 *count*, so it earns only `PARTIAL`, never `PASS`. This check never returns `FAIL`: the
                 audit cannot prove no count exists anywhere the target's own tooling might record one,
                 so the weakest finding it can respect is `PARTIAL`. Every verdict's `summary` states the
                 method used (`static configuration scan; the target's own tools are never run`), so a
                 reader knows this is not a live count. Distrust a `PARTIAL` when the project's quality
                 tool actually does track a number the engine's budget pattern does not recognise —
                 verify by running the tool (Tier C, opt-in) or reading its own report artifact directly.
Method           automated
Look for         Every runner manifest and counting-tool config for an explicit numeric budget pattern;
                 failing that, every lint/type-check/security config and baseline artifact as the
                 weaker, mechanism-only evidence.
Rubric           PASS: an explicit numeric violation budget is committed somewhere the engine reads
                 (`--max-warnings 12`, `max-issues: 5`, `violation_budget = 40`).
                 PARTIAL: a counting surface exists (a configured tool, or a baseline artifact) but no
                 numeric budget is committed; or no counting surface exists at all, in a recognised
                 repository.
                 FAIL: not used by this check — the audit cannot run the target's own tools, so it can
                 never positively prove a count does not exist anywhere.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem or counting configuration exists at all, so a
                 count cannot be ruled out.
Evidence to cite A `file` or `command` evidence item citing the manifest or config where the numeric
                 budget was read, with `note` quoting the matched pattern; for `PARTIAL`, the counting
                 surface found instead.
Absence proof    A PARTIAL cites `<repository>` (when no counting surface exists at all) or every
                 counting-tool config and baseline artifact found (when a surface exists but no number
                 does) as the evidence that no numeric budget pattern matched any of them.
Remediation      No MVP playbook yet (backlog: `add-baseline-and-ratchet`). Commit the count or configure
                 a budget (`--max-warnings N`, `max-issues`, or a `violation budget`) so a regression has
                 a baseline number to compare against.
Pitfalls         `FAIL` never appears for this check by design — reading a `PARTIAL` as a weaker version
                 of a possible `FAIL` the engine declined to give is correct; reading it as "almost a
                 pass" is not. A project whose tool genuinely tracks a count the engine's pattern cannot
                 see (a CI artifact uploaded but not committed as text) is a real gap in this check's
                 coverage, not a defect to excuse away with a more lenient verdict.

## BASE-03 — No-new-violations mechanism

Why it matters   The policy must be executable, not aspirational, or every change quietly adds a little
                  more debt on top of what was already frozen
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `BASE-03`. A ratchet exists when a numeric violation budget is committed (`BASE-02`'s
                 own evidence), or a baseline artifact (`BASE-01`'s own evidence) is referenced by name
                 inside a CI workflow (a comparison step), or a comparison step is documented in
                 `AGENTS.md`/`CLAUDE.md`/`README.md`/`CONTRIBUTING.md` (a sentence matching "ratchet",
                 "no new violations", or "compare ... baseline"). Any of these is `PASS`. A baseline
                 artifact exists but none of the three is found is `FAIL` — the debt is measured but not
                 guarded, which this check treats as a real defect, not a softer gap. No measurement
                 surface at all (no budget, no baseline, no counting tool) is `PARTIAL`: there is nothing
                 yet for a ratchet to compare against, so the absence is not yet proof of a missing
                 policy, only of an earlier gap `BASE-01`/`BASE-02` already own. Distrust a `FAIL` when
                 the CI workflow references the baseline artifact in a form the engine's name-matching
                 does not catch (an environment variable holding the filename rather than the literal
                 name) — verify by reading the workflow step directly.
Method           automated
Look for         The numeric budget evidence `BASE-02` already found; every CI workflow's text for the
                 baseline artifact's own filename; `AGENTS.md`/`CLAUDE.md`/`README.md`/`CONTRIBUTING.md`
                 for a documented comparison-step sentence.
Rubric           PASS: a numeric violation budget is committed, or a committed baseline artifact is
                 referenced by name inside a CI workflow, or a comparison step is documented in one of
                 the four entry documents.
                 PARTIAL: no budget, baseline artifact or counting tool exists at all, in a recognised
                 repository — nothing yet for a ratchet to compare against.
                 FAIL: a baseline artifact is committed but nothing compares against it (no budget, no CI
                 reference, no documented comparison step).
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem or configuration exists at all, so a ratchet
                 cannot be ruled out.
Evidence to cite A `file` or `command` evidence item citing the budget's source, the CI workflow file
                 that references the baseline, or the entry document whose text documents the
                 comparison step.
Absence proof    A FAIL cites every committed baseline artifact as the evidence that a mechanism exists
                 to guard, paired with the absence of a budget, a CI reference to that artifact's name,
                 or a documented comparison step — all three were checked and none matched.
Remediation      No MVP playbook yet (backlog: `add-baseline-and-ratchet`). Once a baseline exists, wire
                 a comparison step — the audit's own `--baseline REPORT.JSON` is the reference pattern,
                 or a CI job that diffs today's count against the committed one — so new findings fail
                 the build.
Pitfalls         A `PARTIAL` here (no measurement surface at all) and a `FAIL` (measured but not guarded)
                 are different defects with different remediation paths — the first needs `BASE-01`/
                 `BASE-02` fixed first, the second needs only a comparison step added on top of what
                 already exists; do not collapse the two into one finding.

## BASE-04 — Coverage floor configured

Why it matters   Coverage is the most common form of the ratchet, and without a configured floor it
                  decays invisibly, one untested branch at a time
                  ([greenfield-bootstrap/README.md § 4.1 Workflows](../../../greenfield-bootstrap/README.md#41-workflows)).
Severity         DEGRADER
Engine           `BASE-04`. Reads test-runner configuration directly for a coverage threshold:
                 `.coveragerc`/`setup.cfg`/`tox.ini`/`pytest.ini`/`pyproject.toml`'s `fail_under` or
                 `--cov-fail-under`, `package.json`'s `coverageThreshold`/`--cov-fail-under`, or
                 vitest/jest/vite/karma config's `coverageThreshold`/`thresholds`/`fail_under`
                 (JavaScript `//` comments are stripped first, so a commented-out threshold is not
                 read as configuration). A configured threshold is `PASS`. A threshold stated only in
                 prose (`AGENTS.md`/`CLAUDE.md`/`README.md`/`CONTRIBUTING.md`, matched by a pattern
                 for "coverage ... threshold/minimum/floor" or a bare percentage near the word
                 "coverage") is `PARTIAL`. Neither, with a recognised ecosystem, is `FAIL`. Distrust a
                 `FAIL` when the threshold is enforced by a CI step reading a coverage report and
                 failing the job outside the test-runner config itself (a separate coverage-gate action)
                 — verify by reading the CI workflow for that step.
Method           automated
Look for         The test-runner's own coverage configuration keys, read directly, not inferred from the
                 test framework's mere presence; failing that, the four entry documents' prose for a
                 stated threshold.
Rubric           PASS: a coverage threshold is configured in test-runner configuration.
                 PARTIAL: a coverage threshold is described in prose only, in one of the four entry
                 documents, with no matching test-runner configuration.
                 FAIL: no coverage threshold is configured and none is documented in prose, and the
                 repository has a recognised ecosystem.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem or test-runner configuration exists at all, so a
                 coverage floor cannot be ruled out.
Evidence to cite A `file` evidence item citing the config file and the matched key (`pyproject.toml:
                 fail_under`, `vitest.config.ts: thresholds`), or, for `PARTIAL`, the entry document and
                 the matched line of prose.
Absence proof    A FAIL cites `<repository>` as the evidence that no threshold-bearing config key, and no
                 prose statement in any of the four entry documents, was found.
Remediation      No MVP playbook yet (backlog: `add-baseline-and-ratchet`). Configure a coverage floor
                 for the test runner (`coverage.fail_under`, `--cov-fail-under`, `coverageThreshold`, or
                 a vitest/jest `thresholds` block) so a drop fails the gate.
Pitfalls         A coverage percentage mentioned in prose as a historical fact ("we're at 80% today") is
                 not the same as a stated floor ("coverage must stay above 80%") — the prose pattern this
                 engine matches is deliberately loose, so read the surrounding sentence before trusting a
                 `PARTIAL` as evidence of an actual, enforced-in-intent threshold rather than a status
                 report.
