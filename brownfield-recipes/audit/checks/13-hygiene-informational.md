# Hygiene (`HYG`) — informational, never scored

> Follows the anatomy in [`README.md`](README.md). Eleven checks, all `method: automated`, all
> `catalogue.json`: `scored: false` with no `req_ids` — reported like every other check, but earning no
> credit. See
> [Why These Checks §14](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#14-hygiene-informational-never-scored)
> for the consequence behind this family: README, CODEOWNERS, PR/issue templates, CONTRIBUTING,
> SECURITY, CHANGELOG, release process, dependency-update automation, license and branch protection are
> how a *team* operates, not what an agent reads before deciding what to edit. They are reported because
> a client engagement needs the whole picture, and left numberless on purpose.
>
> **Verdict contract, shared by every check in this file (from the engine's own `hyg.py` docstring):
> an absent artifact is `FAIL`.** Because every check here is unscored, a `FAIL` is a reported fact that
> never moves the readiness number — write it up like any other finding, just without a score
> consequence. `UNKNOWN` is reserved for "the artifact is present but its quality cannot be settled" (an
> unreadable README, an undatable changelog, an unrecognised CI provider for branch protection) — it is
> never used merely because an artifact is absent. None of these checks writes to the target or runs a
> command in the target's own toolchain; `HYG-07` reads git history read-only for a commit date, never
> wall-clock time (`deterministic-audit/AGENTS.md` §5).
>
> **A described cross-check this pack does not implement.** The framework overview names one exception
> that "bridges" hygiene and scored checks: where `CODEOWNERS` names paths the audit would also place on
> a deny list, consistency between the two is said to be "reported as a note". The engine's `HYG-02`
> checks presence only — it does not read `CODEOWNERS`'s content or compare it against `CON-01`/`CON-02`.
> Do not claim this cross-check runs; if a model notices the two disagree, that observation is the
> model's own judgment, not an engine-reported fact, and should be written up as such.

---

## HYG-01 — README present and non-placeholder

Why it matters   An agent (or a person) must be able to orient itself in this project in seconds, not by
                  opening files at random.
Severity         COSMETIC
Engine           `HYG-01`. A root file whose name starts with `readme` (case-insensitive) is the
                 evidence; with more than one, `README.md` is preferred. Present, at least 200 characters
                 of trimmed body, free of a placeholder marker (`todo`, `tbd`, `placeholder`,
                 `lorem ipsum`, `coming soon`, `fill this in`, `<describe`, case-insensitive), and not a
                 bare heading with no body text, is `PASS`. Present but under the bar, carrying a
                 placeholder marker, or a bare title, is `FAIL` with the reason stated. Present but
                 unreadable (binary or oversized) is `UNKNOWN`. Absent is `FAIL`.
Method           automated
Look for         A root `README*` file; its trimmed character count, a placeholder marker, and whether
                 any non-heading line of body text exists.
Rubric           PASS: a root README exists, reads as text, has at least 200 characters of body, carries
                 no placeholder marker, and is not a bare title.
                 PARTIAL: not used by this check — the engine's own outcome is binary.
                 FAIL: no root README exists, or one exists but is a placeholder (too short, a
                 placeholder marker, or a bare title with no body).
                 NOT_APPLICABLE: never.
                 UNKNOWN when: a root README exists but cannot be read as text (binary or oversized).
Evidence to cite A `file` evidence item citing the README path and the specific reason (character count,
                 marker text, or "a title with no body") for a placeholder FAIL.
Absence proof    A FAIL for "no README" states that no file at the repository root starts with `readme`;
                 a FAIL for a placeholder cites the exact reason the content check failed.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-01`).
Pitfalls         A `FAIL` here never lowers the score — this check is informational; do not treat it as
                 equivalent in severity to a scored `BLOCKER` elsewhere just because the README is the
                 first thing a reader sees.

## HYG-02 — CODEOWNERS present

Why it matters   Review routing should be machine-readable, not tribal knowledge about who owns what.
Severity         COSMETIC
Engine           `HYG-02`. A `CODEOWNERS` file at the root, under `.github/`, or under `docs/` is `PASS`;
                 none at any of those three locations is `FAIL`. This check reads presence only — see the
                 header note above on the cross-check this pack does not implement.
Method           automated
Look for         A file named exactly `CODEOWNERS` at the root, under `.github/`, or under `docs/`.
Rubric           PASS: a `CODEOWNERS` file exists at one of the three recognised locations.
                 PARTIAL: not used by this check.
                 FAIL: no `CODEOWNERS` file exists at any recognised location.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — presence at a fixed location is always determinable.
Evidence to cite A `file` evidence item citing the `CODEOWNERS` path found, for PASS.
Absence proof    A FAIL states that none of the three recognised locations (root, `.github/`, `docs/`)
                 holds a `CODEOWNERS` file.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-02`).
Pitfalls         Do not read `CODEOWNERS`'s own content to judge whether it is well-formed or complete —
                 this check only establishes that the file exists; a model that wants to compare its
                 entries against the deny list is doing its own analysis, not reading an engine verdict.

## HYG-03 — Pull-request template present

Why it matters   A reviewer needs the same information every time a change is filed, not whatever the
                  author happened to think to write.
Severity         COSMETIC
Engine           `HYG-03`. Any file whose basename starts with `pull_request_template`
                 (case-insensitive), normally under `.github/`, is `PASS`. None found is `FAIL`.
Method           automated
Look for         Any file whose basename starts with `pull_request_template`, at any depth.
Rubric           PASS: at least one `pull_request_template*` file exists.
                 PARTIAL: not used by this check.
                 FAIL: no `pull_request_template*` file exists anywhere in the tree.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never.
Evidence to cite A `file` evidence item citing the template path found, for PASS.
Absence proof    A FAIL states that no file anywhere in the tree has a basename starting with
                 `pull_request_template`.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-03`).
Pitfalls         A template referenced only in a GitHub organisation-level `.github` repository is
                 invisible to this check — it reads this repository's own tree only, never an
                 organisation default.

## HYG-04 — Issue templates present

Why it matters   A bug report or feature request filed in a structured way is faster to triage than free
                  text.
Severity         COSMETIC
Engine           `HYG-04`. At least one file under `.github/ISSUE_TEMPLATE/`, or the single-file
                 `.github/ISSUE_TEMPLATE.md`, is `PASS`. Neither found is `FAIL`.
Method           automated
Look for         Any file under `.github/ISSUE_TEMPLATE/`; the single file `.github/ISSUE_TEMPLATE.md`.
Rubric           PASS: at least one file exists under `.github/ISSUE_TEMPLATE/`, or
                 `.github/ISSUE_TEMPLATE.md` exists.
                 PARTIAL: not used by this check.
                 FAIL: neither location has any file.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never.
Evidence to cite A `file` evidence item per issue-template file found (or the single-file form), for PASS.
Absence proof    A FAIL states that `.github/ISSUE_TEMPLATE/` is empty or absent and
                 `.github/ISSUE_TEMPLATE.md` does not exist.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-04`).
Pitfalls         A GitHub "issue forms" YAML (`.github/ISSUE_TEMPLATE/bug_report.yml`) counts exactly like
                 a Markdown template — the check reads the directory's presence, not the file format.

## HYG-05 — CONTRIBUTING present

Why it matters   A contributor should not have to reverse-engineer the setup, the gate and the review
                  flow from reading commit history.
Severity         COSMETIC
Engine           `HYG-05`. Any file anywhere in the tree whose basename starts with `contributing` and is
                 either a bare name or carries a document suffix (`.md`, `.rst`, `.txt`, `.markdown`,
                 `.adoc`) is `PASS`. None found is `FAIL`.
Method           automated
Look for         Any file, at any depth, whose basename starts with `contributing` and is a bare name or
                 a document-suffixed file.
Rubric           PASS: at least one `CONTRIBUTING`-prefixed document exists anywhere in the tree.
                 PARTIAL: not used by this check.
                 FAIL: no `CONTRIBUTING`-prefixed document exists.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never.
Evidence to cite A `file` evidence item citing the document path found, for PASS.
Absence proof    A FAIL states that no file anywhere in the tree has a basename starting with
                 `contributing` and a recognised document form.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-05`).
Pitfalls         A `CONTRIBUTING` section embedded inside `README.md` rather than its own file does not
                 count — the check looks for a separate document, however good the README's own section
                 is.

## HYG-06 — SECURITY present

Why it matters   A vulnerability should have a documented, private way to be reported, not left to
                  whatever channel the reporter happens to try first.
Severity         COSMETIC
Engine           `HYG-06`. Any file at the root, under `.github/`, or under `docs/` whose basename starts
                 with `security` and is either a bare name or carries a document suffix is `PASS`. None
                 found is `FAIL`.
Method           automated
Look for         Any file, at any depth, whose basename starts with `security` and is a bare name or a
                 document-suffixed file.
Rubric           PASS: at least one `SECURITY`-prefixed document exists anywhere in the tree.
                 PARTIAL: not used by this check.
                 FAIL: no `SECURITY`-prefixed document exists.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never.
Evidence to cite A `file` evidence item citing the document path found, for PASS.
Absence proof    A FAIL states that no file anywhere in the tree has a basename starting with `security`
                 and a recognised document form.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-06`).
Pitfalls         Do not confuse this with `SEC-01`–`SEC-03` (the scored `SECURITY HYGIENE` family in
                 [`12-security-hygiene.md`](12-security-hygiene.md)): `HYG-06` only checks whether a
                 disclosure policy document exists, unscored; it says nothing about tracked secrets or
                 ignore coverage.

## HYG-07 — CHANGELOG present and recent

Why it matters   A reader needs to see what changed between two versions without diffing the whole
                  history themselves.
Severity         COSMETIC
Engine           `HYG-07`. Any file anywhere in the tree whose basename starts with `changelog`,
                 `changes` or `history` and is a bare name or document-suffixed file is the candidate
                 (the first match, by sort order, is read). None found is `FAIL` outright. Found: the
                 engine compares, via read-only git queries, the candidate's own last-commit date against
                 `HEAD`'s commit date — **recency is always relative to the repository's own history,
                 never wall-clock time** (`deterministic-audit/AGENTS.md` §5: no `date.today()`). Within
                 365 days (`RECENT_WINDOW`) of `HEAD` is `PASS`; older is `FAIL`, with the age stated.
                 Git unable to supply either date (no repository, git absent, or the file untracked) is
                 `UNKNOWN` — never `FAIL`, and never today's date substituted for the missing one.
Method           automated
Look for         Any file whose basename starts with `changelog`/`changes`/`history`; its own last-commit
                 date, via `git log -1 --format=%cI`, against `HEAD`'s.
Rubric           PASS: a changelog document exists and its last commit is within 365 days of `HEAD`'s.
                 PARTIAL: not used by this check.
                 FAIL: no changelog document exists, or one exists and its last commit predates `HEAD`'s
                 by more than 365 days.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: a changelog document exists but git could not date it, or could not date
                 `HEAD`, against which to compare it.
Evidence to cite A `file` evidence item citing the changelog path and its age in days against `HEAD`, for
                 both PASS and a staleness FAIL.
Absence proof    A FAIL for "no changelog" states that no file anywhere matches the three recognised name
                 prefixes; a staleness FAIL states the exact day count since the changelog's last commit
                 and the 365-day window it exceeds.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-07`).
Pitfalls         An abandoned repository with no commits in two years reads `FAIL` here — correctly, by
                 the engine's own documented design ("judged on its own clock, not the audit machine's")
                 — but a repository frozen in a known-stable state should still have this reported as a
                 fact, not argued away as a false positive.

## HYG-08 — Release process documented

Why it matters   Whoever cuts the next release should be following a written process, not reconstructing
                  it from whoever did it last time's memory.
Severity         COSMETIC
Engine           `HYG-08`. A text or Markdown document whose basename contains `release` is `PASS`. A CI
                 workflow file named `release.yml` is **not** a document and does not count — the engine
                 distinguishes a described process from an automated one. None found is `FAIL`.
Method           automated
Look for         Any document-suffixed file whose basename contains `release`, excluding CI workflow
                 files.
Rubric           PASS: at least one text/Markdown document whose name contains `release` exists.
                 PARTIAL: not used by this check.
                 FAIL: no such document exists (a `release.yml` CI workflow alone does not satisfy it).
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never.
Evidence to cite A `file` evidence item citing the release document path found, for PASS.
Absence proof    A FAIL states that no document (as opposed to a CI workflow file) whose name contains
                 `release` exists anywhere in the tree.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-08`).
Pitfalls         A repository automating its release entirely through `.github/workflows/release.yml`,
                 with no page describing the process in prose, is a correct `FAIL` — automation is not
                 documentation, and the two checks (this one and `HYG-09`) read different evidence.

## HYG-09 — Dependency update automation configured

Why it matters   Dependencies should be patched on a schedule, not discovered stale during an incident.
Severity         COSMETIC
Engine           `HYG-09`. Dependabot (`.github/dependabot.yml`/`.yaml`, or the same names at the root)
                 or Renovate configuration (`renovate.json[5]`, `.renovaterc[.json]`,
                 `.github/renovate.json`, `renovate.config.js`) at any of its conventional locations is
                 `PASS`. None found is `FAIL`.
Method           automated
Look for         The fixed set of conventional Dependabot/Renovate configuration filenames, each at its
                 documented location.
Rubric           PASS: a Dependabot or Renovate configuration file exists at a conventional location.
                 PARTIAL: not used by this check.
                 FAIL: no file from the fixed configuration set exists at any conventional location.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never.
Evidence to cite A `file` evidence item citing the configuration path found, for PASS.
Absence proof    A FAIL states that none of the fixed Dependabot/Renovate filenames were found at any of
                 their conventional locations.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-09`).
Pitfalls         A third-party dependency-update bot configured entirely through an external SaaS
                 dashboard, with no file committed to the repository, is invisible to this check and
                 reads `FAIL` — the engine can only see what is committed.

## HYG-10 — License present

Why it matters   Anyone using or contributing to the code needs to know the terms under which it may be
                  used, without asking.
Severity         COSMETIC
Engine           `HYG-10`. A root file (root only, unlike most of this family) whose basename starts with
                 `license`, `licence`, `copying`, `copyright` or `unlicense` and is a bare name or
                 document-suffixed file is `PASS`. None at the root is `FAIL` — a license file elsewhere
                 in the tree does not count.
Method           automated
Look for         A root-level file whose basename starts with one of the five recognised prefixes.
Rubric           PASS: a root license file (one of the five recognised name prefixes) exists.
                 PARTIAL: not used by this check.
                 FAIL: no root license file exists.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never.
Evidence to cite A `file` evidence item citing the license file path found, for PASS.
Absence proof    A FAIL states that no root-level file starts with any of the five recognised prefixes.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-10`).
Pitfalls         A license mentioned only in `package.json`'s `license` field, or only in `README.md`'s
                 prose, does not satisfy this check — root-only, by design, matches how a license file is
                 conventionally expected and how most tooling discovers it.

## HYG-11 — Branch protection declared as code

Why it matters   Protected-branch rules should be reviewed like any other change, not configured by hand
                  in a settings page nobody diffs.
Severity         COSMETIC
Engine           `HYG-11`. A file whose path contains `branch-protection` or `branch_protection`, or a
                 Terraform (`.tf`) file whose content mentions `branch_protection`, is `PASS`. None found,
                 with a CI provider detected that actually offers branch protection as config-as-code
                 (github, gitlab), is `FAIL`. None found, with no such provider recognised, is `UNKNOWN`
                 — whether protection *can* be declared as code at all is provider-dependent, so absence
                 is not evidence of a gap when the provider itself may not support it.
Method           automated
Look for         A file path containing `branch-protection`/`branch_protection`; a `.tf` file's content
                 for `branch_protection`; `stack.ci_providers` for github or gitlab.
Rubric           PASS: a branch-protection file or a matching Terraform resource exists.
                 PARTIAL: not used by this check.
                 FAIL: no branch-protection configuration exists, and the detected CI provider (github or
                 gitlab) is one that offers it as config-as-code.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no branch-protection configuration exists and no CI provider offering
                 config-as-code protection is recognised.
Evidence to cite A `file` evidence item citing the branch-protection file or Terraform resource found,
                 for PASS; for FAIL, the recognised provider name(s) as the evidence that config-as-code
                 was available but unused.
Absence proof    A FAIL names the CI provider(s) detected that offer config-as-code protection and states
                 that no file or Terraform resource declaring it was found.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `HYG-11`).
Pitfalls         A provider this check does not recognise as offering config-as-code (anything outside
                 github/gitlab) always reads `UNKNOWN`, even if that provider genuinely has no
                 equivalent mechanism — do not read the `UNKNOWN` as "probably fine", only as "not
                 determinable by this check".
