# Release Process

This project uses a strict GitFlow-inspired branching strategy combined with automated releases.

- `main` is the production branch. It contains only released code.
- `dev` is the active development branch.
- CI (`ci.yml`) guards every push/PR to `main` and `dev`.
- Release automation (`release-and-sync.yml`) handles version bumps, changelog generation, GitHub releases, **npm publishing**, and the back-merge to `dev`.
- Direct PRs to `main` may only originate from `dev` (enforced by `enforce-dev-base.yml`).

> **One-time prerequisite:** the automated npm publish uses **npm Trusted Publishing** (GitHub OIDC — no stored token). On <https://npmjs.com> open the package → **Settings → Trusted Publishing**, enable it for source **GitHub** / owner **<org>** / repository **<project>**, and restrict it to the workflow **`release-and-sync.yml`**.

## The Step-by-Step Release Process

1. **Develop:** All features and fixes are PR'd into `dev`.
2. **Stage for Release:** When ready, open a PR from `dev` to `main`.
3. **Merge to Main:** Once CI passes, merge `dev` into `main`.
4. **Release Please:** GitHub Actions automatically opens a "Release PR" against `main` with the version bump and updated `CHANGELOG.md`.
5. **Publish:** Merge the Release PR. The GitHub Release and npm publish happen automatically.
6. **⚠️ THE BACK-MERGE (DO NOT FORGET):** Merge the automated PR from `main` → `dev` immediately to prevent conflicts.

> **Versioning:** Release Please determines the next version from Conventional Commits. To override, edit the Release PR title before merging.
