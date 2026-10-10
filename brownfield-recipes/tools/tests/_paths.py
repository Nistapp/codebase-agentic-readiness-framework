# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Puts the tools folder on `sys.path`, so a test can `import _common` or `import engine`.

A test imports this module first. The unittest runner starts in the tests folder, which does not hold the
tools, and the tools are scripts, not a package.
"""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
