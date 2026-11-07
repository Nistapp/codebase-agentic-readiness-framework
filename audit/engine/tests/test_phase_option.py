# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`--phase` records the phase in the report's provenance and does nothing else.

The help text once said "highest framework phase to evaluate". The engine implements phase 1 only, so a higher
number evaluates nothing more; the text now says what the option does, and these tests hold the text to the
behaviour.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.cli import build_parser  # noqa: E402


def phase_action():
    return next(action for action in build_parser()._actions if "--phase" in action.option_strings)


class PhaseOptionTests(unittest.TestCase):
    def test_the_help_says_the_phase_is_recorded_and_the_engine_implements_phase_one_only(self):
        self.assertEqual(
            phase_action().help,
            "the phase recorded in the report's provenance (default: 1); the engine implements phase 1 only, so a "
            "higher value changes nothing else",
        )

    def test_the_default_is_phase_one_and_the_value_is_an_integer(self):
        action = phase_action()
        self.assertEqual((action.default, action.type), (1, int))

    def test_a_higher_phase_is_recorded_and_changes_no_verdict_and_no_finding(self):
        target = support.fixture("cmd-ok-make")
        default = support.run_audit(target)
        higher = support.run_audit(target, extra_args=("--phase", "3"))
        self.assertEqual((default["provenance"]["phase"], higher["provenance"]["phase"]), (1, 3))
        self.assertEqual(support.verdicts(default), support.verdicts(higher))
        self.assertEqual(default["findings"], higher["findings"])
        self.assertEqual(default["summary"], higher["summary"])


if __name__ == "__main__":
    unittest.main()
