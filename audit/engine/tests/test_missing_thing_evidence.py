# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""A finding about something missing cites `<repository>`, never the first file of the inventory (issue #194).

"`CI-01` CI runs on pull requests" fails a repository with no CI workflow file, and "`TST-01` Test suite exists"
fails one with no test verb and no test file. Each finding is about a file that does not exist, so there is no file
to point at. Both findings used to cite the first path of the sorted inventory, a file the check's read declarations
do not name and that says nothing about CI or tests. Their evidence then moved whenever an unrelated file that sorts
first was added or removed. The checks run in-process here, so coverage traces them.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks.ci import check_ci01  # noqa: E402
from audit.rules.checks.tst import check_tst01  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

#: A node project with a runner but no CI workflow, no test verb and no test file.
_BASE = {"package.json": json.dumps({"scripts": {"lint": "eslint ."}}), "src/index.js": "export {};\n"}
#: An unrelated file whose path sorts before every path of `_BASE`.
_SORTS_FIRST = {".aaa-notes.md": "# notes\n"}


def _run(check, check_id: str, files: dict[str, str]) -> tuple[str, list[list[dict]]]:
    """The verdict and each finding's evidence of one check, run in-process on a repository built from ``files``."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        inventory = build_inventory(root)
        outcome = check(
            spec=REGISTRY_BY_ID[check_id],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=None,
            session=None,
        )
    return outcome.verdict.value, [finding.to_dict()["evidence"] for finding in outcome.findings]


class MissingThingEvidenceTests(unittest.TestCase):
    def assert_cites_the_repository(self, check, check_id: str) -> None:
        verdict, evidence = _run(check, check_id, _BASE)
        self.assertEqual(verdict, "FAIL")
        self.assertEqual(evidence, [[{"path": "<repository>", "line": None, "note": None}]])

        with_first = _run(check, check_id, {**_BASE, **_SORTS_FIRST})
        self.assertEqual(with_first, (verdict, evidence), "an unrelated file that sorts first moved the evidence")

    def test_ci01_without_a_workflow_cites_the_repository(self):
        self.assert_cites_the_repository(check_ci01, "CI-01")

    def test_tst01_without_a_test_verb_or_file_cites_the_repository(self):
        self.assert_cites_the_repository(check_tst01, "TST-01")


if __name__ == "__main__":
    unittest.main()
