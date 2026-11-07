# Documentation

This repository is the Codebase Agentic Readiness Framework: documents that say what makes a codebase safe for AI
coding agents, and tools that check it. This folder is the root index. The pages themselves live beside what they
describe, in three sets.

## The three document sets

| Set | Where | What it holds |
| --- | --- | --- |
| The framework | [`README.md`](../README.md), [`shared/`](framework/), [`brownfield-legacy/`](framework/), [`greenfield/`](../greenfield/) | The normative documents. If a tool disagrees with them, the tool is wrong |
| The requirements | [`spec/`](../spec/README.md) | Numbered requirements (`REQ-...`) for what a repository must have |
| The recipes and their tools | [`docs/`](explanation/README.md) | The audit and implement recipes, the tools they call, the schemas |
| The audit engine | [`audit/engine/docs/`](../audit/engine/docs/architecture/README.md) | The deterministic engine: design, checks, decisions |

## Where to start

- Writing or changing a page: [`STYLE_GUIDE.md`](STYLE_GUIDE.md).
- Deciding something or looking up a decision: [`architecture/adrs/README.md`](architecture/adrs/README.md).
- Orienting before you explore the code: [`architecture/README.md`](architecture/README.md).
- Running the gates and the commit rules: [`AGENTS.md`](../AGENTS.md); setting up and contributing: [`CONTRIBUTING.md`](../CONTRIBUTING.md).
- What changed: [`CHANGELOG.md`](../CHANGELOG.md). How a release is cut: [`RELEASE_PROCESS.md`](../RELEASE_PROCESS.md).
