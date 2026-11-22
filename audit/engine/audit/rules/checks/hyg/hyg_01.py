# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-01: README present and non-placeholder."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import root_readme
from audit.rules.checks.hyg._shared import _finding, _outcome

SPEC = declare("HYG-01", "README present and non-placeholder", "A", Severity.COSMETIC, scored=False)


#: A README below this many characters of trimmed text is present but not documentation.
MIN_README_CHARS = 200

#: Case-insensitive markers that make a README a stub rather than a description.
STUB_MARKERS = ("todo", "tbd", "placeholder", "lorem ipsum", "coming soon", "fill this in", "<describe")

#: Markers that are filler text wherever they stand, so they count anywhere in a README of any length.
FILLER_MARKERS = ("lorem ipsum", "<describe")

#: A README shorter than this many characters is short enough for any marker anywhere in it to make it a stub. The
#: floor is the one AGT-01 sets for an instruction file. In a longer README a word marker counts only when it opens a
#: line (issue #51): a substantive README that says "returns a placeholder answer" in a table row is not a stub.
STUB_MARKER_ANYWHERE_CHARS = 400

#: Markdown that can open a line before its text: indentation, a heading, a quote, a list item, a task box or a cell.
_LINE_MARKUP_RE = re.compile(r"^(?:[\s#>|*+-]|\d+[.)]\s|\[[ xX]\]\s)*")

#: The characters that may follow a marker that opens a line: the end of the line or punctuation, never a word.
_MARKER_END_RE = re.compile(r"[\s*_]*(?:$|[:.!,;()\[\]—–-])")


# ===========================================================================
# HYG-01 — README present and non-placeholder
# ===========================================================================


def _marker_line(text: str) -> tuple[int, str, str] | None:
    """The first line that carries a placeholder marker, as ``(line number, marker, line)``, or ``None``.

    In a README shorter than :data:`STUB_MARKER_ANYWHERE_CHARS` a marker anywhere counts, and a
    :data:`FILLER_MARKERS` marker counts anywhere in a README of any length. In a longer README a word marker
    must open the line, after any Markdown that starts it (``## TODO``, ``- TBD: install steps``,
    ``Coming soon.``), and be followed by the line's end or punctuation, so a word that merely starts with it
    does not count.
    """
    anywhere = len(text.strip()) < STUB_MARKER_ANYWHERE_CHARS
    for number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        for marker in STUB_MARKERS:
            if anywhere or marker in FILLER_MARKERS:
                if marker in lowered:
                    return number, marker, line.strip()
                continue
            lead = lowered[_LINE_MARKUP_RE.match(lowered).end() :]
            if lead.startswith(marker) and _MARKER_END_RE.match(lead, len(marker)):
                return number, marker, line.strip()
    return None


def _readme_reason(text: str) -> str | None:
    stripped = text.strip()
    if len(stripped) < MIN_README_CHARS:
        return f"only {len(stripped)} characters (minimum {MIN_README_CHARS})"
    found = _marker_line(text)
    if found is not None:
        number, marker, line = found
        shown = line if len(line) <= 80 else line[:77] + "..."
        return f"line {number} carries the placeholder marker {marker!r}: {shown}"
    body = [line.strip() for line in stripped.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not body:
        return "a title with no body"
    return None


def check_hyg01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    primary = root_readme(inventory)
    if primary is None:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no README at the repository root",
            [
                _finding(
                    spec,
                    Verdict.FAIL,
                    "orient itself in this project in seconds",
                    "no README exists at the repository root",
                    remediation="Add a root README that says what the project is, how to run it, "
                    "and how to contribute.",
                ),
            ],
        )

    text = inventory.read(primary)
    if text is None:
        return _outcome(spec, Verdict.UNKNOWN, f"{primary} present but not readable as text (binary or oversized)")

    reason = _readme_reason(text)
    if reason is None:
        return _outcome(spec, Verdict.PASS, f"{primary} present and non-placeholder")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"{primary} is a placeholder — {reason}",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "learn what this project is",
                f"{primary} exists but is a placeholder — {reason}",
                evidence=[Evidence(primary)],
                path=primary,
                remediation="Replace the stub with a description, a quick-start, and a link to the documentation.",
            ),
        ],
    )
