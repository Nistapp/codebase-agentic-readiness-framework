# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The stack fixtures: one small, realistic project per ecosystem that no other fixture holds.

Each ``stack-*`` fixture is a project in one ecosystem (Rust with Cargo, .NET, Ruby with Bundler, PHP with
Composer, a Gradle or a Maven build whose README runs the wrapper, a uv project with a root lockfile) or with one command runner (``just``). The checks read names for these stacks (a pin file, a lockfile,
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
    "stack-gradle-wrapper-readme": ({"jvm"}, set()),
    "stack-just-inline-version": ({"rust"}, {"cargo"}),
    "stack-maven-wrapper-readme": ({"jvm"}, {"maven"}),
    "stack-php-composer": ({"php"}, {"composer"}),
    "stack-python-uv-inline-version": ({"python"}, {"uv"}),
    "stack-ruby-bundler": ({"ruby"}, {"bundler"}),
    "stack-rust-cargo": ({"rust"}, {"cargo"}),
}

#: fixture -> {check id: (verdict, a phrase the check's summary holds)}.
VERDICTS: dict[str, dict[str, tuple[str, str]]] = {
    "stack-dotnet": {
        "EXEC-01": ("PASS", "dotnet (global.json)"),
        "NAV-01": ("PASS", "declares StackDotnet.csproj"),
        "NAV-02": ("PASS", "entry point(s): Program.cs"),
        "TOOL-03": ("PASS", "StackDotnet.csproj:Nullable"),
    },
    "stack-gradle-wrapper-readme": {
        "EXEC-01": ("PASS", "jvm (gradlew)"),
        "EXEC-06": ("PASS", "2 documented command(s) resolve"),
        "NAV-02": ("PASS", "entry point(s): src/main/java/app/App.java"),
    },
    "stack-just-inline-version": {
        "EXEC-01": ("PASS", "rust (rust-toolchain.toml)"),
        "EXEC-02": ("PASS", "tracked: Cargo.lock"),
        "EXEC-08": ("FAIL", "1 literal tool version(s) no manifest holds"),
    },
    "stack-maven-wrapper-readme": {
        "EXEC-01": ("PASS", "jvm (mvnw)"),
        "EXEC-06": ("PASS", "2 documented command(s) resolve"),
        "NAV-02": ("PASS", "entry point(s): src/main/java/app/App.java"),
    },
    "stack-php-composer": {
        "EXEC-01": ("PASS", "php (composer.json (require.php))"),
        "EXEC-02": ("PARTIAL", "consistency unverified: composer.lock"),
        "NAV-01": ("PASS", "declares composer.json"),
        "NAV-02": ("PASS", "entry point(s): public/index.php"),
    },
    "stack-python-uv-inline-version": {
        "EXEC-01": ("PASS", "python (pyproject.toml (requires-python))"),
        "EXEC-02": ("PASS", "tracked: uv.lock"),
        "EXEC-08": ("FAIL", "1 literal tool version(s) no manifest holds"),
    },
    "stack-ruby-bundler": {
        "EXEC-01": ("PASS", "ruby (.ruby-version)"),
        "EXEC-02": ("PARTIAL", "consistency unverified: Gemfile.lock"),
        "NAV-01": ("PASS", "declares Gemfile"),
        "NAV-02": ("PASS", "entry point(s): config.ru"),
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

    def test_the_justfile_recipe_that_installs_a_tool_at_a_literal_version_is_the_evidence(self):
        report = matrix.run("stack-just-inline-version")
        (finding,) = [finding for finding in report["findings"] if finding["check"] == "EXEC-08"]
        self.assertEqual(finding["id"], "EXEC-08:justfile")
        self.assertEqual(
            [(item["path"], item.get("line"), item.get("note")) for item in finding["evidence"]],
            [("justfile", 9, "cargo-deny 0.16.1")],
        )

    def test_every_stack_fixture_has_a_row_here_and_in_the_fixture_matrix(self):
        on_disk = {path.name for path in support.FIXTURES_DIR.iterdir() if path.name.startswith("stack-")}
        self.assertEqual(on_disk, set(STACKS))
        self.assertEqual(on_disk, set(VERDICTS))
        self.assertLessEqual(on_disk, set(matrix.MATRIX))


if __name__ == "__main__":
    unittest.main()
