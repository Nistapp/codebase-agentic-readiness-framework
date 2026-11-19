# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Runner precedence is depth first (ADR-0008): a root manifest of any kind beats a nested one.

Every runner kind (a ``Makefile``, a ``package.json``, a Taskfile, a ``pyproject.toml``, a Gradle and a Maven
build) counts only at the root, so a nested manifest is no runner at all. Among the root runners the kind
decides. ``runner_rank`` still orders paths depth first, then by kind, then by path; it is tested on paths here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from audit.rules.checks._common import resolve_all_verbs, runner_commands, runner_rank  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from scope_support import MAKE, NPM, ScopeTestCase  # noqa: E402

#: A Maven build: every pom has the ``test`` and ``verify`` lifecycle phases.
MAVEN = "<project></project>\n"


class RunnerPrecedenceTests(ScopeTestCase):
    def test_a_root_makefile_outranks_a_nested_package_json(self):
        verbs, _ = self.resolved({"Makefile": MAKE, "apps/web/package.json": NPM})
        self.assertEqual(verbs["test"].runner, "Makefile")
        self.assertEqual(verbs["lint"].runner, "Makefile")

    def test_nested_maven_builds_are_no_runners_at_any_depth(self):
        verbs, _ = self.resolved({"apps/pom.xml": MAVEN, "apps/web/deep/pom.xml": MAVEN})
        self.assertEqual(verbs, {})

    def test_the_rank_puts_the_shallowest_path_first_whatever_its_kind(self):
        # pom.xml ranks below build.gradle by kind, but the shallower path wins first
        self.assertEqual(sorted(["apps/web/deep/build.gradle", "apps/pom.xml"], key=runner_rank)[0], "apps/pom.xml")

    def test_a_tie_at_equal_depth_goes_to_the_kind_precedence(self):
        verbs, _ = self.resolved({"Makefile": MAKE, "package.json": NPM})
        self.assertEqual(verbs["test"].runner, "package.json")

    def test_a_tie_at_equal_depth_and_kind_goes_to_the_path(self):
        self.assertEqual(sorted(["b/pom.xml", "a/pom.xml"], key=runner_rank), ["a/pom.xml", "b/pom.xml"])

    def test_precedence_is_applied_per_verb(self):
        verbs, _ = self.resolved({"Makefile": "lint:\n\truff check .\n", "pom.xml": MAVEN})
        self.assertEqual(verbs["lint"].runner, "Makefile")
        self.assertEqual(verbs["test"].runner, "pom.xml")

    def test_bindings_for_one_verb_are_listed_in_precedence_order(self):
        inventory = self.inventory_of({"Makefile": MAKE, "pom.xml": MAVEN})
        bindings = resolve_all_verbs(inventory, detect_stack(inventory))["test"]
        self.assertEqual([b.runner for b in bindings], ["Makefile", "pom.xml"])

    def test_runner_commands_lists_the_root_runners_and_no_nested_one(self):
        inventory = self.inventory_of({"Makefile": MAKE, "pom.xml": MAVEN, "apps/web/pom.xml": MAVEN})
        self.assertEqual([runner for runner, _ in runner_commands(inventory)], ["Makefile", "pom.xml"])


if __name__ == "__main__":
    unittest.main()
