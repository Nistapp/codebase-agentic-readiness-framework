# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the CMD family: command surface.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "cmd-01-missing-verb": {"CMD-01": "FAIL"},
    "cmd-02-weak-check": {"CMD-02": "FAIL"},
    "cmd-03-divergent": {"CMD-03": "FAIL"},
    "cmd-04-write-in-check": {"CMD-04": "FAIL"},
    "cmd-ok-npm": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-ok-root-make-nested-template": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-ok-make": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-ok-make-prereqs": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-ok-make-alias": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-01-make-parse-error": {"CMD-01": "FAIL", "CMD-02": "UNKNOWN", "CMD-03": "UNKNOWN", "CMD-04": "UNKNOWN"},
    "cmd-01-nested-makefile-only": {"CMD-01": "UNKNOWN", "CMD-02": "UNKNOWN", "CMD-03": "UNKNOWN", "CMD-04": "UNKNOWN"},
    "cmd-01-nested-gradle-only": {"CMD-01": "UNKNOWN", "CMD-02": "UNKNOWN", "CMD-03": "UNKNOWN", "CMD-04": "UNKNOWN"},
    "cmd-01-nested-maven-only": {"CMD-01": "UNKNOWN", "CMD-02": "UNKNOWN", "CMD-03": "UNKNOWN", "CMD-04": "UNKNOWN"},
    "cmd-ok-pyproject-poe": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-ok-gradle": {"CMD-01": "PASS", "CMD-02": "PASS", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-ok-maven": {"CMD-01": "PASS", "CMD-02": "UNKNOWN", "CMD-03": "PASS", "CMD-04": "PASS"},
    "cmd-01-maven-no-formatter": {"CMD-01": "FAIL", "CMD-02": "UNKNOWN", "CMD-03": "PASS", "CMD-04": "PASS"},
}
