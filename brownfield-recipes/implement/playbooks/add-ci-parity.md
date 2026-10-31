# Playbook: `add-ci-parity`

> Theme T4 (CI parity). Follows the anatomy in [`README.md`](README.md). Written in IR07.1; applied and corrected
> on a Gradle/Quarkus repository (IR07.2) and a multi-app Node repository (IR07.3).

## Goal

The gate an agent runs locally is the gate CI runs. CI calls the same verbs (`check`, and `security` where it
exists), every scan or test step either blocks the merge or says in its name that it is report-only with its debt
recorded, and a committed record shows which CI job the platform requires before a merge.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| CI-01 | [06-ci.md](../../audit/checks/06-ci.md#ci-01--pipeline-present-triggered-on-prs) | Verification only in most repositories: a workflow with a pull-request trigger exists. Adds or fixes the trigger block when it does not |
| CI-02 | [06-ci.md](../../audit/checks/06-ci.md#ci-02--localci-parity) | CI runs the local verbs, directly or through a wrapper script that calls them |
| CI-03 | [06-ci.md](../../audit/checks/06-ci.md#ci-03--ci-only-steps-flagged) | Every CI step is a local command; a step that exists only in CI is flagged in its name and in the CI doc |
| CI-04 | [06-ci.md](../../audit/checks/06-ci.md#ci-04--ci-enforces-the-same-gate-as-the-local-check) | No gating step swallows its exit code; non-gating steps are visibly report-only; the required-check wiring is recorded with evidence |

## Preconditions

- The state file exists and Stage 1 triage is done. Read it first; respect every `skipped` item and preference.
- **T1 done:** the verbs exist locally ([`define-command-surface`](define-command-surface.md)). **T2 done:** the
  toolchain CI uses is pinned ([`pin-execution-environment`](pin-execution-environment.md)). If a verb CI should
  call does not exist, stop and report; do not invent a CI-only command.
- Preferences read, when present: `ci.edits_authorised` (a `no` or a scoped value limits which files may change;
  honour the exact scope), `ci.image_scan_debt`, `scanner.choice`, `format.mass_reformat`, `layout.command_runner`,
  `lint.mode`, `security.verb`.
- **Run the drift check first.** A finding quoted from the report can be stale (a step already fixed, a wrapper
  already calling the verb). Re-read the workflow on the current default branch and mark stale items `done` with
  the drift as the reason.
- **Public/private boundary.** Nothing from a private repository or workspace (job names, counts, values) goes
  into an open-source repository's docs, or from any target into the framework.

## Inputs to ask

1. **CI shape.** Detect first: does CI already use wrapper scripts (`scripts/ci/*.sh`, one workflow step per
   script)? If yes, keep the convention.

   | Option | Pros | Cons |
   |---|---|---|
   | Keep wrappers, make them call the verbs (recommended where wrappers exist) | Keeps the repository's CI convention, the required job names and the docs-only skip; the same command runs locally | The engine reads `run:` text only, so it cannot follow a wrapper (engine defects A9 and A11); CI-02 may still read UNKNOWN or FAIL after a correct fix |
   | Call the verbs directly in `run:` | Visible to the engine | Reverses the wrapper convention and moves logic back into YAML |

   Say the engine blind spot to the owner before choosing. Record the answer as a preference.
2. **Scan policy.** Per scan step: blocking now, or report-only with recorded debt (see Continue on error). The
   default is "real scan, blocking where it can be, visibly report-only where debt exists". Making everything
   blocking at once turns CI red until the debt is cleared; leaving a placeholder green is not allowed.
3. **Scanner.** Use the existing one or the `scanner.choice` preference. For a lockfile scan offer OSV-Scanner
   (v2.7.0, 2026-10-12, binary) or the ecosystem's own audit command. Currency checked 2026-10-31 (GitHub
   releases API); re-check when applied. Not a new third-party `uses:` action without owner approval: call the
   pinned binary from the wrapper script the way the repository already runs its secret scanner.
4. **Branch-protection evidence.** The owner or an orchestrator with platform access supplies: protection
   mechanism (classic rule or ruleset), required checks, the up-to-date setting, bypass actors, and whether the
   plan allows protection at all. **A session never guesses these.** If they are not supplied, stop for that part.
5. **Names to preserve:** the merge-gate job name and the docs-only skip (path filter or change-detection job).

## Steps

### Generic

1. **Baseline.** List every workflow job and step with its command, `continue-on-error`, `|| true`, `if:` guard
   and `needs`. List the local verbs and what each runs. Write both as a table in the working notes: this is the
   diff between local and CI.
2. **Trigger (CI-01).** Confirm `pull_request` (or the provider's equivalent). Add it only if missing.
3. **Parity (CI-02, CI-03).** For each local verb the gate needs (`check` composes the read-only ones), make the
   CI step run it. In a wrapper repository: edit the wrapper first so it calls the verb, run the wrapper locally,
   then change the workflow only where a step is missing or must be renamed. Every CI command must exist
   locally; a CI-only step (an image scan, a deploy) is named so (`CI-only: ...`) and listed in the CI doc.
4. **Honest scans (CI-04).**
   - A placeholder that prints "skipped" and exits 0 is replaced by the real scan or deleted with the reason
     recorded. Never leave a green no-op.
   - A step that cannot block yet because of existing debt stays non-blocking **only if** its name says so (for
     example `Scan (report-only)`), it writes the finding count to the job summary, and the debt and a review
     date are recorded in the state file.
   - A blocking scan with debt uses an ignore list with a reason and an expiry per entry, so the gate blocks on
     new findings only.
   - Do not weaken a gate that already blocks.
5. **Merge gate.** The aggregate job (the one the platform requires) lists every blocking job in `needs`, runs
   `if: always()`, and fails on anything but success or skipped. A report-only job stays outside `needs`. Do not
   rename the job; a rename silently un-requires it.
6. **Branch-protection record (CI-04).** Commit a short page in `docs/` (or the repository's CI doc): mechanism,
   required check name, up-to-date setting, bypass actors, the date the owner confirmed, and the exact read-only
   command that re-checks it. If the platform cannot enforce a required check (plan limitation), the page says
   so and lists the mitigations; the check is then recorded `partial`, never `done`.
7. **Lint the workflow** with the repository's workflow linter before pushing. Edit workflows only in a PR.
8. **Verify and commit** per logical change (wrapper, workflow, record), each revertible alone.

### GitHub Actions and Gradle

Profile: [`stacks/java.md`](../../stacks/java.md#boundaries). CI usually runs the build and the tests as separate
wrappers. Make the test wrapper (or a new `check` wrapper) run `./gradlew check`, so formatter, static analysis
and tests run as locally. Lockfile-based dependency scan: the scanner reads the committed lockfile; no Gradle
plugin is needed. Keep the image scan (if any) separate from the dependency scan and name it report-only while
its accepted count is recorded.

### GitHub Actions and multi-app Node

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#boundaries). With a per-app layout
(`layout.command_runner`) there is no root `check`: each app's job runs that app's `format:check`, `typecheck`,
`lint` and `test` verbs through the wrapper, with the same flags as local. A verb that is a ratchet locally
(changed files, strict-clean list) is the same ratchet in CI. `npm audit` with the high threshold is the
`security` verb; while findings exist it is report-only by the rule above. A test suite gated by an environment
flag runs in CI by default (set the flag in the wrapper), and any text saying it stays skipped is corrected.

## Continue on error

- Existing scan findings: counted once with the real scan, recorded as debt on the item (`partial`) with count,
  mechanism (ignore file or report-only step) and review date. The step cannot get worse: a blocking scan fails
  on new findings; a report-only step prints the count so a rise is visible. Never mass-fix, suppress or raise
  an ignore list without a reason and expiry per entry.
- Local verbs that are ratchets or report-only (T1) stay so in CI.
- A plan that cannot enforce required checks: item `partial` with that reason.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| CI-01 | Read the workflow's trigger block | A pull-request trigger |
| CI-02 | Read each CI step and wrapper; run the wrapper locally | Every verb CI runs is the local verb with the same arguments; local run is green |
| CI-03 | `grep -n "continue-on-error\|\|\| true" .github/workflows/*.yml scripts/ci/*.sh` plus the step list | Every CI-only step is named so and listed in the CI doc |
| CI-04 | The same grep; the job summary of a CI run; the branch-protection record | No swallowed gating command; every non-blocking step says report-only and has recorded debt; the record names the required check, or says protection cannot be enforced |

The engine reads `run:` text only. After a correct wrapper-based fix a re-audit can still read CI-02 or CI-03
wrongly (defects A9 and A11), and CI-04 needs the platform confirmation: say so in the status and let the
re-audit annotation (IR14) point at the open issues.

## Rollback

`git revert` the commits: wrapper, workflow and record revert alone. A reverted scan returns to its prior state,
but a reverted placeholder is a green no-op again: record that in the PR.

## Do-not-do

- Do not add a third-party `uses:` action without owner approval; do not install a scanner the owner has not
  approved.
- Do not rename the merge-gate job, drop a job from its `needs`, or lower a gate that already blocks.
- Do not leave a green no-op (a step that prints "skipped" and exits 0), and do not hide debt: a non-blocking
  step says so in its name.
- Do not claim a required check exists without the owner-supplied evidence; do not mark CI-04 `done` where the
  platform cannot enforce it.
- Do not edit workflows outside a PR, or beyond the scope of `ci.edits_authorised`.
- Do not mass-fix findings the scan reveals.

## State updates

```bash
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "<wrapper or grep>" --verification-result "<result>"
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --debt "what=dependency findings,count=<n>,baseline=<file>" --note "<report-only step, review date>"
python3 brownfield-recipes/tools/progress.py pref set ci.shape <wrappers-call-verbs|direct> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py pref set ci.edits_authorised <value> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py theme T4 --status branch_open \
  --branch agentic-readiness/<phase>-ci-hooks --target <repo> --phase <phase> --render
```

Only the owner skips an item.
