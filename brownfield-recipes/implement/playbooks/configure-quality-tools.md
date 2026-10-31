# Playbook: `configure-quality-tools`

> Theme T1 (command surface and quality tools). Follows the anatomy in [`README.md`](README.md). Written in
> IR04.1; applied and corrected on a Gradle repository (IR04.2) and a multi-component Node repository (IR04.3).

## Goal

The repository has a formatter, a linter, a type checker in its strictest practical mode and a dependency
scan, each configured in a committed file and reachable through its verb, adopted so that today's code keeps
`check` green and existing debt is counted, recorded and cannot grow.

## Checks resolved

| Check | Rubric | Verb |
|---|---|---|
| TOOL-01 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-01--formatter-configured) | `format`, `format:check` |
| TOOL-02 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-02--linter-configured) | `lint` |
| TOOL-03 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-03--type-checker-configured-strict) | `typecheck` |
| TOOL-04 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-04--dependency--security-scan-verb) | `security` |

The verb names, `check`'s composition and the split of write verbs belong to
[`define-command-surface`](define-command-surface.md). Run both in the same theme branch. TOOL-05 and TOOL-06
(hooks, commit convention) are T4's, not this playbook's.

## Preconditions

- The state file exists and Stage 1 triage is done. Read it first; respect every `skipped` item.
- Preferences this playbook reads, when present: `format.mass_reformat` (`no` forbids reformatting the tree:
  check-only or ratchet), any `format.*`, `lint.*` or `scanner.*` choice already made, `ci.edits_authorised`
  (build-file and CI edits), and any rule that dependency versions stay locked. A step that conflicts stops
  and asks.
- **`security` needs what its scanner reads.** A lockfile-based scanner (OSV-Scanner, `npm audit`) needs a
  tracked lockfile. When it is missing and T2 (`pin-execution-environment`) adds it, the TOOL-04 item is
  `blocked` with reason "needs T2 lockfile", and the `security` verb lands in T2's pull request together with
  the lockfile. Do not pull dependency locking forward into T1 and do not add a placeholder verb.
- The build host meets each tool's own requirement (for example Spotless needs a JDK 17+ host and Gradle 8.1+).
  Check before offering the tool.

## Inputs to ask

1. **Detect first.** Read build plugins, `devDependencies`, config files (`.prettierrc*`, `eslint.config.*`,
   `.eslintrc*`, `biome.json`, `tsconfig.json`, `.editorconfig`, `config/pmd/`, `config/checkstyle/`), the
   style document (`CONVENTIONS.md`, `CONTRIBUTING.md`) and existing CI scan scripts. **A tool the repository
   already has is used, at the version it has.** Upgrading it is not T1 work; offer it only as a separate
   owner choice.
2. **Offer only when nothing exists.** Two to four current options, pros and cons, a recommendation, from the
   tables below. The owner decides; record it with `progress.py pref set`.
3. **Style.** When a style document fixes indentation, line endings or width, the formatter MUST honour it.
   Changing the style document instead is the owner's alternative, never the default.
4. **Adoption mode** for a tool that fails on today's code: ratchet (changed files only) inside `check`, plus a
   report-only full run in CI; or, with the owner's agreement only, the strict full run inside `check`.
   A mass reformat or mass auto-fix is never the default; if the owner wants one, it is its own pull request
   with a `.git-blame-ignore-revs` entry.

### Tool currency

Checked 2026-10-30 against GitHub releases, the Gradle plugin portal and the npm registry. Re-check before
offering a tool; drop one with no release in the last 12 months.

| Tool | Latest | Released | Notes |
|---|---|---|---|
| Spotless Gradle plugin `com.diffplug.spotless` | 8.10.4 | 2026-10-08 | JRE 17+, Gradle 8.1+; `ratchetFrom` built in |
| google-java-format | 1.37.0 | 2026-10-01 | 2-space indent, no options |
| palantir-java-format | 2.102.0 | 2026-10-05 | 120 columns, 4 spaces, no tabs |
| Eclipse JDT formatter (Spotless `eclipse()` step) | ships with Spotless | 2026-10-08 | XML profile, tabs and width configurable |
| PMD | 7.29.0 | 2026-10-30 | Gradle core `pmd` plugin; set `toolVersion` to a 7.x release |
| Error Prone (+ `net.ltgt.errorprone` 5.1.1) | 2.51.0 | 2026-10-22 | `javac` plugin |
| Checkstyle | 14.3.0 | 2026-09-27 | Gradle core `checkstyle` plugin |
| SpotBugs (+ Gradle plugin 6.5.13) | 4.10.5 | 2026-10-12 | Bytecode analysis |
| OSV-Scanner | 2.7.0 | 2026-10-12 | Reads `gradle.lockfile`, `gradle/verification-metadata.xml`, `pom.xml`, npm/pnpm/yarn/bun lockfiles; no API key |
| OWASP Dependency-Check Gradle plugin | 13.0.0 | 2026-08-03 | Needs an NVD API key in practice |
| Trivy | 0.76.1 | 2026-10-21 | `trivy fs`; broad scanner |
| Prettier | 3.9.10 | 2026-10-10 | 181 M weekly downloads |
| ESLint | 10.13.0 | 2026-10-16 | 204 M weekly; `.eslintrc*` removed in 10; bulk suppressions file since 9.24 |
| Biome | 2.6.4 | 2026-10-28 | 25 M weekly; formatter and linter in one |
| TypeScript | 7.0.2 | 2026-07-08 | 402 M weekly; a repository keeps its own major |

Dropped: `audit-ci` (7.1.0, last release 2024-07-03, older than 12 months).

## Steps

1. Same worktree and branch as `define-command-surface`. Set each TOOL item `in_progress` before touching it.
2. Per tool, in this order: formatter, linter, type checker, scan. For each one:
   1. Add the config file (or reuse the existing one) and the dependency, pinned to an exact version.
   2. Point the verb at it (`define-command-surface`).
   3. Run the full read-only form once, on the untouched tree, and count the violations. That count is the debt.
   4. If the count is 0, wire the full run into the verb and `check`. If not, wire the ratchet form into the
      verb used by `check`, add a report-only full run to CI (marked report-only in the step name), and record
      the debt.
3. **Formatter (TOOL-01).** `format` writes, `format:check` reads. With debt, `format:check` checks changed
   files only (ratchet against the integration branch). Never run `format` on the whole tree.
4. **Linter (TOOL-02).** `lint` is read-only; the auto-fix form is a separate write verb. Start with a small,
   bug-oriented ruleset rather than every rule; widening it is a later owner choice.
5. **Type checker (TOOL-03).** Use the strictest mode the codebase passes today. Turning strict on in a
   codebase that fails it is ratcheted (per-file or per-folder), not flipped repository-wide with errors.
   On ecosystems with no strict-mode concept (JVM, Go, Rust), the compiler is the type checker and the engine
   reads TOOL-03 as `UNKNOWN` by design; do not invent a config file.
6. **Scan (TOOL-04).** `security` runs a dependency-vulnerability scan with a fixed severity threshold. It is the
   dependency gate only: secrets scanning (gitleaks and the like) stays in T3 and T4 hooks, not in `security`.
   Reuse a scan command the repository already runs in CI rather than adding a second scanner.

### Java (Gradle)

Profile: [`stacks/java.md`](../../stacks/java.md#tooling-defaults).

| Concern | Options | Recommend |
|---|---|---|
| Formatter | Spotless + Eclipse JDT profile (tabs, any width); Spotless + palantir-java-format (120 columns, spaces); Spotless + google-java-format (2 spaces, no config); change the style document | Eclipse JDT when a style document requires tabs or a custom width; palantir or google when there is no style document |
| Linter | PMD (own `pmdMain`/`pmdTest` tasks, ruleset file); Error Prone (compiler plugin, very few false positives, runs inside `javac`); Checkstyle (style; overlaps a formatter); SpotBugs (bytecode, slower) | PMD first: a standalone read-only `lint` task that can be baselined. Error Prone as the alternative. Checkstyle only when no formatter enforces layout |
| Type check | `compileJava compileTestJava` | This; `-Xlint:all -Werror` later, by owner choice |
| Scan | OSV-Scanner on `gradle.lockfile`; OWASP Dependency-Check (NVD key); Trivy fs; GitHub dependency review (pull requests only) | OSV-Scanner once dependency locking exists (T2); keep an existing OWASP plugin only if the owner has a working NVD key |

- Spotless: `spotless { ratchetFrom 'origin/<integration branch>' }` makes `spotlessCheck` and `spotlessApply`
  touch only files changed since that ref. `formatCheck` depends on `spotlessCheck`, `format` on
  `spotlessApply`. CI needs the integration branch fetched (no shallow clone, or fetch the ref first), or
  `ratchetFrom` fails with "No such reference". Every CI job that has its own checkout and runs the build
  (a code-scanning job included, not only the main build job) needs `fetch-depth: 0`. The full report-only
  run uses a property that disables the ratchet (for example `-PspotlessFull`), read in the build file.
- Eclipse JDT profile: export or write a formatter XML under `config/` that encodes the style document (tabs,
  line endings, width, brace placement), and point `java { eclipse().configFile(...) }` at it.
- PMD: `pmd { toolVersion = '<7.x>'; ruleSetFiles = files('config/pmd/ruleset.xml'); ruleSets = [] }`.
  `lint` depends on `pmdMain` and `pmdTest`. PMD has no baseline file: the ratchet is the ruleset's
  `<exclude-pattern>` list naming each file that has violations today. New files are checked in full; the list
  only shrinks. Applying `pmd` adds `pmdMain` to lifecycle `check`, so the exclude list (or, only by owner
  choice, `ignoreFailures = true` as report-only) must be in place in the same commit.
- `security` depends on the scanner's task or an `Exec` task running `osv-scanner scan -L gradle.lockfile`.

### TypeScript and Node

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#tooling-defaults).

| Concern | Options | Recommend |
|---|---|---|
| Formatter | Prettier; Biome (formatter and linter in one) | Prettier when ESLint stays; Biome only for a new component with no ESLint plugins in use |
| Linter | ESLint (flat config from 9, required from 10); Biome lint | Keep the ESLint the repository has, at its version |
| Type check | `tsc --noEmit` with `strict: true` | This; ratchet strict per folder when today's code fails it |
| Scan | `npm audit --omit=dev --audit-level=high` (built in); OSV-Scanner on the lockfile | `npm audit`, or the exact command the repository's CI scan already runs |

- `format:check` = `prettier --check .` when the tree is clean today, else the same on changed files only
  (`git diff --name-only --diff-filter=ACMR origin/<branch>...HEAD`).
- `lint` = `eslint <paths>` without `--fix`. With debt: on ESLint 9.24 or newer the owner may choose a committed
  `eslint-suppressions.json` (`--suppress-all`, without `--fix`) as the baseline; on older ESLint, lint changed
  files with `--max-warnings=0` in `check`, and run the full lint report-only in CI.
- `typecheck` = `tsc --noEmit -p <config>`. A NestJS scaffold has `strict` off (see the
  [NestJS section](../../stacks/typescript-node.md#nestjs)); count the errors `strict: true` gives before
  proposing the flip, and ratchet if there are any.
- Strict ratchet (TypeScript): `strict: true` does not override an option the base config sets explicitly to
  `false`, so a second config (`tsconfig.strict.json`, extends the base) must set each of those flags to
  `true` itself, or it measures a weaker check than it claims. `tsc` reports errors in imported files, so an
  include list of "clean files" cannot isolate them: include the whole source, run `tsc`, and fail only on
  errors in files absent from a committed debt list (a small script; the list only shrinks, new files are strict
  at once). Count debt with the final config, not with a `--strict` command-line run.
- Changed-files ratchets (`format:check`, `lint`) on a per-app layout: a small script prints the files changed
  since the merge-base with `origin/<branch>` (committed, uncommitted and untracked), the verbs call it, and it
  fails with a clear message when the ref is missing. A writer verb (`format`) that only touches changed files
  keeps `format.mass_reformat=no` safe; a whole-tree writer gets a separate name (`format:all`) and the
  instruction file says it needs the owner's approval.
- A component with no formatter (for example a Create React App component, which bundles only ESLint) gets the
  formatter the other component uses, pinned exact, with the same config; the lockfile diff must be the new
  package only (check `git diff --stat` after `npm install --save-exact`).
- `npm audit` as the `security` verb is red on most real repositories: the item is `partial` (verb exists, debt
  recorded as counts per severity and a review date), never `done`, and the verb stays out of `check`.
- A Create React App component may already be TypeScript and strict: read its `tsconfig.json` before treating
  TOOL-03 as open for it.
- The greenfield [`biome.json`](../../../greenfield-bootstrap/templates/biome.json) and
  [`tsconfig.json`](../../../greenfield-bootstrap/templates/tsconfig.json) templates are references, never
  copied.

## Continue on error

| Debt | How it is counted | How it cannot grow |
|---|---|---|
| Unformatted files | Files the full `format:check` lists | Ratchet on changed files in `check`; full run report-only in CI |
| Lint violations | Violations of the adopted ruleset, full run | Ratchet (changed files, or the exclude or suppressions file); full run report-only in CI |
| Type errors under strict | Errors of the strict run | Strict on for clean folders or files; the rest listed, the list only shrinks |
| Known vulnerabilities | Findings at or above the threshold | `security` fails on new ones; existing ones listed with an owner review date, not suppressed silently |

Record each count on its item (`--debt what=...,count=N[,baseline=FILE]`) and set the item `partial`. T5
(`add-baselines-and-ratchet`) hardens the ratchets and tracks the counts down.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| TOOL-01 | The config file; run `format:check` on the untouched branch | Config present, `format` and `format:check` resolve, `format:check` exits 0 (ratchet) |
| TOOL-02 | The config file; run `lint` | Config present, `lint` resolves, read-only (`git status` clean), exits 0 under the ratchet |
| TOOL-03 | The type-check config; run `typecheck` | Strict flag on where the codebase allows; `typecheck` exits 0. JVM: compile passes; the engine's `UNKNOWN` is expected |
| TOOL-04 | Run `security` | Runs the scanner with its threshold and exits as the scanner says; a `blocked` item names the theme it waits for |

Re-run the engine's TOOL checks on the branch (`engine.py` against the worktree) and compare with the report;
explain every remaining non-`PASS` with the evidence above.

## Rollback

Revert the per-tool commits. Each removes its config file, its dependency and its verb wiring; the ratchet and
report-only CI steps go with them. Nothing outside those files changes.

## Do-not-do

- No mass reformat and no mass auto-fix of the tree, unless the owner chooses it (then its own pull request).
- No rule turned off and no blanket suppression to get green; a baseline file is recorded as debt.
- No dependency upgrade of an existing tool as part of T1.
- No tool the owner did not approve, and no version range: pin exact versions.
- No secrets scanner inside `security`; no placeholder `security` verb.
- Do not put a failing strict check inside `check` without the owner's recorded agreement.

## State updates

```bash
python3 brownfield-recipes/tools/progress.py pref set lint.java pmd --reason "<owner's words>" --by owner \
  --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --commit <sha> --debt "what=PMD violations,count=<N>,baseline=config/pmd/ruleset.xml" \
  --verification-command "./gradlew lint" --verification-result "exit 0 under the exclude list"
python3 brownfield-recipes/tools/progress.py set-status F-nnn blocked --target <repo> --phase <phase> \
  --reason "needs T2 lockfile"
```

`blocked` and `partial` are reached through `in_progress`. An item with debt is never `done`.
Preference keys are lowercase (`^[a-z0-9][a-z0-9._-]{0,63}$`), and a `partial` item cannot go straight to
`done`: set it `in_progress` first.
