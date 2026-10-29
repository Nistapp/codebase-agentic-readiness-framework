# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""What a check's status does: a blocked check does not run, a planned one says so, an implemented one is run.

No catalogued check is blocked any more: ``CON-01`` was, until the engine began to read the prohibitions section. The
status stays as a facility (a check whose contract the framework has not defined can be catalogued and carry no
weight), so its behaviour is tested on a check made here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit import __ruleset_revision__  # noqa: E402
from audit.findings import Severity, Verdict  # noqa: E402
from audit.rules.registry import REGISTRY, REGISTRY_BY_ID, CheckSpec, scoreable  # noqa: E402


def spec(status: str, **changes) -> CheckSpec:
    return CheckSpec(
        id="ZZZ-01", title="A check", tier="B", severity=Severity.BLOCKER, evidence_rule="", status=status, **changes
    )


class StatusTests(unittest.TestCase):
    def test_a_blocked_check_does_not_run_and_is_unknown(self):
        ran = []
        outcome = spec("blocked", impl=lambda **_: ran.append(1)).run()
        self.assertEqual(ran, [])
        self.assertEqual(
            (outcome.check, outcome.title, outcome.tier, outcome.severity, outcome.phase),
            ("ZZZ-01", "A check", "B", Severity.BLOCKER, 1),
        )
        self.assertEqual(
            (outcome.verdict, outcome.status, outcome.summary),
            (Verdict.UNKNOWN, "blocked", "blocked: this ruleset cannot evaluate the check, so it carries weight 0"),
        )

    def test_a_check_with_no_implementation_says_it_is_not_implemented_in_this_ruleset(self):
        outcome = spec("planned").run()
        self.assertEqual((outcome.verdict, outcome.status), (Verdict.UNKNOWN, "planned"))
        self.assertEqual(outcome.summary, f"not implemented in ruleset {__ruleset_revision__}")

    def test_an_implemented_check_is_run_with_its_spec(self):
        calls = []

        def impl(**kwargs):
            calls.append(kwargs)
            return "outcome"

        subject = spec("implemented", impl=impl)
        self.assertEqual(subject.run(target="t", inventory="i"), "outcome")
        self.assertEqual(calls, [{"spec": subject, "target": "t", "inventory": "i"}])


class RegistryTests(unittest.TestCase):
    def test_every_catalogued_check_is_implemented_and_none_is_blocked(self):
        self.assertEqual({s.status for s in REGISTRY}, {"implemented"})

    def test_there_are_fifty_five_scoreable_checks_and_con_01_is_one_of_them(self):
        self.assertEqual(len(scoreable()), 55)
        self.assertEqual(len(REGISTRY), 69)
        con_01 = REGISTRY_BY_ID["CON-01"]
        self.assertEqual(
            (con_01.scored, con_01.status, con_01.severity, con_01.tier), (True, "implemented", Severity.BLOCKER, "B")
        )

    def test_an_emitter_is_not_scoreable_and_con_01_is(self):
        self.assertNotIn("CON-04", {s.id for s in scoreable()})
        self.assertIn("CON-01", {s.id for s in scoreable()})

    def test_the_ruleset_revision_is_a_date_and_a_number(self):
        self.assertRegex(__ruleset_revision__, r"^\d{4}-\d{2}-\d{2}\.[1-9]\d*$")


if __name__ == "__main__":
    unittest.main()
