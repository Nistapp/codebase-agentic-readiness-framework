# Tools CLI Reference

> **Audience:** Everyone
> **Source of truth:** each tool's `--describe` output; generated `tools/CATALOGUE.md` (planned, S2.8)
> **Status:** Live for `engine.py`. The other tools are planned.

> [!NOTE]
> Planned. Only `engine.py` exists. The sections for the other tools are filled in by roadmap steps S2.2 to S2.8 and S5.1, and the generated `tools/CATALOGUE.md` by S2.8.

---

## Summary

| Item | Description | Status |
|---|---|---|
| [`engine.py`](#enginepy) | Runs the deterministic engine from any directory | Live |
| `validate_report.py` | Validates a report against schema and semantic rules | Planned (S2.2) |
| `report.py` | Builds and updates the audit report; the only writer | Planned (S2.3) |
| `render_report.py` | Renders a report to Markdown | Planned (S2.4) |
| `facts.py` | Emits stack and inventory facts, no verdicts | Planned (S2.7) |
| `recipe_lint.py` | Checks recipes for broken references and budgets | Planned (S2.8) |
| `progress.py` | Manages implementation progress | Planned (S5.1) |
| `check_drift.py` | Lists findings affected by changes since the audit | Planned (S5.1) |

## Every tool

Every tool follows the [tool contract](../../tools/README.md#the-contract): one JSON envelope on stdout, the exit codes below, `--describe`, bounded output, no network, no writes inside the target, and a Python 3.11 check first. The explanation is in [Tool Contract](../architecture/contributor-deep-dive/01-tool-contract.md).

| Exit code | Meaning |
|---|---|
| `0` | OK |
| `1` | Usage or input error, including a Python older than 3.11 |
| `2` | The input was read and failed validation |
| `3` | Internal error |

Run a tool as `python3 brownfield-recipes/tools/<tool>.py`, from any directory. Below Python 3.11 a tool prints how to run itself with `uv run --python 3.12`.

---

## engine.py

Runs the [deterministic engine](../../deterministic-audit/README.md) from any directory, writes its JSON report under a name that carries the repository's name, and never replaces a file. The decision to import the engine is [ADR 0001](../architecture/adrs/0001-tools-import-engine.md); the source is [`engine.py`](../../tools/engine.py).

**Synopsis**

```text
python3 brownfield-recipes/tools/engine.py <target> [--out-dir DIR] [--repo-label LABEL] [--phase N]
                                           [--exclude GLOB]... [--max-files N]
                                           [--run-gates --allow-probe VERB... [--timeout SECONDS]]
python3 brownfield-recipes/tools/engine.py --list-checks
python3 brownfield-recipes/tools/engine.py --describe
```

**Inputs**

| Argument | Meaning |
|---|---|
| `<target>` | The repository to scan. It must exist and be a directory. The engine only reads it. |
| `--out-dir DIR` | Where the report goes. It is created if it does not exist, and it must be outside the target. Default: the current directory, which is refused when it is inside the target. |
| `--repo-label LABEL` | The label in the file name: up to 32 of `a` to `z`, `0` to `9`, dot, underscore and hyphen, starting with a letter or digit. Default: derived from the target's directory name, as in [Output files](../../schema/SCHEMA.md#output-files). |
| `--phase N` | The highest framework phase to evaluate. The engine's default is 1. |
| `--exclude GLOB` | An extra path pattern to skip. May be repeated. |
| `--max-files N` | A hard cap on the files the engine inspects. |
| `--run-gates`, `--allow-probe VERB`, `--timeout SECONDS` | Let the engine run the target's own commands. Nothing runs unless `--run-gates` is given and every verb is named in an `--allow-probe`. `--timeout` is the limit per command. |
| `--list-checks` | Print the engine's checks and exit. It takes no other argument. |

The engine's `--force`, `--out`, `--format`, `--fail-on`, `--baseline` and `--emit-baseline` are not offered, and abbreviations of the options above are refused.

**Outputs**

A scan writes one file, `<label>.engine-report.<stamp>.json`, in the output directory. It is the engine's own JSON report, untouched. The envelope's `data` is:

| Key | Meaning |
|---|---|
| `report` | The path of the file written. |
| `label`, `stamp` | The two parts of the name. The stamp is the UTC launch time as `YYYYMMDDTHHMMSSZ`. |
| `target` | The target's resolved path. |
| `engine` | `version` and `ruleset_revision` of the engine that ran. |

`--list-checks` writes nothing. Its `data` holds `engine` (name, version, ruleset revision and hash), `checks` (the engine's list, one entry per check) and `omitted`, the number of checks left out to stay within the output budget, which is `0` today.

**Exit codes**

| Code | When |
|---|---|
| `0` | The report was written, or the checks were listed. |
| `1` | A bad argument, a missing target, an output directory inside the target, a bad label, or a refusal by the engine, whose reason is in `data.error`. |
| `3` | The engine exited with any other code, raised, or reported success without writing the report. |

**Errors**

| Message | Fix |
|---|---|
| `refusing to write inside the target` | Pass `--out-dir` with a directory outside the repository, or run from outside it. |
| `the engine refused the run: --run-gates requires at least one --allow-probe VERB` | Name each verb the engine may run with `--allow-probe`. |
| `the engine refused the run: ... exists; nothing was replaced, run the tool again` | Another run took the name in the same second. Run the tool again. |
| `repo_label ... is not allowed` | Use a label that matches the pattern above. |
| `--list-checks takes no other argument` | Run `--list-checks` on its own. |
