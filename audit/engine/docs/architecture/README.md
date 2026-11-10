# Architecture Documentation

> **Status:** v1 complete — the `audit/` package runs, and every pack (`IDX`, `AGT`, `EXEC`, `CMD`, `DOC`, `NAV`, `SEC`,
> `TOOL`, `CI`, `TST`, `BASE`, `CON` and the informational `HYG` set) is live. All 55 scoreable checks are implemented,
> and Tier-C probe checks report `UNKNOWN` unless probes are permitted. Pages below describe the design of record and
> the current implementation state. See the [style guide](../../../../docs/STYLE_GUIDE.md) § 1, rule 3
> (describe only what exists).
>
> **Related:** this is the router for the engine at `audit/engine/`. The audit recipe builds on it; see
> [`audit/README.md`](../../../README.md). The repository's root router is
> [`docs/README.md`](../../../../docs/README.md).

## ADR Index

| # | Title | Summary |
|---|---|---|
| [0001](adrs/0001-report-not-a-gate.md) | The Audit Reports; It Does Not Gate | A completed scan exits 0 whatever it finds; `--fail-on` exists but is off by default. |
| [0002](adrs/0002-read-only-and-tier-c-opt-in.md) | Read-Only by Default; Tier-C Probes Are Opt-In | The engine never writes to or installs into the target; Tier-C probes run only on explicit request. |
| [0003](adrs/0003-component-depth-declared-depth-1.md) | Component Depth: Declared Components, Depth 1 | Only components a build manifest declares are scored, and only at depth 1. |
| [0004](adrs/0004-no-llm-in-v1.md) | No LLM Calls in v1 | The engine is deterministic and standard-library only, with no model calls. |
| [0005](adrs/0005-module-layout-and-zipapp-distribution.md) | Module Layout and Zipapp Distribution | The package tree is the source; a zipapp is the distributable; nothing needs installing. |
| [0006](adrs/0006-private-check-helpers-and-ignore-engine.md) | Private Check Helpers and the Ignore Engine | Checks share two private helpers, `audit/ignore.py` and `rules/checks/_common.py`; no new stage or pack. |
| [0007](adrs/0007-json-report-render-contract.md) | The JSON Report Is the Render Contract; the Markdown Is a Template Over It | The JSON report (schema v2) is the contract; the Markdown report is a code template over it. |
| [0008](adrs/0008-what-counts-as-the-repository.md) | What Counts as the Repository | Runners rank depth first; templates, examples and fixtures are set aside, and the report lists them. |
| [0009](adrs/0009-nested-ignore-files-and-negation.md) | Nested Ignore Files and Negation | Four checks use a scoped matcher that honours nested `.gitignore` files and negation; the walk is unchanged. |

## Key Documents

| Document | Purpose |
|---|---|
| [glossary.md](glossary.md) | Canonical definitions of audit and readiness terms |

## User Overview (Evaluator / Adopter Track)

| Page | Purpose | Status |
|---|---|---|
| [1. Purpose & Non-Goals](user-overview/01-purpose-and-non-goals.md) | What the audit is, what it refuses to be, and how to read its output | Published |
| [2. The Readiness Model](user-overview/02-the-readiness-model.md) | Phases, tiers, verdicts, severity, and what the score does and does not mean | Published |
| [3. Why These Checks](user-overview/03-why-these-checks.md) | The failure mode behind every check family | Published |

## Contributor Deep Dive

| Page | Purpose | Status |
|---|---|---|
| [1. Scan Engine & Tiering](contributor-deep-dive/01-scan-engine-and-tiering.md) | Pipeline stages, bounded traversal, stage contracts, determinism, self-verification | Published |
| [2. Check Catalogue](contributor-deep-dive/02-check-catalogue.md) | Every check: id, tier, phase, severity, evidence rule, implementation status | Published |

## Reference

| Page | Purpose | Status |
|---|---|---|
| [Changelog](../reference/changelog.md) | What changed between ruleset revisions, and which verdicts move | Live |

## How-To (Task Track)

| Page | Purpose | Status |
|---|---|---|
| [Run an audit](../how-to/run-an-audit.md) | Produce a report against a target repository | Published (design) |
| [Read the report](../how-to/read-the-report.md) | Turn a report into an ordered work queue | Published (design) |
| [Hand findings to remediation](../how-to/hand-findings-to-remediation.md) | Feed the report into the remediation pass | Published (design) |
| [Wire the ratchet into CI](../how-to/wire-the-ratchet-into-ci.md) | Fail only on regression, never on the first scan | Published (design) |

> [!TIP]
> Before you add, change or delete an ADR, read [`ADR_POLICY.md`](../../../../docs/ADR_POLICY.md). Add its row to this
> table and to the root index in the same change.

## Framework Dependencies

This tool implements Phase 1 of an external methodology. Its normative source is
the codebase agentic-readiness framework at the root of this repository (see the [Phased Approach](../../../../docs/framework/phased-approach.md)).
Where the two disagree, the framework wins and this tool has a defect.

The framework is the root of this repository, and the tool finds it from its own location: `--verify-rules`
needs no flag, and every report records its HEAD as `framework_revision`. `--framework <path>` selects a different
checkout, and is required when the tool has been copied out of the repository.
