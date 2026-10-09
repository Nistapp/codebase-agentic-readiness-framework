# Brownfield Recipes — Documentation

> **Status:** Planned. Nothing under `brownfield-recipes/` is implemented yet. Every page below is a placeholder that names the roadmap step that fills it. See [`STYLE_GUIDE.md`](../STYLE_GUIDE.md) § 1.3.

## ADR Index

| # | Title | Status | Date |
|---|---|---|---|
| — | No ADRs yet | — | — |

## Key Documents

| Document | Quadrant | Purpose |
|---|---|---|
| [Style guide](../STYLE_GUIDE.md) | — | Canonical authoring rules |
| [Glossary](glossary.md) | Reference | Canonical terms |

## Tutorials

| Page | Purpose | Status |
|---|---|---|
| [Your first audit on a fixture](../tutorials/first-audit-on-a-fixture.md) | One guided audit on a small sample repo | Planned (S4.6) |

## How-To

| Page | Purpose | Status |
|---|---|---|
| [Run an audit](../how-to/run-an-audit.md) | Produce a confirmed report for a repo | Planned (S3.5) |
| [Implement an audit report](../how-to/implement-an-audit-report.md) | Apply confirmed findings on a branch | Planned (S5.4) |
| [Resume an interrupted run](../how-to/resume-an-interrupted-run.md) | Continue an audit or implementation after a crash | Planned (S2.3, S5.1) |
| [Add a stack profile](../how-to/add-a-stack-profile.md) | Contribute support for a new toolchain | Planned (S3.4) |
| [Run the evals](../how-to/run-the-evals.md) | Evaluate the recipes headlessly | Planned (S4.1) |

## Reference

| Page | Purpose | Status |
|---|---|---|
| [Tools CLI](../reference/tools-cli.md) | Every tool's synopsis, inputs, outputs and exit codes | Planned (S2.1–S2.8) |
| [Harness notes](../reference/harness-notes.md) | Claude Code, opencode, Codex, Cursor specifics | Planned (S4.6) |
| [Checks to framework map](../reference/how-the-checks-map-to-the-framework.md) | Check to requirement to framework section | Planned (S1.5, S4.6) |
| [Licensing](../reference/licensing.md) | Which licence covers what | Live |

## Explanation — User Overview

| Page | Purpose | Status |
|---|---|---|
| [1. Purpose & Non-Goals](user-overview/01-purpose-and-non-goals.md) | What the recipes are and refuse to be | Planned (S4.6) |
| [2. How the Recipes Work](user-overview/02-how-the-recipes-work.md) | Stages and decisions, for evaluators | Planned (S3.5, S5.4) |
| [3. Trust & Safety](user-overview/03-trust-and-safety.md) | What the recipes may do to a repo and machine | Planned (S3.5) |

## Explanation — Contributor Deep Dive

| Page | Purpose | Status |
|---|---|---|
| [1. Tool Contract](contributor-deep-dive/01-tool-contract.md) | The contract every tool follows | Planned (S2.1) |
| [2. Report Schema](contributor-deep-dive/02-report-schema.md) | Schema, versioning, engine mapping | Planned (S1.4) |
| [3. Check Catalogue & Rubrics](contributor-deep-dive/03-check-catalogue-and-rubrics.md) | Catalogue, methods, rubric anatomy | Planned (S1.5, S3.1) |
| [4. Stack Profiles](contributor-deep-dive/04-stack-profiles.md) | How profiles adapt checks and playbooks | Planned (S3.4) |
| [5. Evaluation](contributor-deep-dive/05-evaluation.md) | Corpus, metrics, models | Planned (S4.1) |

## Framework Dependencies

The recipes implement Phase 1 of this repository's framework: [Phased Approach](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) and, once written, [`spec/`](../../../spec/README.md). Where they disagree, the framework wins and the recipes have a defect.

The deterministic engine keeps its own documentation under `brownfield-recipes/deterministic-audit/docs/` after migration (roadmap S0.3–S0.4).
