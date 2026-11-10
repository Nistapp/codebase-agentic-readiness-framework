# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The implement eval's command line and its canned-report builder, without an agent.

`test_implement_eval.py` tests every assertion. This file tests the rest of `implement_eval.py`: the subcommands
(`scenarios`, `materialise`, `assert`), the usage error, `neutralise`, and `build_reports`, which audits the toy
repository with the real tools and writes the two canned final reports. The reports go to a temporary directory, never
into the repository. Standard library only; no network, no `claude`.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _dev_paths

DEV = _dev_paths.DEV
sys.path.insert(0, str(DEV / "eval"))

import _common  # noqa: E402
import implement_eval as ie  # noqa: E402
import validate_report  # noqa: E402


class HandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="implement-eval-cli-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_scenarios_lists_every_scenario(self) -> None:
        result = ie.handler(["scenarios"])
        names = [entry["name"] for entry in result.data["scenarios"]]
        self.assertEqual(names, ie.scenario_names())
        self.assertTrue(all(entry["assertions"] for entry in result.data["scenarios"]))
        self.assertIn("scenarios", result.summary)

    def test_materialise_lays_a_scenario_out(self) -> None:
        name = ie.scenario_names()[0]
        root = self.tmp / "root"
        result = ie.handler(["materialise", name, str(root)])
        self.assertTrue((root / "repo").is_dir())
        self.assertIn(name, result.summary)

    def test_assert_reports_a_failed_assertion_for_an_untouched_scenario(self) -> None:
        name = ie.scenario_names()[0]
        root = self.tmp / "root"
        ie.materialise(name, root)
        transcript = self.tmp / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "result", "result": "stopped", "total_cost_usd": 0.0, "duration_ms": 1000}) + "\n",
            encoding="utf-8",
        )
        result = ie.handler(["assert", name, str(root), str(transcript)])
        self.assertFalse(result.data["passed"])
        self.assertIn("failed", result.summary)

    def test_a_missing_subcommand_is_a_usage_error(self) -> None:
        with self.assertRaises(_common.UsageError):
            ie.handler([])


class NeutraliseTests(unittest.TestCase):
    def test_build_paths_become_neutral(self) -> None:
        document = {
            "path": f"/tmp/implement-eval-build-abc123/{ie.LABEL}/src/app.py",
            "work": "/tmp/implement-eval-build-abc123/engine/out.json",
        }
        ie.neutralise(document)
        self.assertEqual(document["path"], f"{ie.LABEL}/src/app.py")
        self.assertEqual(document["work"], "./engine/out.json")

    def test_a_document_without_build_paths_is_unchanged(self) -> None:
        document = {"path": "src/app.py"}
        ie.neutralise(document)
        self.assertEqual(document, {"path": "src/app.py"})


class BuildReportsTests(unittest.TestCase):
    def test_every_canned_report_is_built_and_valid(self) -> None:
        with tempfile.TemporaryDirectory(prefix="implement-eval-reports-") as tmp:
            reports = Path(tmp)
            with mock.patch.object(ie, "REPORTS", reports):
                written = ie.build_reports()
            self.assertEqual(len(written), 6)
            for variant in ie.VARIANTS:
                documents = sorted((reports / variant).glob("*.json"))
                self.assertEqual(len(documents), 1, variant)
                text = documents[0].read_text(encoding="utf-8")
                self.assertNotIn("/tmp/implement-eval-build-", text)
                document = json.loads(text)
                self.assertEqual(document["status"], "final")
                self.assertEqual(validate_report.validate_document(document).errors, [])
                self.assertTrue(documents[0].with_suffix(".md").is_file())

    def test_one_variant_is_built_alone(self) -> None:
        with tempfile.TemporaryDirectory(prefix="implement-eval-reports-") as tmp:
            reports = Path(tmp)
            with mock.patch.object(ie, "REPORTS", reports):
                written = ie.build_reports(["comm"])
            self.assertEqual(len(written), 2)
            self.assertEqual(sorted(p.name for p in reports.iterdir()), ["comm"])

    def test_an_unknown_variant_is_a_usage_error(self) -> None:
        with self.assertRaises(_common.UsageError):
            ie.build_reports(["nope"])


if __name__ == "__main__":
    unittest.main()
