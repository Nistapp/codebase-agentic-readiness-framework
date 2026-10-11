# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine's fixture matrix, imported: each fixture's real report converts, validates, renders and keeps its verdict.

The engine has a fixture for each defect it detects, and `test_fixture_matrix.py` in its tests holds the verdict each
fixture must give. This test reads that table and does not copy it. For every fixture it scans the fixture with the
real engine, through the launcher, starts a draft for it, imports the report with `report.py import-engine`, and
asserts that the draft has the verdict the matrix promises on every check the matrix names, and that a defect's check
is not PASS. It also asserts that every imported draft is valid and renders, which holds the adapter to the whole of
the engine's output and not only to the three reports in the examples. Standard library only.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import _paths
import _engine_reports as er
import engine as launcher
import render_report
import report as rb
import validate_report as vr
from test_report import call, read_json

TOOLS = _paths.TOOLS
MOMENT = datetime(2026, 10, 10, 9, 30, 0, tzinfo=timezone.utc)


def engine_matrix() -> ModuleType:
    """The engine's own `test_fixture_matrix` module, which holds `MATRIX` and the fixtures' preparation."""
    launcher.load_engine()
    tests = str(launcher.ENGINE_DIR / "tests")
    if tests not in sys.path:
        sys.path.insert(0, tests)
    return importlib.import_module("test_fixture_matrix")


class FixtureMatrixImportTests(unittest.TestCase):
    matrix: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = engine_matrix()

    def imported(self, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Scan the fixture `name` with the engine, import the report into a new draft, and return both."""
        target = self.matrix.prepare(name)
        isolated = {}
        if name in self.matrix.NEEDS_ISOLATED_ENV:
            home = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, home, True)
            isolated = {"HOME": home, "AUDIT_INDEX_STORE": str(Path(home) / "absent-store")}
        if name in self.matrix.NEEDS_GIT:
            self.addCleanup(shutil.rmtree, target.parent, True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.dict(os.environ, isolated):
                report = er.scan(target, root / "engine")
            intake = root / "audit-intake.fixture.json"
            intake.write_text(
                json.dumps(
                    {
                        "intake_version": "0.1",
                        "target_path": str(target),
                        "harness": "none",
                        "model": "none",
                        "provider_exposure_acknowledged": True,
                        "index": {"kind": "none"},
                        "confirmation_policy": "interactive",
                        "output_dir": str(root / "out"),
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(rb, "utc_now", return_value=MOMENT):
                code, envelope, stderr = call(["init", str(intake)])
            self.assertEqual(code, 0, (envelope, stderr))
            draft = Path(envelope["data"]["draft"])
            code, envelope, stderr = call(["import-engine", str(draft), str(report)])
            self.assertEqual(code, 0, (name, envelope, stderr))
            return read_json(draft), envelope

    def test_the_matrix_was_read_and_is_not_empty(self) -> None:
        self.assertGreaterEqual(len(self.matrix.MATRIX), 60)
        expectations = [v for row in self.matrix.MATRIX.values() for v in row.values()]
        self.assertGreater(len([v for v in expectations if v != "PASS"]), 40)

    def test_every_fixture_imports_to_a_valid_draft_that_has_the_verdict_the_matrix_promises(self) -> None:
        defects = 0
        for name in sorted(self.matrix.MATRIX):
            if not self.matrix.MATRIX[name]:
                continue
            with self.subTest(fixture=name):
                document, envelope = self.imported(name)
                self.assertEqual(vr.validate_document(document).errors, [])
                self.assertTrue(render_report.render(document))
                self.assertEqual(len(document["checks"]), 69)
                checks = {c["id"]: c for c in document["checks"]}
                for check_id, expected in self.matrix.MATRIX[name].items():
                    self.assertEqual(checks[check_id]["verdict"], expected, f"{name}: {check_id}")
                    self.assertEqual(checks[check_id]["engine_verdict"], expected, f"{name}: {check_id}")
                    self.assertEqual(checks[check_id]["method"], "automated")
                    if expected != "PASS":
                        defects += 1
                        self.assertNotEqual(checks[check_id]["verdict"], "PASS")
                self.assertEqual(envelope["data"]["checks_imported"], 69)
        self.assertGreater(defects, 40)


if __name__ == "__main__":
    unittest.main()
