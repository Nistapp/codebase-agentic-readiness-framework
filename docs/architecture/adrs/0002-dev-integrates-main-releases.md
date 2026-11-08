# 0002. `dev` Integrates Every Change; `main` Takes Only Promotions From `dev`

* **Status:** Accepted
* **Date:** 2026-11-08
* **Last reviewed:** 2026-11-08
* **Deciders:** [@nistapp]

---

## Context

Before this decision, the repository had one protected branch, `main`. Every pull request went to `main`, and a
release was a tag on `main`. Work that was not ready for a release was on `main` together with released work.

The owner wants two protected branches, the same model as the
[Digital-Assistant-SDK](https://github.com/Digital-Assistant/Digital-Assistant-SDK/blob/main/RELEASE_PROCESS.md)
repository:

* `dev` accepts pull requests from any branch, `main` included. It accepts no direct commits.
* `main` accepts pull requests from `dev` only.

The SDK repository also uses Release Please, a GitHub App and a back-merge job. This repository does not need them.
Its changelogs are written by hand, and its release workflow does not write to any branch.

A GitHub ruleset can require a pull request and status checks. It cannot restrict the source branch of a pull request.

## Decision

1. **Two long-lived branches.** `dev` is the integration branch and the default branch: every change goes to `dev`
   first. `main` is the release branch: it holds only work that was promoted from `dev`. Because `dev` is the default,
   a new pull request, a Dependabot pull request and a plain `git clone` all start on `dev`. The quick start in
   [`README.md`](../../../README.md) clones `main` by name, so a user gets released work.
2. **Rulesets.** Two repository rulesets, declared in
   [`.github/rulesets/`](../../../.github/rulesets/), protect the branches. Both block direct pushes, force pushes and
   deletion, and both have no bypass actors. Both allow merge commits only. The exact rules are in
   [Branch protection](../../reference/branch-protection.md).
3. **Source branch check.** [`pr-source-branch.yml`](../../../.github/workflows/pr-source-branch.yml) emits the
   status `Check source branch` on every pull request into `main`. It passes only when the head branch is `dev` in
   this repository. The `main` ruleset requires it.
4. **Release.** A release is a signed tag on the merge commit of a promotion pull request (`dev` into `main`).
   [`release.yml`](../../../.github/workflows/release.yml) refuses a tag whose commit is not on `main`.
5. **No back-merge.** The changelogs and version strings change on `dev`, before the promotion. Nothing writes to
   `main` except the merge of a promotion pull request. So `main` never holds a change that `dev` does not have. The
   only commits on `main` that `dev` lacks are those merge commits, and they carry no file change.
6. **`main` does not require an up-to-date branch.** Because of item 5, `dev` is never behind `main` in content. A
   strict "up to date" rule on `main` would force a back-merge after every release for no gain. `dev` keeps the strict
   rule, because many branches merge into it.
7. **A local guard.** [`lefthook.yml`](../../../lefthook.yml) stops a commit on `main` or `dev` before the push is
   refused.

The procedures are in [`RELEASE_PROCESS.md`](../../../RELEASE_PROCESS.md) and in
[Contribute a change](../../how-to/contribute-a-change.md).

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Keep one protected branch, `main` (the design before this ADR) | Unreleased work and released work share one branch. The owner wants a release branch that holds released work only. |
| Release Please, a GitHub App and an automated back-merge, as in the SDK repository | The changelogs here are written by hand, per component. Release Please would write to `main`, and that needs the back-merge. The extra App and secrets add risk for no gain. |
| Keep `main` as the default branch (the first version of this ADR, 2026-11-08) | New pull requests and Dependabot security updates open against the default branch. With `main` as the default, they fail `Check source branch` and need a manual change of base. The owner made `dev` the default the same day. |
| Restrict the source branch with the ruleset only | Rulesets cannot express a source branch. A required status check is the only way. |
| Require an up-to-date branch on `main` | It forces a back-merge pull request from `main` into `dev` after each release, with no content change. |
| Squash or rebase merges | One Conventional Commit per logical change must stay revertable alone. A squash joins them; a rebase rewrites them. |

> A later reversal of this decision is folded into this table, so the rejected direction
> keeps its rationale inside the accepted record.

---

## Consequences

### Positive

* `main` holds released work only. Every tag is on `main`, and the release workflow checks it.
* Every change passes `CI Gate` twice: on its pull request into `dev`, and on the promotion pull request into `main`.
* The rules are files in the repository. A change to them is reviewed like code.

### Negative / Trade-offs

* A hotfix must go through `dev`. If `dev` holds work that is not ready, the maintainer must release that work too,
  or revert it on `dev` first.
* `main` shows merge commits that `dev` does not have. GitHub shows `main` as "ahead of `dev`" by that count. This
  is expected and needs no action.
* A visitor to the repository page sees `dev`, which can hold unreleased work. A plain `git clone` also gets `dev`.
  The quick start clones `--branch main`, and the GitHub releases hold the released files.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into
  *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference
  plus the index table in `docs/architecture/adrs/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/0002-dev-integrates-main-releases.md`.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
