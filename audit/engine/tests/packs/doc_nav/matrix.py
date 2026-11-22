# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the DOC and NAV family: documentation and navigation.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "doc-01-empty": {"DOC-01": "PARTIAL"},
    "doc-02-no-style-guide": {"DOC-02": "FAIL"},
    "doc-02-ok-claude-md-fallback": {"DOC-02": "PASS"},
    "doc-03-tracked-artefacts": {"DOC-03": "FAIL"},
    "ignore-ok-nested-gitignore": {"DOC-03": "PASS", "CON-03": "PASS"},
    "doc-04-adr-unindexed": {"DOC-04": "PARTIAL"},
    "doc-04-adr-tombstone": {"DOC-04": "PARTIAL"},
    "doc-04-ok-parent-index": {"DOC-04": "PASS"},
    "doc-05-long-sentences": {"DOC-01": "PASS", "DOC-02": "PASS", "DOC-04": "PASS", "DOC-05": "FAIL"},
    "doc-nav-ok": {
        "DOC-01": "PASS",
        "DOC-02": "PASS",
        "DOC-03": "PASS",
        "DOC-04": "PASS",
        "DOC-05": "PASS",
        "NAV-01": "PASS",
        "NAV-02": "PASS",
        "NAV-03": "PASS",
    },
    "nav-01-no-manifest": {"NAV-01": "UNKNOWN"},
    "nav-01-nested-manifest-only": {"NAV-01": "UNKNOWN"},
    "nav-02-no-entry": {"NAV-02": "FAIL"},
    "nav-02-main-guard-only": {"NAV-02": "FAIL"},
    "nav-03-red-flags": {"NAV-03": "PARTIAL"},
    "nav-05-methods": {"NAV-05": "PARTIAL"},
}
