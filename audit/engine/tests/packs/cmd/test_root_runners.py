# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""A runner manifest counts only at the repository root: a nested one is not a runner and no finding cites it.

``make``, ``npm``, ``task`` and the pyproject task runners read the file in the folder they run in. The audit asks
what an agent can run from the root, so a manifest below it (``tools/Makefile``) declares no verb there. The checks
run in process here, so the coverage run traces them.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.components import detect_components  # noqa: E402
from audit.probes import ProbeSession  # noqa: E402
from audit.rules.checks._common import makefile_errors, resolve_all_verbs, runner_commands  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from audit.target import resolve_target  # noqa: E402
from scope_support import MAKE, NPM, TASKFILE, ScopeTestCase  # noqa: E402

#: GNU Make refuses this file: an unescaped ``format:check:`` is a static pattern rule with no ``%``.
BROKEN_MAKE = "format:check:\n\techo c\n"


def cmd01(root: Path):
    """``CMD-01``'s outcome on the directory ``root``, run in process."""
    target = resolve_target(root)
    inventory = build_inventory(target.path)
    session = ProbeSession(cwd=target.path, user_config=False)
    return REGISTRY_BY_ID["CMD-01"].run(
        target=target,
        inventory=inventory,
        stack=detect_stack(inventory),
        components=detect_components(inventory),
        session=session,
    )


class NestedMakefileTests(ScopeTestCase):
    def test_a_nested_only_makefile_is_not_a_runner(self):
        inventory = self.inventory_of({"tools/Makefile": MAKE})
        self.assertEqual(runner_commands(inventory), ())
        self.assertEqual(resolve_all_verbs(inventory, detect_stack(inventory)), {})

    def test_a_root_makefile_is_the_runner_and_a_nested_one_beside_it_is_not(self):
        inventory = self.inventory_of({"Makefile": MAKE, "tools/Makefile": "check:\n\techo nested\n"})
        self.assertEqual([runner for runner, _ in runner_commands(inventory)], ["Makefile"])
        self.assertNotIn("check", dict(runner_commands(inventory))["Makefile"])

    def test_a_nested_makefile_that_make_refuses_is_no_parse_error(self):
        inventory = self.inventory_of({"tools/Makefile": BROKEN_MAKE})
        self.assertEqual(makefile_errors(inventory), ())

    def test_a_root_makefile_that_make_refuses_is_still_a_parse_error(self):
        inventory = self.inventory_of({"Makefile": BROKEN_MAKE})
        self.assertEqual([error.line for error in makefile_errors(inventory)], [1])

    def test_cmd01_on_the_nested_only_fixture_cites_no_file(self):
        outcome = cmd01(support.fixture("cmd-01-nested-makefile-only"))
        self.assertEqual(outcome.verdict.value, "UNKNOWN")
        self.assertEqual(outcome.findings, [])
        self.assertEqual(
            outcome.summary,
            "no recognised verb runner (package.json, Makefile, Taskfile, pyproject, gradle, maven), "
            "so no verb can be resolved",
        )


class NestedPackageJsonTests(ScopeTestCase):
    def test_a_nested_only_package_json_is_not_a_runner(self):
        inventory = self.inventory_of({"packages/app/package.json": NPM})
        self.assertEqual(runner_commands(inventory), ())
        self.assertEqual(resolve_all_verbs(inventory, detect_stack(inventory)), {})

    def test_a_root_package_json_is_the_runner_and_a_nested_one_beside_it_is_not(self):
        nested = '{"scripts": {"check": "npm test"}}'
        inventory = self.inventory_of({"package.json": NPM, "packages/app/package.json": nested})
        self.assertEqual([runner for runner, _ in runner_commands(inventory)], ["package.json"])
        self.assertNotIn("check", dict(runner_commands(inventory))["package.json"])

    def test_cmd01_on_the_nested_lockfile_fixture_cites_no_file(self):
        """The fixture's only manifest is ``packages/app/package.json``: no runner, so ``UNKNOWN`` and no finding."""
        outcome = cmd01(support.fixture("exec-02-nested-lockfile"))
        self.assertEqual(outcome.verdict.value, "UNKNOWN")
        self.assertEqual(outcome.findings, [])


class NestedTaskfileTests(ScopeTestCase):
    def test_a_nested_only_taskfile_is_not_a_runner(self):
        for name in ("Taskfile.yml", "Taskfile.yaml"):
            with self.subTest(name=name):
                inventory = self.inventory_of({f"apps/web/{name}": TASKFILE})
                self.assertEqual(runner_commands(inventory), ())

    def test_a_root_taskfile_is_the_runner_and_a_nested_one_beside_it_is_not(self):
        nested = "version: '3'\ntasks:\n  check:\n    cmd: task test\n"
        inventory = self.inventory_of({"Taskfile.yml": TASKFILE, "apps/web/Taskfile.yml": nested})
        self.assertEqual([runner for runner, _ in runner_commands(inventory)], ["Taskfile.yml"])
        self.assertNotIn("check", dict(runner_commands(inventory))["Taskfile.yml"])


#: A pyproject.toml whose poe tasks declare ``test`` and ``lint``.
POE = '[tool.poe.tasks]\ntest = "pytest"\nlint = "ruff check ."\n'


class NestedPyprojectTests(ScopeTestCase):
    def test_a_nested_only_pyproject_is_not_a_runner(self):
        inventory = self.inventory_of({"tools/x/pyproject.toml": POE})
        self.assertEqual(runner_commands(inventory), ())
        self.assertEqual(resolve_all_verbs(inventory, detect_stack(inventory)), {})

    def test_a_root_pyproject_is_the_runner_and_a_nested_one_beside_it_is_not(self):
        nested = '[tool.poe.tasks]\ncheck = "poe test"\n'
        inventory = self.inventory_of({"pyproject.toml": POE, "tools/x/pyproject.toml": nested})
        self.assertEqual([runner for runner, _ in runner_commands(inventory)], ["pyproject.toml"])
        self.assertEqual(dict(runner_commands(inventory))["pyproject.toml"]["test"], "pytest")
        self.assertNotIn("check", dict(runner_commands(inventory))["pyproject.toml"])


if __name__ == "__main__":
    unittest.main()
