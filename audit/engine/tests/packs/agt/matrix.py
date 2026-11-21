# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix rows of the AGT family: content contract, competing files and indirection.

``test_fixture_matrix.MATRIX`` joins the tables of all families. A fixture name appears in one table only.
"""

from __future__ import annotations

#: fixture directory -> {check id: expected verdict}
ROWS: dict[str, dict[str, str]] = {
    "agt-01-missing": {"AGT-01": "FAIL", "AGT-08": "PASS", "CON-01": "UNKNOWN", "CON-02": "UNKNOWN"},
    "agt-01-stub": {"AGT-01": "FAIL"},
    "agt-01-mis-cased": {"AGT-01": "PARTIAL"},
    "agt-01-shadowed": {"AGT-01": "PARTIAL"},
    "agt-01-nested-only": {"AGT-01": "PARTIAL", "AGT-08": "PASS"},
    "agt-01-marker-words-in-prose": {"AGT-01": "PASS"},
    "agt-02-uncovered": {"AGT-02": "PARTIAL"},
    "agt-03-incomplete": {"AGT-03": "PARTIAL"},
    "agt-04-missing": {"AGT-04": "FAIL"},
    "agt-05-verbs-named-not-resolved": {"AGT-05": "PARTIAL"},
    "agt-05-ok": {"AGT-05": "PASS"},
    "agt-06-thin": {"AGT-06": "PARTIAL"},
    "agt-07-missing-deny": {"AGT-07": "PARTIAL"},
    "agt-08-competitor": {"AGT-08": "FAIL"},
    "agt-08-copilot-instructions": {"AGT-08": "FAIL"},
    "agt-08-cursor-rule-flat": {"AGT-08": "FAIL"},
    "agt-09-no-release": {"AGT-09": "PARTIAL"},
    "agt-09-ruleset-branch-unnamed": {"AGT-09": "PARTIAL"},
    "agt-12-no-rules": {"AGT-09": "PASS", "AGT-12": "FAIL"},
    "agt-13-no-conventions": {"AGT-12": "PASS", "AGT-13": "FAIL"},
    "agt-10-deferred": {"AGT-10": "FAIL"},
    "agt-10-deferred-dot-folder": {"AGT-10": "FAIL"},
    "agt-10-pointer-dot-folder": {"AGT-10": "PASS"},
    "agt-10-pointer-glob-top-level": {"AGT-10": "PASS"},
}
