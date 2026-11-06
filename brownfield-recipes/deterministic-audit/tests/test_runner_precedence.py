# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Runner precedence is depth first (ADR-0008): a root manifest of any kind beats a nested one."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit.rules.checks._common import resolve_all_verbs, runner_commands  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from scope_support import MAKE, NPM, TASKFILE, ScopeTestCase  # noqa: E402


class RunnerPrecedenceTests(ScopeTestCase):
    def test_a_root_makefile_outranks_a_nested_package_json(self):
        verbs, _ = self.resolved({"Makefile": MAKE, "apps/web/package.json": NPM})
        self.assertEqual(verbs["test"].runner, "Makefile")
        self.assertEqual(verbs["lint"].runner, "Makefile")

    def test_the_shallowest_nested_manifest_wins_among_nested_ones(self):
        verbs, _ = self.resolved({"apps/web/Taskfile.yml": TASKFILE, "apps/web/deep/package.json": NPM})
        self.assertEqual(verbs["test"].runner, "apps/web/Taskfile.yml")

    def test_a_tie_at_equal_depth_goes_to_the_kind_precedence(self):
        verbs, _ = self.resolved({"Makefile": MAKE, "package.json": NPM})
        self.assertEqual(verbs["test"].runner, "package.json")

    def test_a_tie_at_equal_depth_and_kind_goes_to_the_path(self):
        verbs, _ = self.resolved({"b/package.json": NPM, "a/package.json": NPM})
        # one manifest per kind is read (the shallowest, then the first by path): "a/" wins
        self.assertEqual(verbs["test"].runner, "a/package.json")

    def test_precedence_is_applied_per_verb(self):
        verbs, _ = self.resolved({"Makefile": "lint:\n\truff check .\n", "apps/web/package.json": NPM})
        self.assertEqual(verbs["lint"].runner, "Makefile")
        self.assertEqual(verbs["test"].runner, "apps/web/package.json")

    def test_bindings_for_one_verb_are_listed_in_depth_order(self):
        inventory = self.inventory_of({"Makefile": MAKE, "apps/web/package.json": NPM})
        bindings = resolve_all_verbs(inventory, detect_stack(inventory))["test"]
        self.assertEqual([b.runner for b in bindings], ["Makefile", "apps/web/package.json"])

    def test_runner_commands_lists_the_root_runner_first(self):
        inventory = self.inventory_of({"Makefile": MAKE, "apps/web/package.json": NPM})
        self.assertEqual([runner for runner, _ in runner_commands(inventory)], ["Makefile", "apps/web/package.json"])


if __name__ == "__main__":
    unittest.main()
