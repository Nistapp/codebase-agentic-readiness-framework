# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Puts ``../../audit/tools`` on `sys.path`, so an implement tool can import the shared helpers.

An implement tool imports this module first. In a framework checkout the shared helpers (``_common``,
``validate_report``, ``_jsonschema_subset``) live in ``audit/tools/``. In the implement skill bundle they sit beside
the implement tools in ``scripts/tools/`` and that folder does not exist, so this module then does nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

AUDIT_TOOLS = Path(__file__).resolve().parent.parent.parent / "audit" / "tools"

if AUDIT_TOOLS.is_dir() and str(AUDIT_TOOLS) not in sys.path:
    sys.path.insert(0, str(AUDIT_TOOLS))
