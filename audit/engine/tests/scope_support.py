# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Shared harness for the tests of what counts as the repository (ADR-0008)."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks._common import resolve_verbs  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

NPM = '{"scripts": {"test": "vitest run", "lint": "eslint ."}}'
MAKE = "test:\n\tpytest\n\nlint:\n\truff check .\n"
TASKFILE = "version: '3'\ntasks:\n  test:\n    cmd: pytest\n"


class ScopeTestCase(unittest.TestCase):
    """A test case that builds directories which live as long as the test."""

    def inventory_of(self, files: dict[str, str]):
        root = Path(tempfile.mkdtemp(prefix="audit-scope-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for rel, text in files.items():
            support.write(root, rel, text)
        return build_inventory(root)

    def resolved(self, files: dict[str, str]):
        inventory = self.inventory_of(files)
        return resolve_verbs(inventory, detect_stack(inventory)), inventory
