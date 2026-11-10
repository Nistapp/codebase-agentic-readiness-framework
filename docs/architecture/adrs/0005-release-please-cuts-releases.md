# 0005. Release-Please Computes the Version, Writes the Changelog and Tags the Release

## Context

A manual release takes five steps by hand:

1. open a release preparation branch;
2. move the `[Unreleased]` changelog entries under a dated heading;
3. change the version strings;
4. promote `dev` to `main`;
5. push a signed tag.

Hand work drifts. A stale version string makes `audit --version` and every report's provenance name the wrong
version.

The commit subjects follow Conventional Commits, and CI checks them (`dev/commit_lint.py`). So a tool can
compute the next version and write the changelog from them. The owner wants automated versions and releases,
with the back-merge pattern of the
[Digital-Assistant-SDK](https://github.com/Digital-Assistant/Digital-Assistant-SDK/blob/main/RELEASE_PROCESS.md)
repository. The greenfield template in this repository (`greenfield/templates/github/workflows/release-and-sync.yml`)
uses the same pattern.

## Decision

1. **release-please, one root package.** [`release-please-config.json`](../../../release-please-config.json) uses
   the `simple` release type with one package at `.` and tags `vX.Y.Z`. Before 1.0.0, a breaking change bumps MINOR
   and any other change bumps PATCH, as [`RELEASE_PROCESS.md`](../../../RELEASE_PROCESS.md) says.
   [`.release-please-manifest.json`](../../../.release-please-manifest.json) holds the last released version.
2. **The version lives in five places, and the bot changes all five.** The manifest, the `CHANGELOG.md` entry and
   three code lines: the engine's `__version__` and `FRAMEWORK_RELEASE` in `audit/tools/report.py` and
   `implement/tools/progress.py`. Each code line is an `extra-files` entry with the `x-release-please-version`
   marker. `dev/tests/test_release_config.py` fails when a code line and the manifest disagree. `release.yml` refuses
   a tag that differs from `__version__`. Every report and state carries this one version
   ([ADR 0008](0008-one-release-version-and-current-schemas-only.md)).
3. **The release pull request.** On each push to `main`,
   [`release-please.yml`](../../../.github/workflows/release-please.yml) opens or updates a pull request from
   `release-please--branches--main` into `main`. Merging it tags the release and creates the GitHub release, with the
   changelog entry as its notes. `Check source branch` accepts that branch when a bot opened the pull request
   ([ADR 0002](0002-dev-integrates-main-releases.md)).
4. **The changelog is generated, then fixed for lint.** release-please writes `*` bullets and double blank lines. The
   `docs-lint` ratchet covers `CHANGELOG.md` and refuses both. So a job runs `make changelog-fix` (markdownlint
   `--fix`) on the release pull request and pushes the fix. The ratchet does not change. The recipes' own changelog,
   `audit/CHANGELOG.md`, gets no new entries; the root changelog covers the recipes.
5. **Publishing.** `release.yml` has no tag-push trigger, because a tag made with `GITHUB_TOKEN` starts no workflow.
   `release-please.yml` dispatches it with the tag. A dispatch is the one event that `GITHUB_TOKEN` may start a
   workflow with. The maintainer can also dispatch it by hand.
6. **Back-merge.** After a release, `release-please.yml` opens a pull request into `dev` from a new branch,
   `chore/back-merge-vX.Y.Z`, at the release commit. The head is not `main` itself: resolving a conflict with `dev`
   would have to push to `main`.
7. **Token.** A GitHub App installation token, when the variable `RELEASE_APP_CLIENT_ID` and the secret
   `RELEASE_APP_PRIVATE_KEY` are set. Each job asks it for the permissions that job needs. Without them,
   `GITHUB_TOKEN`, and the maintainer closes and reopens each bot pull request to start CI.

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| Manual releases | Hand-kept version strings drift, and the release preparation branch is hand work on every release. |
| release-please targets `dev` | The tag would be on `dev`. A release must be a tag on `main` ([ADR 0002](0002-dev-integrates-main-releases.md)). |
| Keep `CHANGELOG.md` written by hand; release-please only bumps versions | Someone must still date `[Unreleased]` on every release. The owner chose a generated changelog. |
| Take `CHANGELOG.md` out of the `docs-lint` ratchet | It relaxes a gate. The `--fix` job keeps the gate and costs one commit on the release pull request. |
| Call `release.yml` as a reusable workflow | zizmor asks for the new `$/` self-repository syntax and the pinned actionlint rejects it. A dispatch needs neither and no suppression. |
| Back-merge from `main` itself | The `dev` ruleset requires an up-to-date head. Once `dev` moves, the pull request can only be updated by a push to `main`, which the `main` ruleset refuses. |

## Consequences

### Positive

* Nobody edits a version or the changelog by hand. The engine reports the released version.
* The GitHub release notes are the changelog entry.
* A wrong commit type shows: it puts the change under the wrong heading or bumps the wrong part of the version.

### Negative / Trade-offs

* Each release has two more pull requests to merge: the release pull request and the back-merge pull request.
* `main` takes pull requests from two sources, `dev` and the release branch.
* Without the GitHub App, CI does not start on the bot's pull requests until the maintainer closes and reopens them.
* The changelog lists commit subjects, not curated notes. A clear subject matters.
* A failed `release.yml` leaves a release with no files, because release-please creates the release first. The fix is
  a re-run (`RELEASE_PROCESS.md`, "If the release fails").
