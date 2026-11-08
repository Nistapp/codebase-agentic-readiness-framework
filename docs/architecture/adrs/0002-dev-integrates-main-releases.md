# 0002. `dev` Integrates Every Change; `main` Takes Only Promotions From `dev` and the Release Pull Request

* **Status:** Accepted
* **Date:** 2026-11-08
* **Last reviewed:** 2026-11-08 (release-please, [ADR 0005](0005-release-please-cuts-releases.md))
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

The SDK repository also uses Release Please, a GitHub App and a back-merge job. This repository adopted them too
([ADR 0005](0005-release-please-cuts-releases.md)). So `main` takes one more kind of pull request: the release pull
request that release-please opens.

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
   status `Check source branch` on every pull request into `main`. It passes in two cases: the head branch is `dev`
   in this repository, or the head branch is `release-please--branches--main` in this repository and a bot opened the
   pull request. The `main` ruleset requires it.
4. **Release.** A release is a tag `vX.Y.Z` that release-please makes on `main` when its release pull request is
   merged ([ADR 0005](0005-release-please-cuts-releases.md)).
   [`release.yml`](../../../.github/workflows/release.yml) refuses a tag whose commit is not on `main`.
5. **A back-merge after each release.** The release pull request changes the version and the changelog on `main`.
   `dev` gets those changes through a back-merge pull request from `chore/back-merge-vX.Y.Z`, a branch at the release
   commit. Its head is not `main` itself, so "Update branch" never needs a push to `main`.
6. **`main` does not require an up-to-date branch.** Promotions from `dev` and the release pull request both merge into
   `main`. A strict "up to date" rule would make each wait for the other for no gain. `dev` keeps the strict rule,
   because many branches merge into it.
7. **A local guard.** [`lefthook.yml`](../../../lefthook.yml) stops a commit on `main` or `dev` before the push is
   refused.

The procedures are in [`RELEASE_PROCESS.md`](../../../RELEASE_PROCESS.md) and in
[Contribute a change](../../how-to/contribute-a-change.md).

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Keep one protected branch, `main` (the design before this ADR) | Unreleased work and released work share one branch. The owner wants a release branch that holds released work only. |
| No back-merge: changelogs and versions written by hand on `dev` before the promotion (this ADR until release-please, 2026-11-08) | The version strings drifted. The owner adopted release-please ([ADR 0005](0005-release-please-cuts-releases.md)), which writes to `main`, so a back-merge is needed. |
| `main` accepts pull requests from `dev` only, with no exception | release-please opens its release pull request into `main` from its own branch. The exception is narrow: one branch name, opened by a bot. |
| Keep `main` as the default branch (the first version of this ADR, 2026-11-08) | New pull requests and Dependabot security updates open against the default branch. With `main` as the default, they fail `Check source branch` and need a manual change of base. The owner made `dev` the default the same day. |
| Restrict the source branch with the ruleset only | Rulesets cannot express a source branch. A required status check is the only way. |
| Require an up-to-date branch on `main` | A promotion and the release pull request would each have to wait for, or update with, the other. |
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
* Each release needs a back-merge pull request into `dev`. Until it is merged, `dev` shows the previous version.
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
