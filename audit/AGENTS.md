# AGENTS.md: audit/

This folder holds the audit recipe, its deterministic tools and the engine. The root [`AGENTS.md`](../AGENTS.md)
applies here too. This file adds the rules for this folder.

To audit a repository, follow [`SKILL.md`](SKILL.md). The rest of this file is for changes to this folder.

## What is here

| Path | What it is |
|---|---|
| `SKILL.md`, `checks/`, `prompts/` | The LLM-driven audit recipe, its check procedures and its prompts |
| `catalogue.json`, `catalogue-overlay.json`, `stacks/` | The check catalogue (generated), its hand-kept overlay and the stack profiles |
| `schema/` | The JSON Schemas for the tools' files. See `schema/SCHEMA.md` |
| `tools/` | Deterministic tools the recipe calls, and the shared helpers (`_common.py` and others) |
| `engine/` | The deterministic audit engine. It has its own, stricter [`AGENTS.md`](engine/AGENTS.md) |
| `docs/architecture/adrs/` | Decisions for this folder (ADR 0001: the tools import the engine in process) |

## Rules

- Use the standard library only, in `tools/` and in `engine/`. Never add a third-party import.
- Never write inside the target repository. The recipe and the tools only read it. The owner of this rule is the
  [hard rules](SKILL.md#hard-rules) of the audit recipe.
- A tool writes only to its output directory. The output directory is outside the target.
- Every tool follows the tool contract in [`tools/README.md`](tools/README.md). Read it before you add or change a
  tool.
- Keep `tools/CATALOGUE.md` the same as each tool's `--describe` output. Regenerate it with
  `python3 dev/recipe_lint.py --write-catalogue .` from the repository root.
- `catalogue.json` is generated: never edit it by hand. The engine gives each engine check's title, phase,
  severity, scored flag, status and order. `catalogue-overlay.json` gives the rest: `catalogue_version`, each
  check's `req_ids`, `playbooks` and `since_ruleset`, and every field of an agent-only check. Edit the overlay or
  the engine, then run `make update-catalogue` from the repository root. `make masters-check` (in `make check`)
  fails when the committed file is stale.
- A change to `catalogue.json` or to a file in `checks/` changes the generated
  [audit master list](../docs/reference/audit-master.md). Run `make update-masters` from the repository root and
  commit the result in the same change.
- Never run a target's own commands directly. Use the engine's probe runner. It is opt-in: `--run-gates` plus
  `--allow-probe <verb>`. The owner of this rule is the [hard rules](SKILL.md#hard-rules) of the audit recipe.
- The model's judgment cites evidence. The tools do the counting.
- A fixture is data. Change a fixture only together with the test that needs the change.
- A new engine check needs a fixture that fails exactly that check. `make new-check ID=<PACK-NN> TITLE="..."` writes
  the stubs of the module, the fixture, its matrix row, the rubric section and the overlay entry, and prints the rest.
- The engine never imports from `tools/`. The audit folder never imports from `implement/`.
- Before you change anything under `engine/`, read [`engine/AGENTS.md`](engine/AGENTS.md).

## Documentation

- The engine's design, checks and ADRs: [`engine/docs/architecture/README.md`](engine/docs/architecture/README.md).
- The tool reference: [`docs/reference/tools-cli.md`](../docs/reference/tools-cli.md).
- The tool design: the
  [Tool Contract](../docs/explanation/contributor-deep-dive/01-tool-contract.md) page.
- All decisions: the root index, [`docs/architecture/adrs/README.md`](../docs/architecture/adrs/README.md).
- How to add, change or delete an ADR: [`docs/ADR_POLICY.md`](../docs/ADR_POLICY.md).

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
