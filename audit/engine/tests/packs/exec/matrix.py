# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the EXEC family: execution environment.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "exec-01-unpinned": {"EXEC-01": "FAIL"},
    "exec-01-nested-go-unpinned": {"EXEC-01": "FAIL"},
    "exec-01-sibling-module-unpinned": {"EXEC-01": "PARTIAL"},
    "exec-01-python-source-only": {"EXEC-01": "FAIL", "EXEC-02": "UNKNOWN"},
    "exec-01-php-version-file": {"EXEC-01": "PASS"},
    "exec-01-php-unpinned": {"EXEC-01": "FAIL"},
    "exec-01-nested-composer-unpinned": {"EXEC-01": "PARTIAL"},
    "exec-01-tool-versions-only": {"EXEC-01": "PASS"},
    "exec-01-tool-versions-go": {"EXEC-01": "PASS"},
    "exec-02-no-lockfile": {"EXEC-02": "FAIL"},
    "exec-02-nested-lockfile": {"EXEC-02": "FAIL"},
    "exec-02-lockfile-no-manifest": {"EXEC-02": "PARTIAL"},
    "exec-03-no-setup": {"EXEC-03": "FAIL"},
    "exec-03-readme-no-extension": {"EXEC-03": "PASS", "HYG-01": "PASS"},
    "exec-03-devcontainer-subfolder": {"EXEC-03": "PASS"},
    "exec-04-missing-env": {"EXEC-04": "FAIL"},
    "exec-04-reincluded-example": {"EXEC-04": "PASS"},
    "exec-04-anchored-ignored-dir": {"EXEC-04": "PASS"},
    "exec-04-nested-ignored-dir": {"EXEC-04": "PASS"},
    "exec-05-generated": {"EXEC-05": "FAIL"},
    # Committed build output under dist/ and build/: the walk enters both for their tracked files. The build/ file
    # counts because the fixture's own ignore rules match it (issue #260).
    "exec-05-committed-dist": {"EXEC-05": "FAIL", "NAV-03": "PARTIAL"},
    # A hand-written script tracked in build/, no ignore rule and no generated hint: not build output.
    "exec-05-build-script": {"EXEC-05": "PASS"},
    "exec-06-broken-command": {"EXEC-06": "FAIL"},
    "exec-07-dual-lint": {"EXEC-07": "FAIL"},
    "exec-07-dual-python-types": {"EXEC-07": "FAIL"},
    "exec-08-inline-version": {"EXEC-08": "FAIL"},
    "exec-08-duplicate-pin": {"EXEC-08": "PARTIAL"},
    "exec-ok": {
        "EXEC-01": "PASS",
        "EXEC-02": "PASS",
        "EXEC-03": "PASS",
        "EXEC-04": "PASS",
        "EXEC-05": "PASS",
        "EXEC-06": "PASS",
        "EXEC-07": "PASS",
    },
}
