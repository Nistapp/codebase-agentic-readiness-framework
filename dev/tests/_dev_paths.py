# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Puts the dev checks and the audit tools on `sys.path`, so a dev test can `import build_skills`.

A test imports this module first. The unittest runner starts in this tests folder, which holds neither the dev
checks (``dev/``, ``dev/eval/``) nor the tools they import (``audit/tools/``) and their test helpers
(``audit/tools/tests/``); none of them is a package.
"""

from __future__ import annotations

import sys
from pathlib import Path

DEV = Path(__file__).resolve().parents[1]
REPO = DEV.parent
AUDIT_TOOLS = REPO / "audit" / "tools"

for _path in (AUDIT_TOOLS / "tests", AUDIT_TOOLS, DEV / "eval", DEV):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
