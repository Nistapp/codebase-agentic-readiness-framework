# 1. Tool Contract

> **Audience:** Engineers, maintainers
> **Goal:** Explain the contract every deterministic tool follows, what enforces it, and why it has this shape.
> **Status:** Live for the contract and its helpers. The engine launcher section is planned.

> [!NOTE]
> Planned. Section 5, the engine launcher `tools/engine.py` and its decision record, is not written yet. Filled in by roadmap step S2.1. The tool catalogue generated from each tool's manifest is planned for S2.8.

---

## 1. Envelope and exit codes

An agent that calls a dozen tools needs one way to read them all, so every tool prints the same JSON object on stdout and exits with the same four codes. The rules are in the [tools README](../../../tools/README.md#the-contract); this page says where each one lives.

- **The envelope** has six keys in a fixed order: `tool`, `version`, `ok`, `data`, `warnings`, `truncated`. [`make_envelope`](../../../tools/_common.py#L139-L154) builds it and [`encode_envelope`](../../../tools/_common.py#L157-L163) turns it into text. Stdout holds that and nothing else, so a caller can parse it without scanning. A short human summary and every diagnostic go to stderr.
- **The exit codes** are constants in [`_common.py`](../../../tools/_common.py#L42-L52), and each error class carries one:

| Raised | Exit | When |
|---|---|---|
| `UsageError`, `PathNotAllowed` | `1` | A bad argument, a missing file, a path that leaves the target, an output directory inside it, an interpreter that is too old |
| `ValidationFailed` | `2` | The input was read and is invalid; `data.errors` lists what to fix |
| `OutputTooLarge`, or any other exception | `3` | A bug in the tool; the traceback goes to stderr and the envelope still prints with `ok: false` |

- **`run_tool`** ([`_common.py`](../../../tools/_common.py#L204-L250)) is the only place that turns a result or an exception into an envelope and an exit code. A tool does not print, exit or catch for itself, so the contract cannot be half-kept.
- **Why argparse is wrapped.** Argparse exits with `2` on a bad argument, which the contract reserves for failed validation, and it prints no envelope. [`ToolParser`](../../../tools/_common.py#L129-L133) raises a `UsageError` instead, so a mistyped flag exits with `1` and an envelope. `--help` still prints human text and exits `0`.

## 2. Self-description

Each tool declares a [`ToolInfo`](../../../tools/_common.py#L104-L123): its name, summary, synopsis and what it writes. `<tool>.py --describe` prints its `manifest()` as the envelope's `data`, runs no work and needs no other argument. The manifest says `network: false` and `writes_inside_target: false` as facts about every tool, and lists the exit codes.

The manifest is the machine-readable source for the [Tools CLI reference](../../reference/tools-cli.md). A catalogue that collects the manifests into `tools/CATALOGUE.md`, and a linter that fails when a recipe names a tool that does not exist, are planned for S2.8.

## 3. Safety properties

| Property | How it is kept | Where | Test |
|---|---|---|---|
| Output is bounded | A tool trims its lists with `bound_items` to a budget of 48 KiB. `encode_envelope` refuses an envelope over 64 KiB, which is exit `3`, so a tool cannot print more than the limit by accident | [`bound_items`](../../../tools/_common.py#L166-L181) | `BoundedOutputTests`, `ExitCodeTests` |
| Output is deterministic | Keys keep the order they are built in, lists keep their order, and `bound_items` drops from the end | `make_envelope`, `bound_items` | `EnvelopeTests.test_same_input_gives_the_same_bytes` |
| No path escapes the target | `resolve_within` resolves symlinks and `..` first, then checks that the result is inside the target. A symlink that leads out is refused | [`resolve_within`](../../../tools/_common.py#L277-L291) | `PathTests` |
| No write lands in the target | `output_directory` checks the resolved directory before it creates anything, so a directory that reaches the target through a symlink is refused | [`output_directory`](../../../tools/_common.py#L294-L310) | `PathTests` |
| No half-written file | `atomic_write_text` writes a temporary file beside the destination and renames it over. A failure leaves the old file and removes the temporary one | [`atomic_write_text`](../../../tools/_common.py#L316-L335) | `AtomicWriteTests` |
| No file is replaced | `create_new` opens with `O_EXCL` and numbers a taken name; `free_name` treats even a dangling symlink as taken | [`create_new`](../../../tools/_common.py#L408-L432) | `CreateNewTests`, `FreeNameTests` |
| No network | No tool imports a network module. The standard-library-only rule in the root [`AGENTS.md`](../../../../AGENTS.md) keeps third-party clients out, and a tool that needs the target's own commands goes through the engine's probe runner, which is opt-in | Review, and the engine's `--allow-probe` | Not tested; there is nothing to call |
| An old Python gets a hint, not a traceback | `check_python` runs first in `run_tool`. It needs `_common.py` itself to parse as Python 3.9 | [`check_python`](../../../tools/_common.py#L191-L201) | `PreflightTests`, including a parse of every tool file with `feature_version=(3, 9)` |

> [!IMPORTANT]
> The preflight protects only what runs after it. A tool that uses syntax newer than 3.9 at module level fails with a `SyntaxError` before the check can speak, which is why the test parses every file in `tools/` as 3.9.

## 4. Output files

Every file a run writes carries the repository's name, and no tool replaces a file. [Output files](../../../schema/SCHEMA.md#output-files) in the schema notes fixes the rule, so that a re-run cannot destroy a report that someone has already reviewed. [`_common.py`](../../../tools/_common.py#L343-L432) implements it:

- **The label** is `repo_label` from the intake when given, and otherwise [`derive_label`](../../../tools/_common.py#L354-L357) of the target directory's name: lower case, each run of other characters one hyphen, 24 characters at most. An explicit label is checked against `EXPLICIT_LABEL`, the same pattern as `repo_label` in [`audit-intake.schema.json`](../../../schema/audit-intake.schema.json), by [`repo_label`](../../../tools/_common.py#L360-L369).
- **The name** is `<label>.<kind>.<stamp>.<ext>`. [`utc_stamp`](../../../tools/_common.py#L372-L378) gives the stamp, and [`output_name`](../../../tools/_common.py#L381-L392) builds the name and refuses a label, kind, stamp or extension that could change the directory.
- **Exclusive create.** [`create_new`](../../../tools/_common.py#L408-L432) opens the file with `O_EXCL`. When two runs reach one name in the same second, each gets its own file, the second with `-2` after the stamp, and the first is not touched. A failed write removes only the partial file it created.
- **A program that writes the file itself** asks [`free_name`](../../../tools/_common.py#L395-L405) for a name. It creates nothing, so another run can take the name first. That program must therefore refuse to replace a file too, which the engine does without `--force`.
- **The one exception** is a run updating its own draft report. It uses `atomic_write_text` on a file it owns, and a second run starts a new draft.

The tests are in `test_output_files.py`: the label rule (including `Digital_Assistant_microServices` to `digital-assistant-micros`), the stamp, the name, two creations of one name, a dangling symlink holding its name, a failed write, and eight threads racing for one name.

## 5. Engine launcher

- TBD: `tools/engine.py` and the import-path ADR.
