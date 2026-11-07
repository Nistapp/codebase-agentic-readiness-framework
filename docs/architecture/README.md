# Architecture

A map, not a manual. The repository has two layers: documents that say what a ready codebase is, and tools that check
it.

| Part | Path | Reads | Writes |
| --- | --- | --- | --- |
| Framework documents and requirements | `docs/framework/`, `greenfield/`, `spec/` | | |
| Deterministic audit engine | `audit/engine/` | a target repository | nothing in the target |
| Recipe tools | `audit/tools/`, `implement/tools/` | engine reports, state files | the target's two state files, through `progress.py` only |
| LLM-driven recipes | `audit/`, `implement/` | the repository, tool output | through the tools |
| Dev-only checks | `dev/` | the tools, reference packages | nothing |

The engine and the tools use the standard library only and never touch the network. The recipes call the tools to do
the counting; the model's judgment is backed by cited evidence.

Deeper pages:

- Recipes and tools: [`docs/explanation/README.md`](../explanation/README.md).
- The engine: [`audit/engine/docs/architecture/README.md`](../../audit/engine/docs/architecture/README.md).
- Decisions of record: [`adrs/README.md`](adrs/README.md).
