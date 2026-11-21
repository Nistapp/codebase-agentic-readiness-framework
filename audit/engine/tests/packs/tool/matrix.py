# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the TOOL family: tooling.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "tool-01-no-formatter": {"TOOL-01": "FAIL"},
    "tool-02-no-linter": {"TOOL-02": "FAIL"},
    "tool-03-nonstrict-ts": {"TOOL-03": "PARTIAL"},
    "tool-04-no-audit-verb": {"TOOL-04": "FAIL"},
    "tool-04-make-security-no-audit": {"TOOL-04": "PARTIAL"},
    "tool-04-local-only-audit": {"TOOL-04": "PARTIAL"},
    "tool-05-unwired-hooks": {"TOOL-05": "PARTIAL"},
    "tool-05-husky-helpers-only": {"TOOL-05": "FAIL"},
    "tool-05-githooks-helpers-only": {"TOOL-05": "FAIL"},
    "tool-06-no-commit-rule": {"TOOL-06": "FAIL"},
    "tool-06-local-only-commit-rule": {"TOOL-06": "PARTIAL"},
    "tool-06-ci-only-commit-rule": {"TOOL-06": "PARTIAL"},
    "tool-07-no-branch-guard": {"TOOL-05": "PASS", "TOOL-07": "FAIL"},
    "tool-07-guard-no-exit": {"TOOL-05": "PASS", "TOOL-07": "PARTIAL"},
    "tool-ok-node": {
        "TOOL-01": "PASS",
        "TOOL-02": "PASS",
        "TOOL-03": "PASS",
        "TOOL-04": "PASS",
        "TOOL-05": "PASS",
        "TOOL-06": "PASS",
    },
}
