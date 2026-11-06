# Playbook: `add-baselines-and-ratchet`

> Theme T5 (tests and baselines). Follows the anatomy in [`README.md`](README.md). Written in IR08.1; applied and
> corrected on a Gradle repository (IR08.2) and a multi-component Node repository (IR08.3), and corrected from both.

## Goal

Every kind of existing debt the repository carries is counted, committed as a baseline, and guarded inside the gate
so the count can only go down; the test suite's coverage is measured and held by a floor that can only go up; and
the suite's status and its skip markers are recorded, so an agent can tell old debt from the debt it adds.

**The rule this playbook enforces: a baseline only goes down, a floor only goes up.** Raising a count or lowering a
floor needs the owner, and is recorded as described in [Continue on error](#continue-on-error).

## Checks resolved

| Check | Rubric | Mechanism |
|---|---|---|
| BASE-01 | [07-baselines-and-ratchet.md](../../audit/checks/07-baselines-and-ratchet.md#base-01--baseline-artifact-exists) | Tool-native baselines plus one committed counts file, named in `AGENTS.md` |
| BASE-02 | [07-baselines-and-ratchet.md](../../audit/checks/07-baselines-and-ratchet.md#base-02--current-violation-counts-measured) | Each tool's full-tree count, written down |
| BASE-03 | [07-baselines-and-ratchet.md](../../audit/checks/07-baselines-and-ratchet.md#base-03--no-new-violations-mechanism) | A compare step inside `format:check`, run by CI |
| BASE-04 | [07-baselines-and-ratchet.md](../../audit/checks/07-baselines-and-ratchet.md#base-04--coverage-floor-configured) | Coverage threshold in the test runner's own configuration |
| TST-02 | [10-tests.md](../../audit/checks/10-tests.md#tst-02--suite-status-known-tier-c) | Suite status recorded from a real run |
| TST-03 | [10-tests.md](../../audit/checks/10-tests.md#tst-03--skip--xfail-census) | Skip-marker census, each marker judged |
| TST-04 | [10-tests.md](../../audit/checks/10-tests.md#tst-04--fast-path-documented) | One fenced single-test command in `AGENTS.md` (shared with `adapt-agents-md`) |
| TST-05 | [10-tests.md](../../audit/checks/10-tests.md#tst-05--coverage-configuration-present) | Coverage tool configured and a coverage verb |

TST-04 has two playbooks: this one writes the fenced line when the repository's state files the item under T5;
[`adapt-agents-md`](README.md#playbook-list) (T7) then only verifies it. TST-01 (test verb, suite non-empty) is
[`define-command-surface`](define-command-surface.md)'s. Where ratchet commands go follows
[spec decision 0002](../../../spec/decisions/0002-lint-in-the-gate.md): inside `format:check`, never a new member of
`check`.

## Preconditions

- The state file exists and Stage 1 triage is done. Read it first; respect every `skipped` item and preference.
- **T1 done or `partial`**: the counting tools (formatter, linter, type checker, scanner) and their verbs exist
  ([`configure-quality-tools`](configure-quality-tools.md)). **T4 done or `partial`**: CI runs `check`
  ([`add-ci-parity`](add-ci-parity.md)), so a compare step inside the gate is enforced on every pull request.
- **This theme's input is the debt T1-T4 recorded.** List every `debt` entry on every item in the state
  (`progress.py show`): what, count, baseline file. Each one is a candidate for this playbook's baseline.
- Preferences this playbook reads, when present:

| Key | Effect |
|---|---|
| `format.mass_reformat` | `no` forbids fixing debt in bulk to reach a lower baseline |
| `lint.mode`, `typecheck.*` | The ratchet already chosen in T1; reuse it, do not replace it |
| `tests.stack_dependent` | How tests that need live services are run (see [Stack-dependent tests](#stack-dependent-tests)) |
| `tests.coverage_gate` | `check` (default) or `ci`: where the coverage floor is enforced (asked in Inputs) |
| `check.verify_without_stack` | `yes` means `check` must pass without the local service stack |
| `ci.edits_authorised` | Workflow and build-file edits allowed |
| `ci.pr_by_agent` | The ending ([ADR 0003](../../docs/architecture/adrs/0003-push-and-pr-policy.md)) |
| `baseline.exception.*` | Owner-approved raises recorded earlier; never re-ask for one already recorded |

- A rule that dependency versions stay locked (security-only bumps) forbids upgrading a tool only to get its native
  baseline format. Offer the upgrade as a separate owner choice, never inside this theme.

## Inputs to ask

1. **Inventory existing mechanisms first.** Before proposing anything, list what already freezes debt, and use it:

   | Look for | Example | What it already is |
   |---|---|---|
   | A formatter ratchet | Spotless `ratchetFrom`, a changed-files `format:check` script | Baseline and compare for formatting |
   | An exclude or suppressions list | PMD `<exclude-pattern>` list, Checkstyle `suppressions.xml`, SpotBugs exclude filter | Baseline (the list) and compare (the tool fails on files not listed) |
   | A tool-native baseline file | `eslint-suppressions.json`, `.ruff-baseline`, `.secrets.baseline`, `.gitleaksignore` | Baseline and compare |
   | A debt list read by a script | A strict-mode debt list of files, a docs-lint baseline | Baseline and compare |
   | A budget flag | `--max-warnings N`, `max-issues` | Count and compare in one |
   | A report-only CI step with a recorded count | A dependency or image scan with a review date | A count, not yet a compare |

   The engine sees only some of these (see [Verification](#verification)), but each is a real baseline. The
   playbook's job is to make them complete, counted and named, not to replace them.

2. **Baseline form (the default, owner-approved for this playbook).** Tool-native first: a tool that has its own
   baseline, exclude list or budget flag keeps it. Everything else (a scanner count, a strict-mode error count, a
   report-only step's number) goes into **one committed counts file** under the state folder,
   `docs/agentic-readiness/<label>-quality-baseline.json` (renamed to the repository's own convention when it has
   one), checked by a short compare script that `format:check` calls. Alternatives the owner may choose instead: a
   counts file for every tool (one format, but duplicates native ratchets), or tool-native only (no script, but tools
   without a native form stay unguarded). Record a non-default choice with `pref set baseline.form`.

3. **Coverage gate.** Ask per repository, record `pref set tests.coverage_gate check|ci`:
   - `check` (default): the floor sits in the test runner's configuration and the coverage-instrumented run is part
     of `test`, so local `check` and CI fail on a drop. Costs instrumentation time on every `check`.
   - `ci`: the floor sits in the same configuration, but only a CI coverage step runs it; `check` stays fast.
     Local green can then fail in CI. Suggest it when the suite is slow or needs live services and
     `check.verify_without_stack=yes`.

4. **Coverage floor value.** Measure line coverage on the untouched tree; the floor is that number rounded **down**
   to a whole percent. Never a target the repository fails today. It is raised only by a deliberate commit when the
   measured value is at least one point above the floor; no script rewrites it.

5. **Tool choice when nothing exists.** Offer from the table, recommend, let the owner decide, record the choice.

### Tool currency

Checked 2026-11-05 against the release pages and registries. Re-check before offering a tool; drop one with no
stable release in the last 12 months.

| Tool | Latest | Released | Notes |
|---|---|---|---|
| ESLint bulk suppressions (`eslint-suppressions.json`) | ESLint 10.14.0 | 2026-10-30 | Needs ESLint 9.24+; on older ESLint use a changed-files ratchet or a budget flag |
| JaCoCo (Gradle core `jacoco` plugin) | 0.8.16 | 2026-10-26 | `jacocoTestReport`, `jacocoTestCoverageVerification`; misreports Quarkus `@QuarkusTest` classes on its own |
| `io.quarkus:quarkus-jacoco` | from the Quarkus platform BOM | 2026-11-04 (latest 4.0.0.Beta3) | Quarkus's own coverage for `@QuarkusTest`; version comes from the BOM, no new pin |
| Jest `coverageThreshold` | Jest 30.5.2 | 2026-09-18 | Works in Jest 27 and 29; no upgrade needed |
| Vitest `coverage.thresholds` | 5.1.0 | 2026-11-02 | Vitest repositories only |
| `c8` / `nyc` | 12.0.0 / 18.0.0 | 2026-07 / 2026-02 | Coverage for Node test runners without built-in coverage |
| One counts file + compare script | n/a | n/a | One format for every tool without a native baseline; the script is the repository's own code |

Dropped: `betterer` (latest tag 6.0.0-alpha.1, 2024-12; no stable release in about two years).

## Steps

1. Theme branch from the integration branch, in a worktree. Set each T5 item `in_progress` before touching it.
2. **Measure, report-only.** Run each counting tool once over the full tree, on the untouched branch, in its
   read-only form (the full run T1 left report-only, the strict config, the scanner at its threshold). Record each
   number. Do not fix anything to make a number smaller.
3. **Baseline (BASE-01).** For each tool:
   - it has a native baseline or exclude list (inventory step): check it still matches the count; if the list is
     stale (names files that are now clean), shrink it in its own commit;
   - otherwise add an entry to the counts file: tool, what is counted, count, the command that produced it, the
     date. Keep the file small and readable; one entry per tool.
4. **Compare step (BASE-03).** A short script, in the repository's own language and script folder, reruns each
   counts-file tool, compares with the committed count, and exits non-zero when any count went **up**. When a count
   went down it prints the new number and asks for the counts file to be lowered in the same change (it does not
   rewrite the file itself). Call the script from `format:check` (spec decision 0002). Make sure the CI job that runs
   `check` reaches it; name the counts file in that workflow step or its comment so the link is visible.
5. **Counts written down (BASE-02).** Where a tool has a budget flag, put today's count on the flag in the verb
   (`--max-warnings <N>`) instead of a counts-file entry. Every other count lives in the counts file.
6. **Say it in `AGENTS.md`.** One short paragraph in the quality or commands section, in words an agent and the
   audit both read: name each baseline mechanism and file, say "no new violations: `format:check` compares against
   the quality baseline", and state the rule "a baseline only goes down, a coverage floor only goes up; raising
   either needs the owner".
7. **Coverage (TST-05, BASE-04).** Configure the runner's coverage, add or reuse a coverage verb (`test:cov` or
   similar), measure, set the floor (Inputs 4) in the runner's own configuration, and wire it per
   `tests.coverage_gate`. One floor per component in a multi-component repository.
8. **Suite status (TST-02).** Run `test` once (with the services it needs, through the repository's own start
   scripts) and record the result: green, or the failing tests by name as debt. A separate suite outside `check` (an
   end-to-end suite, for example) that fails to load counts too: record it as one failing suite with 0 tests run, in
   the counts file as an informational entry, and do not fix it inside this theme unless the owner chooses. The engine
   reads TST-02 only from a Tier-C probe; this record is for the agent, not a substitute verdict.
9. **Skip census (TST-03).** List every skip, ignore and expected-failure marker. Judge each one: a test that can be
   fixed is an item for the owner; a deliberate skip gets a one-line reason next to it. Never delete or un-skip in
   bulk. The count is debt with the marker list as its baseline.
10. **Fast path (TST-04)**, when the item is in T5: add the single-test command for the repository's runner to
    `AGENTS.md` in a fenced shell block (the engine reads only fenced commands), for example
    `./gradlew test --tests '<Class>'` or `npx jest <path/to/file.spec.ts>`.
11. Commit per change (baseline, compare step, coverage, docs), each revertible alone.

### Java (Gradle)

Profile: [`stacks/java.md`](../../stacks/java.md#baseline--ratchet).

- **Native baselines.** Spotless `ratchetFrom` is the formatter baseline (its count is the files the full run
  lists). A PMD ruleset `<exclude-pattern>` list is the lint baseline; it only shrinks. Neither needs a counts-file
  entry; both are named in `AGENTS.md`. A scanner count (OSV-Scanner, an image scan) goes into the counts file.
- **Coverage.** Apply the core `jacoco` plugin; `jacocoTestReport` writes the report and
  `jacocoTestCoverageVerification { violationRules { rule { limit { minimum = 0.NN } } } }` holds the floor.
  For `tests.coverage_gate=check`, make `check` depend on the verification task; for `ci`, run it in its own CI step.
- **Quarkus.** `@QuarkusTest` classes run inside the Quarkus application; Gradle's JaCoCo agent alone reports them
  wrongly low, and a floor taken from that number is wrong. Add `io.quarkus:quarkus-jacoco` (test scope, version
  from the platform BOM) and have the verification task read the data file Quarkus writes, following the Quarkus
  test-coverage guide for the repository's Quarkus version. Measure only with that in place. On Quarkus 3.2 with
  Gradle the working wiring is `test { jacoco { excludeClassLoaders = ['*QuarkusClassLoader']; destinationFile =
  <a file under the build directory, for example jacoco-quarkus.exec> } }` plus the `quarkus-jacoco` test dependency; the
  report and verification tasks read that one file. Run the suite twice and check the two numbers are identical
  before setting the floor.
- **Measuring the other counts.** A PMD violation count needs the exclude list taken out of the ruleset (in a scratch
  copy), because with the list in place PMD reports nothing for those files. A Spotless full-tree count has no usable
  output (the tool truncates its list), so run the full format task in a scratch copy and count the files that
  changed against the original. Neither goes into the working tree.
- **Engine blind spot.** BASE-04 reads no Gradle build file, so a correct `jacocoTestCoverageVerification` floor
  still reads `FAIL`. Add one sentence with the floor to `AGENTS.md` ("coverage floor: NN% line coverage, enforced by
  `jacocoTestCoverageVerification`") so the audit reads at least `PARTIAL`, and verify from the build file.
- **Fast path**: `./gradlew test --tests '<package>.<Class>'`, optionally `.<method>`.

### TypeScript and Node

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#baseline--ratchet).

- **Native baselines.** ESLint 9.24 or newer: `eslint-suppressions.json` (`eslint --suppress-all`, without `--fix`),
  committed; ESLint prunes entries that no longer apply with `--prune-suppressions`. Older ESLint: keep the
  changed-files ratchet T1 chose and put the full-run count in the counts file, or a `--max-warnings <N>` budget when
  the debt is warnings only. A strict-mode debt list of files from T1 is a baseline; its error count goes into the
  counts file.
- **Coverage.** Jest: `coverageThreshold.global.lines` (and `branches` only when the owner wants it) in the Jest
  configuration, set to the measured floor; `collectCoverageFrom` limited to source files. Per app in a
  multi-component repository. Create React App passes `coverageThreshold` through its `jest` key in
  `package.json`; check the supported keys for the repository's `react-scripts` version. Vitest:
  `test.coverage.thresholds`.
- **Engine visibility.** BASE-04 reads the root `package.json` and `jest.config.*`/`vitest.config.*` files at any
  depth, not a `jest` key in a nested component's `package.json`. In a multi-component repository either keep the
  key where it is and add the floor sentence to `AGENTS.md`, or (owner choice) move that component's Jest config to a
  `jest.config.*` file. Verify from the real config either way. BASE-02 reads only a budget flag, so a counts file
  alone reads `PARTIAL`, and TST-04 accepts a Jest line only with `-t` or `--testNamePattern`; a path-only
  `npx jest <file>` reads `FAIL` (issues #45 and #50). Write the fast-path block in the form the engine reads and
  keep the path-only form out of the verification.
- **Whole-tree counts in `format:check`.** ESLint older than 9.24 has no baseline file, so the compare script runs
  the linter over the whole tree with JSON output and counts errors and files with errors. That adds the linter's
  full run (15-20 s on a mid-sized app) to `format:check`; say so in the paragraph in `AGENTS.md`. The script resolves
  the counts file by an absolute path, because the verb runs it from the component's directory.
- **Floor measured over every source file.** Create React App's Jest collects coverage from every source file, not
  only imported ones, so its measured number is the honest one; leave `collectCoverageFrom` as measured unless the
  owner asks. `coverageThreshold` in the `jest` key of `package.json` is accepted by `react-scripts` 5; prove it by
  running the suite with the floor one point higher, which must fail.
- **Coverage on in `test`, narrowed runs.** With `tests.coverage_gate=check` the `test` verb runs with coverage, so a
  narrowed run (`npm test -- <name>`) measures only some files and fails the floor. The documented fast path turns
  coverage off (`npm test -- --coverage=false --watchAll=false <file>`) or calls the runner directly
  (`npx jest <file> -t "<name>"`).
- **`npm audit` and other scans**: the count per severity goes into the counts file with the review date already
  recorded; the compare step fails on a higher count, not on any finding. Run it from the report-only scan script
  (the same script that writes the job summary), so the step stays report-only; it can turn red when an advisory is
  published against an unchanged lockfile, by design.
- **Fast path**: `npx jest <path/to/file.spec.ts> -t "<name>"` or `npm test -- <name>`; for Create React App,
  `npm test -- --watchAll=false <pattern>` (add `--coverage=false` when `test` runs with coverage).

### Stack-dependent tests

When the unit suites are mocked and need no live service, there is nothing to start: measure with the plain test verb,
skip the stack lock, and take the default `tests.coverage_gate=check`.

When tests need live services (a database, a search engine), measure coverage with the services up, started
through the repository's own scripts, and leave them as found. Two options to offer the owner, never to do unasked:
a containerised test profile (Quarkus Dev Services or Testcontainers) so tests start their own services, or a
unit-only subset as a fast offline verb. Record the answer in `tests.stack_dependent`. With
`check.verify_without_stack=yes`, the coverage gate goes to CI unless the owner says otherwise.

## Continue on error

| Debt | How it is counted | How it cannot grow |
|---|---|---|
| Lint, format, type-check, scan violations | The tool's full read-only run | Native baseline or counts file, compared in `format:check` |
| Coverage below what the owner wants | Measured line coverage | Floor at today's number, in the runner's config |
| Failing tests | Tests failing in a real run, by name | Recorded; a new failure fails `test` |
| Skip markers | Census of markers, each judged | Marker list as baseline; a new marker is a review item |

Every count is recorded on its item with `--debt what=...,count=N,baseline=FILE`, and the item stays `partial`
until the compare step runs in the gate; after that, an item whose only debt is a guarded baseline is still
`partial` (debt exists), never `done`. A coverage floor is recorded as debt that only goes up:
`--debt "what=coverage floor (line %),count=<NN>,baseline=<config file>"`.

**Owner-approved exception.** When a count must go up or a floor down (a new rule the owner turned on, a large
removal of tested code), the owner approves it, and the same commit that edits the baseline records it twice:

- in the state, `progress.py pref set baseline.exception.<what> "<old>-><new> <YYYY-MM-DD> <reason>" --by owner`;
- in the commit body, `Baseline-Exception: <what> <old>-><new> (approved by owner)`.

An agent never raises a count or lowers a floor on its own. It lowers a count or raises a floor only in a
deliberate commit backed by a fresh measured number.

## Verification

Read the real artefact for every check, not only the engine verdict: the engine credits some file names and
phrases, and misses mechanisms it has no reader for.

| Check | Command or file | Expected | What the engine reads |
|---|---|---|---|
| BASE-01 | The counts file and each native baseline; the `AGENTS.md` paragraph | Each tool with debt has a baseline; the paragraph names them | A `*baseline*.json` name, or a "quality baseline" / "no new violations" sentence in `AGENTS.md` or `CLAUDE.md`: `PASS` |
| BASE-02 | The counts file entries and any budget flag | One number per tool, matching a fresh full run | Only a budget flag (`--max-warnings N`, `max-issues N`) in a manifest or counting config gives `PASS`; a counts file alone reads `PARTIAL` |
| BASE-03 | Raise one count by one in a scratch copy and run `format:check` | Exits non-zero naming the tool; the real tree exits 0 | The counts file named in a CI workflow, or a "ratchet" / "no new violations" sentence: `PASS` |
| BASE-04 | The runner config key and its value; run the coverage verb | Floor equals today's number rounded down; the run passes | Root `package.json`, `jest.config.*`, `vitest.config.*`, Python coverage configs: `PASS`. Gradle and nested `package.json`: `FAIL`, or `PARTIAL` with the `AGENTS.md` sentence |
| TST-02 | The recorded run | Green, or failing tests listed as debt | `UNKNOWN` without a Tier-C probe |
| TST-03 | The marker list | Every marker has a reason or an owner item | Engine `PASS` is a census; the rubric's reading is `FAIL` when the total is above zero |
| TST-04 | The fenced block in `AGENTS.md` | One single-test command for the runner | A fenced single-test command: `PASS` |
| TST-05 | The coverage config and verb | Coverage runs and writes a report | A coverage config, key or `--coverage`/`jacoco` in a script or build file: `PASS` |

Re-run the engine on the branch (`engine.py` against the worktree) and compare with the report; explain every
remaining non-`PASS` with the evidence above.

## Rollback

Revert the per-change commits: the counts file and compare script go together with the `format:check` wiring; the
coverage commit removes the plugin or config keys and the verb; the `AGENTS.md` paragraph goes with the last one. A
shrunk exclude list can stay shrunk.

## Do-not-do

- No mass fix, mass reformat or bulk deletion of skip markers to reach a lower count.
- No suppression of a new violation; a baseline holds today's debt only.
- No coverage floor above today's measured number, and no floor taken from a run known to misreport.
- No upgrade of a tool or runner only to get its native baseline format, without the owner.
- No agent edit that raises a count or lowers a floor; no script that rewrites a baseline or floor by itself.
- No new member of `check` for a ratchet; it goes in `format:check`.
- Do not start or stop services outside the repository's own scripts.

## State updates

```bash
python3 brownfield-recipes/tools/progress.py pref set tests.coverage_gate check \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --commit <sha> --debt "what=PMD violations,count=<N>,baseline=config/pmd/ruleset.xml" \
  --debt "what=dependency advisories,count=<N>,baseline=docs/agentic-readiness/<label>-quality-baseline.json" \
  --verification-command "<format:check verb>" --verification-result "exit 0; exit 1 with one count raised"
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --commit <sha> --debt "what=coverage floor (line %),count=<NN>,baseline=<runner config file>"
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "grep -n -A2 'single test' AGENTS.md" --verification-result "fenced block"
python3 brownfield-recipes/tools/progress.py pref set baseline.exception.<what> "<old>-><new> <YYYY-MM-DD> <reason>" \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py theme T5 --status branch_open \
  --branch agentic-readiness/<phase>-baselines --target <repo> --phase <phase> --render
```

`partial` is reached through `in_progress`, and a `partial` item goes back to `in_progress` before it can end
again. The theme ends per [ADR 0003](../../docs/architecture/adrs/0003-push-and-pr-policy.md): commit on the theme
branch and stop, unless the owner recorded `ci.pr_by_agent=yes`; then push the branch and open one pull request into
the integration branch (`theme T5 --status pr_open --branch B --pr N` after it exists). Never merge. Only the owner
skips an item.
