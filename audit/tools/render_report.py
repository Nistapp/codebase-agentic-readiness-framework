# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Render an audit report to Markdown. The Markdown is a pure function of the JSON report.

    render_report.py <report> --out <md>

``render`` takes a report and returns text. It reads nothing but the report, writes nothing, and never looks at a
clock, so one report always gives the same bytes, whatever order its keys come in. The readiness summary is computed
with ``_summary.py``, the code that the validator and the report builder use, and not taken from the file. Editorial
wording, such as what a verdict means, lives here and never in the JSON, so nothing in the Markdown is absent from the
JSON apart from that wording (``schema/SCHEMA.md``, "Summary").

The text of a report comes from a repository, through a model, so it is untrusted. Free text is written with
Markdown's special characters escaped, so that a statement cannot become a link, an image or a heading. A path or a
command sits in a code span and a quote in a fenced block, each with a delimiter longer than any run of backticks
inside it. Control characters, and the characters that reorder or hide text, are written out as ``{U+XXXX}``.

The command line reads a report, validates it with ``validate_report.validate_document``, and refuses one that is
not valid: the renderer reads fields that only a valid report guarantees. It writes the Markdown to ``--out`` as a
new file, never replaces one, and refuses a path inside the audited target. A draft renders too, with a banner that
says it is a draft.

Failure behaviour: a bad argument, a missing report, an ``--out`` that exists or has no folder, or one inside the
target is exit 1. A report that fails the schema or a rule, and a file that is not JSON, is exit 2 with the errors.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import _common
import _summary
import validate_report as vr
from _render_sections import (
    banners as banners,
    title_section as title_section,
    bottom_line_section as bottom_line_section,
    terms_section as terms_section,
    provenance_section as provenance_section,
    summary_section as summary_section,
    verdicts_section as verdicts_section,
    command_surface_section as command_surface_section,
    credential_total_section as credential_total_section,
    secret_shapes_section as secret_shapes_section,
    appendix_section as appendix_section,
    coverage_section as coverage_section,
    stack_section as stack_section,
    run_context_section as run_context_section,
)
from _render_attention import (
    attention_rows as attention_rows,
    attention_section as attention_section,
    overrides_section as overrides_section,
    evidence_in_full_section as evidence_in_full_section,
)
from _render_terms import (
    NO_EVIDENCE as NO_EVIDENCE,
    SEVERITIES as SEVERITIES,
    VERDICTS as VERDICTS,
    COMMIT_CHARS as COMMIT_CHARS,
    BR as BR,
    EVIDENCE_IN_CELL as EVIDENCE_IN_CELL,
    UNMET as UNMET,
    VERDICT_MEANINGS as VERDICT_MEANINGS,
    SEVERITY_MEANINGS as SEVERITY_MEANINGS,
    DISPOSITION_MEANINGS as DISPOSITION_MEANINGS,
    FIRST_ACTIONS as FIRST_ACTIONS,
    UNKNOWN_LISTED as UNKNOWN_LISTED,
    EFFORT_ORDER as EFFORT_ORDER,
    DECIDED_BY as DECIDED_BY,
)
from _render_text import (
    _SPECIAL as _SPECIAL,
    _BLOCK_START as _BLOCK_START,
    _BACKTICKS as _BACKTICKS,
    clean as clean,
    flat as flat,
    text as text,
    prose as prose,
    delimiter as delimiter,
    code as code,
    fenced as fenced,
    cell as cell,
    ALIGNMENTS as ALIGNMENTS,
    table as table,
    blocks as blocks,
    count as count,
    joined as joined,
    yes_no as yes_no,
    score_text as score_text,
)
from _render_evidence import (
    captured as captured,
    evidence_lines as evidence_lines,
    search_text as search_text,
    evidence_item_text as evidence_item_text,
    capped as capped,
    evidence_cell as evidence_cell,
)
from _render_facts import (
    overridden as overridden,
    findings_of as findings_of,
    findings_cite_evidence as findings_cite_evidence,
    needs_attention as needs_attention,
    engine_text as engine_text,
    agent_text as agent_text,
    framework_text as framework_text,
    open_findings as open_findings,
    first_actions as first_actions,
    check_titles as check_titles,
    named_check as named_check,
    family_heading as family_heading,
    action_row as action_row,
    blocker_findings as blocker_findings,
    blockers_phrase as blockers_phrase,
    credit_text as credit_text,
    check_cell as check_cell,
    verdict_cell as verdict_cell,
    fix_cell as fix_cell,
    decision_cell as decision_cell,
    attention_sentence as attention_sentence,
    _RENDERED_PAYLOAD_KINDS as _RENDERED_PAYLOAD_KINDS,
    _and_join as _and_join,
    _payloads_note as _payloads_note,
)

INFO = _common.ToolInfo(
    name="render_report",
    summary="Render an audit report to Markdown. The Markdown is a pure function of the JSON report.",
    synopsis=("render_report.py <report> --out <md>",),
    writes=(
        "<md>, the path given by --out: a new file, never a replacement, and never inside the audited target. "
        "The report is only read."
    ),
)


def render(report: Mapping[str, Any]) -> str:
    """The Markdown for a valid report. It reads only `report`, changes nothing, and gives one text for one report."""
    summary = _summary.compute_summary(report)
    body = blocks(
        title_section(report),
        bottom_line_section(report, summary),
        provenance_section(report),
        summary_section(report, summary),
        verdicts_section(report),
        command_surface_section(report),
        credential_total_section(report),
        secret_shapes_section(report),
        attention_section(report),
        overrides_section(report),
        evidence_in_full_section(report),
        coverage_section(report),
        stack_section(report),
        run_context_section(report),
        appendix_section(report),
        terms_section(),
        ["---", "", "Rendered from the JSON report by `render_report.py`. The JSON report is the record."],
    )
    return "\n".join(body) + "\n"


# --- The command line ---------------------------------------------------------------------------------------------


def refuse_inside_target(report: Mapping[str, Any], out: Path) -> None:
    """The tools never write inside the repository they audit. The check needs the target to be on this machine."""
    named = Path(report["provenance"]["target"]["path"])
    if named.is_dir() and _common.is_within(named.resolve(), out.parent.resolve()):
        raise _common.PathNotAllowed(f"refusing to write inside the target: {out.parent.resolve()}")


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="render_report.py", description=INFO.summary)
    parser.add_argument("report", help="the audit report, draft or final, to render")
    parser.add_argument("--out", required=True, help="the Markdown file to create; it must not exist")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    source = Path(args.report).expanduser()
    document = vr.read_report(source)
    outcome = vr.validate_document(document)
    vr.refuse_unknown_schema(outcome)
    if outcome.errors:
        total = len(outcome.errors)
        raise _common.ValidationFailed(
            f"the report is not valid, so it was not rendered: {count(total, 'error')} in the {outcome.stage} stage",
            errors=outcome.errors,
        )
    out = Path(args.out).expanduser()
    if not out.parent.is_dir():
        raise _common.UsageError(f"the folder for --out does not exist: {out.parent}")
    refuse_inside_target(document, out)
    markdown = render(document)
    try:
        written = _common.create_file(out, markdown)
    except OSError as exc:
        raise _common.UsageError(f"cannot write {out}: {exc.strerror or exc}") from None
    kept, omitted = _common.bound_items(outcome.warnings)
    data: dict[str, Any] = {
        "markdown": str(written),
        "report": str(source),
        "status": document["status"],
        "lines": len(markdown.splitlines()),
        "bytes": len(markdown.encode("utf-8")),
    }
    if omitted:
        data["warnings_omitted"] = omitted
    return _common.Result(
        data=data,
        summary=f"render_report: wrote {written.name} ({data['lines']} lines)",
        warnings=kept,
        truncated=bool(omitted),
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
