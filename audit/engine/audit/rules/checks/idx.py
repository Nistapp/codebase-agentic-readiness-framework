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

import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from urllib.parse import quote

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.payloads import Payload

#: The server this pack checks for, matched as a literal in configuration text.
SERVER_NAME = "codebase-memory-mcp"

#: Project-level MCP configuration candidates, relative to the target root.
_PROJECT_CONFIGS: tuple[str, ...] = (
    "opencode.json",
    "opencode.jsonc",
    ".mcp.json",
    ".cursor/mcp.json",
    ".vscode/mcp.json",
    ".gemini/settings.json",
    ".codex/config.toml",
)

#: Environment override for the index store: a directory of `*.db` files, or one `.db` file.
INDEX_STORE_ENV = "AUDIT_INDEX_STORE"

#: Team-sharing artifact carried inside the target. Compressed with zstd; not stdlib-readable.
_TEAM_ARTIFACT = Path(".codebase-memory") / "graph.db.zst"

#: Column names that would carry an indexed git revision, if a store records one.
_GIT_COLUMN_RE = re.compile(r"(?i)(?:git[_ -]?sha|sha[_ -]?git|revision|commit)")

#: Bounded read for user-level configuration files (they are outside the target inventory).
_READ_LIMIT = 256 * 1024

#: Claude Code's user configuration, under ``$HOME``. It also holds history and caches, so it is read with a larger
#: bound; a file larger than that is unreadable rather than read in part, since a cut JSON file cannot be parsed.
_CLAUDE_USER_CONFIG = ".claude.json"
_CLAUDE_READ_LIMIT = 16 * 1024 * 1024

#: The column of a store's ``projects`` row that records when the project was indexed.
_INDEXED_AT_COLUMN = "indexed_at"


def _outcome(
    spec, verdict: Verdict, summary: str = "", findings: list[Finding] | None = None, data: Payload | None = None
) -> CheckOutcome:
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=summary,
        data=data,
        findings=findings or [],
    )


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _finding(spec, cannot: str, because: str, verdict: Verdict, evidence: list[Evidence], remediation: str) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence,
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# readers
# ---------------------------------------------------------------------------


def _user_configs(session) -> tuple[Path, ...]:
    """User-level MCP configuration candidates, resolved against ``$HOME`` at call time; none under ``--no-user-config``."""
    if not session.user_config:
        return ()
    home = Path.home()
    return (
        home / ".config" / "opencode" / "opencode.json",
        home / ".config" / "opencode" / "opencode.jsonc",
        home / ".codex" / "config.toml",
    )


def _read_user(path: Path) -> str | None:
    """Read a bounded user-level config. Returns None for missing, binary or unreadable files."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(_READ_LIMIT)
    except OSError:
        return None


def _claude_user_registration(path: Path, target) -> tuple[bool | None, str]:
    """Whether Claude Code's ``~/.claude.json`` registers the server for this checkout, and in which scope.

    ``None`` when the file cannot be read or parsed. Its top-level ``mcpServers`` is the user scope, which reaches
    every checkout; ``projects.<path>.mcpServers`` is the local scope of one checkout, read only for the entry whose
    path resolves to the target. A server named in another checkout's entry does not register this one.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            text = handle.read(_CLAUDE_READ_LIMIT + 1)
    except (OSError, UnicodeDecodeError):
        return None, ""
    if len(text) > _CLAUDE_READ_LIMIT:
        return None, ""
    try:
        data = json.loads(text)
    except ValueError:
        return None, ""
    if not isinstance(data, dict):
        return None, ""
    servers = data.get("mcpServers")
    if isinstance(servers, dict) and SERVER_NAME in servers:
        return True, "user scope"
    projects = data.get("projects")
    if isinstance(projects, dict):
        wanted = target.path.resolve()
        for key, entry in projects.items():
            if not isinstance(entry, dict) or _resolve(str(key)) != wanted:
                continue
            local = entry.get("mcpServers")
            if isinstance(local, dict) and SERVER_NAME in local:
                return True, "local scope"
    return False, ""


def _candidate_dbs(store: Path) -> list[Path]:
    """The SQLite databases a store path yields: itself if a `.db`, else its `*.db` children."""
    if store.is_file():
        return [store] if store.suffix == ".db" else []
    if store.is_dir():
        return sorted(path for path in store.glob("*.db") if path.is_file())
    return []


def _read_projects(db: Path) -> list[dict] | None:
    """Rows of a store's ``projects`` table, or None if the database or table cannot be read.

    Opened read-only through a URI so the audit can never create a ``-wal`` file or otherwise mutate
    the index it is inspecting.
    """
    try:
        uri = f"file:{quote(db.resolve().as_posix())}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
    except (sqlite3.Error, OSError):
        return None
    try:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM projects").fetchall()]
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _locate_store(target, session) -> tuple[Path | None, list[str]]:
    """Resolve the index store, returning ``(store_or_None, searched_locations)``.

    Fixed precedence: the ``AUDIT_INDEX_STORE`` override, then the user-level default locations,
    then the team-sharing artifact inside the target. Under ``--no-user-config`` the default locations under
    ``$HOME`` are not looked at; the override is an explicit operator choice and still applies. Every path outside the
    target that is used is recorded on the session, for the report's provenance.
    """
    searched: list[str] = []
    override = os.environ.get(INDEX_STORE_ENV)
    if override:
        path = Path(override).expanduser()
        searched.append(f"{INDEX_STORE_ENV}={_shown(path, target)}")
        if path.exists():
            session.note_user_read(path)
            return path, searched
        return None, searched

    if session.user_config:
        home = Path.home()
        for path in (
            home / ".codebase-memory",
            home / ".cache" / "codebase-memory",
            home / ".cache" / "codebase-memory-mcp",
        ):
            searched.append(str(path))
            if path.exists():
                session.note_user_read(path)
                return path, searched
    else:
        searched.append("user-level locations (not read: --no-user-config)")

    artifact = target.path / _TEAM_ARTIFACT
    searched.append(_shown(artifact, target))
    if artifact.exists():
        return artifact, searched

    return None, searched


def _shown(path: Path, target) -> str:
    """``path`` for a summary: ``<repository>/...`` inside the target, so the text never holds its location."""
    for base, candidate in ((target.path, path), (target.path.resolve(), path.resolve())):
        try:
            rel = candidate.relative_to(base)
        except ValueError:
            continue
        return f"<repository>/{rel.as_posix()}" if rel.parts else "<repository>"
    return str(path)


def _resolve(path_str: str) -> Path | None:
    try:
        return Path(path_str).expanduser().resolve()
    except (OSError, RuntimeError):
        return None


def _match_project(rows: list[dict], target) -> dict | None:
    """The store row whose recorded root resolves to the target root, if any."""
    wanted = target.path.resolve()
    for row in rows:
        root = row.get("root_path")
        if root and _resolve(str(root)) == wanted:
            return row
    return None


# ===========================================================================
# IDX-01 — codebase-memory-mcp registered for this repository
# ===========================================================================


def check_idx01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    present: list[str] = []
    named: list[str] = []
    unreadable: list[str] = []

    for rel in _PROJECT_CONFIGS:
        if not inventory.has(rel):
            continue
        present.append(rel)
        text = inventory.read(rel)
        if text is None:
            unreadable.append(rel)
        elif SERVER_NAME in text:
            named.append(f"{rel} (project)")

    for path in _user_configs(session):
        if not path.is_file():
            continue
        session.note_user_read(path)
        label = str(path)
        present.append(label)
        text = _read_user(path)
        if text is None:
            unreadable.append(label)
        elif SERVER_NAME in text:
            named.append(f"{label} (user)")

    if session.user_config:
        claude = Path.home() / _CLAUDE_USER_CONFIG
        if claude.is_file():
            session.note_user_read(claude)
            label = str(claude)
            present.append(label)
            registered, scope = _claude_user_registration(claude, target)
            if registered is None:
                unreadable.append(label)
            elif registered:
                named.append(f"{label} ({scope})")

    if not present:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no project-level MCP configuration found (user-level configuration not read: --no-user-config)"
            if not session.user_config
            else "no project- or user-level MCP configuration found",
            [
                _finding(
                    spec,
                    "discover the codebase through an MCP index",
                    "no MCP configuration names codebase-memory-mcp for this repository",
                    Verdict.FAIL,
                    [Evidence("<repository>")],
                    "Register the server in a project config (for example `opencode.json`) or a user config "
                    "(`~/.config/opencode/opencode.json`).",
                )
            ],
        )

    if named:
        return _outcome(spec, Verdict.PASS, f"{SERVER_NAME} registered in: {', '.join(sorted(named))}")

    if unreadable:
        return _unknown(spec, f"MCP configuration found but could not be read: {', '.join(sorted(unreadable))}")

    return _outcome(
        spec,
        Verdict.PARTIAL,
        f"MCP configuration present but does not name {SERVER_NAME}: {', '.join(sorted(present))}",
        [
            _finding(
                spec,
                "discover the codebase through an MCP index",
                f"an MCP configuration exists ({', '.join(sorted(present))}) but does not name {SERVER_NAME}",
                Verdict.PARTIAL,
                [Evidence(rel) for rel in sorted(present)],
                f"Add a {SERVER_NAME} server entry to one of the discovered MCP configurations.",
            )
        ],
    )


# ===========================================================================
# IDX-02 — an index exists for this checkout
# ===========================================================================


def check_idx02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    store, searched = _locate_store(target, session)
    locations = f"searched: {', '.join(searched)}"

    if store is None:
        return _unknown(spec, f"index store could not be located; {locations}")

    shown = _shown(store, target)
    dbs = _candidate_dbs(store)
    if not dbs:
        return _unknown(spec, f"index store located ({shown}) but holds no readable database; {locations}")

    roots: list[str] = []
    readable = False
    for db in dbs:
        rows = _read_projects(db)
        if rows is None:
            continue
        readable = True
        roots.extend(str(row.get("root_path", "")) for row in rows)

    if not readable:
        return _unknown(
            spec, f"index store located ({shown}) but no database could be read with the standard library; {locations}"
        )

    wanted = target.path.resolve()
    if any(_resolve(root) == wanted for root in roots if root):
        return _outcome(spec, Verdict.PASS, f"index store {shown} contains a project rooted at <repository>")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"index store {shown} records no project rooted at <repository> ({len(roots)} project(s) present)",
        [
            _finding(
                spec,
                "query a current index of this checkout",
                "the index store contains no project whose root resolves to <repository>",
                Verdict.FAIL,
                [Evidence(str(store))],
                "Index this checkout with codebase-memory-mcp so agents have a graph to query.",
            )
        ],
    )


# ===========================================================================
# IDX-03 — index freshness (Tier C)
# ===========================================================================


def _indexed_git_sha(store: Path, target) -> tuple[str | None, str, dict | None]:
    """The store's recorded git revision for the target, or ``(None, reason, row)``.

    The comparison is only possible when a store exposes a revision column; today's schema records a
    project's root and index time only, and that absence is reported rather than guessed. ``row`` is the
    matching project row, for the time-based comparison, or ``None`` when no row matches.
    """
    dbs = _candidate_dbs(store)
    if not dbs:
        return (
            None,
            f"no readable index database at {_shown(store, target)} (a .zst artifact needs zstd, which the standard library lacks)",
            None,
        )

    columns: list[str] = []
    found: dict | None = None
    for db in dbs:
        rows = _read_projects(db)
        if rows is None:
            continue
        if rows and not columns:
            columns = sorted(rows[0].keys())
        match = _match_project(rows, target)
        if match is None:
            continue
        found = match
        for key, value in match.items():
            if _GIT_COLUMN_RE.search(key) and value:
                return str(value), f"column {key!r}", match
        break

    if found is None:
        return None, "no project matching this checkout was found in the index store", None
    return (
        None,
        f"the store records project root and index time but no git revision (columns: {', '.join(columns) or 'unknown'})",
        found,
    )


def _git_query(path: Path, *args: str) -> str | None:
    """A read-only git query in ``path``; ``None`` when git is absent or fails."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "--no-optional-locks", *args],
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _head_moved_at(path: Path) -> int | None:
    """When HEAD last moved, in Unix seconds: the later of HEAD's committer time and its newest reflog entry.

    A checkout of an older commit after the index ran keeps an old committer time, so the reflog entry is what
    shows that HEAD moved. A clone with no reflog falls back to the committer time.
    """
    times: list[int] = []
    committed = _git_query(path, "log", "-1", "--format=%ct", "HEAD")
    if committed and committed.isdigit():
        times.append(int(committed))
    moved = re.fullmatch(r"HEAD@\{(\d+)\}", _git_query(path, "log", "-g", "-1", "--date=unix", "--format=%gd", "HEAD") or "")
    if moved:
        times.append(int(moved.group(1)))
    return max(times) if times else None


def _parse_time(value: object) -> dt.datetime | None:
    """An ISO 8601 index time as an aware UTC datetime; ``None`` when it is missing or cannot be read."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def _stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _time_based(spec, store: Path, target, row: dict, reason: str) -> CheckOutcome:
    """IDX-03 by time, when the store records no revision: the index time against the time HEAD last moved."""
    indexed = _parse_time(row.get(_INDEXED_AT_COLUMN))
    if indexed is None:
        return _unknown(spec, f"indexed revision cannot be compared to HEAD: {reason}, and no readable index time")
    moved_at = _head_moved_at(target.path)
    if moved_at is None:
        return _unknown(spec, "indexed revision cannot be compared to HEAD: git gives no time for HEAD")
    head = dt.datetime.fromtimestamp(moved_at, dt.timezone.utc)
    if indexed >= head:
        return _outcome(
            spec,
            Verdict.PASS,
            f"index built at {_stamp(indexed)}, at or after HEAD last moved ({_stamp(head)}); the store records no "
            "revision, so this is a time comparison and does not cover uncommitted edits made since",
        )
    return _outcome(
        spec,
        Verdict.PARTIAL,
        f"index built at {_stamp(indexed)}, before HEAD last moved ({_stamp(head)}); the store records no revision, "
        "so the graph may not match HEAD",
        [
            _finding(
                spec,
                "trust the graph to reflect the current revision",
                f"the index was built at {_stamp(indexed)}, before HEAD last moved at {_stamp(head)}",
                Verdict.PARTIAL,
                [Evidence(_shown(store, target), note=f"indexed_at {_stamp(indexed)}; HEAD moved {_stamp(head)}")],
                "Re-index this checkout so the graph matches HEAD.",
            )
        ],
    )


def check_idx03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if target.git_sha is None:
        return _unknown(spec, "target is not a git repository, so there is no HEAD for the index to match")

    if not session.enabled:
        return _unknown(
            spec,
            "index freshness is a Tier-C probe; re-run with --run-gates to compare the indexed revision against HEAD",
        )

    store, searched = _locate_store(target, session)
    if store is None:
        return _unknown(spec, f"index store could not be located; searched: {', '.join(searched)}")

    sha, reason, row = _indexed_git_sha(store, target)
    if sha is None and row is not None:
        return _time_based(spec, store, target, row, reason)
    if sha is None:
        return _unknown(spec, f"indexed revision cannot be compared to HEAD: {reason}")
    if sha == target.git_sha:
        return _outcome(spec, Verdict.PASS, f"indexed revision {sha} equals HEAD")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"indexed revision {sha} does not match HEAD {target.git_sha}",
        [
            _finding(
                spec,
                "trust the graph to reflect the current revision",
                f"the index was built at {sha} but HEAD is {target.git_sha}",
                Verdict.FAIL,
                [Evidence(str(store), note=f"indexed {sha}; HEAD {target.git_sha}")],
                "Re-index this checkout so the graph matches HEAD.",
            )
        ],
    )


IMPLEMENTATIONS = {
    "IDX-01": check_idx01,
    "IDX-02": check_idx02,
    "IDX-03": check_idx03,
}
