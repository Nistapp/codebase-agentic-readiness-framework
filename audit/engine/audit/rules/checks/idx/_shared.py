# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one IDX check uses."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.payloads import Payload

#: Environment override for the index store: a directory of `*.db` files, or one `.db` file.
INDEX_STORE_ENV = "AUDIT_INDEX_STORE"

#: Team-sharing artifact carried inside the target. Compressed with zstd; not stdlib-readable.
_TEAM_ARTIFACT = Path(".codebase-memory") / "graph.db.zst"


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
