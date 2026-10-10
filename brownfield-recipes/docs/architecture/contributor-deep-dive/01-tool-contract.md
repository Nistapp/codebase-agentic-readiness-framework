# 1. Tool Contract

> **Audience:** Engineers, maintainers
> **Goal:** Explain the contract every deterministic tool follows, what enforces it, and why it has this shape.
> **Status:** Live for the contract and its helpers. The engine launcher section is planned.

> [!NOTE]
> Planned. Section 4, the engine launcher `tools/engine.py` and its decision record, is not written yet. Filled in by roadmap step S2.1. The tool catalogue generated from each tool's manifest is planned for S2.8.

---

## 1. Envelope and exit codes

An agent that calls a dozen tools needs one way to read them all, so every tool prints the same JSON object on stdout and exits with the same four codes. The rules are in the [tools README](../../../tools/README.md#the-contract); this page says where each one lives.

- **The envelope** has six keys in a fixed order: `tool`, `version`, `ok`, `data`, `warnings`, `truncated`. [`make_envelope`](../../../tools/_common.py#L136-L151) builds it and [`encode_envelope`](../../../tools/_common.py#L154-L160) turns it into text. Stdout holds that and nothing else, so a caller can parse it without scanning. A short human summary and every diagnostic go to stderr.
- **The exit codes** are constants in [`_common.py`](../../../tools/_common.py#L39-L49), and each error class carries one:

| Raised | Exit | When |
|---|---|---|
| `UsageError`, `PathNotAllowed` | `1` | A bad argument, a missing file, a path that leaves the target, an output directory inside it, an interpreter that is too old |
| `ValidationFailed` | `2` | The input was read and is invalid; `data.errors` lists what to fix |
| `OutputTooLarge`, or any other exception | `3` | A bug in the tool; the traceback goes to stderr and the envelope still prints with `ok: false` |

- **`run_tool`** ([`_common.py`](../../../tools/_common.py#L201-L247)) is the only place that turns a result or an exception into an envelope and an exit code. A tool does not print, exit or catch for itself, so the contract cannot be half-kept.
- **Why argparse is wrapped.** Argparse exits with `2` on a bad argument, which the contract reserves for failed validation, and it prints no envelope. [`ToolParser`](../../../tools/_common.py#L126-L130) raises a `UsageError` instead, so a mistyped flag exits with `1` and an envelope. `--help` still prints human text and exits `0`.

## 2. Self-description

Each tool declares a [`ToolInfo`](../../../tools/_common.py#L101-L120): its name, summary, synopsis and what it writes. `<tool>.py --describe` prints its `manifest()` as the envelope's `data`, runs no work and needs no other argument. The manifest says `network: false` and `writes_inside_target: false` as facts about every tool, and lists the exit codes.

The manifest is the machine-readable source for the [Tools CLI reference](../../reference/tools-cli.md). A catalogue that collects the manifests into `tools/CATALOGUE.md`, and a linter that fails when a recipe names a tool that does not exist, are planned for S2.8.

## 3. Safety properties

| Property | How it is kept | Where | Test |
|---|---|---|---|
| Output is bounded | A tool trims its lists with `bound_items` to a budget of 48 KiB. `encode_envelope` refuses an envelope over 64 KiB, which is exit `3`, so a tool cannot print more than the limit by accident | [`bound_items`](../../../tools/_common.py#L163-L178) | `BoundedOutputTests`, `ExitCodeTests` |
| Output is deterministic | Keys keep the order they are built in, lists keep their order, and `bound_items` drops from the end | `make_envelope`, `bound_items` | `EnvelopeTests.test_same_input_gives_the_same_bytes` |
| No path escapes the target | `resolve_within` resolves symlinks and `..` first, then checks that the result is inside the target. A symlink that leads out is refused | [`resolve_within`](../../../tools/_common.py#L274-L288) | `PathTests` |
| No write lands in the target | `output_directory` checks the resolved directory before it creates anything, so a directory that reaches the target through a symlink is refused | [`output_directory`](../../../tools/_common.py#L291-L307) | `PathTests` |
| No half-written file | `atomic_write_text` writes a temporary file beside the destination and renames it over. A failure leaves the old file and removes the temporary one | [`atomic_write_text`](../../../tools/_common.py#L313-L332) | `AtomicWriteTests` |
| No network | No tool imports a network module. The standard-library-only rule in the root [`AGENTS.md`](../../../../AGENTS.md) keeps third-party clients out, and a tool that needs the target's own commands goes through the engine's probe runner, which is opt-in | Review, and the engine's `--allow-probe` | Not tested; there is nothing to call |
| An old Python gets a hint, not a traceback | `check_python` runs first in `run_tool`. It needs `_common.py` itself to parse as Python 3.9 | [`check_python`](../../../tools/_common.py#L188-L198) | `PreflightTests`, including a parse of every tool file with `feature_version=(3, 9)` |

> [!IMPORTANT]
> The preflight protects only what runs after it. A tool that uses syntax newer than 3.9 at module level fails with a `SyntaxError` before the check can speak, which is why the test parses every file in `tools/` as 3.9.

## 4. Engine launcher

- TBD: `tools/engine.py` and the import-path ADR.
