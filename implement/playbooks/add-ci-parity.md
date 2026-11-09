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
| CI-05 | [06-ci.md](../../audit/checks/06-ci.md#ci-05--workflow-files-are-linted) | A workflow linter that knows the CI provider runs from the local surface and in CI |

## Preconditions

- The shared procedure in `SKILL.md` applies: [Stage 3](../SKILL.md#stage-3-apply) (state read first, drift first,
  worktree, one item at a time) and [Stage 4](../SKILL.md#stage-4-close-the-theme) (engine re-check, gate, ending).
- **T1 done:** the verbs exist locally ([`define-command-surface`](define-command-surface.md)). **T2 done:** the
  toolchain CI uses is pinned ([`pin-execution-environment`](pin-execution-environment.md)). If a verb CI should
  call does not exist, stop and report; do not invent a CI-only command.
- Preferences read, when present: `ci.edits_authorised` (a `no` or a scoped value limits which files may change;
  honour the exact scope), `ci.image_scan_debt`, `scanner.choice`, `format.mass_reformat`, `layout.command_runner`,
  `lint.mode`, `security.verb`, `ci.workflow_linter`, `hooks.manager`.
- **Drift** ([Stage 3](../SKILL.md#stage-3-apply), step 2): a step already fixed or a wrapper already calling the verb
  makes a finding stale; re-read the workflow on the current integration branch.

## Inputs to ask

1. **CI shape.** Detect first: does CI already use wrapper scripts (`scripts/ci/*.sh`, one workflow step per
   script)? If yes, keep the convention.

   | Option | Pros | Cons |
   |---|---|---|
   | Keep wrappers, make them call the verbs (recommended where wrappers exist) | Keeps the repository's CI convention, the required job names and the docs-only skip; the same command runs locally | The engine reads `run:` text only, so it cannot follow a wrapper (known engine defects); CI-02 may still read UNKNOWN or FAIL after a correct fix |
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
6. **Workflow linter (CI-05).** Detect first and keep a linter that already runs. Look in Makefile targets,
   `package.json` scripts, hooks (`.husky/`, `.pre-commit-config.yaml`, `lefthook.yml`) and CI steps. If there is
   none, choose the linter by CI provider and the route by stack (the stack profile's Tooling defaults).
   Currency checked 2026-11-09 (GitHub releases API, PyPI); re-check when applied.

   | Provider | Recommend | Version, date | Notes |
   |---|---|---|---|
   | GitHub Actions | actionlint, plus zizmor for security | actionlint v1.7.12, 2026-03-30; zizmor 1.32.0, 2026-11-02 | actionlint checks syntax, expressions and action inputs; zizmor finds script injection and over-broad permissions. One is enough for CI-05; offer both |
   | GitLab, Azure, Bitbucket, CircleCI, Buildkite | check-jsonschema with the provider's built-in schema | 0.39.0, 2026-10-26 | Offline. `glab ci lint` and `circleci config validate` also count but need the platform CLI |
   | Jenkins | none offline | — | CI-05 reads `UNKNOWN`; say so, add nothing |

   | Stack | Local route |
   |---|---|
   | Node with Husky | a `lint:workflows` script, called from `.husky/pre-commit` when workflow files are staged |
   | Python with pre-commit | the `actionlint` hook (`rhysd/actionlint`), `zizmorcore/zizmor-pre-commit`, or check-jsonschema's `check-github-workflows` / `check-gitlab-ci` hooks |
   | Make, Gradle, lefthook or mixed | a `workflow-lint` target or lefthook command that runs the linter on the workflow folder |

   Each developer installs the linter once. Pin its version where the repository pins its other dev tools, never
   in the workflow alone. Record the choice as the preference `ci.workflow_linter`.

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
7. **Workflow lint (CI-05).** Add the chosen linter to the local surface (the route from Inputs 6). Run the same
   command in CI as a blocking step, beside the gate. Prefer calling the local command over a third-party
   `uses:` action; an action needs the owner's approval. Fix what the linter reports in the workflows you edit.
   Record older findings as debt, as for scans. Lint every workflow you changed before pushing. Edit workflows
   only in a PR.
8. **Commits:** wrapper, workflow, record.

### GitHub Actions and Gradle

Profile: [`stacks/java.md`](../../audit/stacks/java.md#boundaries). CI usually runs the build and the tests as separate
wrappers. Make the test wrapper (or a new `check` wrapper) run `./gradlew check`, so formatter, static analysis
and tests run as locally. Lockfile-based dependency scan: the scanner reads the committed lockfile; no Gradle
plugin is needed. Keep the image scan (if any) separate from the dependency scan and name it report-only while
its accepted count is recorded.

### GitHub Actions and multi-app Node

Profile: [`stacks/typescript-node.md`](../../audit/stacks/typescript-node.md#boundaries). With a per-app layout
(`layout.command_runner`) there is no root `check`: each app's job runs that app's `format:check`, `typecheck`,
`lint` and `test` verbs through the wrapper, with the same flags as local. A verb that is a ratchet locally
(changed files, strict-clean list) is the same ratchet in CI. `npm audit` with the high threshold is the
`security` verb; while findings exist it is report-only by the rule above. A test suite gated by an environment
flag runs in CI by default (set the flag in the wrapper), and any text saying it stays skipped is corrected.

Lessons from the multi-app Node application (IR07.3):

- The wrapper runs the same three steps as the app's `check` (`format:check`, `typecheck`, tests), each in its own
  `echo "==> ..."` block, so a failure names the step. The changed-files ratchets need the merge-base, so every job
  that runs them checks out with `fetch-depth: 0` (the default shallow clone makes them fail or pass vacuously).
- Point `setup-node` at each app's own `.nvmrc` (`node-version-file`), one source of truth per app.
- A report-only audit step keeps the script's non-zero exit (the step shows its real outcome) and
  `continue-on-error` keeps it out of the gate. The script writes the counts per severity to
  `GITHUB_STEP_SUMMARY` when it is set; test that locally with `GITHUB_STEP_SUMMARY=/tmp/x.md`. An image scan
  needs Docker and the built image, so its first count comes from the pull request's own CI run, not from the
  session.
- A finding's second clause can be stale while the first stands (here: the test flag already defaulted to on).
  Mark the clause stale in the item's note; do not rewrite the finding.
- A README table row you add counts against any Markdown lint baseline. Keep new rows under the line limit and put
  longer notes in a wrapped paragraph.

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
| CI-05 | Run the local workflow-lint command; read the CI step | The linter runs locally and in CI and is clean on the edited workflows; the engine reads CI-05 `PASS` |

The engine reads `run:` text only. After a correct wrapper-based fix a re-audit can still read CI-02 or CI-03
wrongly (known engine defects), and CI-04 needs the platform confirmation: say so in the pull request body; the
close-out comparison (`SKILL.md` Stage 5) labels the move.

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

Beyond the shared lines in [Stage 3](../SKILL.md#stage-3-apply) (`in_progress`, the theme rows) and
[Stage 4](../SKILL.md#stage-4-close-the-theme) (the ending):

```bash
python3 implement/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "<wrapper or grep>" --verification-result "<result>"
python3 implement/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --debt "what=dependency findings,count=<n>,baseline=<file>" --note "<report-only step, review date>"
python3 implement/tools/progress.py pref set ci.shape <wrappers-call-verbs|direct> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set ci.edits_authorised <value> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set ci.workflow_linter <actionlint|zizmor|check-jsonschema|...> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
```
