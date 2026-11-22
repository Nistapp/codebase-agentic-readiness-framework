# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""IDX-01: codebase-memory-mcp registered for this repository."""

from __future__ import annotations

import json
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.idx._shared import _finding, _outcome, _resolve, _unknown

SPEC = declare("IDX-01", "codebase-memory-mcp registered for this repository", "A", Severity.BLOCKER)

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


#: Bounded read for user-level configuration files (they are outside the target inventory).
_READ_LIMIT = 256 * 1024

#: Claude Code's user configuration, under ``$HOME``. It also holds history and caches, so it is read with a larger
#: bound; a file larger than that is unreadable rather than read in part, since a cut JSON file cannot be parsed.
_CLAUDE_USER_CONFIG = ".claude.json"
_CLAUDE_READ_LIMIT = 16 * 1024 * 1024


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


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.checks import idx
    from audit.rules.reads import ANY_DEPTH, Reads, What, _held

    return Reads(
        where=(*_held(idx, "_PROJECT_CONFIGS", ANY_DEPTH),),
        what=What("phrase", ("codebase-memory-mcp",)),
        binding="file",
        note=(
            "Each config is kept when Inventory.has finds its name at any depth but read by its exact root "
            "path, so a nested-only copy reads as unreadable (UNKNOWN). Three user configs under $HOME are "
            "read too, unless --no-user-config, and Claude Code's ~/.claude.json is parsed: its top-level "
            "mcpServers or the projects entry of this checkout's path."
        ),
    )
