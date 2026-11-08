# Documentation

This repository is the Codebase Agentic Readiness Framework. It says what makes a codebase safe for AI coding agents,
and it holds tools that check a codebase. This page is the one router for the documentation. Each page under `docs/`
is linked below, once. The engine keeps its own docs tree beside its code; its router is under
[Components](#components).

To audit a repository, open Claude Code at the root of this repository and say "Audit `<repo-path>` and write the
output to `<output-path>`". To fix the findings, say "Start implementing the fixes on `<repo-path>` based on
`<audit-json-path>`".

## Tutorials

| Page | What it teaches |
| --- | --- |
| [First audit on a fixture](tutorials/first-audit-on-a-fixture.md) | One guided audit on a small sample repository |

## How-to guides

| Page | What it does |
| --- | --- |
| [Contribute a change](how-to/contribute-a-change.md) | Move one change from a work branch into `dev` through a pull request |
| [Install the skills](how-to/install-the-skills.md) | Put both skills from a release into a project, with no clone |
| [Run an audit](how-to/run-an-audit.md) | Produce a confirmed report through the agent and the audit recipe |
| [Implement an audit report](how-to/implement-an-audit-report.md) | Apply the confirmed findings, one theme per branch |
| [Resume an interrupted run](how-to/resume-an-interrupted-run.md) | Continue an audit or an implementation after a stop |
| [Add a stack profile](how-to/add-a-stack-profile.md) | Add support for a new toolchain |
| [Run the evals](how-to/run-the-evals.md) | Evaluate the recipes headlessly |

## Reference

| Page | What it lists |
| --- | --- |
| [Tools CLI](reference/tools-cli.md) | Each tool's synopsis, inputs, outputs and exit codes |
| [Harness notes](reference/harness-notes.md) | What differs between Claude Code, opencode, Codex and Cursor |
| [Checks to framework map](reference/how-the-checks-map-to-the-framework.md) | Each check, its requirement and its framework section |
| [Evaluation results](reference/eval-results.md) | Fixture-sweep and real-repository results |
| [Self-audit](reference/self-audit.md) | This repository's own Phase 1 score and the CI ratchet |
| [Development tooling](reference/dev-tooling.md) | Each tool that checks this repository, its command, its CI job and its pin |
| [Branch protection](reference/branch-protection.md) | The branch model, and the rulesets on `dev` and `main` |
| [Licensing](reference/licensing.md) | Which licence covers which files |
| [Glossary](glossary.md) | The terms of the recipes and tools |

## Explanation

| Page | What it explains |
| --- | --- |
| [Explanation index](explanation/README.md) | The two tracks below, in reading order |
| [Purpose and non-goals](explanation/user-overview/01-purpose-and-non-goals.md) | What the recipes are, and what they refuse to be |
| [How the recipes work](explanation/user-overview/02-how-the-recipes-work.md) | The stages and decisions, for evaluators |
| [Trust and safety](explanation/user-overview/03-trust-and-safety.md) | What the recipes may do to a repository and a machine |
| [Tool contract](explanation/contributor-deep-dive/01-tool-contract.md) | The contract that each tool follows |
| [Report schema](explanation/contributor-deep-dive/02-report-schema.md) | The schema, its versions and the engine mapping |
| [Check catalogue and rubrics](explanation/contributor-deep-dive/03-check-catalogue-and-rubrics.md) | The catalogue, the methods and the rubric anatomy |
| [Stack profiles](explanation/contributor-deep-dive/04-stack-profiles.md) | How profiles adapt checks and playbooks |
| [Evaluation](explanation/contributor-deep-dive/05-evaluation.md) | The corpus, the metrics and the models |
| [Architecture](architecture/README.md) | A map of the repository's parts and what each reads and writes |

## The framework

The framework is normative. If a tool disagrees with it, the tool is wrong.

| Page | What it holds |
| --- | --- |
| [Overview](framework/overview.md) | What an agentic-ready codebase is |
| [Phased approach](framework/phased-approach.md) | The four phases; the recipes implement Phase 1 |
| [Brownfield track](framework/brownfield-track.md) | How to make a legacy codebase agentic-ready |
| [Tool ecosystem](framework/tool-ecosystem.md) | Index tools and other tools the framework uses |
| [Risks and mitigations](framework/risks-and-mitigations.md) | The risk register |
| [References](framework/references.md) | Sources |
| [Framework glossary](framework/glossary.md) | The framework's own terms |
| [`spec/`](../spec/README.md) | The numbered requirements (`REQ-...`) for a repository |
| [`greenfield/`](../greenfield/README.md) | The recipe and templates for a new project |

## Decisions

The [ADR index](architecture/adrs/README.md) lists every decision of record, in all five groups. ADRs live beside the
component they govern ([ADR 0001](architecture/adrs/0001-decisions-live-beside-the-component.md)).

## Components

| Component | Entry point |
| --- | --- |
| The audit recipe, its checks, schemas and tools | [`audit/README.md`](../audit/README.md) |
| The implement recipe, its playbooks and tools | [`implement/README.md`](../implement/README.md) |
| The deterministic audit engine (own docs tree) | [`audit/engine/docs/architecture/README.md`](../audit/engine/docs/architecture/README.md) |

The [worked example](../audit/schema/examples/server-worked-example/README.md) shows a real run: two audits of one
repository, before and after the implement recipe.

## Writing docs

| Page | Use |
| --- | --- |
| [Communication rules](COMMUNICATION_RULES.md) | Plain-language rules, diagrams, and how to report and ask for decisions |
| [Style guide](STYLE_GUIDE.md) | The authoring rules for every page |
| [Tutorial template](templates/tutorial-template.md) | Start a tutorial |
| [How-to template](templates/how-to-template.md) | Start a how-to guide |
| [Reference template](templates/reference-template.md) | Start a reference page |
| [Architecture doc template](templates/architecture-doc-template.md) | Start an architecture page |
| [ADR template](templates/adr-template.md) | Start a decision record |

Gates and commit rules: [`AGENTS.md`](../AGENTS.md). Setup and contributing: [`CONTRIBUTING.md`](../CONTRIBUTING.md).
Changes: [`CHANGELOG.md`](../CHANGELOG.md). Releases: [`RELEASE_PROCESS.md`](../RELEASE_PROCESS.md).
