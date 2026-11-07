# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Puts the implement tools, the audit tools and their test helpers on `sys.path`, for the implement tools' tests.

A test imports this module first. The unittest runner starts in this tests folder, which holds neither the implement
tools (``implement/tools/``) nor the shared helpers they import (``audit/tools/``) nor the shared test helpers
(``audit/tools/tests/``, for example ``_git``); none of them is a package.
"""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parents[1]
AUDIT = REPO / "audit"
AUDIT_TOOLS = AUDIT / "tools"

for _path in (AUDIT_TOOLS / "tests", AUDIT_TOOLS, TOOLS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
