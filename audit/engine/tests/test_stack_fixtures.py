# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The stack fixtures: one small, realistic project per ecosystem that no other fixture holds.

Each ``stack-*`` fixture is a project in one ecosystem (Rust with Cargo, .NET, Ruby with Bundler, PHP with
Composer) or with one command runner (``just``). The checks read names for these stacks (a pin file, a lockfile,
an entry point, a runner file) that no other fixture holds, so without them those reads never run in a test.

The test asserts what the engine detects (the ecosystems and the package managers) and the verdict and summary of
each check that reads one of the stack's names. A fixture that reads git's tracked set is prepared the way the
fixture matrix prepares it (``test_fixture_matrix.prepare``).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
import test_fixture_matrix as matrix  # noqa: E402

from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

#: fixture -> (ecosystems, package managers) that stack detection must report.
STACKS: dict[str, tuple[set[str], set[str]]] = {
    "stack-dotnet": ({"dotnet"}, set()),
    "stack-rust-cargo": ({"rust"}, {"cargo"}),
}

#: fixture -> {check id: (verdict, a phrase the check's summary holds)}.
VERDICTS: dict[str, dict[str, tuple[str, str]]] = {
    "stack-dotnet": {
        "EXEC-01": ("PASS", "dotnet (global.json)"),
        "NAV-02": ("PASS", "entry point(s): Program.cs"),
        "TOOL-03": ("PASS", "StackDotnet.csproj:Nullable"),
    },
    "stack-rust-cargo": {
        "EXEC-01": ("PASS", "rust (rust-toolchain.toml)"),
        "EXEC-02": ("PASS", "tracked: Cargo.lock"),
        "NAV-01": ("PASS", "declares Cargo.toml"),
        "NAV-02": ("PASS", "entry point(s): src/main.rs"),
    },
}


class StackFixtureTests(unittest.TestCase):
    def test_each_stack_fixture_is_detected_as_its_ecosystem(self):
        for name, (ecosystems, managers) in sorted(STACKS.items()):
            with self.subTest(fixture=name):
                stack = detect_stack(build_inventory(support.fixture(name)))
                self.assertEqual(stack.ecosystems, ecosystems)
                self.assertEqual(stack.package_managers, managers)

    def test_each_stack_fixture_reports_the_verdicts_of_the_checks_that_read_its_names(self):
        for name, expected in sorted(VERDICTS.items()):
            with self.subTest(fixture=name):
                report = matrix.run(name)
                checks = {check["id"]: check for check in report["checks"]}
                for check_id, (verdict, phrase) in expected.items():
                    self.assertEqual(checks[check_id]["verdict"], verdict, f"{name}: {check_id}")
                    self.assertIn(phrase, checks[check_id]["summary"], f"{name}: {check_id}")

    def test_every_stack_fixture_has_a_row_here_and_in_the_fixture_matrix(self):
        on_disk = {path.name for path in support.FIXTURES_DIR.iterdir() if path.name.startswith("stack-")}
        self.assertEqual(on_disk, set(STACKS))
        self.assertEqual(on_disk, set(VERDICTS))
        self.assertLessEqual(on_disk, set(matrix.MATRIX))


if __name__ == "__main__":
    unittest.main()
