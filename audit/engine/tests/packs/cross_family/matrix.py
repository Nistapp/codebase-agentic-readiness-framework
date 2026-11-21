# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the cross-family family: carried data, layout and stack fixtures, and the AGT-content positive fixture.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    # -- carried data (ADR-0008; tests/test_repository_scope.py) -------------------------------
    "carried-jvm-example-package": {"NAV-02": "PASS", "TST-01": "PASS", "TST-03": "PASS"},
    # -- an app per folder, no root manifest (issues #20, #56) --------------------------------
    "layout-app-per-folder": {
        "AGT-02": "PASS",
        "BASE-04": "PASS",
        "EXEC-02": "PASS",
        "EXEC-03": "PASS",
        "EXEC-04": "PASS",
        "NAV-01": "PARTIAL",
    },
    # -- stacks no other fixture holds (tests/test_stack_fixtures.py) -------------------------
    "stack-dotnet": {"EXEC-01": "PASS", "EXEC-02": "FAIL", "NAV-01": "PASS", "NAV-02": "PASS", "TOOL-03": "PASS"},
    "stack-dotnet-locked": {
        "EXEC-01": "PASS",
        "EXEC-02": "PASS",
        "NAV-01": "PASS",
        "NAV-02": "PASS",
        "TOOL-03": "PASS",
    },
    "stack-gradle-wrapper-readme": {"EXEC-01": "PASS", "EXEC-02": "FAIL", "EXEC-06": "PASS", "NAV-02": "PASS"},
    "stack-just-inline-version": {"EXEC-01": "PASS", "EXEC-02": "PASS", "EXEC-08": "FAIL", "NAV-02": "PASS"},
    "stack-maven-wrapper-readme": {"EXEC-01": "PASS", "EXEC-02": "FAIL", "EXEC-06": "PASS", "NAV-02": "PASS"},
    "stack-php-composer": {"EXEC-01": "PASS", "EXEC-02": "PARTIAL", "NAV-01": "PASS", "NAV-02": "PASS"},
    "stack-python-uv-inline-version": {"EXEC-01": "PASS", "EXEC-02": "PASS", "EXEC-08": "FAIL", "NAV-02": "PASS"},
    "stack-ruby-bundler": {"EXEC-01": "PASS", "EXEC-02": "PARTIAL", "NAV-01": "PASS", "NAV-02": "PASS"},
    "stack-rust-cargo": {"EXEC-01": "PASS", "EXEC-02": "PASS", "NAV-01": "PASS", "NAV-02": "PASS"},
    # -- the AGT-content positive fixture -----------------------------------------------------
    "governed-minimal": {
        "AGT-01": "PASS",
        "AGT-02": "PASS",
        "AGT-03": "PASS",
        "AGT-04": "PASS",
        "AGT-06": "PASS",
        "AGT-07": "PASS",
        "AGT-09": "PASS",
        "AGT-10": "PASS",
        "AGT-12": "PASS",
        "AGT-13": "PASS",
    },
}
