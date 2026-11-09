# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Tell which audit findings the repository has moved under since the audit.

    check_drift.py <report> <target> [--json]

Reads the report's ``provenance.target.git_sha`` and compares it with ``HEAD`` of the target, read-only. It lists the
paths changed between the two commits, and the findings whose cited ``file`` evidence or ``remediation.touches``
intersect them (a changed path equals a cited path, or sits below a cited directory). It judges nothing: a finding
listed here is one the agent should re-check before it acts on the report's text.

Two more facts come with it, neither of which changes the exit code. ``data.dirty`` is true when the target's working
tree has uncommitted changes (``git status --porcelain`` is not empty; null when git could not say), so an agent need
not run ``git status`` by hand. ``data.report_changed`` compares the report file's SHA-256 with the digest
``progress.py init`` recorded in the target's state: true when they differ, false when they match, null when the
target has no state, the state has no digest for this report (a ``0.1`` state) or the report is not one the state lists.

``data.status`` is one of ``current`` (``HEAD`` is the audited commit), ``drifted`` (it is not), ``sha_missing`` (the
audited commit is not in the target's history, so nothing can be compared and every finding is unverified) and
``no_sha`` (the report recorded none). The tool exits 0 in every case; the status carries the answer. ``--json`` is
accepted for symmetry with the other tools; the output is always the JSON envelope.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import _audit_tools_path  # noqa: F401  (puts audit/tools on sys.path in a checkout)
import _common
import progress
import validate_report

INFO = _common.ToolInfo(
    name="check_drift",
    summary="List the audit findings whose cited files changed between the audited commit and HEAD.",
    synopsis=("check_drift.py REPORT REPO [--json]",),
    writes="nothing",
)

COMMIT_TAIL = "^{commit}"


def changed_paths(target: Path, sha: str) -> list[str] | None:
    """Paths that differ between `sha` and HEAD (deletions included, renames as delete plus add), sorted. None on failure."""
    done = validate_report.git_output(target, ["diff", "--name-only", "-z", "--no-renames", sha, "HEAD", "--"])
    if done is None or done.returncode != 0:
        return None
    return sorted({name for name in done.stdout.split("\0") if name})


def revision(target: Path, name: str) -> str | None:
    done = validate_report.git_output(target, ["rev-parse", "--verify", "--quiet", name + COMMIT_TAIL])
    if done is None or done.returncode != 0:
        return None
    return done.stdout.strip() or None


def is_ancestor(target: Path, sha: str) -> bool | None:
    done = validate_report.git_output(target, ["merge-base", "--is-ancestor", sha, "HEAD"])
    if done is None or done.returncode not in (0, 1):
        return None
    return done.returncode == 0


def finding_paths(finding: Mapping[str, Any]) -> list[str]:
    """The repository paths a finding rests on: its file evidence and its remediation `touches`, deduplicated, in order."""
    paths: list[str] = []
    for evidence in finding["evidence"]:
        path = evidence.get("path")
        if evidence["kind"] == "file" and path is not None:
            paths.append(path)
    paths.extend(finding["remediation"].get("touches", []))
    return list(dict.fromkeys(path.strip("/") for path in paths if path.strip("/")))


def hits(cited: str, changed: Sequence[str]) -> list[str]:
    prefix = cited + "/"
    return [path for path in changed if path == cited or path.startswith(prefix)]


def affected_findings(report: Mapping[str, Any], changed: Sequence[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for finding in report["findings"]:
        moved = sorted({path for cited in finding_paths(finding) for path in hits(cited, changed)})
        if moved:
            out.append({"id": finding["id"], "check": finding["check"], "changed_paths": moved})
    return out


def is_dirty(target: Path) -> bool | None:
    """Whether the working tree has uncommitted changes (`git status --porcelain` prints anything). None if git fails."""
    done = validate_report.git_output(target, ["status", "--porcelain"])
    if done is None or done.returncode != 0:
        return None
    return bool(done.stdout.strip())


def recorded_digest(target: Path, report_file: Path, label: str) -> str | None:
    """The SHA-256 the target's state recorded for `report_file`, or None: no state, no digest, or another report."""
    try:
        _, state_path = progress.find_state(target, label)
        state = progress.read_state(state_path)
    except _common.ToolError:
        return None
    resolved = report_file.resolve()
    relative = resolved.relative_to(target).as_posix() if _common.is_within(target, resolved) else None
    for entry in state["source_reports"]:
        if entry["path"] == relative or (relative is None and Path(entry["path"]).name == resolved.name):
            digest = entry.get("sha256")
            return digest if isinstance(digest, str) else None
    return None


def report_changed(target: Path, report_file: Path, label: str) -> bool | None:
    """True when the report file no longer matches the digest `progress.py init` recorded; None when none was recorded."""
    recorded = recorded_digest(target, report_file, label)
    if recorded is None:
        return None
    return hashlib.sha256(report_file.read_bytes()).hexdigest() != recorded


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="check_drift.py", description=INFO.summary)
    parser.add_argument("report", help="the audit report (JSON)")
    parser.add_argument("target", help="the audited repository")
    parser.add_argument("--json", action="store_true", help="accepted for symmetry; the output is always JSON")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    target = _common.resolve_target(args.target)
    document = validate_report.read_report(Path(args.report).expanduser())
    outcome = validate_report.validate_document(document)
    validate_report.refuse_unknown_schema(outcome)
    if outcome.errors:
        count = len(outcome.errors)
        raise _common.ValidationFailed(
            f"the report is not valid: {count} error{'' if count == 1 else 's'} in the {outcome.stage} stage",
            errors=outcome.errors,
        )
    audited = document["provenance"]["target"]["git_sha"]
    head = revision(target, "HEAD")
    if head is None:
        raise _common.UsageError(f"cannot read HEAD of {target}: not a git repository, or it has no commits")
    versions, warnings = validate_report.compare_versions(
        document, progress.RECIPE_VERSION, progress.framework_revision()
    )
    data: dict[str, Any] = {"audited_sha": audited, "head_sha": head, "drifted": False, "versions": versions}
    data["dirty"] = is_dirty(target)
    data["report_changed"] = report_changed(
        target, Path(args.report).expanduser(), document["provenance"]["target"]["label"]
    )
    if data["report_changed"]:
        warnings.append(
            "the report file differs from the digest recorded when the state was created; it was edited, "
            "so do not trust its text until the owner has confirmed the change"
        )
    if data["dirty"]:
        warnings.append("the target's working tree has uncommitted changes")
    truncated = False
    if audited is None:
        data.update(status="no_sha", changed_paths=[], findings=[])
        warnings.append("the report records no git_sha, so drift cannot be measured; re-check every finding")
    elif (resolved := revision(target, audited)) is None:
        data.update(status="sha_missing", changed_paths=[], findings=[])
        warnings.append(
            "the audited commit is not in the target's history (rewritten or not fetched); re-check every finding"
        )
    elif resolved == head:  # the report may keep a short id; compare the full ones
        data.update(status="current", changed_paths=[], findings=[])
    else:
        changed = changed_paths(target, audited)
        if changed is None:
            raise _common.UsageError("git could not compare the audited commit with HEAD")
        if is_ancestor(target, audited) is False:
            warnings.append(
                "the audited commit is not an ancestor of HEAD (history was rewritten); the diff is between the two trees"
            )
        kept_paths, omitted_paths = _common.bound_items(changed)
        kept_findings, omitted_findings = _common.bound_items(affected_findings(document, changed))
        data.update(
            status="drifted", drifted=True, changed_count=len(changed), changed_paths=kept_paths, findings=kept_findings
        )
        if omitted_paths:
            data["changed_paths_omitted"] = omitted_paths
        if omitted_findings:
            data["findings_omitted"] = omitted_findings
        truncated = bool(omitted_paths or omitted_findings)
    summary = f"check_drift: {data['status']}"
    if versions["relation"] != "same":
        summary += f"; the report is from an {versions['relation']} framework release"
    if data["status"] == "drifted":
        summary += f", {data['changed_count']} paths changed, {len(data['findings'])} findings affected"
    if data["report_changed"]:
        summary += "; the report file was edited since the state was created"
    if data["dirty"]:
        summary += "; the working tree is dirty"
    return _common.Result(data=data, summary=summary, warnings=warnings, truncated=truncated)


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
