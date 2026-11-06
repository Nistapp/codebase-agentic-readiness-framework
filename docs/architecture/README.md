# Architecture

A map, not a manual. The repository has two layers: documents that say what a ready codebase is, and tools that check
it.

| Part | Path | Reads | Writes |
| --- | --- | --- | --- |
| Framework documents and requirements | `shared/`, `brownfield-legacy/`, `greenfield-bootstrap/`, `spec/` | | |
| Deterministic audit engine | `brownfield-recipes/deterministic-audit/` | a target repository | nothing in the target |
| Recipe tools | `brownfield-recipes/tools/` | engine reports, state files | the target's two state files, through `progress.py` only |
| LLM-driven recipes | `brownfield-recipes/audit/`, `brownfield-recipes/implement/` | the repository, tool output | through the tools |
| Dev-only checks | `brownfield-recipes/dev/` | the tools, reference packages | nothing |

The engine and the tools use the standard library only and never touch the network. The recipes call the tools to do
the counting; the model's judgment is backed by cited evidence.

Deeper pages:

- Recipes and tools: [`brownfield-recipes/docs/architecture/README.md`](../../brownfield-recipes/docs/architecture/README.md).
- The engine: [`brownfield-recipes/deterministic-audit/docs/architecture/README.md`](../../brownfield-recipes/deterministic-audit/docs/architecture/README.md).
- Decisions of record: [`adrs/README.md`](adrs/README.md).
