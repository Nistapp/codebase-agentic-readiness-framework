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
   [`audit/CHANGELOG.md`](audit/CHANGELOG.md) and the engine's
   [changelog](audit/engine/docs/reference/changelog.md) agree with it.
3. The numbers that appear in more than one place (the self-audit score in
   [Self-Audit](docs/reference/self-audit.md), the check count) are current.
4. Locally, `make check`, `make security` and `make validate-skills` pass.

## Tagging

`main` is protected: changes arrive only through a pull request that passes `CI Gate`
([branch protection](docs/reference/branch-protection.md)). Merge the release pull request first, then tag the merge
commit.

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
2. `python3 audit/engine/build.py`, which builds the reproducible single-file
   engine, `audit.pyz`.
3. `make validate-skills`, which builds the `agentic-readiness-audit` and `agentic-readiness-implement` skill
   bundles and validates both against the Agent Skills specification.
4. Zips the two bundles from `dev/dist/skills/`: `agentic-readiness-audit-<tag>.zip` and
   `agentic-readiness-implement-<tag>.zip`.
5. Writes `SHA256SUMS` over `audit.pyz` and the two zips.
6. Creates the GitHub release for the tag and attaches `audit.pyz`, the two zips and `SHA256SUMS`. The release body
   says "See CHANGELOG.md"; replace it with the release notes afterwards (see "After the release").

Every action in the workflow is pinned by commit SHA. To check a download, run `sha256sum -c SHA256SUMS` in the folder
that holds all four files.

## If it fails

The release is created in the last step, so a failure earlier leaves no release. Fix the cause on `main`, delete the
tag locally and on the remote, and tag again. Do not edit a published release's files.

## After the release

Update the `[Unreleased]` heading in the changelogs, and the version named in [`README.md`](README.md) and
[`audit/README.md`](audit/README.md). Replace the release body with short notes: what a user can do with this release,
and a link to the changelog entry (`gh release edit vX.Y.Z --notes-file <file>`).

## Release-day checklist

- [ ] `CI Gate` is green on the commit to tag. Locally, `make check`, `make security`, `make docs-lint` and
      `make validate-skills` pass.
- [ ] The ruleset on `main` is enabled, and [branch protection](docs/reference/branch-protection.md) says so with
      the date.
- [ ] `SECURITY.md` is present. Private vulnerability reporting, secret scanning and push protection are on.
- [ ] The root `README.md` quick start works from a fresh clone in a clean directory (Linux checked; macOS by the
      maintainer, or stated as CI-only).
- [ ] The docs state platform support truthfully: no native Windows claim.
- [ ] The changelogs have `[X.Y.Z] - YYYY-MM-DD` under an empty `[Unreleased]`.
- [ ] After the tag: `release.yml` passes; the release lists `audit.pyz`, both skill zips and `SHA256SUMS`; and
      `sha256sum -c SHA256SUMS` passes on the downloads.
