# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the TST family: tests.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "tst-01-no-suite": {"TST-01": "PARTIAL"},
    "tst-03-skip-markers": {"TST-03": "PASS"},
    "tst-04-no-fastpath": {"TST-04": "FAIL"},
    "tst-05-no-coverage": {"TST-05": "FAIL"},
}
