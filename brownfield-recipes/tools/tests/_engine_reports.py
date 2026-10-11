# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Engine reports (schema v2) built by hand, for the tests of the engine adapter.

A check is made from the catalogue's own entry, so that its title, phase, severity and `scored` flag agree with the
catalogue as rule 2 of the validator requires. A finding is made as the engine's `Finding.to_dict` makes it. The
real reports are in `schema/examples/realistic/`; these are for the cases they do not hold. Standard library only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import _paths  # noqa: F401
import validate_report as vr

CATALOGUE: dict[str, Mapping[str, Any]] = {entry["id"]: entry for entry in vr.load_catalogue()["checks"]}


def provenance(target: Path | str, **changes: Any) -> dict[str, Any]:
    """The `provenance` object of an engine report, as the engine writes it."""
    document: dict[str, Any] = {
        "tool": "python-agentic-audit",
        "version": "0.1.0",
        "ruleset_revision": "2026-09-28.13",
        "ruleset_hash": "0123456789abcdef",
        "scanned_at": "2026-10-10T06:57:38+00:00",
        "target": str(target),
        "git_sha": None,
        "git_branch": None,
        "git_dirty": None,
        "phase": 1,
        "probes_enabled": False,
        "framework_revision": None,
    }
    document.update(changes)
    return document


def check(check_id: str, verdict: str = "PASS", **changes: Any) -> dict[str, Any]:
    """An engine check made from the catalogue's entry for `check_id`."""
    entry = CATALOGUE[check_id]
    document: dict[str, Any] = {
        "id": check_id,
        "pack": check_id.split("-")[0],
        "title": entry["title"],
        "tier": "A",
        "severity": entry["severity"],
        "phase": entry["phase"],
        "scored": entry["scored"],
        "status": "implemented",
        "verdict": verdict,
        "summary": f"{check_id} is {verdict}.",
        "data": {},
    }
    document.update(changes)
    return document


def evidence(path: str, line: int | None = None, note: str | None = None) -> dict[str, Any]:
    return {"path": path, "line": line, "note": note}


def finding(check_id: str, path: str | None = None, **changes: Any) -> dict[str, Any]:
    """An engine finding. Its id is the check's id, and a path after a colon when it has one."""
    entry = CATALOGUE[check_id]
    document: dict[str, Any] = {
        "id": check_id if path is None else f"{check_id}:{path}",
        "check": check_id,
        "phase": entry["phase"],
        "severity": entry["severity"],
        "verdict": "FAIL",
        "statement": "An agent cannot do the thing because the thing is missing.",
        "evidence": [],
        "remediation": "Add the thing.",
    }
    document.update(changes)
    return document


def probe(
    verb: str = "test", command: Sequence[str] = ("npm", "test"), exit_code: int | None = 0, **changes: Any
) -> dict[str, Any]:
    """A probe the engine ran, as `ProbeResult` is written into the report."""
    document: dict[str, Any] = {
        "verb": verb,
        "command": list(command),
        "exit_code": exit_code,
        "duration_s": 1.234,
        "timed_out": False,
        "output_tail": "ok\n",
        "refused_reason": None,
        "redactions": 0,
    }
    document.update(changes)
    return document


def refused_probe(verb: str = "test", command: Sequence[str] = ("npm", "test")) -> dict[str, Any]:
    """A probe the engine refused to run, as the report records it by default."""
    return probe(
        verb,
        command,
        None,
        duration_s=0.0,
        output_tail="",
        refused_reason="probes disabled (pass --run-gates)",
    )


def report(
    target: Path | str,
    checks: Sequence[Mapping[str, Any]] = (),
    findings: Sequence[Mapping[str, Any]] = (),
    not_applicable: Sequence[str] = (),
    probes: Sequence[Mapping[str, Any]] = (),
    **changes: Any,
) -> dict[str, Any]:
    """An engine report with the parts given. The parts a test does not use are empty."""
    document: dict[str, Any] = {
        "schema_version": "2",
        "provenance": provenance(target),
        "summary": {"phase1_score": None},
        "stack": {
            "ecosystems": [],
            "package_managers": [],
            "ci_providers": [],
            "test_frameworks": [],
            "hook_managers": [],
            "notes": [],
        },
        "inventory": {"files_inspected": 0, "files_skipped": 0, "truncated": False},
        "components": [],
        "candidate_components": [],
        "checks": [dict(c) for c in checks],
        "findings": [dict(f) for f in findings],
        "unattested": [],
        "not_applicable": list(not_applicable),
        "probes": [dict(p) for p in probes],
    }
    document.update(changes)
    return document
