# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the BASE family: baselines.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "base-01-no-baseline": {"BASE-01": "FAIL"},
    "base-02-no-count": {"BASE-02": "PARTIAL"},
    "base-03-no-ratchet": {"BASE-03": "FAIL"},
    "base-04-no-coverage-floor": {"BASE-04": "FAIL"},
    "base-ok": {"BASE-01": "PASS", "BASE-02": "PASS", "BASE-03": "PASS", "BASE-04": "PASS"},
}
