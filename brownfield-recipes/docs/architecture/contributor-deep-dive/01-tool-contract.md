# 1. Tool Contract

> **Audience:** Engineers, maintainers
> **Goal:** Explain the contract every deterministic tool follows, what enforces it, and why it has this shape.
> **Status:** Live.

> [!NOTE]
> Planned. The tool catalogue generated from each tool's manifest is planned for S2.8. `engine.py`, `validate_report.py`, `report.py` and `render_report.py` follow the contract today.

---

## 1. Envelope and exit codes

An agent that calls a dozen tools needs one way to read them all, so every tool prints the same JSON object on stdout and exits with the same four codes. The rules are in the [tools README](../../../tools/README.md#the-contract); this page says where each one lives.

- **The envelope** has six keys in a fixed order: `tool`, `version`, `ok`, `data`, `warnings`, `truncated`. [`make_envelope`](../../../tools/_common.py#L147-L162) builds it and [`encode_envelope`](../../../tools/_common.py#L165-L171) turns it into text. Stdout holds that and nothing else, so a caller can parse it without scanning. A short human summary and every diagnostic go to stderr.
- **The exit codes** are constants in [`_common.py`](../../../tools/_common.py#L42-L52), and each error class carries one:

| Raised | Exit | When |
|---|---|---|
| `UsageError`, `PathNotAllowed` | `1` | A bad argument, a missing file, a path that leaves the target, an output directory inside it, an interpreter that is too old |
| `ValidationFailed` | `2` | The input was read and is invalid; `data.errors` lists what to fix |
| `OutputTooLarge`, or any other exception | `3` | A bug in the tool; the traceback goes to stderr and the envelope still prints with `ok: false` |

- **`run_tool`** ([`_common.py`](../../../tools/_common.py#L212-L258)) is the only place that turns a result or an exception into an envelope and an exit code. A tool does not print, exit or catch for itself, so the contract cannot be half-kept.
- **Why argparse is wrapped.** Argparse exits with `2` on a bad argument, which the contract reserves for failed validation, and it prints no envelope. [`ToolParser`](../../../tools/_common.py#L129-L141) raises a `UsageError` instead, so a mistyped flag exits with `1` and an envelope. The parser also refuses abbreviations, so `--out` cannot quietly mean `--out-dir`, and a flag added later cannot change what an old recipe's abbreviation means. `--help` still prints human text and exits `0`.

## 2. Self-description

Each tool declares a [`ToolInfo`](../../../tools/_common.py#L103-L123): its name, summary, synopsis and what it writes. `<tool>.py --describe` prints its `manifest()` as the envelope's `data`, runs no work and needs no other argument. The manifest says `network: false` and `writes_inside_target: false` as facts about every tool, and lists the exit codes.

The manifest is the machine-readable source for the [Tools CLI reference](../../reference/tools-cli.md). A catalogue that collects the manifests into `tools/CATALOGUE.md`, and a linter that fails when a recipe names a tool that does not exist, are planned for S2.8.

## 3. Safety properties

| Property | How it is kept | Where | Test |
|---|---|---|---|
| Output is bounded | A tool trims its lists with `bound_items` to a budget of 48 KiB. `encode_envelope` refuses an envelope over 64 KiB, which is exit `3`, so a tool cannot print more than the limit by accident | [`bound_items`](../../../tools/_common.py#L174-L189) | `BoundedOutputTests`, `ExitCodeTests` |
| Output is deterministic | Keys keep the order they are built in, lists keep their order, and `bound_items` drops from the end | `make_envelope`, `bound_items` | `EnvelopeTests.test_same_input_gives_the_same_bytes` |
| No path escapes the target | `resolve_within` resolves symlinks and `..` first, then checks that the result is inside the target. A symlink that leads out is refused | [`resolve_within`](../../../tools/_common.py#L285-L299) | `PathTests` |
| No write lands in the target | `output_directory` checks the resolved directory before it creates anything, so a directory that reaches the target through a symlink is refused | [`output_directory`](../../../tools/_common.py#L302-L318) | `PathTests` |
| No half-written file | `atomic_write_text` writes a temporary file beside the destination and renames it over. A failure leaves the old file and removes the temporary one | [`atomic_write_text`](../../../tools/_common.py#L324-L343) | `AtomicWriteTests` |
| No file is replaced | `create_new` and `create_new_group` open with `O_EXCL` and number a taken name; `create_file` refuses a path that is taken; `free_name` treats even a dangling symlink as taken | [`create_new_group`](../../../tools/_common.py#L476-L504) | `CreateNewTests`, `CreateNewGroupTests`, `CreateFileTests`, `FreeNameTests` |
| No network | No tool imports a network module. The standard-library-only rule in the root [`AGENTS.md`](../../../../AGENTS.md) keeps third-party clients out, and a tool that needs the target's own commands goes through the engine's probe runner, which is opt-in | Review, and the engine's `--allow-probe` | Not tested; there is nothing to call |
| An old Python gets a hint, not a traceback | `check_python` runs first in `run_tool`. It needs `_common.py` itself to parse as Python 3.9 | [`check_python`](../../../tools/_common.py#L199-L209) | `PreflightTests`, including a parse of every tool file with `feature_version=(3, 9)` |

> [!IMPORTANT]
> The preflight protects only what runs after it. A tool that uses syntax newer than 3.9 at module level fails with a `SyntaxError` before the check can speak, which is why the test parses every file in `tools/` as 3.9.

## 4. Output files

Every file a run writes carries the repository's name, and no tool replaces a file. [Output files](../../../schema/SCHEMA.md#output-files) in the schema notes fixes the rule, so that a re-run cannot destroy a report that someone has already reviewed. [`_common.py`](../../../tools/_common.py#L351-L514) implements it:

- **The label** is `repo_label` from the intake when given, and otherwise [`derive_label`](../../../tools/_common.py#L363-L366) of the target directory's name: lower case, each run of other characters one hyphen, 24 characters at most. An explicit label is checked against `EXPLICIT_LABEL`, the same pattern as `repo_label` in [`audit-intake.schema.json`](../../../schema/audit-intake.schema.json), by [`repo_label`](../../../tools/_common.py#L369-L378).
- **The name** is `<label>.<kind>.<stamp>.<ext>`. [`utc_stamp`](../../../tools/_common.py#L381-L387) gives the stamp, and [`output_name`](../../../tools/_common.py#L390-L401) builds the name and refuses a label, kind, stamp or extension that could change the directory.
- **Exclusive create.** [`create_new`](../../../tools/_common.py#L507-L514) opens the file with `O_EXCL`. When two runs reach one name in the same second, each gets its own file, the second with `-2` after the stamp, and the first is not touched. A failed write removes only the partial file it created.
- **Files that share a name.** The final report is a JSON file and a Markdown file with one name apart from the extension. [`create_new_group`](../../../tools/_common.py#L476-L504) claims every name of the group with `O_EXCL` before it writes any of them. If either name is taken, it gives back the names it had claimed and moves both files to the next number, so the pair never comes apart. A failed write removes the files that call created and nothing else.
- **A path the caller named.** [`create_file`](../../../tools/_common.py#L460-L473) writes the file an `--out` argument names. It creates the file or refuses, and never replaces or writes through anything that is already there, a symlink included.
- **A program that writes the file itself** asks [`free_name`](../../../tools/_common.py#L404-L414) for a name. It creates nothing, so another run can take the name first. That program must therefore refuse to replace a file too, which the engine does without `--force`.
- **The one exception** is a run updating its own draft report. It uses `atomic_write_text` on a file it owns, and a second run starts a new draft.

The tests are in `test_output_files.py`: the label rule (including `Digital_Assistant_microServices` to `digital-assistant-micros`), the stamp, the name, two creations of one name, a dangling symlink holding its name, a failed write, and eight threads racing for one name.

## 5. Engine launcher

[`tools/engine.py`](../../../tools/engine.py) runs the deterministic engine from any directory, and it is the only way the recipes run it. It has two modes and no others:

| Mode | Command | `data` holds |
|---|---|---|
| Scan | `engine.py <target> [--out-dir DIR] [--repo-label LABEL] [--phase N] [--exclude GLOB]... [--max-files N] [--run-gates --allow-probe VERB... [--timeout SECONDS]]` | The report's path, label and stamp, the target, and the engine's version and ruleset revision |
| List | `engine.py --list-checks` | The engine's identity and its checks, bounded like any list |

Every option is in the [Tools CLI reference](../../reference/tools-cli.md#enginepy). What matters for the contract:

- **How it reaches the engine.** In process, through [`load_engine`](../../../tools/engine.py#L57-L66) and [`run_engine`](../../../tools/engine.py#L69-L83), as [ADR 0001](../adrs/0001-tools-import-engine.md) decides. The engine's stdout and stderr are captured, so the launcher's stdout stays one envelope. What the engine said on stderr, apart from its "report written" line, goes into the summary, and anything it printed on stdout becomes a warning.
- **What the launcher decides, so that the engine cannot do otherwise.** It asks for `--format json` and nothing else, so no Markdown file appears beside the report. It names the report `<label>.engine-report.<stamp>.json` with [`free_name`](../../../tools/_common.py#L404-L414) and puts it in a directory that [`output_directory`](../../../tools/_common.py#L302-L318) has checked is outside the target. The engine skips that check when it is given `--out`, so this is where the guard lives.
- **What it never passes.** The launcher's parser does not accept `--force`, `--out`, `--format`, `--fail-on`, `--baseline` or `--emit-baseline`, so the engine never gets them. `--force` is the one that matters most: the engine refuses to replace a JSON report without it, and that refusal is the backstop when another run takes the chosen name before the engine writes. `--emit-baseline` is withheld because the `CON-04` draft is a second file beside the report, and the launcher's envelope names one. The engine refuses to replace an existing draft without `--force`, as it does a report, so the withholding is a choice about the envelope and not a guard.
- **Exit codes.** The engine's exit code `0` is `0`. Its `1`, a refusal such as `--run-gates` without `--allow-probe`, is `1`, with the engine's own reason in `data.error`. Any other code, an exception, or a success that left no report is `3`, because the launcher offers nothing that makes the engine exit `2`.
- **The stamp** is the launch time. The engine records its own `scanned_at` inside the report.

> [!WARNING]
> Two runs on one repository that start in the same second can both choose the same name. The first to finish writes it, and the engine refuses to replace it for the second, which exits `1` and can simply be run again. No report is lost or overwritten, but the second run is not renumbered, because the launcher cannot reserve a name that the engine insists is free.

The tests are in `test_engine.py`. They start the launcher as a script from the filesystem root, scan the engine's own fixtures, and check that the target is byte-for-byte unchanged afterwards.
