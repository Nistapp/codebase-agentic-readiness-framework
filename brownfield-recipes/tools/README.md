# Tools

> **Audience:** Engineers who write or call a tool, and agents that run one.
> **Source of truth:** [`_common.py`](_common.py) and each tool's `--describe` output.
> **Status:** The contract below is binding for every tool in this folder. The tools themselves arrive step by step; the [Tools CLI reference](../docs/reference/tools-cli.md) says which exist.

Deterministic tools do the counting, validation and rendering for the brownfield recipes. The agent decides what a result means; a tool never judges, and its output overrides the agent's own arithmetic or formatting. Every tool is standard-library Python that runs from a fresh clone with no install step:

```bash
python3 brownfield-recipes/tools/<tool>.py <arguments>
```

Why the contract exists: an agent that calls a dozen tools needs one way to read them all. The design is in the [Tool Contract](../docs/architecture/contributor-deep-dive/01-tool-contract.md) page.

---

## The contract

A tool MUST do all of the following.

### 1. Print one envelope on stdout

Stdout holds exactly one JSON object and nothing else, except for `--help`, which prints human text.

```json
{
  "tool": "engine",
  "version": "0.1.0",
  "ok": true,
  "data": {},
  "warnings": [],
  "truncated": false
}
```

| Key | Meaning |
|---|---|
| `tool` | The tool's name, which is its file name without `.py`. |
| `version` | The tool's version. |
| `ok` | `true` when the tool did what was asked. |
| `data` | The result. Its shape is the tool's own and is documented in the [Tools CLI reference](../docs/reference/tools-cli.md). When `ok` is `false` it holds a short `error` string, and a list `errors` when there are several. |
| `warnings` | Strings the caller should read, in a stable order. |
| `truncated` | `true` when the tool left items out to stay within the output budget. `data` then says how many. |

The same input gives the same bytes, apart from anything the tool says is time-dependent. Keys keep the order above, so a diff of two runs is readable.

A short human summary goes to stderr, one or two lines. Progress and diagnostics go to stderr too, never to stdout.

### 2. Use the exit codes

| Code | Meaning |
|---|---|
| `0` | OK. |
| `1` | Usage or input error: a bad argument, a missing file, a path that is not allowed, a Python that is too old. |
| `2` | The input was read and failed validation. The validator and the report tools use this; `data.errors` lists what to fix. |
| `3` | Internal error: a bug in the tool. The traceback goes to stderr, and the envelope still prints with `ok: false`. |

### 3. Describe itself

`<tool>.py --describe` prints an envelope whose `data` is a manifest: `name`, `version`, `summary`, `synopsis`, `writes` (what the tool writes, and where), `network` (always `false`), `writes_inside_target` (always `false`) and `exit_codes`. It needs no other argument and runs no work. The generated tool catalogue is built from these manifests.

### 4. Keep its output small

Output is bounded so that a large repository cannot flood the agent's context. A tool lists at most a fixed number of bytes of items, drops the rest in a deterministic order and sets `truncated: true`. A tool that would exceed the hard limit fails with exit code `3` rather than print a partial envelope.

### 5. Stay off the network

No tool opens a socket, calls a package index or fetches a URL. The one thing that can reach the network is a target's own command that the engine's probe runner executes, and only when the operator allowed that verb explicitly.

### 6. Never write inside the target

A tool reads the repository it is pointed at and never writes there: no report, no cache, no lock file, no temporary file. Output goes to an output directory outside the target, and a tool refuses an output directory that is inside the target, including through a symlink. A tool also refuses to read a path that resolves outside the target, so a symlink cannot lead it out.

### 7. Never replace a file

A tool that writes a file gives it a name that carries the repository's name, `<label>.<kind>.<stamp>.<ext>`, and creates it only if the name is free. When the name is taken, which happens if two runs start in the same second, the tool adds `-2`, `-3` and so on after the stamp. No tool has an overwrite option. There are two exceptions, each a run atomically replacing a file it owns in place: a run updating its own draft report, and `recipe_lint.py --write-catalogue` regenerating [`tools/CATALOGUE.md`](CATALOGUE.md). The rule, the label and the stamp are defined under "Output files" in the [report schema notes](../schema/SCHEMA.md#output-files).

### 8. Check the Python version first

The minimum is Python 3.11. Before it does anything else a tool checks the interpreter, and below the minimum it prints the envelope with `ok: false`, a hint on stderr and exits `1`:

```text
engine: needs Python 3.11 or newer, found 3.9.6
  run it with:  uv run --python 3.12 python3 brownfield-recipes/tools/engine.py ...
```

For this to work, the file that holds the check and every file it imports first must parse as Python 3.9 syntax.

---

## Writing a tool

A tool imports [`_common.py`](_common.py), which keeps the contract above, so a tool only says what it does:

```python
INFO = _common.ToolInfo(name="mytool", summary="...", synopsis=("mytool.py <target>",), writes="nothing")


def handler(argv: Sequence[str]) -> _common.Result:
    args = PARSER.parse_args(argv)  # a _common.ToolParser
    return _common.Result(data={"target": args.target}, summary="one line for stderr")


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
```

`run_tool` runs the Python check, answers `--describe`, prints the envelope and the summary, and turns an exception into the right exit code. A handler raises `UsageError` (exit 1), `ValidationFailed` (exit 2) or lets a bug escape (exit 3).

| Helper | Use it to |
|---|---|
| `ToolParser` | Parse arguments. A bad argument becomes a `UsageError`, so it exits with 1 and an envelope, not with argparse's 2, and an abbreviation of an option is refused. |
| `bound_items` | Keep a list within the output budget and learn how many items were left out. |
| `resolve_target` | Turn the target argument into a resolved directory that exists. |
| `resolve_within` | Read a path the target names, refusing one that leaves the target through `..` or a symlink. |
| `output_directory` | Get the directory a tool may write to, refusing one inside the target. |
| `atomic_write_text` | Replace a file the run itself owns, such as its own draft, in one step. |
| `repo_label`, `derive_label` | Get the label for output file names: the intake's `repo_label`, or one derived from the target directory's name. |
| `utc_stamp`, `output_name` | Build the stamp and the file name. |
| `free_name` | Find the first name nothing occupies, for a program that writes the file itself and refuses to replace one. It creates nothing. |
| `create_new` | Write a new file under the output name, creating it exclusively and numbering it `-2`, `-3` when the name is taken. |
| `create_new_group` | Write files that share one name apart from the extension, such as a final report's JSON and Markdown. A taken name moves the whole group to the next number. |
| `create_file` | Write a file at a path the caller named, such as `--out`. It creates the file or refuses; it never replaces one. |

Tests are in [`tests/`](tests/) and run with `make test`. A test starts with `import _paths`, which puts this folder on the import path.

---

## Licence

The tools are licensed under the GNU Affero General Public License, version 3 or later (`AGPL-3.0-or-later`), and each Python file says so in its header. The licence covers the tools. It does not extend to the repository a tool reads or to a report a tool helps produce: those belong to you. This `README.md` and the other documentation are GFDL 1.3. The full table is in [Licensing](../docs/reference/licensing.md).
