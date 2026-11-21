# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the CI family: continuous integration.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "ci-01-no-pr-trigger": {"CI-01": "PARTIAL"},
    "ci-01-nested-workflow-only": {"CI-01": "FAIL"},
    "ci-02-parity-break": {"CI-02": "FAIL"},
    "ci-03-ci-only-step": {"CI-03": "FAIL"},
    "ci-05-no-workflow-lint": {"CI-05": "FAIL"},
    "ci-05-ci-only-lint": {"CI-05": "PARTIAL"},
    "ci-ok-gh": {"CI-01": "PASS", "CI-02": "PASS", "CI-03": "PASS", "CI-05": "PASS"},
}
