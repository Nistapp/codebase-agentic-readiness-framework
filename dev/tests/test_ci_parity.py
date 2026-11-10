# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CI runs every step of ``make check``, split into parallel jobs.

CI does not call ``make check`` as one command: ``.github/workflows/ci.yml`` runs its steps as separate jobs, so
they run at once. These tests fail when a step of ``check`` (or a suite of ``test``) has no CI job, so a step
added to ``check`` cannot silently drop out of the gate that decides a pull request.

CI also splits the slow suites into shards (``SHARDED_SUITES``, ``TEST_SHARDS``, ``dev/test_shard.py``). These tests fail when a
matrix misses a shard, when a shard leaves the coverage environment, or when a verb (``test``, ``coverage``) starts
to shard. The nightly workflow runs the verbs whole.
"""

from __future__ import annotations

import re
import subprocess
import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import test_shard
from _dev_paths import REPO

MAKEFILE = REPO / "Makefile"
CI = REPO / ".github" / "workflows" / "ci.yml"
NIGHTLY = REPO / ".github" / "workflows" / "nightly.yml"
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


def make_recipe(text: str, name: str) -> str:
    """The recipe lines (tab-indented) of the rule ``name``."""
    match = re.search(rf"^{re.escape(name)}:(?!=)[^\n]*\n(?P<recipe>(?:\t[^\n]*\n)*)", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"the Makefile has no rule {name!r}")
    return match.group("recipe")


def ci_jobs(text: str) -> dict[str, str]:
    """Each job's block of the workflow ``text``, by job id."""
    body = text[text.index("\njobs:\n") :]
    return {
        match["job"]: match["block"]
        for match in re.finditer(r"^  (?P<job>[a-z0-9-]+):\n(?P<block>(?:(?:    .*)?\n)*)", body, re.MULTILINE)
    }


def job_shards(block: str) -> list[int] | None:
    """The job's ``matrix.shard`` list, or None when it has none."""
    match = re.search(r"^      matrix:\n        shard: \[(?P<shards>[^\]]*)\]$", block, re.MULTILINE)
    return None if match is None else [int(shard) for shard in match["shards"].split(",")]


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
        self.sharded = make_variable(self.makefile, "SHARDED_SUITES")
        self.count = int(make_variable(self.makefile, "TEST_SHARDS")[0])

    def test_every_step_of_check_has_a_ci_job(self) -> None:
        steps = [step for step in make_rule(self.makefile, "check") if step != "test"]
        self.assertIn("test", make_rule(self.makefile, "check"))
        self.assertEqual([step for step in steps if step not in self.ci], [], "steps of check that CI never runs")

    def runs(self, target: str, targets: set[str]) -> bool:
        """``target`` runs whole, or in shards (test_shard_matrices_list_every_shard checks that none is missing)."""
        return target in targets or f"{target}-shard" in targets

    def parts(self, kind: str) -> set[str]:
        """Every target that ``make <kind>-part`` runs over its TEST_SHARDS parts: each sharded suite's shard target,
        plus ``<KIND>_PART_<i>``."""
        recipe = make_recipe(self.makefile, f"{kind}-part")
        self.assertIn(f"$(SHARDED_SUITES:%={kind}-%-shard) $({kind.upper()}_PART_$(SHARD))", recipe)
        targets = {f"{kind}-{suite}-shard" for suite in self.sharded}
        for shard in range(1, self.count + 1):
            targets.update(make_variable(self.makefile, f"{kind.upper()}_PART_{shard}"))
        return targets

    def expand(self, targets: set[str]) -> set[str]:
        """``targets`` with test-part and coverage-part replaced by what they run."""
        expanded = set(targets)
        for kind in ("test", "coverage"):
            if f"{kind}-part" in targets:
                expanded |= self.parts(kind)
        return expanded

    def job_targets(self, job: str) -> set[str]:
        return self.expand(ci_targets(ci_jobs(CI.read_text(encoding="utf-8"))[job]))

    def test_every_part_of_security_has_a_ci_job(self) -> None:
        # CI runs `make security` as one job per part. `security` is its two parts, as prerequisites, and runs
        # nothing of its own, so the CI jobs cover all of it (TOOL-04 follows the prerequisites, issue #89).
        self.assertEqual(make_rule(self.makefile, "security"), ["security-secrets", "security-deps"])
        self.assertEqual(make_recipe(self.makefile, "security"), "", "security must run nothing but its two parts")
        parts = ["security-secrets", "security-deps"]
        self.assertEqual([part for part in parts if part not in self.ci], [], "parts of security that CI never runs")

    def test_the_secrets_scan_runs_without_go(self) -> None:
        # The secrets scan needs Python and uv only; Go is set up in security-deps alone.
        jobs = ci_jobs(CI.read_text(encoding="utf-8"))
        self.assertEqual(ci_targets(jobs["security-secrets"]), {"security-secrets"})
        self.assertNotIn("setup-go", jobs["security-secrets"])
        self.assertEqual(ci_targets(jobs["security-deps"]), {"security-deps"})
        self.assertIn("setup-go", jobs["security-deps"])

    def test_every_test_suite_has_a_ci_job(self) -> None:
        # A suite counts when CI runs it plainly (test-dev), under coverage (coverage-engine runs test-engine's
        # suite) or in shards (coverage-engine-shard, through coverage-part).
        ci = self.expand(self.ci)
        missing = [
            suite
            for suite in self.suites
            if not self.runs(suite, ci) and not self.runs(suite.replace("test-", "coverage-", 1), ci)
        ]
        self.assertEqual(missing, [], "test suites that CI never runs")

    def test_every_suite_runs_on_python_3_14(self) -> None:
        # The Python 3.14 job runs `make test-part` once per shard: every suite of `make test`, split over the parts.
        block = ci_jobs(CI.read_text(encoding="utf-8"))["test-py314"]
        self.assertRegex(block, r'python-version: "3\.14"')
        targets = self.job_targets("test-py314")
        self.assertIn("test-part", targets)
        self.assertEqual([s for s in self.suites if not self.runs(s, targets)], [], "suites Python 3.14 never runs")
        self.assertIn("verify-rules", targets)

    def test_every_coverage_suite_runs_in_the_coverage_parts(self) -> None:
        targets = self.job_targets("test-coverage")
        self.assertIn("coverage-part", targets)
        missing = [suite for suite in self.coverage_suites if not self.runs(suite, targets)]
        self.assertEqual(missing, [], "coverage suites the Python 3.11 parts never run")

    def test_the_nightly_run_calls_the_unsharded_verbs(self) -> None:
        # CI runs the suites in shards; the nightly run calls the verbs whole, as a person does.
        nightly = NIGHTLY.read_text(encoding="utf-8")
        self.assertRegex(nightly, r"(?m)^  schedule:\n    - cron: ")
        self.assertLessEqual({"check", "coverage", "test"}, ci_targets(nightly))
        self.assertNotIn("SHARD", nightly)

    def test_coverage_combines_every_suite_ci_measures(self) -> None:
        self.assertEqual(make_rule(self.makefile, "coverage"), [*self.coverage_suites, "coverage-combine"])
        for target in self.coverage_suites:
            with self.subTest(target=target):
                self.assertIn(target.replace("coverage-", "test-", 1), self.suites)
        # CI's data comes in one file per shard of each sharded suite; only SHARDED=1 makes coverage-combine expect
        # them all.
        coverage_job = ci_jobs(CI.read_text(encoding="utf-8"))["coverage"]
        self.assertRegex(coverage_job, r"(?m)^\s*- run: make coverage-combine SHARDED=1$")

    def test_the_sharded_combine_expects_one_file_per_shard(self) -> None:
        # Read what make would combine, so a wrong COMBINE_PARTS cannot pass on a partial total.
        def data_files(*args: str) -> set[str]:
            out = subprocess.run(
                ["make", "-s", "-n", "-C", str(REPO), "coverage-combine", *args],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            combine = next(line for line in out.splitlines() if " combine " in line)
            return set(re.findall(r"\.coverage\.([a-z0-9-]+)", combine))

        unsharded = {suite.removeprefix("coverage-") for suite in self.coverage_suites}
        self.assertEqual(data_files(), unsharded)
        shards = {f"{suite}-{i}" for suite in self.sharded for i in range(1, self.count + 1)}
        self.assertEqual(data_files("SHARDED=1"), (unsharded - set(self.sharded)) | shards)

    def test_shard_matrices_list_every_shard(self) -> None:
        # A job that runs a shard target must run it once for each of the TEST_SHARDS shards, or a part of a suite
        # never runs. Each shard reads its number from the job's SHARD variable.
        shard_targets = {"test-part", "coverage-part"} | {
            f"{kind}-{suite}-shard" for kind in ("test", "coverage") for suite in self.sharded
        }
        sharded = []
        for job, block in ci_jobs(CI.read_text(encoding="utf-8")).items():
            if not shard_targets & ci_targets(block):
                continue
            sharded.append(job)
            with self.subTest(job=job):
                self.assertEqual(job_shards(block), list(range(1, self.count + 1)), "list shards 1 to TEST_SHARDS")
                self.assertRegex(block, r"(?m)^      SHARD: \$\{\{ matrix\.shard \}\}$")
        self.assertEqual(sorted(sharded), ["test-coverage", "test-py314"], "both Pythons run the suites in shards")

    def test_the_makefile_and_the_runner_shard_the_same_suites(self) -> None:
        self.assertEqual(sorted(self.sharded), sorted(test_shard.SUITES))
        for suite in self.sharded:
            with self.subTest(suite=suite):
                self.assertIn(f"test-{suite}", self.suites)
                self.assertIn(f"$(call test_shard,{suite})", make_recipe(self.makefile, f"test-{suite}-shard"))

    def test_a_coverage_shard_runs_in_the_coverage_environment(self) -> None:
        # The same environment as coverage-<suite> (an empty HOME, CI=true), so a shard measures what CI measures;
        # its own HOME and data file, so the shards of one part cannot clear each other's.
        for suite in self.sharded:
            with self.subTest(suite=suite):
                recipe = make_recipe(self.makefile, f"coverage-{suite}-shard")
                self.assertIn(f"$(call coverage_env,{suite}-$(SHARD))", recipe)
                self.assertIn(f"COVERAGE_FILE=$(COVERAGE_DATA).{suite}-$(SHARD)", recipe)
                self.assertIn(f"$(call test_shard,{suite})", recipe)

    def test_the_verbs_never_shard(self) -> None:
        rules = ["test", "coverage", *(f"{kind}-{suite}" for kind in ("test", "coverage") for suite in self.sharded)]
        for rule in rules:
            with self.subTest(rule=rule):
                recipe = make_recipe(self.makefile, rule) + " ".join(make_rule(self.makefile, rule))
                self.assertNotIn("SHARD", recipe)
                self.assertNotIn("test_shard", recipe)

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

    def test_the_merge_queue_runs_ci_with_its_own_base_and_head(self) -> None:
        # The `dev` ruleset has a merge queue: CI Gate must report on merge_group. In a merge group the pull_request
        # payload is empty, so a job that diffs BASE..HEAD from it alone checks nothing there.
        text = CI.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^  merge_group:\n    types: \[checks_requested\]$")
        for line in text.splitlines():
            with self.subTest(line=line.strip()):
                if "github.event.pull_request.base.sha" in line:
                    self.assertIn("github.event.merge_group.base_sha", line)
                if "github.event.pull_request.head.sha" in line:
                    self.assertIn("github.event.merge_group.head_sha", line)

    def test_the_parser_reads_jobs_and_shards(self) -> None:
        sample = (
            "on: push\njobs:\n  t:\n    strategy:\n      matrix:\n        shard: [1, 2]\n    steps:\n"
            "      - run: make a\n\n  u:\n    steps: []\n"
        )
        jobs = ci_jobs(sample)
        self.assertEqual(sorted(jobs), ["t", "u"])
        self.assertEqual(job_shards(jobs["t"]), [1, 2])
        self.assertEqual(ci_targets(jobs["t"]), {"a"})
        self.assertIsNone(job_shards(jobs["u"]))

    def test_the_parser_reads_a_step_list(self) -> None:
        sample = "      - run: make format-check typecheck\n        run: make -j4 --output-sync=target test X=1\n"
        self.assertEqual(ci_targets(sample), {"format-check", "typecheck", "test"})


if __name__ == "__main__":
    unittest.main()
