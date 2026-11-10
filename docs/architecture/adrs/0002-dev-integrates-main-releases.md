# 0002. `dev` Integrates Every Change; `main` Takes Only Promotions From `dev` and the Release Pull Request

## Context

With one protected branch, every pull request goes to it and a release is a tag on it. Work that is not ready for
a release then sits on the same branch as released work.

The owner wants two protected branches, the same model as the
[Digital-Assistant-SDK](https://github.com/Digital-Assistant/Digital-Assistant-SDK/blob/main/RELEASE_PROCESS.md)
repository:

* `dev` accepts pull requests from any branch, `main` included. It accepts no direct commits.
* `main` accepts pull requests from `dev` only.

The SDK repository also uses Release Please, a GitHub App and a back-merge job. This repository uses them too
([ADR 0005](0005-release-please-cuts-releases.md)). So `main` takes one more kind of pull request: the release pull
request that release-please opens.

A GitHub ruleset can require a pull request and status checks. It cannot restrict the source branch of a pull request.

## Decision

1. **Two long-lived branches.** `dev` is the integration branch and the default branch: every change goes to `dev`
   first. `main` is the release branch: it holds only work that was promoted from `dev`. `dev` is the default. So new
   pull requests, Dependabot pull requests and a plain `git clone` start on `dev`. The quick start in
   [`README.md`](../../../README.md) clones `main` by name, so a user gets released work.
2. **Rulesets.** Two repository rulesets, declared in
   [`.github/rulesets/`](../../../.github/rulesets/), protect the branches. Both block direct pushes, force pushes and
   deletion, and both have no bypass actors. Both allow merge commits only. The exact rules are in
   [Branch protection](../../reference/branch-protection.md).
3. **Source branch check.** [`pr-source-branch.yml`](../../../.github/workflows/pr-source-branch.yml) emits the
   status `Check source branch` on every pull request into `main`. It passes in two cases:

   * the head branch is `dev` in this repository;
   * the head branch is `release-please--branches--main` in this repository, and a bot opened the pull request.

   The `main` ruleset requires it.
4. **Release.** A release is a tag `vX.Y.Z` that release-please makes on `main` when its release pull request is
   merged ([ADR 0005](0005-release-please-cuts-releases.md)).
   [`release.yml`](../../../.github/workflows/release.yml) refuses a tag whose commit is not on `main`.
5. **A back-merge after each release.** The release pull request changes the version and the changelog on `main`.
   `dev` gets those changes through a back-merge pull request from `chore/back-merge-vX.Y.Z`, a branch at the release
   commit. Its head is not `main` itself, so resolving a conflict with `dev` never needs a push to `main`.
6. **`main` does not require an up-to-date branch.** Promotions from `dev` and the release pull request both merge into
   `main`. A strict "up to date" rule would make each wait for the other for no gain. `dev` does not require it
   either. Its merge queue tests each pull request merged onto the latest `dev`. The rule would only add a CI run per
   update ([`branch-protection.md`](../../reference/branch-protection.md)).
7. **A local guard.** [`lefthook.yml`](../../../lefthook.yml) stops a commit on `main` or `dev` before the push is
   refused.

The procedures are in [`RELEASE_PROCESS.md`](../../../RELEASE_PROCESS.md) and in
[Contribute a change](../../how-to/contribute-a-change.md).

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| One protected branch, `main` | Unreleased work and released work share one branch. The owner wants a release branch that holds released work only. |
| No back-merge: changelogs and versions written by hand on `dev` before the promotion | Hand-written version strings drift. release-please ([ADR 0005](0005-release-please-cuts-releases.md)) writes to `main`, so a back-merge is needed. |
| `main` accepts pull requests from `dev` only, with no exception | release-please opens its release pull request into `main` from its own branch. The exception is narrow: one branch name, opened by a bot. |
| `main` as the default branch | New pull requests and Dependabot security updates open against the default branch. With `main` as the default, they fail `Check source branch` and need a manual change of base. |
| Restrict the source branch with the ruleset only | Rulesets cannot express a source branch. A required status check is the only way. |
| Require an up-to-date branch on `main` | A promotion and the release pull request would each have to wait for, or update with, the other. |
| Squash or rebase merges | One Conventional Commit per logical change must stay revertable alone. A squash joins them; a rebase rewrites them. |

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
