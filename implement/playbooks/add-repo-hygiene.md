# Playbook: `add-repo-hygiene`

> Theme T8 (hygiene and index freshness). Follows the anatomy in [`README.md`](README.md). Written in IR11.1;
> applied and corrected on a Gradle repository (IR11.2) and a multi-component Node repository (IR11.3). Its sibling
> [`register-index`](register-index.md) owns the index checks of the same theme.

## Goal

The repository tells a newcomer, human or agent, who owns what (CODEOWNERS), how to contribute (README,
CONTRIBUTING, pull-request and issue templates), how to report a vulnerability (SECURITY), how releases happen
(a release-process page and, where the release tool writes one, the changelog), and where the rules for merging
live (a branch-protection page). Each file is small, true against the repository, and sits where the audit reads it.

**The rule this playbook enforces: write only what is true, and only what the repository needs.** All eleven checks
are cosmetic and unscored, so a long, generic template that nobody keeps true is worse than a short page that is.
A value the playbook cannot know (a mailbox, a response time, a second reviewer) is a named placeholder plus an owner
action in the state, never an invented contact.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| HYG-01 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-01--readme-present-and-non-placeholder) | A root README of at least 200 characters of body, no placeholder marker, not a bare title; written from the repository's own files |
| HYG-02 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-02--codeowners-present) | A `CODEOWNERS` file at `.github/` with a default rule, the existing path rules kept, and a commented-out second-reviewer placeholder |
| HYG-03 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-03--pull-request-template-present) | A `.github/pull_request_template.md` that asks for what the repository's gate and PR rules require |
| HYG-04 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-04--issue-templates-present) | At least one file under `.github/ISSUE_TEMPLATE/` (bug report, feature request) |
| HYG-05 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-05--contributing-present) | A `CONTRIBUTING` document naming the repository's own setup, gate, branch and review flow |
| HYG-06 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-06--security-present) | A `SECURITY` document: how to report privately, with owner-supplied contact values as a named placeholder |
| HYG-07 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-07--changelog-present-and-recent) | Verification, and a decision: a changelog the release tool writes is not hand-written (Steps 6) |
| HYG-08 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-08--release-process-documented) | A short document (name contains `release`) describing the release process in prose |
| HYG-09 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-09--dependency-update-automation-configured) | Verification only: a Dependabot or Renovate file already exists in most repositories |
| HYG-10 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-10--license-present) | Verification only; the playbook never chooses a licence |
| HYG-11 | [13-hygiene-informational.md](../../audit/checks/13-hygiene-informational.md#hyg-11--branch-protection-declared-as-code) | A page whose path contains `branch-protection` that records the rules in the repository's own words |

**Where a file counts.** The checks read the repository root, `.github/`, `.gitlab/` and `docs/` (HYG-10 and HYG-01:
the root only). A file inside a component's directory does not count, so a component README does not close HYG-01,
and nothing under a carried-data directory (`templates/`, `examples/`, `fixtures/`) counts at all. Write each file at
one of those places.

**What the engine does not check.** HYG-02 reads presence only. The engine does not compare CODEOWNERS paths with
the deny list, and the playbook never claims it does. A model that notices a disagreement writes it up as its own
observation.

## Preconditions

- The shared procedure in `SKILL.md` applies: [Stage 3](../SKILL.md#stage-3-apply) (state read first, drift first,
  worktree, one item at a time) and [Stage 4](../SKILL.md#stage-4-close-the-theme) (engine re-check, gate, ending).
- **T6 done or `partial`.** The README and CONTRIBUTING link to the documentation home and the style guide that
  [`establish-docs-contract`](establish-docs-contract.md) set up. T7 done or `partial`: CONTRIBUTING and the
  release-process page must agree with the `AGENTS.md` branch and release sentence
  ([`adapt-agents-md`](adapt-agents-md.md)).
- **Drift** ([Stage 3](../SKILL.md#stage-3-apply), step 2): a `CODEOWNERS` added with the CI work, or a
  `branch-protection` page written with the CI runbook, closes an item without the state knowing. An existing file is
  never replaced by a template.
- **Detect before writing.** For each file, list what exists at the four locations, then read it. An existing
  `CONTRIBUTING` that is generic, or names a flow this repository does not use, is a diff to propose, not a file to
  overwrite.
- Preferences this playbook reads, when present:

| Key | Effect |
|---|---|
| `github.owner_handle` | The handle CODEOWNERS and the SECURITY text name. Absent: ask (Inputs 3) |
| `codeowners.default` | `owner-owns-all` (default rule `*` for the owner) or a path-by-path map the owner supplied |
| `security.disclosure` | `github-private-reporting` (default), `mailbox`, or `private-contact` for a private repository |
| `ci.commit_rule`, `commit.convention` | What CONTRIBUTING and the PR template say about titles and messages |
| `ci.branch_protection`, `ci.branch_protection_runbook` | Whether the rules are enforced or only recorded; who may change the setting |
| `agents_md.release_tags` | `never-tag-or-release` means the release page says agents never tag |
| `format.mass_reformat` | `no`: new Markdown only, no reformatting of existing pages |

## Inputs to ask

No tool is installed. Ask once, as one batch: the playbook writes every file below from
the repository's own facts, adapted from [`greenfield/templates/`](../../greenfield/templates/)
(`SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `RELEASE_PROCESS.md`, and `github/` for `CODEOWNERS`, the
pull-request template and the issue templates), shows them together, and takes one review. The owner is asked only for
the policy files, and for nothing else:

1. **Show the batch.** The list of files to create or change, each with the check it closes and whether it already
   exists. Offer item-by-item review only if the owner asks for it.
2. **CODEOWNERS (HYG-02).** Confirm the owner handle for this repository, even when the state holds one for another
   repository: a handle is per repository. Default shape: keep the existing path rules, add a default `*` line for the
   owner, and add the second-reviewer line as a comment. **Required code-owner review stays off**: with one owner it
   would block every pull request. The playbook never enables it and never edits the GitHub setting.
3. **SECURITY (HYG-06).** Ask for the mailbox and the response time. If the owner has not supplied them, write the
   document with the placeholder `TODO(owner)` where each value goes. The disclosure path by repository kind:
   - **Public repository:** GitHub private vulnerability reporting, plus the placeholder for a mailbox and a response
     time.
   - **Private repository:** "report privately to the repository owner", no public-disclosure promises, no response-time
     promise unless the owner states one.

   Either way record two owner actions as a note on the item (`--note "owner action: ..."`) and list them in the
   pull request body: "enable private vulnerability reporting in the repository settings" (an agent can neither
   read nor set it), and "fill the `TODO(owner)` values". The placeholder marker does
   not affect HYG-06, which reads only that a `SECURITY` document exists.
4. **Everything else** is derived, not asked: the README from the repository's files, CONTRIBUTING from the gate and
   the PR rules in `AGENTS.md`, the templates from the PR and commit rules in the state.

## Steps

### Generic

1. **Baseline.** Run the audit launcher for HYG-01 to HYG-11. Build the table "check, location found, verdict, action".
   Close every present item as `done` with the file as evidence. A check that passes and has no item gets no state
   entry, only a line in the pull request body ([Stage 3](../SKILL.md#stage-3-apply), step 5). Name each new file by
   this repository's own convention: look at the neighbouring file names, the casing of existing root
   files, and `AGENTS.md` and CONTRIBUTING first, and follow them (for example `docs/branch-protection.md` beside other
   kebab-case pages).
2. **README (HYG-01).** Skip when a root README exists and passes. Otherwise write about 40 lines, from the
   repository's own files only (manifests, `AGENTS.md`, the docs index, the scripts, the CI files): what the repository
   is, its components, how to start and test it through the documented commands, where the docs live (link the docs
   home), and the PR rules. At least 200 characters of body text, no `todo`, `tbd`, `placeholder`, `coming soon` or
   `fill this in` anywhere in it, more than a title. Do not copy another repository's description. A proprietary
   repository may describe itself in full; an open-source one describes only what is in it. The README is one more page
   to keep true, so link to the docs rather than restate them.
3. **CODEOWNERS (HYG-02).** Create or extend `.github/CODEOWNERS` as Inputs 2 says. Keep every existing path rule.
   Verify each path in a rule exists (`test -e`); an owner rule for a path that is gone is a note, not a deletion.
4. **PR template and issue templates (HYG-03, HYG-04).** `.github/pull_request_template.md`: a short checklist drawn
   from the repository's gate and rules (the verification command, docs updated with code, the title rule, no secret
   added), not the full generic template. `.github/ISSUE_TEMPLATE/bug_report.md` and `feature_request.md` (or the
   YAML form equivalents; the check reads the directory, not the format). Name the real commands. Do not add a
   `config.yml` that disables blank issues unless the owner asks.
5. **CONTRIBUTING and SECURITY (HYG-05, HYG-06).** CONTRIBUTING: where the setup is (link, do not restate), the gate
   command, the branch and PR flow as the repository actually runs it (squash into the integration branch, who merges),
   the title rule, and where `AGENTS.md` fits. Write it as a diff when a generic one exists. SECURITY: as Inputs 3.
6. **CHANGELOG and release process (HYG-07, HYG-08).** Find out who writes the changelog:
   - **A release tool writes it** (`release-please-config.json`, `.releaserc*`, `changesets`, a release workflow that
     mentions `CHANGELOG`): do not hand-write or seed `CHANGELOG`. The tool creates it at the first release; a seeded
     file risks a malformed first entry. HYG-07 stays `partial` with the debt "no changelog until the first release
     is cut" and the revisit trigger "first release pull request merged". The check reads the file's last commit
     within 365 days of `HEAD`, so it recovers by itself once the tool commits.
   - **No tool:** offer the keep-a-changelog skeleton from the template, one entry per release, and let the owner
     decide.

   The release-process page (HYG-08) is a short document, not the 358-line template. A workflow file named
   `release.yml` does not count; the check wants prose. It states: which tool opens release pull requests and tags,
   what a merge to the release branch triggers, how versions are decided (the commit or title convention), who
   merges the release pull request, and that agents never tag or release (when `agents_md.release_tags` says so).
   Name it with `release` in the file name, at the root or `docs/`. It needs no CI edit; if the page would need a
   workflow change to become true, say so as a finding instead of editing CI.
7. **Branch protection (HYG-11).** Branch protection is a GitHub or GitLab setting, not a file. Write a page whose path
   contains `branch-protection` (for example `docs/branch-protection.md`) in the repository's own words: the protected
   branch, the required status check by name (the gate job), whether review is required, and how to change it. If the
   state says the platform plan cannot enforce protection (a private repository on a free plan returns an error for
   rulesets), the page says **"recorded, not enforced"** at the top; it must not read as enforcement. Never copy a
   private runbook from another repository; describe the rules from the repository's own workflow files and the
   owner's answers. Never call the GitHub settings API.
8. **Dependency updates and licence (HYG-09, HYG-10).** Verify only. If the dependency-update file exists, record
   `done` when the check has an item; when it has none (the audit passed it), name it in the pull request body and
   record nothing. If a `LICENSE` is missing, do not pick one: raise it as an owner question and set the item
   `blocked` (reason: the owner chooses a licence).
9. **Commits:** one per concern: policy files (CODEOWNERS and SECURITY); contribution files (README, CONTRIBUTING
   and the templates); release and protection pages.

### Gradle and Quarkus

Profile: [`stacks/java.md`](../../audit/stacks/java.md). The README and CONTRIBUTING name the wrapper commands (`./gradlew
...`) and the Java version the toolchain needs. CODEOWNERS paths follow the Gradle layout (`/src/main/`, `/src/test/`,
`/scripts/ci/`). Release tools in this stack are usually release-please (`simple` type, root) or the Gradle release
plugin; the release page says which tags the tool creates.

### Node (npm, NestJS, React) with several components

Profile: [`stacks/typescript-node.md`](../../audit/stacks/typescript-node.md). In a repository with several apps, one root
README links to the apps' own READMEs; it does not replace them and they do not replace it. CODEOWNERS uses one path
rule per app only if the owner supplies different owners; otherwise the default `*` line is enough. A release tool that
tags per package (component in the tag) is described in the release page with the tag format. Commands in the README
and CONTRIBUTING are the root scripts, or per-app commands with the directory named.

## Continue on error

- **A value the owner has not supplied** (mailbox, response time, second reviewer): the file is written with a
  `TODO(owner)` placeholder, the item is `done` for the check (presence), and the missing value is a state note and an
  owner action. Nothing is invented.
- **HYG-07 under a release tool:** `partial`, `--debt "what=changelog absent until first release,count=1"`, with the
  revisit trigger in the note.
- **HYG-11 on a plan that cannot enforce protection:** `done` for the check (the page exists) with the note
  "recorded, not enforced"; the unenforced setting is an owner action, not debt.
- **A missing licence:** the item is `blocked` until the owner chooses one; it is not debt the playbook can fix.
- None of this is a count of violations, so no ratchet or baseline file applies: report-only is the wiring.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| HYG-01 | `wc -m README.md`; read the first lines; grep for the marker words | Root file, 200+ characters of body, no marker, not a bare title; `PASS` |
| HYG-02 | `ls .github/CODEOWNERS`; `test -e` on each path in a rule | File present; `PASS` |
| HYG-03 | `ls .github/pull_request_template*` | Present; `PASS` |
| HYG-04 | `ls .github/ISSUE_TEMPLATE/` | At least one file; `PASS` |
| HYG-05 | `ls CONTRIBUTING*` at the root or `docs/` | Present, and its commands resolve; `PASS` |
| HYG-06 | `ls SECURITY*` at the root, `.github/` or `docs/` | Present; `PASS` |
| HYG-07 | Launcher run | `PASS` once the release tool has committed the file; until then `FAIL` and the item is `partial` |
| HYG-08 | `ls` for a document with `release` in its name | Present as prose, not only `release.yml`; `PASS` |
| HYG-09, HYG-10 | `ls .github/dependabot.yml`, `ls LICENSE*` | Present; `PASS` (verified, not added) |
| HYG-11 | `ls docs/*branch-protection*` | Present, says "recorded, not enforced" where that is true; `PASS` |

## Rollback

`git revert` the commits, one per concern. Nothing outside the repository changes: GitHub settings (private
vulnerability reporting, branch protection, required reviews) are never touched, so there is nothing to put back.

## Do-not-do

- Do not overwrite an existing hygiene file with a template; propose a diff.
- Do not hand-write or seed a changelog that a release tool owns, and do not tag or release.
- Do not enable required code-owner review, and do not edit any GitHub or GitLab setting.
- Do not invent a mailbox, a response time or a second reviewer.
- Do not copy `RELEASE_PROCESS.md` whole; write the short page.
- Do not copy a private runbook, another repository's page, or its values into a repository's file.
- Do not choose a licence.
- Do not create a file in a component directory expecting it to count.
- Do not reformat existing pages (`format.mass_reformat`).

## State updates

Beyond the shared lines in [Stage 3](../SKILL.md#stage-3-apply) and [Stage 4](../SKILL.md#stage-4-close-the-theme), on
the T8 branch shared with [`register-index`](register-index.md):

```bash
python3 implement/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "ls .github/CODEOWNERS" --verification-result "present"
python3 implement/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "ls SECURITY.md" --verification-result "present" \
  --note "owner action: enable private vulnerability reporting; fill TODO(owner) mailbox and response time"
python3 implement/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --debt "what=changelog absent until first release,count=1" \
  --note "release tool writes it; revisit when the first release pull request is merged"
python3 implement/tools/progress.py pref set github.owner_handle <@handle> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set codeowners.default owner-owns-all \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set security.disclosure <github-private-reporting|private-contact> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
```

Record a preference only when the owner answers; absent means the default above. The theme closes once, after
both T8 playbooks ([Stage 4](../SKILL.md#stage-4-close-the-theme)).
