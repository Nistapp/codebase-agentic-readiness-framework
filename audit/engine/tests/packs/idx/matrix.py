# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the IDX family: index. These fixtures are machine-local; they run with an isolated HOME and an absent index store.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "idx-01-no-mcp-config": {"IDX-01": "FAIL"},
    "idx-02-no-index": {"IDX-02": "UNKNOWN", "IDX-03": "UNKNOWN"},
}
