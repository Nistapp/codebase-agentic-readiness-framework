# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Carried data is set aside (ADR-0008): the walk, the tracked set, the report and the fixture.

The framework's own audit read a template's ``package.json`` as the runner and credited hygiene files from the
templates it ships. Each test below is one rule of the ADR, built from a directory in a temp dir.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.ignore import tracked_files  # noqa: E402
from audit.rules.checks._common import runner_commands, tracked_in_scope  # noqa: E402
from audit.scan import CARRIED_DATA_DIRS, build_inventory  # noqa: E402
from scope_support import MAKE, NPM, ScopeTestCase  # noqa: E402


class SetAsideTests(ScopeTestCase):
    def test_a_template_manifest_is_not_a_runner(self):
        verbs, inventory = self.resolved({"Makefile": MAKE, "templates/package.json": NPM})
        self.assertEqual(verbs["test"].runner, "Makefile")
        self.assertEqual([runner for runner, _ in runner_commands(inventory)], ["Makefile"])

    def test_every_listed_name_sets_a_directory_aside(self):
        for name in CARRIED_DATA_DIRS:
            with self.subTest(name=name):
                inventory = self.inventory_of(
                    {"Makefile": MAKE, f"{name}/CONTRIBUTING.md": "x", "src/app.py": "x = 1\n"}
                )
                self.assertEqual(inventory.paths(), ["Makefile", "src/app.py"])
                self.assertEqual([(s.path, s.files) for s in inventory.set_aside], [(name, 1)])

    def test_the_list_is_the_documented_one(self):
        self.assertEqual(
            sorted(CARRIED_DATA_DIRS),
            sorted(["templates", "template", "examples", "example", "fixtures", "samples", "testdata", "scaffold"]),
        )

    def test_the_name_is_compared_whole_and_without_regard_to_case(self):
        inventory = self.inventory_of(
            {"Makefile": MAKE, "Templates/a.md": "x", "vendor-samples/b.md": "x", "my_examples/c.md": "x"}
        )
        self.assertEqual(inventory.paths(), ["Makefile", "my_examples/c.md", "vendor-samples/b.md"])
        self.assertEqual([s.path for s in inventory.set_aside], ["Templates"])

    def test_a_nested_carried_directory_is_recorded_once_at_its_outermost(self):
        inventory = self.inventory_of(
            {"Makefile": MAKE, "docs/templates/a.md": "x", "docs/templates/examples/b.md": "x", "docs/guide.md": "x"}
        )
        self.assertEqual([(s.path, s.files) for s in inventory.set_aside], [("docs/templates", 2)])
        self.assertEqual(inventory.paths(), ["Makefile", "docs/guide.md"])

    def test_the_audited_directorys_own_name_is_not_a_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            support.write(root, "Makefile", MAKE)
            inventory = build_inventory(root)
        self.assertEqual(inventory.paths(), ["Makefile"])
        self.assertEqual(inventory.set_aside, [])

    def test_a_carried_directory_that_holds_the_only_manifest_is_the_project(self):
        inventory = self.inventory_of(
            {"examples/app/package.json": NPM, "examples/app/index.js": "x\n", "README.md": "x"}
        )
        self.assertEqual(inventory.set_aside, [])
        self.assertIn("examples/app/package.json", inventory.paths())

    def test_a_carried_directory_without_a_manifest_is_still_set_aside_when_there_is_none_anywhere(self):
        inventory = self.inventory_of({"README.md": "x", "examples/a.md": "x"})
        self.assertEqual([s.path for s in inventory.set_aside], ["examples"])

    def test_set_aside_files_cannot_be_read_or_matched(self):
        inventory = self.inventory_of({"Makefile": MAKE, "templates/CODEOWNERS": "* @a\n"})
        self.assertFalse(inventory.has("CODEOWNERS"))
        self.assertEqual(inventory.match("CODEOWNERS"), [])
        self.assertIsNone(inventory.read("templates/CODEOWNERS"))

    def test_is_set_aside_answers_for_a_path_under_a_recorded_directory(self):
        inventory = self.inventory_of({"Makefile": MAKE, "templates/a.md": "x"})
        self.assertTrue(inventory.is_set_aside("templates/a.md"))
        self.assertTrue(inventory.is_set_aside("templates/sub/b.md"))
        self.assertFalse(inventory.is_set_aside("templatesx/a.md"))
        self.assertFalse(inventory.is_set_aside("Makefile"))

    def test_the_tracked_set_leaves_out_what_was_set_aside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "Makefile", MAKE)
            support.write(root, "fixtures/.env", "X=1\n")
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "-f", "."], check=True)
            inventory = build_inventory(root)

            class _Target:
                path = root

            self.assertIn("fixtures/.env", tracked_files(root) or set())
            self.assertEqual(tracked_in_scope(_Target(), inventory), {"Makefile"})


class ReportedSetAsideTests(unittest.TestCase):
    def test_the_report_names_what_it_set_aside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "Makefile", MAKE)
            support.write(root, "templates/a.md", "x")
            support.write(root, "templates/b.md", "x")
            report = support.run_audit(root)
        self.assertEqual(report["inventory"]["set_aside"], [{"path": "templates", "files": 2}])
        self.assertEqual(report["inventory"]["files_set_aside"], 2)

    def test_a_repository_that_set_nothing_aside_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "Makefile", MAKE)
            report = support.run_audit(root)
        self.assertEqual(report["inventory"]["set_aside"], [])
        self.assertEqual(report["inventory"]["files_set_aside"], 0)

    def test_the_markdown_report_lists_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            support.write(root, "Makefile", MAKE)
            support.write(root, "templates/a.md", "x")
            out = Path(tmp) / "out"
            out.mkdir()
            proc = subprocess.run(
                [sys.executable, "-m", "audit", str(root), "--format", "both", "--out", str(out / "report.json")],
                cwd=str(support.REPO_ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = (out / "report.md").read_text(encoding="utf-8")
        self.assertIn("Set aside as carried data", text)
        self.assertIn("`templates`", text)


class RootMakefileNestedTemplateFixtureTests(unittest.TestCase):
    """The fixture of the precedence fix: a root Makefile with the seven verbs, and a template's package.json."""

    def test_the_root_makefile_is_the_runner_and_nothing_diverges(self):
        report = support.run_audit(support.fixture("cmd-ok-root-make-nested-template"))
        verdicts = support.verdicts(report)
        for check in ("CMD-01", "CMD-02", "CMD-03", "CMD-04"):
            self.assertEqual(verdicts[check], "PASS", check)
        cmd01 = next(c for c in report["checks"] if c["id"] == "CMD-01")
        self.assertNotIn("templates/", cmd01["summary"])

    def test_the_template_files_earn_no_hygiene_credit(self):
        verdicts = support.verdicts(support.run_audit(support.fixture("cmd-ok-root-make-nested-template")))
        for check in ("HYG-02", "HYG-03", "HYG-05", "HYG-06", "HYG-09"):
            self.assertEqual(verdicts[check], "FAIL", check)

    def test_the_report_says_the_template_directory_was_set_aside(self):
        report = support.run_audit(support.fixture("cmd-ok-root-make-nested-template"))
        self.assertEqual([s["path"] for s in report["inventory"]["set_aside"]], ["templates"])


if __name__ == "__main__":
    unittest.main()
