# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Which ecosystems the engine recognises, and from what.

A manifest names an ecosystem. A project that has none (a tool written against the standard library alone) is
still a project, so Python is also recognised from its own source files, and the stack says it did so.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import SOURCE_SIGNALS, Stack, detect_stack  # noqa: E402

NOTE = "python recognised from its source files: no manifest names it"


def stack_of(files: dict[str, str]) -> Stack:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        return detect_stack(build_inventory(root))


class PythonFromSourceTests(unittest.TestCase):
    def test_a_python_source_file_with_no_manifest_is_a_python_project_and_the_stack_says_how(self):
        stack = stack_of({"src/app.py": "print(1)\n"})
        self.assertEqual(stack.ecosystems, {"python"})
        self.assertEqual(stack.source_only, {"python"})
        self.assertEqual(stack.notes, [NOTE])

    def test_a_manifest_names_the_ecosystem_and_the_source_is_not_the_reason(self):
        for manifest in ("pyproject.toml", "setup.py", "requirements.txt", "requirements-dev.txt", "Pipfile"):
            with self.subTest(manifest=manifest):
                stack = stack_of({manifest: "\n", "src/app.py": "print(1)\n"})
                self.assertEqual((stack.ecosystems, stack.source_only, stack.notes), ({"python"}, set(), []))

    def test_a_test_file_a_generated_file_or_a_vendored_file_is_not_the_projects_source(self):
        for rel in (
            "tests/test_app.py",
            "test_app.py",
            "app_test.py",
            "src/app.test.py",
            "src/__tests__/x.py",
            "generated/x.py",
            "vendor/x.py",
            "node_modules/pkg/x.py",
            "dist/x.py",
            "build/x.py",
        ):
            with self.subTest(file=rel):
                self.assertEqual(stack_of({rel: "print(1)\n"}).ecosystems, set())

    def test_source_in_a_language_the_engine_has_no_signal_for_is_not_guessed_at(self):
        for rel in ("src/app.rb", "src/app.zig", "src/app.lua", "src/index.js", "src/app.go", "src/App.java"):
            with self.subTest(file=rel):
                stack = stack_of({rel: "x\n"})
                self.assertEqual((stack.ecosystems, stack.source_only), (set(), set()))
                self.assertEqual(stack.notes, ["no recognised build manifest — stack-dependent checks report UNKNOWN"])

    def test_a_suffix_that_only_contains_py_is_not_python(self):
        for rel in ("src/app.pyc", "src/app.pyi", "src/app.python", "src/app.py.txt", "src/pytest"):
            with self.subTest(file=rel):
                self.assertEqual(stack_of({rel: "x\n"}).ecosystems, set())

    def test_another_ecosystems_manifest_does_not_hide_python_source(self):
        stack = stack_of({"package.json": "{}\n", "tools/gen.py": "print(1)\n"})
        self.assertEqual(stack.ecosystems, {"node", "python"})
        self.assertEqual(stack.source_only, {"python"})
        self.assertEqual(stack.notes, [NOTE])

    def test_the_only_ecosystem_with_a_source_signal_is_python_and_its_signal_is_the_py_suffix(self):
        self.assertEqual(SOURCE_SIGNALS, {"python": ".py"})

    def test_the_stack_describes_a_source_only_python_project(self):
        self.assertEqual(stack_of({"src/app.py": "print(1)\n"}).describe(), "ecosystems: python")


class VerbRunnerTests(unittest.TestCase):
    """The runner manifests a stack lists, each once, in the order of the ecosystems that hint at them."""

    def test_a_makefile_at_any_depth_is_listed_once_though_five_ecosystems_hint_at_it(self):
        self.assertEqual(stack_of({"Makefile": "all:\n"}).verb_runners, ["Makefile"])
        self.assertEqual(stack_of({"tools/Makefile": "all:\n"}).verb_runners, ["Makefile"])

    def test_the_runners_follow_the_order_of_the_ecosystem_table(self):
        files = {"Makefile": "all:\n", "package.json": "{}\n"}
        self.assertEqual(stack_of(files).verb_runners, ["package.json", "Makefile"])

    def test_a_manifest_that_is_not_a_verb_runner_is_not_listed(self):
        self.assertEqual(stack_of({"Rakefile": "task :x\n", "Gemfile": "\n"}).verb_runners, [])

    def test_a_manifest_names_its_ecosystem_at_any_depth_and_by_its_basename(self):
        self.assertEqual(stack_of({"deep/er/package.json": "{}\n"}).ecosystems, {"node"})
        self.assertEqual(stack_of({"my-package.json": "{}\n"}).ecosystems, set())
        self.assertEqual(stack_of({"deep/requirements-prod.txt": "x\n"}).ecosystems, {"python"})


if __name__ == "__main__":
    unittest.main()
