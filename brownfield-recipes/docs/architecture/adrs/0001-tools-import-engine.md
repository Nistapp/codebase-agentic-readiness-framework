# 0001. Tools Import the Engine in Process

* **Status:** Accepted
* **Date:** 2026-10-10
* **Last reviewed:** 2026-10-10
* **Deciders:** [@nistapp]

---

## Context

The recipes' tools and the deterministic engine are both standard-library Python, and the tools need the engine in two ways. `tools/engine.py` must run it from any working directory with one command. Later tools need pieces of it rather than a whole run: the validator wants the engine's secret-redaction patterns (S2.2), and the facts tool wants its file inventory (S2.7).

Four constraints bind the choice:

- One copy of each module. A second copy of the engine's code would drift from the first.
- No install step. A fresh clone must run `python3 brownfield-recipes/tools/<tool>.py` at once, because an audit starts on a machine where nothing is set up.
- The engine's behaviour and tests do not change for the sake of the tools.
- Standard library only, in both.

The engine is a package named `audit` in [`deterministic-audit/`](../../../deterministic-audit/audit/__init__.py). Its entry point, [`main(argv)`](../../../deterministic-audit/audit/__main__.py), takes the arguments explicitly and returns the exit code, which [ADR-0005 of the engine](../../../deterministic-audit/docs/architecture/adrs/0005-module-layout-and-zipapp-distribution.md) keeps stable.

## Decision

A tool imports the engine in process. [`load_engine`](../../../tools/engine.py#L57-L66) puts `deterministic-audit/` on `sys.path`, resolved from the location of `engine.py`, and imports `audit.__main__`. It then refuses to go on if the `audit` package it got did not come from that folder, so a different package called `audit` that happens to be installed cannot be run in its place.

- [`tools/engine.py`](../../../tools/engine.py) calls the engine's `main(argv)` through [`run_engine`](../../../tools/engine.py#L69-L83), with its stdout and stderr captured, so the launcher's own stdout stays a single envelope.
- A tool that needs engine internals calls `engine.load_engine()` first and imports from `audit` after it, so that the path and the guard are always the same.
- The engine never imports from `tools/`. The dependency runs one way.
- `tools/_common.py` does not import the engine. A tool that needs only the contract does not pay for the engine.

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Run the engine as a subprocess (`python3 -m audit`) | It isolates the engine's module-level state and gives clean exit codes. But it cannot hand over internals, so the validator and the facts tool would need a second mechanism beside it. Two mechanisms for one engine is worse than one. |
| A shared `common/` package that both depend on (the design plan's fallback) | Nothing needs it: the import works, and a shared package would move engine code that has no reason to move. |
| Install the engine, or run the `dist/audit.pyz` build | Both add a step before the first audit. The zipapp also needs a build and goes stale against the source. |
| Copy the engine's modules into `tools/` | Two copies drift. |

## Consequences

### Positive

* One copy of the engine, run from any directory, with no install.
* The engine's tests and behaviour are untouched.
* A tool can reuse an engine pattern or function instead of re-deriving it.

### Negative / Trade-offs

* `audit` is a generic top-level name. If another `audit` is already imported in the same interpreter, the launcher stops with an error instead of running the wrong code. It does not try to work around it.
* The engine keeps some state at module level, for example the target that `CON-04` writes beside. The engine resets it at the start of every scan, but a process should still run one scan, which is how every tool is used.
* Tools that reuse engine internals couple to them. A refactor in the engine can break a tool, and `make test` is what catches it, because it runs both suites.
