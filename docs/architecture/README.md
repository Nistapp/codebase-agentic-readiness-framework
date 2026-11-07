# Architecture

A map, not a manual. The repository has two layers: documents that say what a ready codebase is, and tools that check
it. The root router is [`docs/README.md`](../README.md).

| Part | Path | Reads | Writes |
| --- | --- | --- | --- |
| Framework documents | `docs/framework/`, `greenfield/` | | |
| Requirements | `spec/` | | |
| Audit recipe | `audit/` (`SKILL.md`, `checks/`, `stacks/`, `schema/`) | the target, tool output | the report, through the tools |
| Audit tools | `audit/tools/` | engine reports, facts, drafts | the report files in the output directory |
| Deterministic audit engine | `audit/engine/` | a target repository | nothing in the target |
| Implement recipe | `implement/` (`SKILL.md`, `playbooks/`, `state.md`) | a final report, the target | fixes on a branch per theme |
| Implement tools | `implement/tools/` | state files, reports | the target's two state files, through `progress.py` only |
| Dev-only checks | `dev/` | the tools, reference packages | nothing |
| Documentation | `docs/` | | |

The engine and the tools use the standard library only and never touch the network. The recipes call the tools to do
the counting; the model's judgment is backed by cited evidence. The implement tools import the audit tools, and the
audit tools import the engine in process
([audit ADR 0001](../../audit/docs/architecture/adrs/0001-tools-import-engine.md)).

Deeper pages:

- The audit recipe: [`audit/README.md`](../../audit/README.md).
- The implement recipe: [`implement/README.md`](../../implement/README.md).
- The engine: [`audit/engine/docs/architecture/README.md`](../../audit/engine/docs/architecture/README.md).
- Why the recipes work this way: [`docs/explanation/README.md`](../explanation/README.md).
- Decisions of record: [`adrs/README.md`](adrs/README.md).
