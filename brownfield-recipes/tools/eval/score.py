# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Score a headless audit report against its ground truth (DP §11, review R-07).

    score.py <report> <expected> [--target <repo>]

``<expected>`` matches ``schema/eval-expected.schema.json``: one entry per check the corpus has ground truth
for, each with the verdict(s) that count as right. The report's own ``provenance.target.label``/``git_sha``
must match ``expected.repo_label``/``repo_sha``; a run against a different commit is not comparable, so a
mismatch is recorded rather than silently scored (the expected-results schema's own description) and every
metric that depends on the comparison comes back ``null``.

Metrics, each against the expected file:

- ``schema_valid``: whether ``<report>`` parses and validates against ``audit-report.schema.json``.
- ``blocker_recall``: of the expected checks that are ground-truth blockers (catalogue severity ``BLOCKER``,
  ``"PASS"`` not an acceptable verdict), the share the report also reports as an open blocker
  (``_summary.open_blockers``, the same predicate the report's own summary counts).
- ``false_positive_candidates``: expected checks whose only acceptable verdict is ``PASS`` but whose report
  verdict is not — candidates for the run having flagged something that was not actually wrong.
- ``override_precision``: of the report's checks that carry ``override_reason`` and that the expected file
  has ground truth for, the share whose resulting verdict is acceptable.
- ``evidence_validity``: with ``--target`` only — of the report's ``kind: file`` evidence citations, the
  share whose path exists in the target at the recorded commit, and whose ``lines`` (when given) fit the
  file.

Standard library only.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common
import _summary
import validate_report

INFO = _common.ToolInfo(
    name="score",
    summary="Score a headless audit report against its expected-results ground truth.",
    synopsis=("score.py <report> <expected> [--target <repo>]",),
    writes="nothing",
)


# --- Loading --------------------------------------------------------------------------------------------


def read_json(path: Path, what: str) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _common.UsageError(f"cannot read the {what} {path}: {exc.strerror or exc}") from None
    return validate_report.parse_report(text, what)


def catalogue_severities() -> dict[str, str]:
    """Each catalogue check id's severity."""
    return {check["id"]: check["severity"] for check in validate_report.load_catalogue()["checks"]}


def expected_by_id(expected: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {entry["id"]: entry for entry in expected["checks"]}


def report_verdicts(report: Mapping[str, Any]) -> dict[str, str]:
    return {check["id"]: check["verdict"] for check in report["checks"]}


# --- Matching the report to its ground truth -------------------------------------------------------------


@dataclass
class Match:
    """Whether `report` and `expected` describe the same run, and why not when they do not."""

    comparable: bool
    reason: str = ""


def match_target(report: Mapping[str, Any], expected: Mapping[str, Any]) -> Match:
    target = report["provenance"]["target"]
    report_sha = target["git_sha"]
    expected_sha = expected["repo_sha"]
    if report_sha != expected_sha:
        got = report_sha[:12] if report_sha else "none"
        return Match(False, f"the report's commit ({got}) does not match the expected file's ({expected_sha[:12]})")
    if target["label"] != expected["repo_label"]:
        return Match(
            False,
            f"the report's repo_label ({target['label']!r}) does not match the expected file's "
            f"({expected['repo_label']!r})",
        )
    return Match(True)


# --- blocker_recall ---------------------------------------------------------------------------------------


def expected_blockers(expected: Mapping[str, Any], severities: Mapping[str, str]) -> list[str]:
    """Expected-check ids that are ground-truth blockers: catalogue severity BLOCKER, PASS not acceptable."""
    return [
        entry["id"]
        for entry in expected["checks"]
        if severities.get(entry["id"]) == "BLOCKER" and "PASS" not in entry["acceptable_verdicts"]
    ]


def blocker_recall(
    report: Mapping[str, Any], expected: Mapping[str, Any], severities: Mapping[str, str]
) -> dict[str, Any]:
    wanted = expected_blockers(expected, severities)
    reported = {check["id"] for check in _summary.open_blockers(report["checks"])}
    matched = [check_id for check_id in wanted if check_id in reported]
    missed = [check_id for check_id in wanted if check_id not in reported]
    return {
        "ratio": round(len(matched) / len(wanted), 4) if wanted else None,
        "expected_total": len(wanted),
        "matched": matched,
        "missed": missed,
    }


# --- false_positive_candidates -----------------------------------------------------------------------------


def false_positive_candidates(report: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    """Expected-PASS-only checks the report did not verdict PASS: candidates for a wrongly flagged check."""
    verdicts = report_verdicts(report)
    should_pass = [entry["id"] for entry in expected["checks"] if entry["acceptable_verdicts"] == ["PASS"]]
    flagged = [check_id for check_id in should_pass if verdicts.get(check_id) != "PASS"]
    return {
        "rate": round(len(flagged) / len(should_pass), 4) if should_pass else None,
        "expected_total": len(should_pass),
        "ids": flagged,
    }


# --- override_precision --------------------------------------------------------------------------------------


def override_precision(report: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    """Of the report's overridden checks the expected file has ground truth for, the share landing acceptably."""
    by_id = expected_by_id(expected)
    overridden = [check for check in report["checks"] if check.get("override_reason") and check["id"] in by_id]
    correct = [check["id"] for check in overridden if check["verdict"] in by_id[check["id"]]["acceptable_verdicts"]]
    incorrect = [check["id"] for check in overridden if check["id"] not in correct]
    return {
        "ratio": round(len(correct) / len(overridden), 4) if overridden else None,
        "overridden_total": len(overridden),
        "correct": correct,
        "incorrect": incorrect,
    }


# --- Putting it together -----------------------------------------------------------------------------------


def score(report: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    outcome = validate_report.validate_document(report)
    schema_valid = outcome.stage != "schema"
    data: dict[str, Any] = {
        "repo_label": expected["repo_label"],
        "schema_valid": schema_valid,
    }
    if not schema_valid:
        kept, omitted = _common.bound_items(outcome.errors, limit_bytes=_common.ITEM_BUDGET_BYTES // 2)
        data["schema_errors"] = kept
        if omitted:
            data["schema_errors_omitted"] = omitted
        data["comparable"] = False
        data["comparable_reason"] = "the report is not schema-valid; ground-truth metrics are not computed"
        return data

    match = match_target(report, expected)
    data["comparable"] = match.comparable
    if not match.comparable:
        data["comparable_reason"] = match.reason
        return data

    severities = catalogue_severities()
    data["metrics"] = {
        "blocker_recall": blocker_recall(report, expected, severities),
        "false_positive_candidates": false_positive_candidates(report, expected),
        "override_precision": override_precision(report, expected),
    }
    return data


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="score.py", description=INFO.summary)
    parser.add_argument("report", help="the audit report to score")
    parser.add_argument("expected", help="the expected-results file to score it against")
    parser.add_argument("--target", help="the audited repository, for the evidence_validity metric")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    report = read_json(Path(args.report).expanduser(), "report")
    expected = read_json(Path(args.expected).expanduser(), "expected-results file")
    data = score(report, expected)
    comparable = data.get("comparable")
    if not data["schema_valid"]:
        summary = "score: the report is not schema-valid"
    elif comparable is False:
        summary = f"score: not comparable ({data['comparable_reason']})"
    else:
        metrics = data["metrics"]
        summary = (
            f"score: blocker_recall={metrics['blocker_recall']['ratio']} "
            f"false_positive_rate={metrics['false_positive_candidates']['rate']} "
            f"override_precision={metrics['override_precision']['ratio']}"
        )
    return _common.Result(data=data, summary=summary)


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
