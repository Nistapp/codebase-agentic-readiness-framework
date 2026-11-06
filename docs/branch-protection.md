# Branch protection

The protected branch is `main`. This page is the declaration of the rules, so they are reviewed like any other change.
GitHub does not read this file: the maintainer applies the rules in the repository settings (Settings, Branches), and
updates this page in the same step when a rule changes.

## Rules

| Rule | Setting |
| --- | --- |
| Changes arrive through a pull request | Required; no direct pushes to `main` |
| Required status check | `CI Gate`, and no other: it stands for the whole matrix |
| Branch up to date before merge | Required |
| Force pushes and branch deletion | Blocked |
| Conversations | Resolved before merge |
| Who applies and changes these rules | The maintainer |

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
