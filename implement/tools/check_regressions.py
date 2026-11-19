# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Compare two engine reports of one theme worktree: which passing checks a theme lost, and what else moved.

    check_regressions.py <base.json> <close.json> [--changed-from <worktree> [--base <sha>]]

Both files are the audit engine's own JSON reports (``engine.py --out-dir``), not audit reports. ``base`` was taken
on the theme worktree before the theme's first change, ``close`` at theme close. The tool reads both and writes
nothing.

Checks are matched by id. A check in the report's ``not_applicable`` list has the verdict ``NOT_APPLICABLE``; a check
in neither list is missing. Each check gets one class:

- ``lost_pass``: ``PASS`` at base and anything else at close (``PARTIAL``, ``FAIL``, ``UNKNOWN``, ``NOT_APPLICABLE``
  or missing). It stops the theme.
- ``regressed``: ``PARTIAL`` at base and ``FAIL`` at close. It stops the theme too.
- ``improved``: a move up along ``FAIL < PARTIAL < PASS``.
- ``changed``: any other verdict move, for example ``UNKNOWN`` to ``FAIL``.
- ``added``: missing at base, present at close. ``removed``: present at base (not as ``PASS``), missing at close.
- ``evidence``: the same verdict on both sides, but the evidence differs.
- ``unchanged``: the same verdict and the same evidence. These checks are counted, not listed.

The evidence of a check is its ``summary``, its ``data`` payload and the engine findings raised for it, as in
``dev/docindex/evidence.py``. A changed part is named ``summary``, ``data.<key>`` (``data`` when it is not an
object) or ``finding <id> added``, ``removed`` or ``changed``. Every listed row carries the parts that changed.

The tool refuses (exit 2) to compare two reports when a move could not be laid on the theme: the reports differ in
``provenance.ruleset_hash``, ``target``, ``phase``, ``user_config.read_allowed``, ``probes_enabled`` or, with probes
on, the verbs the ``--allow-probe`` list let through; or the close report is not newer than the base report
(``scanned_at``). Each difference is one line of ``data.errors``.

``data.status`` is ``lost`` when at least one check is ``lost_pass`` or ``regressed``, and ``clean`` otherwise. The
tool exits 0 in both cases; the status carries the answer. It judges nothing else: the owner decides what a stop
means.

With ``--changed-from <worktree>`` every listed row is also laid against the paths the theme changed. The paths come
from read-only git in the worktree: ``git diff --name-only`` from ``--base`` (by default the base report's
``git_sha``) to the working tree, plus the untracked files git does not ignore. The worktree must be the reports'
target. Each row gets ``reads_hit``: the places of the check's read declaration (the engine's
``audit.rules.reads``, loaded through ``engine.py``) that a changed path meets, with the paths, and ``via`` when an
upstream step reads the place for the check. A row no changed path explains has ``unattributed: true``: report
only, never a stop, and a possible gap in the declaration for the framework to look at. ``declared`` is false for a
check with no declaration; ``named_by_text`` is true when the check also reads paths the target's text names,
which no place lists.

A place matches a path as the consistency map's schema states the scopes: ``root`` the exact path from the root;
``any-depth`` the base name in any folder; ``repository-level`` the base name at the root or directly in
``.github/``, ``.gitlab/`` or ``docs/``; ``glob`` a glob from the root, where ``*``, ``?`` and ``[...]`` stay inside
one folder and ``**`` matches any number of folders, none included (so ``docs/**/*.md`` matches ``docs/a.md``). A
place with case ``fold`` is matched in lower case.
"""

from __future__ import annotations

import fnmatch
import importlib
import json
import posixpath
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import _audit_tools_path  # noqa: F401  (puts audit/tools on sys.path in a checkout)
import _common
import engine
import validate_report

INFO = _common.ToolInfo(
    name="check_regressions",
    summary="Compare two engine reports of one theme worktree: lost passes, regressions, other moves and evidence changes.",
    synopsis=("check_regressions.py BASE CLOSE [--changed-from WORKTREE [--base SHA]]",),
    writes="nothing",
)

ENGINE_SCHEMA_VERSION = "2"
PASS = "PASS"
PARTIAL = "PARTIAL"
FAIL = "FAIL"
NOT_APPLICABLE = "NOT_APPLICABLE"
RANK = {FAIL: 0, PARTIAL: 1, PASS: 2}

#: The classes of a check, in the order the counts list them.
CLASSES = ("lost_pass", "regressed", "improved", "changed", "added", "removed", "evidence", "unchanged")
#: The classes that stop the theme.
STOPS = ("lost_pass", "regressed")
#: The verdict moves that are reported, never a stop.
MOVES = ("improved", "changed", "added", "removed")

#: The engine's refusal for a verb outside ``--allow-probe`` ends with this text (``audit.probes.eligible``).
ALLOW_REFUSAL = "not in --allow-probe list"


@dataclass(frozen=True)
class CheckEvidence:
    """One check of one engine report: its verdict and its evidence (summary, data, findings by id)."""

    verdict: str
    summary: Any
    data: Any
    findings: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class Row:
    """One check compared: its class, its verdict on each side (``None`` when missing) and the changed evidence."""

    check: str
    kind: str
    base: str | None
    close: str | None
    evidence: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "class": self.kind,
            "base": self.base,
            "close": self.close,
            "evidence": list(self.evidence),
        }


# --- Reading an engine report ---------------------------------------------------------------------------


def _shape_problems(report: Any) -> list[str]:
    """What the comparison needs from an engine report and does not find, as one line each."""
    if not isinstance(report, dict):
        return ["the top level must be an object"]
    problems: list[str] = []
    if report.get("schema_version") != ENGINE_SCHEMA_VERSION:
        problems.append(f"/schema_version: expected {ENGINE_SCHEMA_VERSION!r}, found {report.get('schema_version')!r}")
    provenance = report.get("provenance")
    if not isinstance(provenance, dict):
        problems.append("/provenance: must be an object")
    else:
        for key in ("ruleset_hash", "target", "scanned_at"):
            if not isinstance(provenance.get(key), str):
                problems.append(f"/provenance/{key}: must be a string")
        if isinstance(provenance.get("scanned_at"), str) and scan_time(provenance["scanned_at"]) is None:
            problems.append("/provenance/scanned_at: must be an ISO 8601 time with a UTC offset")
        if not isinstance(provenance.get("phase"), int):
            problems.append("/provenance/phase: must be an integer")
        if not isinstance(provenance.get("probes_enabled"), bool):
            problems.append("/provenance/probes_enabled: must be a boolean")
        user_config = provenance.get("user_config")
        if not isinstance(user_config, dict) or not isinstance(user_config.get("read_allowed"), bool):
            problems.append("/provenance/user_config/read_allowed: must be a boolean")
    checks = report.get("checks")
    if not isinstance(checks, list):
        problems.append("/checks: must be a list")
    else:
        seen: set[str] = set()
        for index, check in enumerate(checks):
            if not isinstance(check, dict) or not isinstance(check.get("id"), str):
                problems.append(f"/checks/{index}: must be an object with a string id")
            elif not isinstance(check.get("verdict"), str):
                problems.append(f"/checks/{index}/verdict: must be a string")
            elif check["id"] in seen:
                problems.append(f"/checks/{index}: check {check['id']} is listed twice")
            else:
                seen.add(check["id"])
    findings = report.get("findings")
    if not isinstance(findings, list):
        problems.append("/findings: must be a list")
    else:
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict) or not isinstance(finding.get("check"), str):
                problems.append(f"/findings/{index}: must be an object with a string check")
    not_applicable = report.get("not_applicable")
    if not isinstance(not_applicable, list) or not all(isinstance(item, str) for item in not_applicable):
        problems.append("/not_applicable: must be a list of check ids")
    probes = report.get("probes")
    if not isinstance(probes, list) or not all(
        isinstance(probe, dict) and isinstance(probe.get("verb"), str) for probe in probes
    ):
        problems.append("/probes: must be a list of objects with a string verb")
    return problems


def scan_time(text: str) -> datetime | None:
    """`scanned_at` as an aware time, or None when it is not ISO 8601 with a UTC offset."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.utcoffset() is not None else None


def read_engine_report(path: str, which: str) -> dict[str, Any]:
    """The parsed engine report at `path`. A missing file is a `UsageError`, a wrong shape `ValidationFailed`."""
    document = validate_report.read_report(Path(path).expanduser(), f"{which} engine report")
    problems = _shape_problems(document)
    if problems:
        count = len(problems)
        raise _common.ValidationFailed(
            f"the {which} file is not an engine report: {count} error{'' if count == 1 else 's'}",
            errors=[f"{which}: {problem}" for problem in problems],
        )
    report: dict[str, Any] = document
    return report


# --- Refusals ------------------------------------------------------------------------------------------


def allowed_verbs(report: Mapping[str, Any]) -> list[str] | None:
    """The probe verbs the ``--allow-probe`` list let through, sorted; ``None`` when probes were off."""
    if not report["provenance"]["probes_enabled"]:
        return None
    return sorted(
        {
            probe["verb"]
            for probe in report["probes"]
            if not str(probe.get("refused_reason") or "").endswith(ALLOW_REFUSAL)
        }
    )


def settings(report: Mapping[str, Any]) -> dict[str, Any]:
    """The run settings that must be equal on both sides, by name."""
    provenance = report["provenance"]
    return {
        "ruleset_hash": provenance["ruleset_hash"],
        "target": provenance["target"],
        "phase": provenance["phase"],
        "user_config.read_allowed": provenance["user_config"]["read_allowed"],
        "probes_enabled": provenance["probes_enabled"],
        "allowed probe verbs": allowed_verbs(report),
    }


def refusals(base: Mapping[str, Any], close: Mapping[str, Any]) -> list[str]:
    """Why the two reports cannot be compared, one line each; empty when they can."""
    old, new = settings(base), settings(close)
    problems = [
        f"{name} differs: base {json.dumps(old[name])}, close {json.dumps(new[name])}"
        for name in old
        if old[name] != new[name]
    ]
    base_at, close_at = base["provenance"]["scanned_at"], close["provenance"]["scanned_at"]
    base_time, close_time = scan_time(base_at), scan_time(close_at)
    if base_time is None or close_time is None or close_time <= base_time:
        problems.append(f"the close report is not newer than the base report: base {base_at}, close {close_at}")
    return problems


# --- The comparison -------------------------------------------------------------------------------------


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def checks_of(report: Mapping[str, Any]) -> dict[str, CheckEvidence]:
    """Each check of an engine report by id, with its findings; a ``not_applicable`` id has no evidence."""
    findings: dict[str, dict[str, list[str]]] = {}
    for finding in report["findings"]:
        fid = str(finding.get("id", finding["check"]))
        body = {key: value for key, value in finding.items() if key != "id"}
        findings.setdefault(finding["check"], {}).setdefault(fid, []).append(_canonical(body))
    checks: dict[str, CheckEvidence] = {}
    for check in report["checks"]:
        cid = check["id"]
        checks[cid] = CheckEvidence(
            verdict=check["verdict"],
            summary=check.get("summary"),
            data=check.get("data"),
            findings={fid: tuple(sorted(bodies)) for fid, bodies in findings.get(cid, {}).items()},
        )
    for cid in report["not_applicable"]:
        checks.setdefault(cid, CheckEvidence(verdict=NOT_APPLICABLE, summary=None, data=None, findings={}))
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


def classify(base: str | None, close: str | None, evidence: Sequence[str]) -> str:
    """The class of one check from its verdict on each side (``None`` when missing) and its changed evidence."""
    if base == PASS and close != PASS:
        return "lost_pass"
    if base == PARTIAL and close == FAIL:
        return "regressed"
    if base is None:
        return "added"
    if close is None:
        return "removed"
    if base != close:
        if base in RANK and close in RANK and RANK[close] > RANK[base]:
            return "improved"
        return "changed"
    return "evidence" if evidence else "unchanged"


def compare(base: Mapping[str, Any], close: Mapping[str, Any]) -> list[Row]:
    """Every check of either report, by id, with its class. Assumes :func:`refusals` found nothing."""
    old, new = checks_of(base), checks_of(close)
    rows: list[Row] = []
    for cid in sorted(set(old) | set(new)):
        before, after = old.get(cid), new.get(cid)
        parts = evidence_changes(before, after) if before is not None and after is not None else ()
        verdicts = (before.verdict if before else None, after.verdict if after else None)
        rows.append(Row(cid, classify(*verdicts, parts), *verdicts, parts))
    return rows


# --- Read attribution ----------------------------------------------------------------------------------

ROOT_SCOPE = "root"
ANY_DEPTH = "any-depth"
REPOSITORY_LEVEL = "repository-level"
GLOB = "glob"
#: The folders a ``repository-level`` place may sit in, besides the root (the consistency map schema).
REPOSITORY_LEVEL_FOLDERS = ("", ".github", ".gitlab", "docs")
FOLD = "fold"
#: How many changed paths one hit place lists; the rest are counted.
PATHS_PER_PLACE = 5
COMMIT_TAIL = "^{commit}"


@dataclass(frozen=True)
class Place:
    """One place a check reads, as plain data: a path or pattern, its scope, the upstream step and the case rule."""

    path: str
    scope: str
    via: str | None = None
    case: str = "exact"


@dataclass(frozen=True)
class Declaration:
    """What one check reads: its places, and whether it also reads paths that the target's own text names."""

    places: tuple[Place, ...]
    named_by_text: bool = False


def glob_matches(pattern: str, path: str) -> bool:
    """Whether a path from the root matches a glob from the root, folder by folder.

    ``*``, ``?`` and ``[...]`` match inside one folder name; a ``**`` folder matches any number of folders, none
    included, so ``**/AGENTS.md`` matches ``AGENTS.md`` and ``docs/**/*.md`` matches ``docs/a.md``.
    """
    parts, names = pattern.split("/"), path.split("/")

    @lru_cache(maxsize=None)
    def match(i: int, j: int) -> bool:
        if i == len(parts):
            return j == len(names)
        if parts[i] == "**":
            return match(i + 1, j) or (j < len(names) and match(i, j + 1))
        return j < len(names) and fnmatch.fnmatchcase(names[j], parts[i]) and match(i + 1, j + 1)

    return match(0, 0)


def place_matches(place: Place, path: str) -> bool:
    """Whether a changed path, from the worktree's root, is one the place covers, as its scope says."""
    pattern = place.path
    if place.case == FOLD:
        pattern, path = pattern.lower(), path.lower()
    if place.scope in (ROOT_SCOPE, GLOB):
        return glob_matches(pattern, path)
    named = fnmatch.fnmatchcase(posixpath.basename(path), pattern)
    if place.scope == REPOSITORY_LEVEL:
        return named and posixpath.dirname(path) in REPOSITORY_LEVEL_FOLDERS
    return named  # any-depth


def hits(declaration: Declaration, changed: Sequence[str]) -> list[dict[str, Any]]:
    """Each place of the declaration that at least one changed path meets, in declaration order, with the paths."""
    out: list[dict[str, Any]] = []
    for place in dict.fromkeys(declaration.places):
        paths = [path for path in changed if place_matches(place, path)]
        if not paths:
            continue
        hit: dict[str, Any] = {"place": place.path, "scope": place.scope}
        if place.via:
            hit["via"] = place.via
        hit["paths"] = paths[:PATHS_PER_PLACE]
        if len(paths) > PATHS_PER_PLACE:
            hit["paths_omitted"] = len(paths) - PATHS_PER_PLACE
        out.append(hit)
    return out


def attribute(row: Row, declarations: Mapping[str, Declaration], changed: Sequence[str]) -> dict[str, Any]:
    """A listed row with the read places the changed paths hit; ``unattributed`` when none is hit."""
    declaration = declarations.get(row.check)
    found = hits(declaration, changed) if declaration is not None else []
    return {
        **row.to_json(),
        "declared": declaration is not None,
        "named_by_text": bool(declaration and declaration.named_by_text),
        "reads_hit": found,
        "unattributed": not found,
    }


@lru_cache(maxsize=1)
def load_declarations() -> tuple[dict[str, Declaration], str]:
    """The engine's read declarations as plain data, by check id, and the engine's ruleset hash.

    They come from the engine's own ``audit.rules.reads``, loaded through ``engine.py`` as ``validate_report`` loads
    the credential patterns, so they are never copied here.
    """
    engine.load_engine()
    reads = importlib.import_module("audit.rules.reads")
    registry = importlib.import_module("audit.rules.registry")
    declarations = {
        check_id: Declaration(
            places=tuple(Place(item.path, item.scope, item.via, item.case) for item in entry.where),
            named_by_text=bool(entry.named_by_text),
        )
        for check_id, entry in reads.READS.items()
    }
    return declarations, str(registry.ruleset_hash())


def revision(worktree: Path, name: str) -> str | None:
    done = validate_report.git_output(worktree, ["rev-parse", "--verify", "--quiet", name + COMMIT_TAIL])
    if done is None or done.returncode != 0:
        return None
    return done.stdout.strip() or None


def changed_paths(worktree: Path, base_sha: str) -> list[str]:
    """The paths the worktree changed since `base_sha`: tracked changes to the working tree and untracked files."""
    diff = validate_report.git_output(worktree, ["diff", "--name-only", "-z", "--no-renames", base_sha, "--"])
    untracked = validate_report.git_output(worktree, ["ls-files", "-z", "--others", "--exclude-standard"])
    if diff is None or diff.returncode != 0 or untracked is None or untracked.returncode != 0:
        raise _common.UsageError(f"git could not list the paths changed in {worktree} since {base_sha}")
    return sorted({name for name in (diff.stdout + "\0" + untracked.stdout).split("\0") if name})


def theme_changes(
    worktree_arg: str, base_arg: str | None, base: Mapping[str, Any], close: Mapping[str, Any]
) -> tuple[str, list[str]]:
    """The base commit, resolved, and the changed paths of the theme worktree; refuse a worktree that is not the target."""
    worktree = _common.resolve_target(worktree_arg)
    target = Path(close["provenance"]["target"]).expanduser().resolve()
    if worktree != target:
        raise _common.UsageError(f"--changed-from {worktree} is not the reports' target {target}")
    wanted = base_arg or base["provenance"].get("git_sha")
    if not isinstance(wanted, str) or not wanted:
        raise _common.UsageError("the base report records no git_sha; give the base commit with --base")
    resolved = revision(worktree, wanted)
    if resolved is None:
        raise _common.UsageError(f"the base commit {wanted} is not in the history of {worktree}")
    return resolved, changed_paths(worktree, resolved)


# --- The command ---------------------------------------------------------------------------------------


def side(path: str, report: Mapping[str, Any]) -> dict[str, Any]:
    provenance = report["provenance"]
    return {
        "report": Path(path).name,
        "git_sha": provenance.get("git_sha"),
        "git_dirty": provenance.get("git_dirty"),
        "scanned_at": provenance["scanned_at"],
        "engine_version": provenance.get("version"),
    }


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="check_regressions.py", description=INFO.summary)
    parser.add_argument("base", help="the engine report taken before the theme's first change (JSON)")
    parser.add_argument("close", help="the engine report taken at theme close (JSON)")
    parser.add_argument(
        "--changed-from", metavar="WORKTREE", help="the theme worktree: lay each listed check on the paths it changed"
    )
    parser.add_argument(
        "--base",
        dest="base_sha",
        metavar="SHA",
        help="the commit the theme started from (default: the base report's git_sha)",
    )
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    if args.base_sha is not None and args.changed_from is None:
        raise _common.UsageError("--base needs --changed-from")
    base = read_engine_report(args.base, "base")
    close = read_engine_report(args.close, "close")
    problems = refusals(base, close)
    if problems:
        count = len(problems)
        raise _common.ValidationFailed(
            f"refused: {count} reason{'' if count == 1 else 's'} the two reports are not one theme's base and close, "
            "so a move cannot be laid on the theme",
            errors=problems,
        )
    rows = compare(base, close)
    counts = {kind: sum(1 for row in rows if row.kind == kind) for kind in CLASSES}
    status = "lost" if any(counts[kind] for kind in STOPS) else "clean"
    budget = _common.ITEM_BUDGET_BYTES // 4
    data: dict[str, Any] = {
        "status": status,
        "base": side(args.base, base),
        "close": side(args.close, close),
        "counts": counts,
    }
    warnings: list[str] = []
    omitted: dict[str, int] = {}
    listed = [row for row in rows if row.kind in (*STOPS, *MOVES, "evidence")]
    shown: dict[str, dict[str, Any]] = {row.check: row.to_json() for row in listed}
    if args.changed_from is not None:
        base_sha, changed = theme_changes(args.changed_from, args.base_sha, base, close)
        declarations, engine_hash = load_declarations()
        shown = {row.check: attribute(row, declarations, changed) for row in listed}
        kept_paths, omitted_paths = _common.bound_items(changed, limit_bytes=budget)
        unattributed = sum(1 for row in shown.values() if row["unattributed"])
        data["changes"] = {
            "base_sha": base_sha,
            "changed_count": len(changed),
            "changed_paths": kept_paths,
            "unattributed": unattributed,
        }
        if omitted_paths:
            omitted["changed_paths"] = omitted_paths
        if engine_hash != base["provenance"]["ruleset_hash"]:
            warnings.append(
                f"the engine here has ruleset hash {engine_hash} and the reports {base['provenance']['ruleset_hash']}: "
                "the read declarations may not be the ones the reports' checks used"
            )
        if unattributed:
            warnings.append(
                f"{unattributed} listed check{'' if unattributed == 1 else 's'} moved with no declared read hit by a "
                "changed path: report only, and a possible gap in the read declarations"
            )
    for name, kinds in (("stops", STOPS), ("moves", MOVES), ("evidence_changes", ("evidence",))):
        kept, left_out = _common.bound_items(
            [shown[row.check] for row in listed if row.kind in kinds], limit_bytes=budget
        )
        data[name] = kept
        if left_out:
            omitted[name] = left_out
    if omitted:
        data["omitted"] = omitted
    if base["provenance"].get("version") != close["provenance"].get("version"):
        warnings.append(
            f"the engine versions differ (base {base['provenance'].get('version')}, close "
            f"{close['provenance'].get('version')}); the ruleset hash is the same, so the checks are the same"
        )
    if close["provenance"].get("git_dirty"):
        warnings.append("the close report was taken on a working tree with uncommitted changes")
    stops = counts["lost_pass"] + counts["regressed"]
    summary = (
        f"check_regressions: {status}; {counts['lost_pass']} lost pass, {counts['regressed']} regressed, "
        f"{sum(counts[kind] for kind in MOVES)} other verdict moves, {counts['evidence']} evidence changes"
    )
    if "changes" in data:
        summary += f", {data['changes']['unattributed']} unattributed"
    if stops:
        summary += "; stop the theme and ask the owner"
    return _common.Result(data=data, summary=summary, warnings=warnings, truncated=bool(omitted))


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
