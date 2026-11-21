# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the SEC family: secrets.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "sec-01-tracked-env": {"SEC-01": "FAIL"},
    "sec-01-excluded-env": {"SEC-01": "FAIL"},
    "sec-01-tracked-ignored-env": {"SEC-01": "FAIL", "SEC-03": "PASS"},
    "sec-03-tracked-ignored-key": {"SEC-01": "PASS", "SEC-03": "FAIL"},
    "sec-02-key-shaped": {"SEC-02": "FAIL"},
    "sec-03-thin-ignore": {"SEC-03": "FAIL"},
    "sec-03-ok-negated-exception": {"SEC-03": "PASS"},
    "sec-01-ok": {"SEC-01": "PASS", "SEC-02": "PASS", "SEC-03": "PASS"},
    "sec-02-expression-assignment": {"SEC-02": "PASS"},
    "sec-02-env-reference": {"SEC-02": "PASS"},
}
