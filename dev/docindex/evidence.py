# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The evidence comparison: run the audit engine into a fresh folder, then compare two runs check by check.

A verdict-only comparison misses a break that keeps the verdict but changes what the verdict rests on, so
:func:`compare` reports both: a check whose verdict changed, and a check whose verdict stayed but whose evidence
changed. The evidence of a check is its ``summary``, its typed ``data`` payload (files, counts) and the findings the
engine raised for it (statement, severity, verdict, and each evidence entry's path, line and note).

:func:`run` writes one run folder:

- ``reports/<name>.json``: the engine's JSON report for each target (``repo`` for this repository, the fixture's name
  for an engine fixture, ``scaffold`` for a fresh scaffold of the project's templates);
- ``run.json``: the run record, written last: the engine version, the target kind, the commit (and whether the tree
  was dirty), and each report with the target path it was made from.

The folder must not exist or must be empty, and it must lie outside the repository, so a run never writes into the
tree it may scan. Each engine run is ``<python> -m audit <target> --out <report> --format json --no-user-config``
(plus the target's ``--exclude`` globs) with the engine folder as the current folder, as ``make self-audit`` runs it,
without ``--baseline`` or ``--force``. A report that is missing after the run, or older than the run's start, is
refused (:class:`StaleReportError`): the engine can leave an old file in place and still exit 0.

:func:`compare` reads two run folders and matches the reports by name and the checks by id. Before comparing, each
string in the evidence has its report's target path (and the run's work folder) replaced by a placeholder, so two
runs of the same fixture from different temporary folders compare equal. The provenance (timestamps, paths) is never
compared. :func:`to_text` and :func:`diff_to_json` write the report, sorted, with no timestamps.

This module is part of the generic core and imports no other ``dev/`` module. The entry point, ``dev/doc_index.py``,
supplies the :class:`Project`: the engine folder, the repository and the targets of each kind.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

RUN_FORMAT = "docindex-evidence-run/1"
COMPARE_FORMAT = "docindex-evidence-compare/1"
RUN_RECORD = "run.json"
REPORTS = "reports"
TARGET_KINDS: tuple[str, ...] = ("repo", "fixtures", "scaffold")
TARGET_PLACEHOLDER = "<target>"
WORK_PLACEHOLDER = "<work>"
_STAMP = ".evidence-run-start"
_REPORT_KEYS = ("name", "report", "target_path")

#: Runs one command: ``(argv, cwd, env)`` to ``(exit code, stdout, stderr)``.
Runner = Callable[[Sequence[str], Path, Mapping[str, str]], tuple[int, str, str]]


class EvidenceError(ValueError):
    """A run or a comparison that cannot go on: a failed command, an unreadable run folder or report."""


class RefusedError(EvidenceError):
    """A run that is refused before or after the engine runs: the caller exits 2."""


class StaleReportError(RefusedError):
    """A report that is missing after its run, or older than the run's start."""


def run_command(argv: Sequence[str], cwd: Path, env: Mapping[str, str]) -> tuple[int, str, str]:
    """The default :data:`Runner`: a subprocess with ``env`` over the current environment, no bytecode written."""
    full = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **env}
    try:
        proc = subprocess.run(list(argv), cwd=cwd, env=full, capture_output=True, text=True, check=False)
    except OSError as exc:
        return 127, "", f"{argv[0]}: {exc}"
    return proc.returncode, proc.stdout, proc.stderr


@dataclass(frozen=True)
class Target:
    """One folder the engine audits: its report name, its path, its ``--exclude`` globs and extra environment."""

    name: str
    path: Path
    excludes: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Project:
    """What the entry point supplies: the engine folder, the repository, and the targets of a kind.

    ``targets(kind, work)`` returns the targets of ``kind`` (one of :data:`TARGET_KINDS`); it may prepare them in
    ``work``, a temporary folder that lives for the run.
    """

    engine_dir: Path
    repo: Path
    targets: Callable[[str, Path], Sequence[Target]]
    python: str = sys.executable
    runner: Runner = run_command


def prepare_out(out: Path, repo: Path) -> None:
    """Create ``out``; refuse a folder that is not empty, a file, or a folder inside ``repo``."""
    if out.resolve().is_relative_to(repo.resolve()):
        raise RefusedError(f"{out} is inside the repository; give a folder outside it")
    if out.exists() and not out.is_dir():
        raise RefusedError(f"{out} exists and is not a folder")
    if out.is_dir() and any(out.iterdir()):
        raise RefusedError(f"{out} is not empty; give a new or an empty folder")
    out.mkdir(parents=True, exist_ok=True)


def start_stamp(out: Path) -> int:
    """The run's start on the file system's clock, in nanoseconds: the modification time of a file made now."""
    stamp = out / _STAMP
    stamp.write_bytes(b"")
    try:
        return stamp.stat().st_mtime_ns
    finally:
        stamp.unlink()


def check_fresh(report: Path, started_ns: int) -> None:
    """Refuse a report that is missing, or whose modification time is before ``started_ns``."""
    if not report.is_file():
        raise StaleReportError(f"the engine wrote no report at {report}")
    if report.stat().st_mtime_ns < started_ns:
        raise StaleReportError(f"{report} is older than the run's start; the engine did not write it")


def engine_command(python: str, target: Target, report: Path) -> list[str]:
    """The engine run for one target, as ``make self-audit`` runs it, without the baseline."""
    command = [python, "-m", "audit", str(target.path), "--out", str(report), "--format", "json", "--no-user-config"]
    for glob in target.excludes:
        command.extend(("--exclude", glob))
    return command


def _checked(runner: Runner, argv: Sequence[str], cwd: Path, what: str) -> str:
    code, out, err = runner(argv, cwd, {})
    if code != 0:
        raise EvidenceError(f"{what} failed (exit {code}): {err.strip() or out.strip()}")
    return out


def engine_version(project: Project) -> str:
    """The engine's ``--version`` line."""
    out = _checked(project.runner, [project.python, "-m", "audit", "--version"], project.engine_dir, "audit --version")
    return out.strip()


def commit(project: Project) -> dict[str, Any]:
    """The repository's ``HEAD`` commit and whether the working tree differs from it."""
    repo = str(project.repo)
    sha = _checked(project.runner, ["git", "-C", repo, "rev-parse", "HEAD"], project.repo, "git rev-parse").strip()
    status = _checked(project.runner, ["git", "-C", repo, "status", "--porcelain"], project.repo, "git status")
    return {"commit": sha, "dirty": bool(status.strip())}


def run(out: Path, kind: str, project: Project, work: Path) -> dict[str, Any]:
    """Run the engine on the targets of ``kind`` into the fresh folder ``out`` and return the run record.

    ``work`` is the temporary folder the targets may be prepared in. Raises :class:`RefusedError` for a folder that
    is not fresh or a stale report, and :class:`EvidenceError` when a command fails.
    """
    if kind not in TARGET_KINDS:
        raise EvidenceError(f"unknown target {kind!r}; expected one of {', '.join(TARGET_KINDS)}")
    prepare_out(out, project.repo)
    started = start_stamp(out)
    version = engine_version(project)
    revision = commit(project)
    reports_dir = out / REPORTS
    reports_dir.mkdir()
    reports: list[dict[str, str]] = []
    for target in sorted(project.targets(kind, work), key=lambda item: item.name):
        report = reports_dir / f"{target.name}.json"
        command = engine_command(project.python, target, report.resolve())
        code, stdout, stderr = project.runner(command, project.engine_dir, target.env)
        if code != 0:
            raise EvidenceError(f"the engine failed on {target.name} (exit {code}): {stderr.strip() or stdout.strip()}")
        check_fresh(report, started)
        reports.append({"name": target.name, "report": f"{REPORTS}/{report.name}", "target_path": str(target.path)})
    record: dict[str, Any] = {
        "format": RUN_FORMAT,
        "target": kind,
        "engine_version": version,
        **revision,
        "work": str(work),
        "reports": reports,
    }
    (out / RUN_RECORD).write_text(to_json(record), encoding="utf-8")
    return record


def to_json(data: Mapping[str, Any]) -> str:
    """The one JSON form of a run record or a comparison: sorted keys, two-space indent, a final newline."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"cannot read {path}: {exc}") from exc


def load_run(folder: Path) -> dict[str, Any]:
    """The run record of a run folder; a missing or malformed record raises :class:`EvidenceError`."""
    record = _read_json(folder / RUN_RECORD)
    if not isinstance(record, dict) or record.get("format") != RUN_FORMAT:
        raise EvidenceError(f"{folder}: not an evidence run (no {RUN_RECORD} of format {RUN_FORMAT})")
    reports = record.get("reports")
    shape = f"{folder}/{RUN_RECORD}: the reports are not a list of name, report and target_path"
    if not isinstance(reports, list):
        raise EvidenceError(shape)
    for entry in reports:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) for key in _REPORT_KEYS):
            raise EvidenceError(shape)
    return record


def _normalise(value: Any, replacements: Sequence[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        for old, new in replacements:
            if old:
                value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_normalise(item, replacements) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalise(item, replacements) for key, item in value.items()}
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class CheckEvidence:
    """One check of one report: its verdict and its evidence (summary, data, findings by id)."""

    verdict: str
    summary: Any
    data: Any
    findings: Mapping[str, tuple[str, ...]]


def checks_of(report: Any, replacements: Sequence[tuple[str, str]] = ()) -> dict[str, CheckEvidence]:
    """Each check of a parsed engine report, by id, with its findings; a wrong shape raises :class:`EvidenceError`."""
    if not isinstance(report, dict) or not isinstance(report.get("checks"), list):
        raise EvidenceError("not an engine report: no checks list")
    findings: dict[str, dict[str, list[str]]] = {}
    raw_findings = report.get("findings", [])
    if not isinstance(raw_findings, list):
        raise EvidenceError("not an engine report: the findings are not a list")
    for finding in raw_findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("check"), str):
            raise EvidenceError(f"a finding without a check: {finding!r}")
        fid = str(finding.get("id", finding["check"]))
        body = _normalise({key: value for key, value in finding.items() if key != "id"}, replacements)
        findings.setdefault(finding["check"], {}).setdefault(fid, []).append(_canonical(body))
    checks: dict[str, CheckEvidence] = {}
    for check in report["checks"]:
        if not isinstance(check, dict) or not isinstance(check.get("id"), str):
            raise EvidenceError(f"a check without an id: {check!r}")
        cid = check["id"]
        if cid in checks:
            raise EvidenceError(f"check {cid} is listed twice")
        checks[cid] = CheckEvidence(
            verdict=str(check.get("verdict")),
            summary=_normalise(check.get("summary"), replacements),
            data=_normalise(check.get("data"), replacements),
            findings={fid: tuple(sorted(bodies)) for fid, bodies in findings.get(cid, {}).items()},
        )
    return checks


def evidence_changes(old: CheckEvidence, new: CheckEvidence) -> tuple[str, ...]:
    """The parts of a check's evidence that differ, sorted: ``summary``, ``data.<key>``, ``finding <id> <how>``."""
    parts: list[str] = []
    if old.summary != new.summary:
        parts.append("summary")
    if isinstance(old.data, dict) and isinstance(new.data, dict):
        keys = set(old.data) | set(new.data)
        parts.extend(
            f"data.{key}"
            for key in keys
            if key not in old.data or key not in new.data or _canonical(old.data[key]) != _canonical(new.data[key])
        )
    elif _canonical(old.data) != _canonical(new.data):
        parts.append("data")
    for fid in set(old.findings) | set(new.findings):
        if fid not in old.findings:
            parts.append(f"finding {fid} added")
        elif fid not in new.findings:
            parts.append(f"finding {fid} removed")
        elif old.findings[fid] != new.findings[fid]:
            parts.append(f"finding {fid} changed")
    return tuple(sorted(parts))


@dataclass(frozen=True)
class CheckChange:
    """One check that changed: its verdict on each side (``None`` when absent) and the evidence parts that differ."""

    report: str
    check: str
    old_verdict: str | None
    new_verdict: str | None
    evidence: tuple[str, ...]

    @property
    def kind(self) -> str:
        """``added``, ``removed``, ``verdict`` (the verdict changed) or ``evidence`` (same verdict)."""
        if self.old_verdict is None:
            return "added"
        if self.new_verdict is None:
            return "removed"
        return "verdict" if self.old_verdict != self.new_verdict else "evidence"


@dataclass(frozen=True)
class Comparison:
    """What changed from one run to another: the reports on one side only, and each changed check, sorted."""

    reports_added: tuple[str, ...]
    reports_removed: tuple[str, ...]
    changes: tuple[CheckChange, ...]

    @property
    def empty(self) -> bool:
        return not (self.reports_added or self.reports_removed or self.changes)


def compare_reports(name: str, old: Mapping[str, CheckEvidence], new: Mapping[str, CheckEvidence]) -> list[CheckChange]:
    """The changed checks of one report, by check id."""
    changes: list[CheckChange] = []
    for cid in sorted(set(old) | set(new)):
        before, after = old.get(cid), new.get(cid)
        if before is None or after is None:
            changes.append(
                CheckChange(name, cid, before.verdict if before else None, after.verdict if after else None, ())
            )
            continue
        parts = evidence_changes(before, after)
        if parts or before.verdict != after.verdict:
            changes.append(CheckChange(name, cid, before.verdict, after.verdict, parts))
    return changes


def _replacements(record: Mapping[str, Any], entry: Mapping[str, str]) -> list[tuple[str, str]]:
    pairs = [(entry["target_path"], TARGET_PLACEHOLDER)]
    work = record.get("work")
    if isinstance(work, str):
        pairs.append((work, WORK_PLACEHOLDER))
    return pairs


def _run_checks(folder: Path) -> tuple[dict[str, Any], dict[str, dict[str, CheckEvidence]]]:
    record = load_run(folder)
    reports: dict[str, dict[str, CheckEvidence]] = {}
    for entry in record["reports"]:
        path = folder / entry["report"]
        try:
            reports[entry["name"]] = checks_of(_read_json(path), _replacements(record, entry))
        except EvidenceError as exc:
            raise EvidenceError(f"{path}: {exc}") from exc
    return record, reports


def compare(old_folder: Path, new_folder: Path) -> tuple[dict[str, Any], dict[str, Any], Comparison]:
    """The two run records and what changed from the run in ``old_folder`` to the run in ``new_folder``."""
    old_record, old = _run_checks(old_folder)
    new_record, new = _run_checks(new_folder)
    if old_record.get("target") != new_record.get("target"):
        raise EvidenceError(
            f"the runs have different targets: {old_record.get('target')} and {new_record.get('target')}"
        )
    changes: list[CheckChange] = []
    for name in sorted(set(old) & set(new)):
        changes.extend(compare_reports(name, old[name], new[name]))
    comparison = Comparison(
        reports_added=tuple(sorted(set(new) - set(old))),
        reports_removed=tuple(sorted(set(old) - set(new))),
        changes=tuple(changes),
    )
    return old_record, new_record, comparison


def _side(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in ("commit", "dirty", "engine_version", "target")}


def diff_to_json(old: Mapping[str, Any], new: Mapping[str, Any], comparison: Comparison) -> str:
    """The comparison as deterministic JSON: each side's commit and engine, and the changes."""
    return to_json(
        {
            "format": COMPARE_FORMAT,
            "old": _side(old),
            "new": _side(new),
            "reports_added": list(comparison.reports_added),
            "reports_removed": list(comparison.reports_removed),
            "changes": [
                {
                    "report": change.report,
                    "check": change.check,
                    "kind": change.kind,
                    "old_verdict": change.old_verdict,
                    "new_verdict": change.new_verdict,
                    "evidence": list(change.evidence),
                }
                for change in comparison.changes
            ],
        }
    )


def _side_line(label: str, record: Mapping[str, Any]) -> str:
    dirty = " (dirty)" if record.get("dirty") else ""
    return f"{label}: {record.get('commit')}{dirty}, {record.get('engine_version')}, target {record.get('target')}"


def _change_line(change: CheckChange) -> str:
    if change.kind == "added":
        return f"  {change.check}: check added ({change.new_verdict})"
    if change.kind == "removed":
        return f"  {change.check}: check removed (was {change.old_verdict})"
    head = (
        f"  {change.check}: verdict {change.old_verdict} -> {change.new_verdict}"
        if change.kind == "verdict"
        else f"  {change.check}: same verdict {change.new_verdict}, evidence changed"
    )
    return head + (f": {', '.join(change.evidence)}" if change.evidence else "")


def to_text(old: Mapping[str, Any], new: Mapping[str, Any], comparison: Comparison) -> str:
    """The comparison as text: the two sides, then one block per report with a changed check, then the counts."""
    lines = [_side_line("old", old), _side_line("new", new)]
    if comparison.empty:
        lines.append("no verdict or evidence changed")
        return "\n".join(lines) + "\n"
    lines.extend(f"report added: {name}" for name in comparison.reports_added)
    lines.extend(f"report removed: {name}" for name in comparison.reports_removed)
    current: str | None = None
    for change in comparison.changes:
        if change.report != current:
            current = change.report
            lines.append(f"report {current}:")
        lines.append(_change_line(change))
    kinds = [change.kind for change in comparison.changes]
    lines.append(
        f"{kinds.count('verdict')} verdict changed, {kinds.count('evidence')} same verdict with different evidence, "
        f"{kinds.count('added')} check added, {kinds.count('removed')} check removed"
    )
    return "\n".join(lines) + "\n"
