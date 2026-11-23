# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""``make gate`` runs every gate that CI's ``ci-gate`` job needs.

``make gate`` is the one command a person runs before a pull request: it runs ``check``, ``security``, ``docs-lint``,
``commit-lint``, ``self-audit`` and ``coverage``. CI's ``ci-gate`` job lists the jobs a pull request needs
(``needs: [...]`` in ``.github/workflows/ci.yml``). These tests read that list, so a job added to CI with no gate
here fails the test until someone maps it. The mapping below is written out on purpose: it says which gate covers
which job, and a job with no entry is an error.

The gates are the ``GATE_FIRST`` and ``GATE_THEN`` variables of the ``Makefile``.
"""

from __future__ import annotations

import re
import subprocess
import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from _dev_paths import REPO
from test_ci_parity import CI, MAKEFILE, ci_jobs, ci_targets, make_rule, make_variable

#: The gate of ``make gate`` that covers each job CI Gate needs. Python 3.11 and 3.14 jobs map to the one gate that
#: runs the same suites on the machine's own Python: ``make gate`` never installs another Python (the comment above
#: GATE_FIRST in the Makefile says why). A job with no entry fails ``test_every_ci_gate_job_has_a_gate``.
JOBS_OF_GATE = {
    "check": ("static", "crosscheck", "test-dev", "test-py314"),
    "coverage": ("test-coverage", "coverage"),
    "security": ("security-secrets", "security-deps"),
    "self-audit": ("self-audit",),
    "docs-lint": ("docs",),
    "commit-lint": ("commits",),
}
GATE_FOR_JOB = {job: gate for gate, jobs in JOBS_OF_GATE.items() for job in jobs}


def ci_gate_needs(text: str) -> list[str]:
    """The jobs ``ci-gate`` needs, read from the workflow text."""
    match = re.search(r"^  ci-gate:\n(?:    .*\n)*?    needs: \[(?P<needs>[^\]]*)\]", text, re.MULTILINE)
    if match is None:
        raise AssertionError("ci-gate has no needs list")
    return [need.strip() for need in match["needs"].split(",") if need.strip()]


def reachable(makefile: str, gate: str) -> set[str]:
    """The gate's own target and every target it runs as a prerequisite, through ``check`` and ``test`` too."""
    suites = make_variable(makefile, "TEST_SUITES")
    coverage_suites = make_variable(makefile, "COVERAGE_SUITES")
    found: set[str] = set()
    todo = [gate]
    while todo:
        target = todo.pop()
        if target in found:
            continue
        found.add(target)
        if target == "test":
            todo.extend(suites)
        elif target == "coverage":
            todo.extend([*coverage_suites, "coverage-combine"])
        else:
            todo.extend(make_rule(makefile, target) if _has_rule(makefile, target) else [])
    return found


def _has_rule(makefile: str, target: str) -> bool:
    return re.search(rf"^{re.escape(target)}:(?!=)", makefile, re.MULTILINE) is not None


def normalise(target: str) -> str:
    """CI's shard and part targets run pieces of ``test`` and ``coverage``."""
    if target in ("test-part", "coverage-part"):
        return target.removesuffix("-part")
    if target == "coverage-combine":
        return "coverage"
    return target.removesuffix("-shard") if target.endswith("-shard") else target


class GateRunsWhatCiNeeds(unittest.TestCase):
    def setUp(self) -> None:
        self.makefile = MAKEFILE.read_text(encoding="utf-8")
        self.ci = CI.read_text(encoding="utf-8")
        self.first = make_variable(self.makefile, "GATE_FIRST")
        self.then = make_variable(self.makefile, "GATE_THEN")
        self.gates = [*self.first, *self.then]

    def test_every_ci_gate_job_has_a_gate(self) -> None:
        needs = ci_gate_needs(self.ci)
        self.assertEqual([job for job in needs if job not in GATE_FOR_JOB], [], "jobs CI Gate needs, with no gate")
        self.assertEqual(
            [job for job in needs if GATE_FOR_JOB[job] not in self.gates],
            [],
            "jobs mapped to a gate that `make gate` does not run",
        )

    def test_the_mapping_names_no_job_that_ci_dropped(self) -> None:
        self.assertEqual(sorted(set(GATE_FOR_JOB) - set(ci_gate_needs(self.ci))), [], "stale mapping entries")

    def test_a_gate_covers_the_targets_of_its_ci_jobs(self) -> None:
        # Every target a CI job runs is part of the gate the job maps to (`check` runs `test`, which runs the suites).
        jobs = ci_jobs(self.ci)
        for job in ci_gate_needs(self.ci):
            covered = reachable(self.makefile, GATE_FOR_JOB[job])
            for target in ci_targets(jobs[job]):
                with self.subTest(job=job, target=target):
                    self.assertIn(
                        normalise(target),
                        covered,
                        f"CI job {job} runs make {target}, which gate {GATE_FOR_JOB[job]} leaves out",
                    )

    def test_the_gate_runs_in_two_waves_and_coverage_waits(self) -> None:
        # check's tests and coverage both build audit/engine/dist/audit.pyz in place: they must not overlap.
        self.assertIn("check", self.first)
        self.assertEqual(self.then, ["coverage"])
        self.assertNotIn("coverage", self.first)

    def test_a_gate_target_exists_for_each_gate(self) -> None:
        out = subprocess.run(
            ["make", "-s", "-n", "-C", str(REPO), "gate", "TEST_JOBS="], capture_output=True, text=True, check=True
        ).stdout
        for gate in self.gates:
            with self.subTest(gate=gate):
                self.assertIn(f"gate-{gate}", out)
                self.assertRegex(out, rf"TEST_SUITES_SUBMAKE= {re.escape(gate)};")


if __name__ == "__main__":
    unittest.main()
