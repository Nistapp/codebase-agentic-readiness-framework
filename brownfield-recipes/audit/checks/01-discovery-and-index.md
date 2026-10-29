# Discovery and Index (`IDX`)

> Follows the anatomy in [`README.md`](README.md). Three checks, all `method: automated`. See
> [Why These Checks §2](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#2-discovery-and-index-idx)
> for the consequence behind this family: an agent that cannot query structure falls back to `grep` and
> whole-file reads, so every downstream phase of the framework depends on `codebase-memory-mcp`.

---

## IDX-01 — codebase-memory-mcp registered for this repository

Why it matters   Every later check and playbook assumes an agent can reach the index; without
                  registration an agent has no way to discover that one should exist
                  ([`brownfield-legacy/Phased-Approach.md` § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         BLOCKER
Engine           `IDX-01`. Reads project-level MCP configs inside the target (`opencode.json`/`.jsonc`,
                 `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, `.gemini/settings.json`,
                 `.codex/config.toml`) and user-level configs under `$HOME`, for the literal
                 `codebase-memory-mcp`. Distrust a `FAIL` when the harness in use names a config file the
                 engine's list does not cover yet — ask the user which harness and config they use, then
                 look there directly. A config present but unreadable is `UNKNOWN`, not `FAIL`.
Method           automated
Look for         Ask the user which harness they run (Stage 0 intake) and which MCP config it reads; open
                 that file directly rather than re-deriving the engine's search order. For a project-level
                 config, confirm the server is named; for a user-level config, note that it registers every
                 checkout on that machine, not only this one.
Rubric           PASS: a readable project- or user-level config names `codebase-memory-mcp`.
                 PARTIAL: a config exists but the server name is absent or commented out.
                 FAIL: no MCP config of any known kind exists, project- or user-level.
                 NOT_APPLICABLE: never — every repository can register an index.
                 UNKNOWN when: a candidate config exists but cannot be read (permissions, encoding), or the
                 user names a harness whose config file this check's engine list does not cover.
Evidence to cite The config file's path and the line or quoted fragment naming (or failing to name) the
                 server, as a `file` evidence item; `captured_by: tool` when the engine's own evidence is
                 kept unchanged, `captured_by: agent` when the agent looked at a config the engine's list
                 does not cover.
Absence proof    A FAIL records a `glob` search entry for each config path class the engine checks
                 (project-level, user-level) with its scope and a `0` hit count, plus a `grep` entry over
                 any config file that was found but did not name the server.
Remediation      `register-index`
Pitfalls         A user-level config registers every checkout on the machine, including ones that have no
                 index yet (that gap is `IDX-02`, not this check) — do not read a user-level `PASS` here as
                 proof an index exists. A harness not in the engine's config list is a reason to ask the
                 user, not a reason to report `FAIL`.

## IDX-02 — An index exists for this checkout

Why it matters   An index of a different checkout is worse than none: it answers confidently with
                  structure that no longer exists
                  ([`brownfield-legacy/Phased-Approach.md` § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         BLOCKER
Engine           `IDX-02`. Resolves the index store by a fixed order (the `AUDIT_INDEX_STORE` override,
                 then `~/.codebase-memory/`, `~/.cache/codebase-memory/`, `~/.cache/codebase-memory-mcp/`,
                 then `.codebase-memory/graph.db.zst` inside the target), opens a SQLite `.db` store
                 read-only, and matches a `projects` row whose `root_path` resolves to the target. Distrust
                 a `FAIL` when the store is a `.zst` team artifact the engine cannot open (needs `zstd`, not
                 in the standard library) or lives somewhere outside the searched locations — the engine
                 reports `UNKNOWN` in both cases, never `FAIL`, so a `FAIL` here is never a tooling gap.
Method           automated
Look for         Use the index tool itself: a query that returns real results for this checkout (for
                 example `get_architecture` or `list_projects`) is stronger evidence than re-reading the
                 engine's store location, because it proves the index both exists and answers.
Rubric           PASS: the index answers a structural query for this checkout, or the engine finds a store
                 row whose root resolves to the target.
                 PARTIAL: the index exists but returns an architecture summary that is clearly stale
                 (file counts far off the facts tool's inventory) without yet being `HEAD`-verified (that
                 verification is `IDX-03`).
                 FAIL: a readable store exists and holds no project for this root.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: the store cannot be located or its format cannot be read; `IDX-01` is itself
                 `FAIL` or `UNKNOWN` (nothing to query).
Evidence to cite An `index_query` evidence item (`index_tool`, `query`, `result_summary`) for a direct
                 query, or a `file` item citing the store path and the matched `root_path` row for the
                 engine's own method.
Absence proof    A FAIL records an `index` search entry: the query or lookup attempted, the project scope
                 (the target's resolved path), and a `0` hit count.
Remediation      `register-index`
Pitfalls         The store is machine-local; a developer who keeps it at a non-default path and has not set
                 `AUDIT_INDEX_STORE` will see the engine report `UNKNOWN`, which must not be escalated to
                 `FAIL` without first asking where they keep it.

## IDX-03 — Index freshness vs HEAD

Why it matters   A stale graph is stale context: an agent edits based on symbols that have already moved
                  or been deleted
                  ([`brownfield-legacy/Phased-Approach.md` § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `IDX-03`, Tier C only (`--run-gates`); without probes the engine reports `UNKNOWN` by
                 construction. Compares the store's recorded git revision against `target.git_sha` when the
                 store schema exposes one; this schema today records a project's root and index time but no
                 revision, so the engine's own verdict is `UNKNOWN` with that limitation stated. Distrust a
                 engine `PASS` only if the index tool itself reports a different freshness signal (for
                 example a `detect_changes` call naming files touched since the index last ran).
Method           automated
Look for         If Tier C was not allowed this run, ask the index tool directly: `detect_changes` or an
                 equivalent freshness query against the current `HEAD`. Treat a tool-reported freshness
                 check as stronger than the engine's own, which this store cannot currently perform.
Rubric           PASS: the index's recorded revision matches `HEAD`, or a direct freshness query reports no
                 drift.
                 PARTIAL: the index predates `HEAD` by a small, named set of commits with no change to
                 indexed symbols (confirmed by `git diff --stat` against the commit range).
                 FAIL: the index predates `HEAD` and the drift touches files the agent is about to rely on.
                 NOT_APPLICABLE: the target is not a git repository (there is no `HEAD` to compare against).
                 UNKNOWN when: Tier C was not allowed and no direct freshness query is available; the store
                 schema exposes no revision and no tool-level freshness signal exists either.
Evidence to cite A `command` evidence item for the engine's Tier-C comparison (`command`, `exit_code`,
                 `output_tail`), or an `index_query` item for a direct freshness query, each with
                 `captured_by` set to who ran it.
Absence proof    A FAIL or UNKNOWN that rests on "the store has no revision column" records a `grep` search
                 entry over the store's schema (the columns inspected) with its hit count.
Remediation      `register-index`
Pitfalls         `UNKNOWN` is the honest answer whenever Tier C is off and no index tool offers its own
                 freshness signal — this is a limitation of the store schema, not evidence that the index is
                 stale, and must not be read as a soft `FAIL`.
