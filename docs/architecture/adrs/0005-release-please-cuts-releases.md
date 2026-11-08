# 0005. Release-Please Computes the Version, Writes the Changelog and Tags the Release

* **Status:** Accepted
* **Date:** 2026-11-08
* **Last reviewed:** 2026-11-08
* **Deciders:** [@nistapp]

---

## Context

Up to v0.3.0, a release was manual. The maintainer opened a release preparation branch, moved the `[Unreleased]`
changelog entries under a dated heading, changed the version strings by hand, promoted `dev` to `main`, and pushed a
signed tag. The tag push started [`release.yml`](../../../.github/workflows/release.yml).

That hand work drifted. The engine's `__version__` said `0.1.0` through the v0.2.0 and v0.3.0 releases, so
`audit --version` and every report's provenance named the wrong version.

The commit subjects already follow Conventional Commits, and CI checks them (`dev/commit_lint.py`). So a tool can
compute the next version and write the changelog from them. The owner asked for automated versions and releases,
with the back-merge pattern of the
[Digital-Assistant-SDK](https://github.com/Digital-Assistant/Digital-Assistant-SDK/blob/main/RELEASE_PROCESS.md)
repository. The greenfield template in this repository (`greenfield/templates/github/workflows/release-and-sync.yml`)
uses the same pattern.

## Decision

1. **release-please, one root package.** [`release-please-config.json`](../../../release-please-config.json) uses
   the `simple` release type with one package at `.` and tags `vX.Y.Z`. Before 1.0.0, a breaking change bumps MINOR
   and any other change bumps PATCH, as [`RELEASE_PROCESS.md`](../../../RELEASE_PROCESS.md) says.
   [`.release-please-manifest.json`](../../../.release-please-manifest.json) holds the last released version.
2. **The version lives in three places, and the bot changes all three.** The manifest, the engine's `__version__`
   (an `extra-files` entry with the `x-release-please-version` marker) and the `CHANGELOG.md` entry.
   `dev/tests/test_release_config.py` fails when the manifest and `__version__` disagree. `release.yml` refuses a tag
   that differs from `__version__`.
3. **The release pull request.** On each push to `main`,
   [`release-please.yml`](../../../.github/workflows/release-please.yml) opens or updates a pull request from
   `release-please--branches--main` into `main`. Merging it tags the release and creates the GitHub release, with the
   changelog entry as its notes. `Check source branch` accepts that branch when a bot opened the pull request
   ([ADR 0002](0002-dev-integrates-main-releases.md)).
4. **The changelog is generated, then fixed for lint.** release-please writes `*` bullets and double blank lines. The
   `docs-lint` ratchet covers `CHANGELOG.md` and refuses both. So a job runs `make changelog-fix` (markdownlint
   `--fix`) on the release pull request and pushes the fix. The ratchet does not change. The recipes' own changelog,
   `audit/CHANGELOG.md`, gets no new entries; the root changelog covers the recipes from v0.3.1 on.
5. **Publishing.** `release.yml` has no tag-push trigger, because a tag made with `GITHUB_TOKEN` starts no workflow.
   `release-please.yml` dispatches it with the tag. A dispatch is the one event that `GITHUB_TOKEN` may start a
   workflow with. The maintainer can also dispatch it by hand.
6. **Back-merge.** After a release, `release-please.yml` opens a pull request into `dev` from a new branch,
   `chore/back-merge-vX.Y.Z`, at the release commit. The head is not `main` itself: the `dev` ruleset requires an
   up-to-date branch, and "Update branch" would have to push to `main`.
7. **Token.** A GitHub App installation token when the variable `RELEASE_APP_CLIENT_ID` and the secret
   `RELEASE_APP_PRIVATE_KEY` are set; each job asks it for the permissions that job needs. Without them,
   `GITHUB_TOKEN`, and the maintainer closes and reopens each bot pull request to start CI.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Keep releases manual (the design before this ADR) | The version strings drifted (`0.1.0` in the engine at v0.3.0), and the release preparation branch was hand work on every release. |
| release-please targets `dev` | The tag would be on `dev`. A release must be a tag on `main` ([ADR 0002](0002-dev-integrates-main-releases.md)). |
| Keep `CHANGELOG.md` written by hand; release-please only bumps versions | Someone must still date `[Unreleased]` on every release. The owner chose a generated changelog. |
| Take `CHANGELOG.md` out of the `docs-lint` ratchet | It relaxes a gate. The `--fix` job keeps the gate and costs one commit on the release pull request. |
| Call `release.yml` as a reusable workflow | zizmor asks for the new `$/` self-repository syntax and the pinned actionlint rejects it. A dispatch needs neither and no suppression. |
| Back-merge from `main` itself | The `dev` ruleset requires an up-to-date head. Once `dev` moves, the pull request can only be updated by a push to `main`, which the `main` ruleset refuses. |

> A later reversal of this decision is folded into this table, so the rejected direction
> keeps its rationale inside the accepted record.

---

## Consequences

### Positive

* Nobody edits a version or the changelog by hand. The engine reports the released version.
* The GitHub release notes are the changelog entry.
* A wrong commit type now shows: it puts the change under the wrong heading or bumps the wrong part of the version.

### Negative / Trade-offs

* Each release has two more pull requests to merge: the release pull request and the back-merge pull request.
* `main` now takes pull requests from two sources, `dev` and the release branch.
* Without the GitHub App, CI does not start on the bot's pull requests until the maintainer closes and reopens them.
* The changelog lists commit subjects, not curated notes. A clear subject matters more than before.
* A failed `release.yml` leaves a release with no files, because release-please creates the release first. The fix is
  a re-run (`RELEASE_PROCESS.md`, "If the release fails").

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into
  *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference
  plus the index table in `docs/architecture/adrs/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/0005-release-please-cuts-releases.md`.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
