# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the CON family: constraints.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "con-01-names-existing-paths": {"CON-01": "PASS", "CON-02": "UNKNOWN"},
    "con-01-names-missing-paths": {"CON-01": "PARTIAL", "CON-02": "UNKNOWN"},
    "con-01-names-no-path": {"CON-01": "FAIL", "CON-02": "UNKNOWN"},
    "con-02-unprotected-tests": {"CON-01": "PASS", "CON-02": "FAIL"},
    "con-02-protected": {"CON-01": "PASS", "CON-02": "PASS"},
    "con-02-partly-protected": {"CON-02": "PARTIAL"},
    "con-02-no-test-directory": {"CON-02": "UNKNOWN"},
    "con-02-no-prohibitions-section": {"CON-01": "UNKNOWN", "CON-02": "UNKNOWN"},
    "con-02-specs-are-not-tests": {"CON-02": "PASS"},
    "con-03-artefacts-not-ignored": {"CON-03": "FAIL"},
}
