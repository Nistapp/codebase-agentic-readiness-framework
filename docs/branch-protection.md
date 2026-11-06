# Branch protection

**Status: recommended, not enabled.** On 2026-11-06 the settings of `Nistapp/codebase-agentic-readiness-framework`
were read from GitHub: `main` is not protected (the API answers 404 "Branch not protected") and the repository has no
rulesets. The rules below are what the maintainer recommends; nothing on GitHub enforces them yet. Until the maintainer
turns them on, `CI Gate` runs on every pull request and every push but nothing blocks a merge when it fails.

This page is the declaration of the recommended rules, so they are reviewed like any other change. GitHub does not read
this file: the maintainer applies the rules in the repository settings, and updates this page in the same step.

## Recommended rules

The protected branch would be `main`.

| Rule | Recommended setting |
| --- | --- |
| Changes arrive through a pull request | Required; no direct pushes to `main` |
| Required status check | `CI Gate`, and no other: it stands for the whole matrix |
| Branch up to date before merge | Required |
| Force pushes and branch deletion | Blocked |
| Conversations | Resolved before merge |
| Merge method | Merge commit, so each Conventional Commit can be reverted alone |
| Who applies and changes these rules | The maintainer |

## How the maintainer turns it on

In the repository on GitHub: Settings, Branches (or Rules, Rulesets), add a rule for `main`, and set each row of the
table above. `CI Gate` appears in the list of required checks only after it has run once on the repository. To re-check
the result without the web page, read the branch (`gh api repos/Nistapp/codebase-agentic-readiness-framework/branches/main/protection`):
a 404 means protection is off. When the settings change, edit the status line above with the new date and result.

## The required check

`CI Gate` is the last job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). It needs five jobs and fails
unless each one succeeded:

| Job | What it runs |
| --- | --- |
| `check` | `make check` on Ubuntu and macOS, Python 3.11 and 3.14 |
| `security` | `make security` |
| `coverage` | `make coverage`, which fails below the floor in `.coveragerc` |
| `self-audit` | `make self-audit`: the engine on this repository; exit 2 when a finding appears that `.audit-baseline.json` did not have |
| `docs` | `make docs-lint` and the Mermaid render check, when Markdown changed |

Requiring `CI Gate` alone means a new matrix leg or a renamed job never needs a settings change. Add a new job to
`needs:` in the workflow, not to the branch rules.

## Who merges

A session of an AI agent never pushes, tags or merges in this repository
([ADR 0003](../brownfield-recipes/docs/architecture/adrs/0003-push-and-pr-policy.md) covers the target repositories;
the rule for this one is in [`AGENTS.md`](../AGENTS.md)). The maintainer pushes and merges.
