# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The words and limits of the rendered report: verdict meanings, severities and the counts that cap a section.

Private to ``render_report.py``; nothing here reads a report.
"""

from __future__ import annotations

NO_EVIDENCE = "We did not find any evidence."
SEVERITIES = ("BLOCKER", "DEGRADER", "COSMETIC")
VERDICTS = ("PASS", "PARTIAL", "FAIL", "UNKNOWN", "NOT_APPLICABLE")
COMMIT_CHARS = 12
BR = "<br>"
EVIDENCE_IN_CELL = 8
UNMET = ("PARTIAL", "FAIL", "UNKNOWN")

# What a verdict and a severity mean, in the report's own words. The JSON carries the words PASS and BLOCKER; the
# meaning is editorial and lives here.
VERDICT_MEANINGS = {
    "PASS": "The requirement is met.",
    "PARTIAL": "Part of the requirement is met.",
    "FAIL": "The requirement is not met.",
    "UNKNOWN": "The evidence could not be gathered. It is never read as a pass.",
    "NOT_APPLICABLE": "The check does not apply to this repository.",
}
SEVERITY_MEANINGS = {
    "BLOCKER": "Agent work is impossible, unsafe or unverifiable. Fix before onboarding agents.",
    "DEGRADER": "Agent work is possible but unreliable or wasteful.",
    "COSMETIC": "Hygiene. Fix when convenient.",
}
DISPOSITION_MEANINGS = {
    "pending": "No decision yet.",
    "confirmed": "The finding stands as written.",
    "edited": "The finding stands, with its wording or evidence corrected.",
    "rejected": "The finding is wrong (a false positive). It leaves the backlog.",
    "deferred": "The finding is real, and the person chose to leave it open for now.",
}
# The bottom line: how many first actions it names, and how many UNKNOWN check IDs it lists before "and N more".
FIRST_ACTIONS = 3
UNKNOWN_LISTED = 5
EFFORT_ORDER = {"S": 0, "M": 1, "L": 2}
DECIDED_BY = {
    "interactive": "Decided by the person, on this finding alone.",
    "batch": "Decided by the person, as one of a group of findings that are not blockers.",
    "policy": "Set by the confirmation policy, not by a person.",
}
