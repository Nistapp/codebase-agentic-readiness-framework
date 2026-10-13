# Tests (`TST`)

> Follows the anatomy in [`README.md`](README.md). Five checks, all `method: automated`. See
> [Why These Checks §11](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#11-tests-tst)
> for the consequence behind this family: verification is the single biggest lever on agent output, so a
> suite that is absent, unknown, weakened or slow to subset undoes most of what the rest of Phase 1 buys.
> Every check reads the engine's `TST` pack (`deterministic-audit/audit/rules/checks/tst.py`), whose
> module docstring names each check's own `UNKNOWN` conditions and its deliberate limits (test-file
> discovery is the scan's own classification; marker and fast-path/coverage detection are textual pattern
> matches, not a parse). The `test` verb is read the same way `CMD`/`CI`/`TOOL` read it, through the
> shared `resolve_verbs` helper, so the four families cannot drift on what "the test verb" means.

---

## TST-01 — Test verb exists, suite non-empty

Why it matters   An agent cannot verify a change it cannot run; a resolvable `test` verb and a real suite
                  are the floor every other test check stands on
                  ([greenfield-bootstrap/README.md § 3.2 Testing Policies](../../../greenfield-bootstrap/README.md#32-testing-policies-enforced-via-agentsmd)).
Severity         BLOCKER
Engine           `TST-01`. Resolves the `test` verb through the same `resolve_verbs` table `CMD`/`CI`/
                 `TOOL` use, and counts test-source files: a source file the scan classifies `Kind.TEST`
                 (by a `test_`/`_test.`/`.test.`/`.spec.`/`tests/`/`test/`/`__tests__/` convention),
                 restricted to a fixed set of source suffixes so a config file such as
                 `vitest.config.ts` or `tsconfig.test.json` is never counted as a test. A verb that
                 resolves with no matching file, or files with no resolvable verb, is `PARTIAL` (half the
                 surface exists); neither, with a recognised ecosystem, is `FAIL`; neither with **no**
                 recognised ecosystem is `UNKNOWN` — an unrecognised repository is not proof that no
                 suite exists. Distrust a `FAIL`/`PARTIAL` naming "no test file" when the suite is laid
                 out under a convention the scan's classification does not recognise — verify by reading
                 the test runner's own configuration for where it points before trusting the absence.
Method           automated
Look for         The resolved `test` verb binding (runner and command); every test-source file the scan
                 classifies `Kind.TEST`, filtered to source suffixes, plus the framework-specific globs
                 (`*_test.go`, `tests/*.rs`).
Rubric           PASS: a `test` verb resolves and at least one test-source file exists.
                 PARTIAL: a `test` verb resolves but no test-source file exists, or test-source files
                 exist but no `test` verb resolves.
                 FAIL: no `test` verb resolves and no test-source file exists, with a recognised
                 ecosystem.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no `test` verb resolves, no test-source file exists, and no ecosystem is
                 recognised at all.
Evidence to cite A `command` evidence item for the resolved verb (binding + note) on a PARTIAL that has a
                 verb; `file` evidence items for the test files found (up to 12) on a PARTIAL that has
                 files; for FAIL, a `file` evidence item for a representative repository path (there is
                 nothing more specific to cite for a true absence).
Absence proof    A FAIL states plainly that no verb resolves and no test-source file matches any
                 convention, citing the search the scan already performed (its classification pass) as
                 the proof of absence rather than re-running a separate search.
Remediation      `define-command-surface`
Pitfalls         A PARTIAL with a verb but no files, and a PARTIAL with files but no verb, are different
                 defects with different fixes (add a test file vs. define the verb) — read which
                 half of the pair the finding actually names before writing remediation; do not treat
                 both as the same gap.

## TST-02 — Suite status known (Tier C)

Why it matters   Whether the suite is green *today* determines what an agent can safely attempt; without
                  this an agent inherits a red baseline and cannot tell its own regressions from yours
                  ([greenfield-bootstrap/README.md § 3.2 Testing Policies](../../../greenfield-bootstrap/README.md#32-testing-policies-enforced-via-agentsmd)).
Severity         DEGRADER
Engine           `TST-02`, the pack's only Tier-C probe. No `test` verb resolves ⇒ `UNKNOWN` outright —
                 there is nothing to run (this is `TST-01`'s own finding, not doubled here). When a verb
                 resolves, the engine runs it as a read-only `ProbePlan`; the probe is refused unless
                 `--run-gates` **and** `--allow-probe test` were both given, and a refusal is recorded in
                 the report's `probes` array with the verdict `UNKNOWN`, never an error or a `FAIL`
                 (`deterministic-audit/AGENTS.md` §2.2, ADR-0002). A timed-out probe is also `UNKNOWN`.
                 Exit 0 is `PASS`; any other exit is `FAIL`. **When probes are off** (the default for the
                 audit recipe, which never requests `--run-gates`), this check is `UNKNOWN` on every run,
                 and the agent does not attempt its own run of the suite as a substitute — running the
                 target's own tools outside the engine's Tier-C runner is the one thing this recipe never
                 does (root `AGENTS.md` § Boundaries: "Never run another repository's own commands
                 directly while auditing it"). Record the `UNKNOWN` as the honest state, with the test
                 verb's binding cited as what *would* run if a Tier-C pass were requested; do not infer
                 a status from `TST-03`'s census or from CI's own last recorded run.
Method           automated
Look for         Whether the recorded run was permitted at all (`probes[]` in the report, or the launcher
                 flags passed); if permitted, the probe's exit code and duration.
Rubric           PASS: the test verb was run as a Tier-C probe and exited 0.
                 PARTIAL: not used by this check — the probe's own outcome is binary once it runs.
                 FAIL: the test verb was run as a Tier-C probe and exited non-zero.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no `test` verb resolves; the probe was refused (Tier C not requested, or
                 `test` not in `--allow-probe`); or the probe timed out.
Evidence to cite A `command` evidence item citing the run command, exit code and `captured_by` for
                 PASS/FAIL; for a refusal, cite the `probes[]` entry's own refusal reason verbatim rather
                 than restating it.
Absence proof    Not applicable in the Tier-C-off case — the refusal reason recorded in `probes[]` is
                 itself the record of why no run happened, so no separate search is performed.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `TST-02`); a `FAIL`
                 points at whichever test is failing, which is specific to the run, not a generic fix.
Pitfalls         A green CI run is not evidence for this check — `TST-02` is this run's own Tier-C
                 execution, not a historical signal, and the two can disagree (a flaky suite, an
                 environment difference). Do not upgrade an `UNKNOWN` to `PASS` on CI's say-so.

## TST-03 — Skip / xfail census

Why it matters   A suite weakened with skip and expected-failure markers to reach green is the fingerprint
                  of a gate that no longer catches the regressions it was meant to
                  ([greenfield-bootstrap/README.md § 3.2 Testing Policies](../../../greenfield-bootstrap/README.md#32-testing-policies-enforced-via-agentsmd)).
Severity         DEGRADER
Engine           `TST-03`. Counts skip/ignore/expected-failure markers (`@pytest.mark.skip`, `it.skip`,
                 `#[ignore]`, `@Disabled`, and their per-language-family equivalents) across every
                 readable test-source file, grouped by family (javascript/vitest/jest/mocha, python, go,
                 rust, jvm). **The engine's own verdict is a census, never a verdict on the count**: it
                 returns `PASS` whenever at least one test file was read, whatever the total is, and
                 `UNKNOWN` only when no test file exists or none could be read. It never returns `FAIL`,
                 even when the total is large. REQ-SH-047 ("the test suite MUST NOT contain skipped,
                 ignored or expected-failure tests") is stricter than the engine enforces — **always
                 distrust an engine `PASS` here**: read the census total the engine's `data` payload
                 reports, and override to `FAIL` (with `override_reason`) whenever that total is greater
                 than zero, citing the breakdown as the counter-evidence. An engine `PASS` with total `0`
                 is the only reading that should stand unoverridden.
Method           automated
Look for         The engine's own `Counter` payload (`value`, `unit: "skip/xfail markers"`, and the
                 per-family `breakdown`) attached to the `TST-03` outcome; read it directly rather than
                 re-counting the markers independently.
Rubric           PASS: the census total is zero.
                 PARTIAL: not used by this check — the override is binary (zero or not).
                 FAIL: the census total is greater than zero (an agent override of the engine's own
                 `PASS`, per A2: engine-first with counter-evidence).
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no test-source file exists, or none of the test-source files found could
                 be read — matches `TST-01`'s own absence state, not a separate finding.
Evidence to cite An `index_query` or `file` evidence item citing the engine's `Counter` payload verbatim
                 (the total and the per-family breakdown) as the override's counter-evidence.
Absence proof    Not applicable to a FAIL here — the census total itself, read from the payload, is the
                 evidence; an UNKNOWN cites the test-file absence `TST-01` already recorded.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `TST-03`); each
                 marker needs its own judgment (fix the test, or document why the skip is deliberate), so
                 note the specific markers found rather than pointing at a generic playbook.
Pitfalls         A marker pattern matched inside a string literal or a comment is still counted — this is
                 a deliberate census limit (`tst.py`'s own docstring), acceptable for a count but not a
                 reason to distrust a nonzero total; do not discount the total on the theory that some
                 hits might be false positives without reading them.

## TST-04 — Fast path documented

Why it matters   Agent iteration speed is the workflow; without a documented single-test invocation an
                  agent waits out the whole suite per attempt, or stops running tests altogether
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         DEGRADER
Engine           `TST-04`. With no test-source file at all, this is `UNKNOWN` — there is no suite for a
                 fast path to act on, and the absence is `TST-01`'s own finding, not doubled here. With at
                 least one test file, reads the four entry documents (README.md, AGENTS.md, CLAUDE.md,
                 CONTRIBUTING.md) for a fenced shell command matching a per-runner single-test/subset
                 pattern (`pytest -k`, `pytest ... ::Name`, `npm test -- <name>`, `go test -run`,
                 `cargo test <name>`, `gradlew ... --tests`, `mvn -Dtest=`, and more), deliberately
                 excluding a plain full-suite invocation (`npm test`, `pytest` alone), which is `TST-01`'s
                 concern, not this one's. Distrust a `FAIL` when the fast path is documented in a doc file
                 outside the fixed four — verify by reading whichever onboarding doc the repository
                 actually points to.
Method           automated
Look for         A fenced shell command in README.md, AGENTS.md, CLAUDE.md or CONTRIBUTING.md matching a
                 single-test/subset invocation pattern for the detected runner.
Rubric           PASS: at least one entry document shows a single-test/subset invocation.
                 PARTIAL: not used by this check — the engine's own outcome is binary once a test file
                 exists.
                 FAIL: at least one test file exists, the entry documents are readable, and none shows a
                 single-test/subset invocation.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no test-source file exists at all (owned by `TST-01`).
Evidence to cite A `file` evidence item citing the doc, line and matched command for PASS; for FAIL, the
                 scope searched (which of the four entry documents were present) as the evidence read.
Absence proof    A FAIL states the search scope explicitly (which entry documents were present and
                 read), so "none shows a fast path" is a checked claim, not an assumption.
Remediation      `adapt-agents-md`
Pitfalls         A documented full-suite command (`npm test`, `pytest`) is not evidence for this check
                 even when it is the only command shown — the pattern set deliberately excludes it, so a
                 `FAIL` next to an otherwise well-documented test section is not a contradiction.

## TST-05 — Coverage configuration present

Why it matters   A ratchet (`BASE-03`) needs a number to hold the line on, and coverage is the number for
                  the test surface; with none configured there is no floor to hold
                  ([greenfield-bootstrap/README.md § 3.1 vitest.config.ts](../../../greenfield-bootstrap/README.md#31-vitestconfigts--with-coverage)).
Severity         COSMETIC
Engine           `TST-05`. Looks for coverage configuration by several independent routes: a dedicated
                 config file (`.coveragerc`, `.nycrc`, `.c8rc`, `codecov.yml`, and others), a `coverage`
                 key inside a runner config (`vitest`/`jest`/`vite`/`karma`), a package script or resolved
                 verb invoking a coverage tool (`--coverage`, `--cov`, `c8`, `nyc`, `jacoco`), or a
                 `[tool.coverage]`/`[coverage]` section in `pyproject.toml`/`setup.cfg`/`tox.ini`. This
                 check runs regardless of detected ecosystem — there is no `UNKNOWN` path. **Coverage is
                 never run** — that would be Tier C, and this check reads configuration only. Distrust a
                 `FAIL` where the coverage tool used is one the pattern list does not yet name — verify by
                 reading the resolved test command directly.
Method           automated
Look for         The fixed coverage-config filename set, at any depth for the dedicated files; runner
                 configs and `pyproject.toml`/`setup.cfg`/`tox.ini` for a coverage section or key; package
                 scripts and resolved verbs for a coverage-invoking flag or tool name.
Rubric           PASS: any one of the routes above finds coverage configured.
                 PARTIAL: not used by this check — the engine's own outcome is binary.
                 FAIL: none of the routes finds coverage configured.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — the configuration scan runs unconditionally.
Evidence to cite A `file`/`command` evidence item per route that matched, for PASS (the config file, the
                 package script, or the resolved verb's command).
Absence proof    A FAIL states that none of the routes (dedicated file, runner config key, package
                 script/verb, language-section) found coverage configured, which stands as the search
                 record since each route was checked.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `TST-05`); note the
                 route appropriate to the detected runner inline rather than pointing at a generic
                 playbook.
Pitfalls         Coverage *configured* is not coverage *enforced* — this check and `BASE-04` (a coverage
                 floor in the test runner's own configuration) read overlapping but distinct evidence; a
                 `PASS` here does not imply `BASE-04` also passes, and the two should be read together,
                 not substituted for one another.
