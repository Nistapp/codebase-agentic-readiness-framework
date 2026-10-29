# Brownfield Recipes — Documentation

> **Status:** Live for v0.1 (the audit MVP): the schemas, the check catalogue, the engine, the tools, the
> audit recipe, the eval harness and the fixture-sweep plus real-repo results are all built and published.
> The implementation recipe (v0.2, milestone M5) is not written yet. Each page below carries its own
> status, and a page marked Planned names the roadmap step that fills it. See
> [`STYLE_GUIDE.md`](../STYLE_GUIDE.md) § 1.3.

## ADR Index

| # | Title | Status | Date |
|---|---|---|---|
| [0001](adrs/0001-tools-import-engine.md) | Tools Import the Engine in Process | Accepted | 2026-10-10 |

## Key Documents

| Document | Quadrant | Purpose |
|---|---|---|
| [Style guide](../STYLE_GUIDE.md) | — | Canonical authoring rules |
| [Glossary](glossary.md) | Reference | Canonical terms |
| [Deterministic engine docs](../../deterministic-audit/docs/architecture/README.md) | Explanation | The engine's own doc router and ADR index |

## Tutorials

| Page | Purpose | Status |
|---|---|---|
| [Your first audit on a fixture](../tutorials/first-audit-on-a-fixture.md) | One guided audit on a small sample repo | Live |

## How-To

| Page | Purpose | Status |
|---|---|---|
| [Run an audit](../how-to/run-an-audit.md) | Produce a confirmed report for a repo | Live (S3.5) |
| [Implement an audit report](../how-to/implement-an-audit-report.md) | Apply confirmed findings on a branch | Planned (S5.4) |
| [Resume an interrupted run](../how-to/resume-an-interrupted-run.md) | Continue an audit or implementation after a crash | Live for audits (S2.3); implementations Planned (S5.1) |
| [Add a stack profile](../how-to/add-a-stack-profile.md) | Contribute support for a new toolchain | Live; four profiles exist (S3.4 closed) |
| [Run the evals](../how-to/run-the-evals.md) | Evaluate the recipes headlessly | Live for the corpus, expected-results format, scorer and the Claude Code runner (S4.1); other harnesses' own runner scripts stay Planned, deferred per `D57` |

## Reference

| Page | Purpose | Status |
|---|---|---|
| [Tools CLI](../reference/tools-cli.md) | Every tool's synopsis, inputs, outputs and exit codes | Live for `engine.py`, `validate_report.py`, `report.py`, `render_report.py`, `facts.py`, `recipe_lint.py` (all eight rules), the generated `tools/CATALOGUE.md` and `build_skills.py`; `progress.py` and `check_drift.py` Planned (S5.1) |
| [Harness notes](../reference/harness-notes.md) | Claude Code, opencode, Codex, Cursor specifics | Live for Claude Code and opencode, the two actually run (S4.1.3, S4.5.3); Codex and Cursor untested |
| [Checks to framework map](../reference/how-the-checks-map-to-the-framework.md) | Check to requirement to framework section | Live; the generated table covers all 71 checks |
| [Licensing](../reference/licensing.md) | Which licence covers what | Live |
| [Evaluation Results](../reference/eval-results.md) | Fixture-sweep and real-repo results, cost/time, misses | Live for the fixture sweep (S4.2) and the real-repo runs (S4.3, one run per repo under `D61`); a second harness/model's scored comparison (`S4.3.4`) stays Planned, deferred per `D57` |

## Explanation — User Overview

| Page | Purpose | Status |
|---|---|---|
| [1. Purpose & Non-Goals](user-overview/01-purpose-and-non-goals.md) | What the recipes are and refuse to be | Live for the audit recipe; the implementation recipe it describes is Planned (M5) |
| [2. How the Recipes Work](user-overview/02-how-the-recipes-work.md) | Stages and decisions, for evaluators | Live for audits (S3.5); the implementation loop Planned (S5.4) |
| [3. Trust & Safety](user-overview/03-trust-and-safety.md) | What the recipes may do to a repo and machine | Live for audits (S3.5); implementation safety Planned (S5.4) |

## Explanation — Contributor Deep Dive

| Page | Purpose | Status |
|---|---|---|
| [1. Tool Contract](contributor-deep-dive/01-tool-contract.md) | The contract every tool follows | Live |
| [2. Report Schema](contributor-deep-dive/02-report-schema.md) | Schema, versioning, engine mapping | Live (the validator, the report builder, the engine adapter and the renderer are live) |
| [3. Check Catalogue & Rubrics](contributor-deep-dive/03-check-catalogue-and-rubrics.md) | Catalogue, methods, rubric anatomy | Live; every check family is written (S3.1, S3.2, S3.3 all closed), 71 checks across thirteen files |
| [4. Stack Profiles](contributor-deep-dive/04-stack-profiles.md) | How profiles adapt checks and playbooks | Live; S3.4 is closed, four profiles written |
| [5. Evaluation](contributor-deep-dive/05-evaluation.md) | Corpus, metrics, models | Live for the corpus format, scorer, Claude Code runner, the fixture sweep and the real-repo runs plus the rubric-tightening round they fed (S4.1–S4.4); a second harness/model's scored comparison (`S4.3.4`) and other harnesses' runner scripts stay Planned |

## Framework Dependencies

The recipes implement Phase 1 of this repository's framework: [Phased Approach](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) and, once written, [`spec/`](../../../spec/README.md). Where they disagree, the framework wins and the recipes have a defect.

The deterministic engine keeps its own documentation under `brownfield-recipes/deterministic-audit/docs/` after migration (roadmap S0.3–S0.4).
