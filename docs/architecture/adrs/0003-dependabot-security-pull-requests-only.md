# 0003. Dependabot Opens Security Pull Requests Only; Major Versions Are Advisory

* **Status:** Accepted
* **Date:** 2026-11-08
* **Last reviewed:** 2026-11-09
* **Deciders:** [@nistapp]

---

## Context

Dependabot opened weekly version-update pull requests for the GitHub Actions, for example #47 and #48. Each one is
work for the maintainer, and a major version can break CI or the release.

The owner wants two things:

* Dependabot opens a pull request only for a security fix.
* A major version is advisory: it never arrives as a pull request that is ready to merge.

Before this decision, the dev tool versions were in the `Makefile` only (ruff, mypy, detect-secrets, coverage,
jsonschema, skills-ref, markdownlint-cli2) and in the workflows (uv). Dependabot cannot read a `Makefile`, so these
tools had no security alerts.

GitHub's documentation (the Dependabot options reference and "Configuring Dependabot security updates", read on
2026-11-08) gives these facts:

* `open-pull-requests-limit: 0` stops version updates. Security updates have their own, fixed limit.
* `ignore`, with `update-types`, applies to version updates and to security updates.
* `groups` with `applies-to: security-updates` joins security fixes into one pull request.
* When an entry sets `target-branch`, its options stop applying to security updates. Security updates always use
  the default branch.
* `exclude-paths` applies to version updates only.

## Decision

1. **Security pull requests only.** Each entry in [`.github/dependabot.yml`](../../../.github/dependabot.yml) sets
   `open-pull-requests-limit: 0`. Dependabot security updates stay on in the repository settings.
2. **Majors are advisory.** Each entry for a real dependency ignores `version-update:semver-major`. A security fix
   that needs a major version opens no pull request. Its alert stays in the Security tab. The maintainer upgrades by
   hand on a `chore/` branch from `dev`.
3. **One pull request per ecosystem.** A `security-fixes` group joins the minor and patch security fixes.
4. **No `target-branch`.** The default branch is `dev`
   ([ADR 0002](0002-dev-integrates-main-releases.md)), so every Dependabot pull request goes to `dev` without it.
5. **The dev tools are visible to Dependabot.** Their versions move to three manifests in `dev/tools/`, each with a
   lockfile:

   | Manifest | Lockfile | Tools | Dependabot ecosystem |
   |---|---|---|---|
   | [`pyproject.toml`](../../../dev/tools/pyproject.toml) (group `tools`) | `uv.lock` | actionlint-py, check-jsonschema, coverage, detect-secrets, jsonschema, mypy, ruff, skills-ref, uv, zizmor | `uv` |
   | [`package.json`](../../../dev/tools/package.json) | `package-lock.json` | markdownlint-cli2, mermaid-cli | `npm` |
   | [`osv/go.mod`](../../../dev/tools/osv/go.mod) (a `tool` directive) | `osv/go.sum` | osv-scanner ([ADR 0006](0006-security-verb-audits-dependencies-with-osv-scanner.md)) | `gomod` |

   Nothing installs these projects. The [`Makefile`](../../../Makefile), [`lefthook.yml`](../../../lefthook.yml),
   [`dev/mermaid_check.py`](../../../dev/mermaid_check.py) and the workflows (`setup-uv` `version-file`) read each
   version from them, and still run the tools through `uvx`, `npx` and `go tool`. The root [`.nvmrc`](../../../.nvmrc) pins
   Node for CI's `docs` job. [`test_tool_pins.py`](../../../dev/tests/test_tool_pins.py) fails when a pin is not
   exact, when a lockfile disagrees with its manifest, or when another file repeats a version.
6. **Data is not a dependency.** The greenfield template (`greenfield/templates/`) and the engine's test fixtures
   (`audit/engine/tests/fixtures/`) have entries that ignore every dependency. Their alerts stay visible; Dependabot
   never edits them. A fixture is test data (`AGENTS.md`).
7. **Routine and major upgrades are planned.** Before each release, the maintainer reviews the pins and the open
   alerts ([`RELEASE_PROCESS.md`](../../../RELEASE_PROCESS.md#dependency-updates)).

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Weekly version updates for every level (the design before this ADR) | A pull request each week, majors included. A major can break CI or the release. |
| Version updates for minor and patch only | Minor releases of ruff and markdownlint often change rules, which changes many files. The owner wants security pull requests only. |
| Patch-only version updates for the dev tools, grouped monthly | Offered on 2026-11-08; the owner chose security pull requests only. |
| `target-branch: dev` on each entry | It stops `ignore` and `groups` from applying to security updates. `dev` is the default branch, so it is not needed. |
| Keep the tool pins in the `Makefile` | Dependabot cannot read a `Makefile`. The tools would get no security alerts. |
| `requirements.txt` without a lockfile | The repository's own audit then fails `EXEC-02` (no lockfile) for Python and Node, and `EXEC-01` for Node. |
| Exclude `dev/tools/` from the self-audit | It narrows a gate to get green. |
| Pin `uv` in each workflow | Four copies of one version, and Dependabot does not read a `setup-uv` input. |

> A later reversal of this decision is folded into this table, so the rejected direction
> keeps its rationale inside the accepted record.

---

## Consequences

### Positive

* Dependabot opens a pull request only for a security fix that is not a major version.
* The dev tools and their dependencies (through the lockfiles) get security alerts.
* Each tool version is written once. A Dependabot pull request changes the manifest and its lockfile together.

### Negative / Trade-offs

* A vulnerability whose only fix is a major version waits for the maintainer. No pull request reminds them; the
  alert does.
* Nobody is told about a routine new version. The release checklist holds the review step.
* Two lockfiles, about 380 KB together, are in the repository. After a manual pin change, regenerate them
  (`uv lock --directory dev/tools`; `npm install --package-lock-only --ignore-scripts` in `dev/tools`).
* The template and the fixtures can raise alerts that need no action. The maintainer dismisses them.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into
  *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference
  plus the index table in `docs/architecture/adrs/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/0003-dependabot-security-pull-requests-only.md`.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
