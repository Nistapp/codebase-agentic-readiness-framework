# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`IDX` pack — discovery and the codebase index.

Anchor: `docs/framework/phased-approach.md` § Phase 1: Agentic Bootstrap ("Configure and run
`codebase-memory-mcp` to index source files, symbols, relationships, dependencies, and tests").

Implemented here: `IDX-01` … `IDX-03`.

The pack verifies that the checkout is *discoverable to agents through `codebase-memory-mcp`*: the
server is registered for it (`IDX-01`), an index exists for its root (`IDX-02`), and — Tier C only —
the indexed revision matches `HEAD` (`IDX-03`). It reads configuration and index metadata; it never
runs the indexer and never mutates the store.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **IDX-01** — an MCP configuration that names `codebase-memory-mcp`. Project-level candidates are
  read from inside the target (`opencode.json`/`opencode.jsonc`, `.mcp.json`, `.cursor/mcp.json`,
  `.vscode/mcp.json`, `.gemini/settings.json`, `.codex/config.toml`); user-level candidates are read
  from `$HOME` (`~/.config/opencode/opencode.json`/`.jsonc`, `~/.codex/config.toml`, and Claude Code's
  `~/.claude.json`). A project-level config is inherently scoped to this checkout; a user-level config that
  names the server applies to every checkout, so it registers this one too. `~/.claude.json` is parsed, not
  searched: it also holds the servers of other checkouts (`projects.<path>.mcpServers`), so it registers this
  one only through its top-level `mcpServers` (user scope) or the entry of this checkout's own path (local
  scope). A config present but naming no server is `PARTIAL`;
  no config at all is `FAIL` (BLOCKER: an agent cannot discover the codebase); a config that exists
  but cannot be read is `UNKNOWN`.
* **IDX-02** — the index store. It lives outside the target and its exact path is environment
  dependent, so it is resolved in a fixed order: the `AUDIT_INDEX_STORE` environment override, then
  `~/.codebase-memory/`, `~/.cache/codebase-memory/`, `~/.cache/codebase-memory-mcp/`, then the
  team-sharing artifact `.codebase-memory/graph.db.zst` inside the target. A SQLite `.db` store is
  opened read-only with the standard library; a project whose `root_path` resolves to the target is a
  `PASS`, and a readable store with no such project is `FAIL`. **If the store cannot be located, or
  its format cannot be read with the standard library (a `.zst` artifact needs `zstd`), the verdict
  is `UNKNOWN`** — no location is invented and no absence is claimed. The searched locations are
  recorded in `detail`. A path inside the target is written as `<repository>/...`, so the summary is the
  same wherever the checkout sits; a store under `$HOME` or the override is machine state and is written
  as it is.
* **IDX-03 (Tier C)** — compares the index's recorded git revision against `target.git_sha`. It is
  gated on `--run-gates`; without probes it is `UNKNOWN`. It never mutates the store. A store that exposes
  a revision column is compared directly: equal is `PASS`, different is `FAIL`. Today's store records a
  project's root and index time (`indexed_at`) but no revision, so the check compares times instead: the
  index time against the time HEAD last moved, the later of HEAD's committer time and the newest entry of
  HEAD's reflog (a checkout, a commit, a reset). An index built at or after that time is `PASS`. One built
  before it is `PARTIAL`, never `FAIL`: a commit of files that were indexed before they were committed moves
  HEAD without changing the tree. A time-based `PASS` does not cover uncommitted edits made after the index
  ran. With no index time or no HEAD time, the check is `UNKNOWN`. A non-git target is `UNKNOWN`.

Deliberate limits, recorded rather than hidden. **Registration is detected by the server name in a
config file, not by a live handshake** (`index-in-use` is on the unattested list). **A user-level
config cannot be attributed to one checkout** — it is accepted as registration for all of them.
**The index store is machine-local**; absence of a known store location degrades to `UNKNOWN` so a
machine that keeps its store elsewhere is never reported as unindexed.
"""

from __future__ import annotations

from audit.rules.checks.idx import idx_01, idx_02, idx_03
from audit.rules.checks.idx._shared import (
    INDEX_STORE_ENV as INDEX_STORE_ENV,
    _TEAM_ARTIFACT as _TEAM_ARTIFACT,
    _outcome as _outcome,
    _unknown as _unknown,
    _finding as _finding,
    _candidate_dbs as _candidate_dbs,
    _read_projects as _read_projects,
    _locate_store as _locate_store,
    _shown as _shown,
    _resolve as _resolve,
)
from audit.rules.checks.idx.idx_01 import (
    SERVER_NAME as SERVER_NAME,
    _PROJECT_CONFIGS as _PROJECT_CONFIGS,
    _READ_LIMIT as _READ_LIMIT,
    _CLAUDE_USER_CONFIG as _CLAUDE_USER_CONFIG,
    _CLAUDE_READ_LIMIT as _CLAUDE_READ_LIMIT,
    _user_configs as _user_configs,
    _read_user as _read_user,
    _claude_user_registration as _claude_user_registration,
    check_idx01 as check_idx01,
)
from audit.rules.checks.idx.idx_02 import (
    check_idx02 as check_idx02,
)
from audit.rules.checks.idx.idx_03 import (
    _GIT_COLUMN_RE as _GIT_COLUMN_RE,
    _INDEXED_AT_COLUMN as _INDEXED_AT_COLUMN,
    _match_project as _match_project,
    _indexed_git_sha as _indexed_git_sha,
    _git_query as _git_query,
    _head_moved_at as _head_moved_at,
    _parse_time as _parse_time,
    _stamp as _stamp,
    _time_based as _time_based,
    check_idx03 as check_idx03,
)
from audit.rules.spec import CheckSpec

#: The IDX checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    idx_01.SPEC,
    idx_02.SPEC,
    idx_03.SPEC,
)

IMPLEMENTATIONS = {
    "IDX-01": check_idx01,
    "IDX-02": check_idx02,
    "IDX-03": check_idx03,
}
