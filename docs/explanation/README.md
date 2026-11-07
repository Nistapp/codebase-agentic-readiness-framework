# Explanation

> **Status:** Live for v0.1 (the audit MVP): the schemas, the check catalogue, the engine, the tools, the
> audit recipe, the eval harness and the fixture-sweep plus real-repo results are all built and published.
> The implementation recipe (v0.2.0): Stages 0 to 5, the state contract and its tools, the thirteen
> playbooks and its skill bundle are live. Each page below carries its own
> status, and a page marked Planned names the roadmap step that fills it. See
> [`STYLE_GUIDE.md`](../STYLE_GUIDE.md) § 1.3.

These pages explain why the audit and implement recipes work the way they do. For tutorials, how-to guides, reference
pages and decisions, use the root router: [`docs/README.md`](../README.md).

## User overview

For evaluators and adopters. Read in order.

| Page | Purpose | Status |
|---|---|---|
| [1. Purpose & Non-Goals](user-overview/01-purpose-and-non-goals.md) | What the recipes are and refuse to be | Live |
| [2. How the Recipes Work](user-overview/02-how-the-recipes-work.md) | Stages and decisions, for evaluators | Live for audits and implementations |
| [3. Trust & Safety](user-overview/03-trust-and-safety.md) | What the recipes may do to a repo and machine | Live; §5 is a table of what the implement recipe may and never does; the push/PR rule is [ADR 0003](../../implement/docs/architecture/adrs/0003-push-and-pr-policy.md); the risks are in the [risk register](../framework/risks-and-mitigations.md) (R9-R14) |

## Contributor deep dive

For engineers who change the recipes or their tools.

| Page | Purpose | Status |
|---|---|---|
| [1. Tool Contract](contributor-deep-dive/01-tool-contract.md) | The contract every tool follows | Live |
| [2. Report Schema](contributor-deep-dive/02-report-schema.md) | Schema, versioning, engine mapping | Live (the validator, the report builder, the engine adapter and the renderer are live) |
| [3. Check Catalogue & Rubrics](contributor-deep-dive/03-check-catalogue-and-rubrics.md) | Catalogue, methods, rubric anatomy | Live; every check family is written (S3.1, S3.2, S3.3 all closed), 71 checks across thirteen files |
| [4. Stack Profiles](contributor-deep-dive/04-stack-profiles.md) | How profiles adapt checks and playbooks | Live; three profiles plus `stacks/README.md` |
| [5. Evaluation](contributor-deep-dive/05-evaluation.md) | Corpus, metrics, models | Live for the corpus format, scorer, Claude Code runner, the fixture sweep and the real-repo runs plus the rubric-tightening round they fed (S4.1–S4.4); a second harness/model's scored comparison (`S4.3.4`) and other harnesses' runner scripts stay Planned |

## Framework dependencies

The recipes implement Phase 1 of this repository's framework:
[Phased Approach](../framework/phased-approach.md#phase-1-agentic-bootstrap-) and [`spec/`](../../spec/README.md), the
numbered requirements. Where they disagree, the framework wins and the recipes have a defect.

The engine explains itself in its own tree: [`audit/engine/docs/architecture/README.md`](../../audit/engine/docs/architecture/README.md).
