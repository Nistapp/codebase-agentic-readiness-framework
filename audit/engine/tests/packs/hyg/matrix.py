# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the HYG family: hygiene (informational, reported never scored).

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "hyg-01-placeholder-readme": {"HYG-01": "FAIL", "HYG-10": "FAIL"},
    "hyg-09-uncovered-ecosystem": {"HYG-09": "PARTIAL"},
    "hyg-09-target-branch-trap": {"HYG-09": "PARTIAL"},
    "hyg-10-no-license": {"HYG-01": "PASS", "HYG-10": "FAIL"},
    "hyg-11-no-source-branch-check": {"HYG-11": "PARTIAL"},
    "hyg-13-thin-contributing": {"HYG-05": "PASS", "HYG-13": "FAIL"},
    "hyg-minimal": {f"HYG-{n:02d}": "FAIL" for n in range(1, 11)} | {"HYG-11": "UNKNOWN", "HYG-13": "UNKNOWN"},
}
