# Brownfield Recipes

> [!NOTE]
> Planned. Nothing here is implemented yet. The build is tracked in the implementation roadmap, which a maintainer passes to the agent by path.

Recipes that a coding agent runs to audit an existing repository for agentic readiness, and then to implement the confirmed findings. Deterministic tools do the counting, validation and rendering; the agent does the judgment.

| Folder | Contents | Status |
|---|---|---|
| `audit/` | The audit recipe and its check files | Planned |
| `implement/` | The implementation recipe and its playbooks | Planned |
| [`schema/`](schema/SCHEMA.md) | The report and intake schemas, version 0.1, with examples. The progress schema is not written yet | Live (report, intake) |
| `stacks/` | Stack profiles | Planned |
| [`tools/`](tools/README.md) | The tool contract and shared helpers. The tools themselves follow | Live (contract, helpers, the engine launcher, the validator, the report builder); the other tools Planned |
| [`deterministic-audit/`](deterministic-audit/README.md) | The deterministic engine, migrated with its history | Live |
| [`docs/`](docs/architecture/README.md) | Documentation, Diátaxis layout | Placeholders |

Licensing: [docs/reference/licensing.md](docs/reference/licensing.md).
