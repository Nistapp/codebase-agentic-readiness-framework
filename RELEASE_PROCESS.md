# Release process

Only the maintainer cuts a release. A session of an AI agent never pushes, tags or starts the release workflow
([`AGENTS.md`](AGENTS.md)).

## What a release is

A tag `vMAJOR.MINOR.PATCH` on `main`. The tag triggers
[`.github/workflows/release.yml`](.github/workflows/release.yml), which publishes a GitHub release carrying the
files a one-off user needs without cloning or building anything.

## Before you tag

1. `main` is green: the `CI Gate` check has passed on the commit you will tag.
2. [`CHANGELOG.md`](CHANGELOG.md) has a heading for the version, moved down from `[Unreleased]`, and
   [`brownfield-recipes/CHANGELOG.md`](brownfield-recipes/CHANGELOG.md) and the engine's
   [changelog](brownfield-recipes/deterministic-audit/docs/reference/changelog.md) agree with it.
3. The numbers that appear in more than one place (the self-audit score in
   [Self-Audit](brownfield-recipes/docs/reference/self-audit.md), the check count) are current.
4. Locally, `make check`, `make security` and `make validate-skills` pass.

## Tagging

```bash
git switch main && git pull --ff-only
git tag -s vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Use `git tag -a` if you do not sign tags.

## What the workflow does

On a pushed tag matching `v*` it runs, on Ubuntu with `contents: write` as the only permission and no secret beyond
`GITHUB_TOKEN`:

1. `make check` and `make security`, so a tag on a red commit publishes nothing.
2. `python3 brownfield-recipes/deterministic-audit/tools/build.py`, which builds the reproducible single-file
   engine, `audit.pyz`.
3. `make validate-skills`, which builds the `agentic-readiness-audit` and `agentic-readiness-implement` skill
   bundles and validates both against the Agent Skills specification.
4. Zips the audit bundle under `dist/skills/`. The implement bundle is built and validated but not attached yet.
5. Writes `SHA256SUMS` over `audit.pyz` and the zip.
6. Creates the GitHub release for the tag and attaches `audit.pyz`, the skill zip and `SHA256SUMS`.

Every action in the workflow is pinned by commit SHA. To check a download, run `sha256sum -c SHA256SUMS`.

## If it fails

The release is created in the last step, so a failure earlier leaves no release. Fix the cause on `main`, delete the
tag locally and on the remote, and tag again. Do not edit a published release's files.

## After the release

Update the `[Unreleased]` heading in the changelogs, and the version named in [`README.md`](README.md) and
[`brownfield-recipes/README.md`](brownfield-recipes/README.md).
