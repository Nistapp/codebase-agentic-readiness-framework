# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Every check outcome carries a summary a person can read (issue #21).

The audit recipe shows the engine's one-line summary beside each verdict. "`AGT-01` Instruction file present" and
"`AGT-10` Instruction indirection resolves" returned an empty summary on most repositories, so the report had
nothing to show for them. This test runs every check on every fixture in-process (so coverage traces the checks)
and fails on an empty summary.
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.evaluate import evaluate  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from audit.target import resolve_target  # noqa: E402

_ARGS = argparse.Namespace(allow_probe=[], timeout=30, run_gates=False, no_user_config=True)


class CheckSummaryTests(unittest.TestCase):
    def test_no_check_returns_an_empty_summary_on_any_fixture(self):
        empty: list[str] = []
        for fixture in sorted(p for p in Path(support.FIXTURES_DIR).iterdir() if p.is_dir()):
            inventory = build_inventory(fixture)
            result = evaluate(
                target=resolve_target(fixture), inventory=inventory, stack=detect_stack(inventory), args=_ARGS
            )
            empty += [f"{fixture.name}: {o.check} {o.verdict.value}" for o in result.outcomes if not o.summary.strip()]
        self.assertEqual(empty, [])


if __name__ == "__main__":
    unittest.main()
