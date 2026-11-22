# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The `import-engine` helpers of `report.py`: check an engine report against the draft's target and bring its results
into the draft, once. `report.py` re-exports every name.
"""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import _common
import _engine_adapter as adapter
import _summary
import engine as engine_launcher
import validate_report as vr
from _report_checks import check_counts, recorded_checks
from _report_draft import Change, in_schema_order, report_schema, same_commit
from _report_findings import finding_counts, initial_decision, next_finding_id


def resolved_path(text: str) -> Path:
    """A path as text, resolved without requiring it to exist, so that two spellings of one place compare equal."""
    return Path(text).expanduser().resolve()


def agree_with_target(document: Mapping[str, Any], conversion: adapter.Conversion) -> list[str]:
    """Refuse an engine report of another repository or of another commit, and warn when only one side knows the commit.

    The draft's target facts were captured by `init` from the directory itself, so they are kept. The engine's evidence
    is checked against the draft's commit, so a scan of a different commit would be checked against the wrong files.
    """
    target = document["provenance"]["target"]
    problems: list[str] = []
    if resolved_path(target["path"]) != resolved_path(conversion.target_path):
        problems.append(
            f"the engine scanned {conversion.target_path}, and the draft's target is {target['path']}; "
            "import a report of the draft's own repository"
        )
    recorded, scanned = target["git_sha"], conversion.git_sha
    if recorded is not None and scanned is not None and not same_commit(recorded, scanned):
        problems.append(
            f"the engine scanned commit {scanned}, and the draft recorded commit {recorded}; scan again, or start a "
            "new draft with init"
        )
    if problems:
        raise _common.ValidationFailed("the engine report is not of this draft's target", errors=problems)
    if (recorded is None) != (scanned is None):
        known, other = ("the engine", "the draft") if recorded is None else ("the draft", "the engine")
        return [f"only {known} knows the target's commit, so {other}'s cannot be compared"]
    return []


@lru_cache(maxsize=1)
def engine_meanings() -> dict[str, str]:
    """The engine's own words for each unattested item. They come from the engine and are never copied here (ADR 0001)."""
    engine_launcher.load_engine()
    presentation = importlib.import_module("audit.report.presentation")
    return dict(presentation.UNATTESTED_MEANINGS)


def score_differences(document: Mapping[str, Any], conversion: adapter.Conversion) -> list[str]:
    """Say so when the engine's phase-1 score and the report's differ. The report's is the spec's, and is the one kept."""
    ours = _summary.compute_summary(document)["phase1_score"]
    theirs = conversion.engine_score
    if theirs is None or round(theirs, _summary.SCORE_PLACES) == ours:
        return []
    return [
        f"the engine's phase-1 score is {theirs} and the report's is {ours}; the report's follows "
        "spec/readiness-summary.md and is the one kept"
    ]


def apply_import(document: dict[str, Any], engine: Any) -> tuple[Change, list[str]]:
    """Bring the engine's results into the draft, once. A draft that already holds an engine report is refused.

    The engine's checks are added after any the agent has recorded, in the engine's order. Its findings follow the
    run's policy as `add-finding` does. The draft's own target facts are kept.
    """
    if "engine" in document["provenance"]:
        held = document["provenance"]["engine"]
        raise _common.ValidationFailed(
            f"this draft already holds an engine report (ruleset {held['ruleset_hash']})",
            errors=[
                "a second import would replace the first one's checks and the decisions made on them; "
                "start a new draft with init to audit again"
            ],
        )
    conversion = adapter.convert(
        engine,
        catalogue=vr.load_catalogue(),
        taken_keys=[finding["key"] for finding in document["findings"]],
        meanings=engine_meanings(),
    )
    warnings = agree_with_target(document, conversion)
    recorded = recorded_checks(document)
    repeated = [check["id"] for check in conversion.checks if check["id"] in recorded]
    if repeated:
        raise _common.ValidationFailed(
            f"the draft already records {', '.join(repeated)}",
            errors=[f"{name} is already in the draft" for name in repeated],
        )
    provenance = document["provenance"]
    names = list(report_schema()["properties"]["provenance"]["properties"])
    provenance["engine"] = conversion.engine
    document["provenance"] = {name: provenance[name] for name in names if name in provenance}
    first_check, first_finding = len(document["checks"]), len(document["findings"])
    for check in conversion.checks:
        document["checks"].append(in_schema_order(check, "check"))
    for found in conversion.findings:
        finding = {"id": next_finding_id(document["findings"]), **found, **initial_decision(document)}
        document["findings"].append(in_schema_order(finding, "finding"))
    document["unattested"].extend(conversion.unattested)
    document["stack"] = conversion.stack
    document["components"] = conversion.components
    document["coverage"]["inventory"] = conversion.inventory
    warnings += score_differences(document, conversion)
    verdicts: dict[str, int] = {}
    for check in conversion.checks:
        verdicts[check["verdict"]] = verdicts.get(check["verdict"], 0) + 1
    data = {
        "engine": conversion.engine,
        "checks_imported": len(conversion.checks),
        "by_verdict": dict(sorted(verdicts.items())),
        "findings_imported": len(conversion.findings),
        "unattested_listed": len(conversion.unattested),
        "probes_carried": conversion.probes_carried,
        "evidence_not_carried": conversion.evidence_not_carried,
        **check_counts(document),
        **finding_counts(document),
    }
    touched = [f"/checks/{n}/" for n in range(first_check, len(document["checks"]))]
    touched += [f"/findings/{n}/" for n in range(first_finding, len(document["findings"]))]
    return Change(data=data, touched=touched), warnings + conversion.warnings
