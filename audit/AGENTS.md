# AGENTS.md: audit/

This folder holds the audit recipe, its deterministic tools and the engine. The root [`AGENTS.md`](../AGENTS.md)
applies here too. This file adds the rules for this folder.

To audit a repository, follow [`SKILL.md`](SKILL.md). The rest of this file is for changes to this folder.

## What is here

| Path | What it is |
|---|---|
| `SKILL.md`, `checks/`, `prompts/` | The LLM-driven audit recipe, its check procedures and its prompts |
| `catalogue.json`, `stacks/` | The check catalogue and the stack profiles |
| `schema/` | The JSON Schemas for the tools' files. See `schema/SCHEMA.md` |
| `tools/` | Deterministic tools the recipe calls, and the shared helpers (`_common.py` and others) |
| `engine/` | The deterministic audit engine. It has its own, stricter [`AGENTS.md`](engine/AGENTS.md) |
| `docs/architecture/adrs/` | Decisions for this folder (ADR 0001: the tools import the engine in process) |

## Rules

- Use the standard library only, in `tools/` and in `engine/`. Never add a third-party import.
- Never write inside the target repository. The recipe and the tools only read it.
- A tool writes only to its output directory. The output directory is outside the target.
- Every tool follows the tool contract in [`tools/README.md`](tools/README.md). Read it before you add or change a
  tool.
- Keep `tools/CATALOGUE.md` the same as each tool's `--describe` output. Regenerate it with
  `python3 dev/recipe_lint.py --write-catalogue .` from the repository root.
- Never run a target's own commands directly. Use the engine's probe runner. It is opt-in: `--run-gates` plus
  `--allow-probe <verb>`.
- The model's judgment cites evidence. The tools do the counting.
- A fixture is data. Change a fixture only together with the test that needs the change.
- A new engine check needs a fixture that fails exactly that check.
- The engine never imports from `tools/`. The audit folder never imports from `implement/`.
- Before you change anything under `engine/`, read [`engine/AGENTS.md`](engine/AGENTS.md).

## Documentation

- The engine's design, checks and ADRs: [`engine/docs/architecture/README.md`](engine/docs/architecture/README.md).
- The tool reference: [`docs/reference/tools-cli.md`](../docs/reference/tools-cli.md).
- The tool design: the
  [Tool Contract](../docs/explanation/contributor-deep-dive/01-tool-contract.md) page.
- All decisions: the root index, [`docs/architecture/adrs/README.md`](../docs/architecture/adrs/README.md).

## Test this folder

Run the engine's tests from `audit/engine/`:

```bash
python3 -m unittest discover -s tests
```

Run the tools' tests and the recipe linter from the repository root:

```bash
python3 -m unittest discover -s audit/tools/tests
python3 dev/recipe_lint.py .
```

Before you propose a change, run `make check` and `make security` from the repository root.
