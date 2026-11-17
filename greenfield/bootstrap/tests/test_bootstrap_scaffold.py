# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""A full render of this checkout's `greenfield/templates/` into a temporary directory.

Runs `bootstrap.main` in-process with `--no-git` and without `--install`, so it needs no git, npm or network. The
generated tree must match the plan, carry the inputs, keep the hooks executable and leave the document templates
untouched. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from _bootstrap_support import IDENTITY, TEMPLATES, bootstrap, run_main


def files_under(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


class LibraryScaffoldTests(unittest.TestCase):
    """One render, default flags plus a scoped name: the library form."""

    tmp: tempfile.TemporaryDirectory[str]
    target: Path
    out: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls.tmp.name) / "my-lib"
        argv = [str(cls.target), "--org", "acme", "--description", "A library", "--node", "22", "--no-git", *IDENTITY]
        code, cls.out, err = run_main(argv)
        if code != 0:
            raise AssertionError(f"scaffold failed ({code}):\n{err}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_the_tree_is_the_plan_plus_the_gitkeeps(self) -> None:
        plan = [rel for _, rel in bootstrap.build_plan(TEMPLATES, with_cli=False, with_infra=False)]
        self.assertEqual(files_under(self.target), sorted([*plan, "artefacts/.gitkeep", "specs/.gitkeep"]))
        self.assertIn(f"wrote {len(plan) + 2} files", self.out)

    def test_no_git_repository_is_made(self) -> None:
        self.assertFalse((self.target / ".git").exists())
        self.assertIn("git init -b dev && git add -A", self.out)

    def test_package_json_carries_the_inputs(self) -> None:
        data = json.loads((self.target / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "@acme/my-lib")
        self.assertEqual(data["description"], "A library")
        self.assertEqual(data["author"], "Ada Lovelace <ada@example.com>")
        self.assertEqual(data["engines"], {"node": ">=22.0.0"})
        self.assertEqual(data["repository"]["url"], "git+https://github.com/ada/my-lib.git")
        self.assertNotIn("bin", data)

    def test_the_node_version_is_pinned(self) -> None:
        self.assertEqual((self.target / ".nvmrc").read_text(encoding="utf-8").strip(), "22")

    def test_text_files_carry_the_inputs(self) -> None:
        security = (self.target / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("ada@example.com", security)
        self.assertNotIn("<your-email>", security)

    def test_the_hooks_are_executable(self) -> None:
        for rel in bootstrap.EXECUTABLE_FILES:
            with self.subTest(rel=rel):
                mode = (self.target / rel).stat().st_mode
                self.assertTrue(mode & stat.S_IXUSR, f"{rel} is not executable")

    def test_other_files_are_not_made_executable(self) -> None:
        mode = (self.target / "package.json").stat().st_mode
        if os.name == "posix":
            self.assertFalse(mode & stat.S_IXUSR)

    def test_document_templates_are_copied_byte_for_byte(self) -> None:
        for template in sorted((TEMPLATES / "docs" / "templates").iterdir()):
            with self.subTest(template=template.name):
                copied = self.target / "docs" / "templates" / template.name
                self.assertEqual(copied.read_bytes(), template.read_bytes())

    def test_files_without_placeholders_are_copied_byte_for_byte(self) -> None:
        inputs = {"resolved_name": "x", "github_owner": "x", "author": "x", "email": "", "description": "x"}
        tokens = bootstrap.build_substitutions(argparse.Namespace(node_version="24", **inputs))
        for src, rel in bootstrap.build_plan(TEMPLATES, with_cli=False, with_infra=False):
            text = src.read_text(encoding="utf-8")
            if rel == "package.json" or any(token in text for token in tokens) or "YYYY-MM-DD" in text:
                continue
            with self.subTest(rel=rel):
                self.assertEqual((self.target / rel).read_bytes(), src.read_bytes())

    def test_the_next_steps_are_printed(self) -> None:
        self.assertIn("next steps", self.out)
        self.assertIn(f"cd {self.target}", self.out)


class OptionalGroupTests(unittest.TestCase):
    def render(self, *flags: str) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "tool"
        code, _, err = run_main([str(target), "--no-git", *IDENTITY, *flags])
        self.assertEqual(code, 0, err)
        return target, tmp

    def test_cli_adds_the_entry_point_and_the_bin_entry(self) -> None:
        target, _ = self.render("--cli")
        self.assertTrue((target / "src" / "cli" / "index.ts").is_file())
        data = json.loads((target / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(data["bin"], {"tool": "./dist/cli/index.js"})

    def test_lib_has_neither(self) -> None:
        target, _ = self.render("--lib")
        self.assertFalse((target / "src" / "cli").exists())
        self.assertNotIn("bin", json.loads((target / "package.json").read_text(encoding="utf-8")))

    def test_with_infra_copies_the_infra_folder(self) -> None:
        target, _ = self.render("--with-infra")
        self.assertEqual(
            sorted(p.name for p in (target / "infra").iterdir()),
            sorted(p.name for p in (TEMPLATES / "infra").iterdir()),
        )


class InputTextTests(unittest.TestCase):
    """Free text from the command line lands in the generated files as written."""

    def render(self, *flags: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pkg"
            code, _, err = run_main([str(target), "--no-git", "--github-owner", "ada", *flags])
            self.assertEqual(code, 0, err)
            data = json.loads((target / "package.json").read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        return data

    def test_quotes_and_backslashes_keep_package_json_valid(self) -> None:
        # A double quote or a backslash used to break package.json with a JSONDecodeError traceback.
        description = 'Parses "quoted" text and C:\\paths\\ too'
        author = 'Bob "the Builder" O\'Neil'
        data = self.render("--description", description, "--author", author, "--email", "bob@example.com")
        self.assertEqual(data["description"], description)
        self.assertEqual(data["author"], f"{author} <bob@example.com>")

    def test_non_ascii_text_is_kept(self) -> None:
        data = self.render("--description", "Café ✓ 日本", "--author", "José", "--email", "jo@example.com")
        self.assertEqual(data["description"], "Café ✓ 日本")
        self.assertEqual(data["author"], "José <jo@example.com>")


if __name__ == "__main__":
    unittest.main()
