# 0006. One Committed `.mcp.json`; Agents Offer Each Person a One-Time Setup for Their Harness

* **Status:** Accepted
* **Date:** 2026-11-09
* **Last reviewed:** 2026-11-09
* **Deciders:** [@nistapp]

---

## Context

This repository asks target repositories to register the code index, `codebase-memory-mcp` (`IDX-01`,
`REQ-SH-001`). Until v0.3.3 it did not register the index for itself, and its own self-audit showed that.

Six harnesses are in use. Each reads a different project file, and they act differently on the first start
(checked 2026-11-09 in each harness's own documentation; the table is in
[Development tooling](../../reference/dev-tooling.md#agent-tools-mcp)):

* Claude Code reads `.mcp.json` and asks each person to approve each server.
* VS Code with Copilot also reads a root `.mcp.json`, and starts it in a trusted folder.
* Cursor (`.cursor/mcp.json`), Gemini CLI (`.gemini/settings.json`), opencode (`opencode.json`) and Codex CLI
  (`.codex/config.toml`) do not read `.mcp.json`.
* opencode connects a project server with no prompt.
* Antigravity keeps its servers at user level only (`agy mcp add`, checked with `agy` 1.5.1).

An MCP server is a program that runs on the person's machine. Many people clone this repository only to audit
their own code; they do not need the server here. The owner decided on one committed file, not one per harness.

---

## Decision

1. **One committed source.** [`.mcp.json`](../../../.mcp.json) lists `codebase-memory-mcp` with its bare command:
   no path, no version and no package runner. Each person installs the server and keeps its version. The
   one-place pin rule (ADR 0003, `dev/tests/test_tool_pins.py`) needs no exception.
2. **Approval stays with each person.** The committed `.claude/settings.json` never sets
   `enableAllProjectMcpServers` or `enabledMcpjsonServers`. `dev/tests/test_mcp_config.py` checks this.
3. **A one-time offer, from the top of `AGENTS.md`.** Every harness reads `AGENTS.md`. Before it edits a file,
   the agent runs `python3 dev/mcp_config.py status --harness <name>`. If it prints `not asked`, the agent makes
   the offer in [Set up the agent tools](../../how-to/set-up-agent-tools.md). It makes no offer for an audit or
   an implement run on another repository.
4. **The agent names its harness.** It uses its own knowledge, then `dev/mcp_config.py detect`. That reads the
   variable each harness sets (`CLAUDECODE`, `ANTIGRAVITY_AGENT`, `OPENCODE`). A nested harness inherits the outer
   one's variable, so more than one match means "ask the person". An unlisted harness uses `--harness other`.
5. **The answer is recorded per harness, outside git.** `.agentic-readiness/setup.json` is git-ignored. A
   declined offer is recorded too, so the agent asks once per harness and clone.
6. **Project scope by default.** [`dev/mcp_config.py`](../../../dev/mcp_config.py) translates `.mcp.json` into each
   harness's format and merges it into the project file, or the user file with `--scope user`. Git ignores the
   project files it writes. It never replaces a different entry with the same name. For Claude Code and VS Code it
   writes nothing and explains the approval. For Antigravity it prints the `agy mcp add` command; for `other`, the
   plain entry.
7. **Nothing is installed by the tool or the agent.** `check` runs `<command> --version` for a command on `PATH`.
   For a missing command it prints the upstream install routes. They carry `--skip-config`, so the installer
   writes no config into other harnesses. The person runs the installer.
8. **No gate depends on MCP or a language server.** Anything that must be right runs through `make`. A
   language server is an optional aid: `pyrightconfig.json` mirrors the `mypy.ini` import paths, and the offer
   does not cover it.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| A committed config file for each harness | The owner chose one file. Six copies drift, and opencode would start a committed server with no prompt |
| `npx -y codebase-memory-mcp@<version>` in `.mcp.json` | The package downloads a native binary when it runs. The version would need a second place or a generator. It can differ from the version that built the person's index |
| A dedicated skill for the offer | Not every harness reads skills. Every harness reads `AGENTS.md` |
| Detect the harness from environment variables only | Only Claude Code's variable is confirmed. A wrong guess writes the wrong file |
| Record the answer in a tracked file | One person's answer would apply to every clone |
| Serena in `.mcp.json` | Only Claude Code and VS Code read the file, and both have their own language-server route. The harnesses that need Serena do not read it, and its launch command differs per harness (`--context`) |
| Pre-approve the server in `.claude/settings.json` | It would start a program on every contributor's machine without asking |
| No offer: document the setup only | The setup is easy to miss, and agents then read whole files where a graph query would do |

---

## Consequences

### Positive

* The self-audit passes `IDX-01`.
* A contributor gets the index in their own harness with one question, and is asked only once.
* `.mcp.json` stays the one source; the per-harness files are local copies.

### Negative / Trade-offs

* The offer depends on the agent following `AGENTS.md`; nothing enforces it.
* The translation follows each harness's current format (opencode `mcp.servers`, checked with opencode v2.0.24). A
  harness that changes its format needs a change in `dev/mcp_config.py`.
* Each person installs a binary to get the benefit.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into
  *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference
  plus the index table in `docs/architecture/adrs/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/0006-first-run-agent-tool-offer.md`.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
