# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CI runs every step of ``make check``, split into parallel jobs.

CI does not call ``make check`` as one command: ``.github/workflows/ci.yml`` runs its steps as separate jobs, so
they run at once. These tests fail when a step of ``check`` (or a suite of ``test``) has no CI job, so a step
added to ``check`` cannot silently drop out of the gate that decides a pull request.
"""

from __future__ import annotations

import re
import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from _dev_paths import REPO

MAKEFILE = REPO / "Makefile"
CI = REPO / ".github" / "workflows" / "ci.yml"
#: A workflow step that runs make: `run: make a b c`, alone on its line.
CI_MAKE = re.compile(r"^\s*(?:-\s+)?run:\s*make\s+(?P<args>[^#|&;]+?)\s*$", re.MULTILINE)


def make_rule(text: str, name: str) -> list[str]:
    """The prerequisites of the rule ``name``, in order."""
    match = re.search(rf"^{re.escape(name)}:(?!=)(?P<needs>[^\n;]*)$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"the Makefile has no rule {name!r}")
    return match.group("needs").split()


def make_variable(text: str, name: str) -> list[str]:
    """The words of the simple variable ``name`` (``NAME := ...``)."""
    match = re.search(rf"^{re.escape(name)}\s*:=(?P<value>[^\n]*)$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"the Makefile has no variable {name!r}")
    return match.group("value").split()


def ci_targets(text: str) -> set[str]:
    """Every make target a CI step names, without options and variable assignments."""
    return {
        word
        for match in CI_MAKE.finditer(text)
        for word in match.group("args").split()
        if not word.startswith("-") and "=" not in word
    }


class CheckRunsInCI(unittest.TestCase):
    def setUp(self) -> None:
        self.makefile = MAKEFILE.read_text(encoding="utf-8")
        self.ci = ci_targets(CI.read_text(encoding="utf-8"))
        self.suites = make_variable(self.makefile, "TEST_SUITES")
        self.coverage_suites = make_variable(self.makefile, "COVERAGE_SUITES")

    def test_every_step_of_check_has_a_ci_job(self) -> None:
        steps = [step for step in make_rule(self.makefile, "check") if step != "test"]
        self.assertIn("test", make_rule(self.makefile, "check"))
        self.assertEqual([step for step in steps if step not in self.ci], [], "steps of check that CI never runs")

    def test_every_test_suite_has_a_ci_job(self) -> None:
        # A suite counts when CI runs it plainly (test-dev) or under coverage (coverage-engine runs test-engine's suite).
        missing = [
            suite
            for suite in self.suites
            if suite not in self.ci and suite.replace("test-", "coverage-", 1) not in self.ci
        ]
        self.assertEqual(missing, [], "test suites that CI never runs")

    def test_ci_runs_the_whole_test_verb_too(self) -> None:
        # The Python 3.14 job runs `make test`: every suite, the way a person runs it.
        self.assertIn("test", self.ci)

    def test_coverage_combines_every_suite_ci_measures(self) -> None:
        self.assertIn("coverage-combine", self.ci)
        self.assertEqual(make_rule(self.makefile, "coverage"), [*self.coverage_suites, "coverage-combine"])
        for target in self.coverage_suites:
            with self.subTest(target=target):
                self.assertIn(target, self.ci)
                self.assertIn(target.replace("coverage-", "test-", 1), self.suites)

    def test_ci_gate_needs_every_other_job(self) -> None:
        # A job that CI Gate does not need can fail, or never finish, while the gate passes.
        text = CI.read_text(encoding="utf-8")
        jobs = re.findall(r"^  (?P<job>[a-z0-9-]+):$", text[text.index("\njobs:\n") :], re.MULTILINE)
        needs = re.search(r"^  ci-gate:\n(?:    .*\n)*?    needs: \[(?P<needs>[^\]]*)\]", text, re.MULTILINE)
        self.assertIsNotNone(needs, "ci-gate has no needs list")
        assert needs is not None
        self.assertEqual(
            sorted(job for job in jobs if job != "ci-gate"), sorted(n.strip() for n in needs["needs"].split(","))
        )

    def test_the_parser_reads_a_step_list(self) -> None:
        sample = "      - run: make format-check typecheck\n        run: make -j4 --output-sync=target test X=1\n"
        self.assertEqual(ci_targets(sample), {"format-check", "typecheck", "test"})


if __name__ == "__main__":
    unittest.main()
