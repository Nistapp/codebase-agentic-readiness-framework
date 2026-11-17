# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The scaffolder's post-write gate, `verify_tree`: it fails loudly on an incomplete or half-filled project.

A template tree that lacks one of `MANDATORY_FILES` must fail the run and name the file; this checkout's tree must
pass. A placeholder left in a generated file, an empty file and an invalid `package.json` fail too. Standard library
only.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from _bootstrap_support import IDENTITY, TEMPLATES, bootstrap, copy_templates, run_main


class MandatoryFilesTests(unittest.TestCase):
    def test_this_checkouts_templates_produce_every_mandatory_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out"
            code, _, err = run_main([str(target), "--name", "pkg", "--no-git", *IDENTITY])
            self.assertEqual(code, 0, err)
            missing = [rel for rel in bootstrap.MANDATORY_FILES if not (target / rel).is_file()]
        self.assertEqual(missing, [])

    def test_every_mandatory_file_but_the_gitkeeps_has_a_template(self) -> None:
        planned = {rel for _, rel in bootstrap.build_plan(TEMPLATES, with_cli=False, with_infra=False)}
        generated = {"artefacts/.gitkeep", "specs/.gitkeep"}
        self.assertEqual(sorted(set(bootstrap.MANDATORY_FILES) - planned - generated), [])

    def test_a_template_tree_missing_a_mandatory_file_fails_and_names_it(self) -> None:
        # Not one of the three files resolve_templates looks for, so only the post-write gate can catch it.
        for template, target_rel in (("SECURITY.md", "SECURITY.md"), ("husky/commit-msg", ".husky/commit-msg")):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as tmp:
                copy = copy_templates(Path(tmp))
                (copy / template).unlink()
                code, _, err = run_main(
                    [str(Path(tmp) / "out"), "--name", "pkg", "--no-git", "--templates", str(copy), *IDENTITY]
                )
                self.assertNotEqual(code, 0)
                self.assertIn("generated project is incomplete, missing:", err)
                self.assertIn(target_rel, err)


class VerifyTreeTests(unittest.TestCase):
    """`verify_tree` on a finished scaffold, edited to break one rule at a time."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "out"
        code, _, err = run_main([str(self.target), "--name", "pkg", "--no-git", *IDENTITY])
        self.assertEqual(code, 0, err)
        self.written = sorted(
            path.relative_to(self.target).as_posix() for path in self.target.rglob("*") if path.is_file()
        )

    def fails(self) -> str:
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            bootstrap.verify_tree(self.target, self.written)
        self.assertNotEqual(raised.exception.code, 0)
        return err.getvalue()

    def test_the_unedited_scaffold_passes(self) -> None:
        bootstrap.verify_tree(self.target, self.written)

    def test_a_written_file_that_disappeared_is_missing(self) -> None:
        (self.target / "CONVENTIONS.md").unlink()
        self.assertIn("missing: CONVENTIONS.md", self.fails())

    def test_an_unreplaced_placeholder_fails_and_is_listed(self) -> None:
        for token in ("<your-email>", "<project>", "[Project Name]", "[@github-handle]"):
            with self.subTest(token=token):
                readme = self.target / "README.md"
                original = readme.read_text(encoding="utf-8")
                readme.write_text(original + f"\nContact {token}\n", encoding="utf-8")
                try:
                    message = self.fails()
                finally:
                    readme.write_text(original, encoding="utf-8")
                self.assertIn("unsubstituted placeholders survived", message)
                self.assertIn(f"README.md: {token}", message)

    def test_document_templates_keep_their_placeholders(self) -> None:
        adr = self.target / "docs" / "templates" / "adr-template.md"
        adr.write_text(adr.read_text(encoding="utf-8") + "\n<project-name> by <author>\n", encoding="utf-8")
        bootstrap.verify_tree(self.target, self.written)

    def test_a_placeholder_in_an_unplanned_file_fails_too(self) -> None:
        (self.target / "extra.txt").write_text("<org>\n", encoding="utf-8")
        self.assertIn("extra.txt: <org>", self.fails())

    def test_binary_files_are_not_read_for_placeholders(self) -> None:
        (self.target / "logo.bin").write_bytes(b"\xff\xfe<org>\x00")
        bootstrap.verify_tree(self.target, self.written)

    def test_a_git_folder_is_not_read_for_placeholders(self) -> None:
        (self.target / ".git").mkdir()
        (self.target / ".git" / "COMMIT_EDITMSG").write_text("<project>\n", encoding="utf-8")
        bootstrap.verify_tree(self.target, self.written)

    def test_an_empty_written_file_fails(self) -> None:
        (self.target / "CONVENTIONS.md").write_text("", encoding="utf-8")
        self.assertIn("unexpectedly empty: CONVENTIONS.md", self.fails())

    def test_the_gitkeeps_may_be_empty(self) -> None:
        self.assertEqual((self.target / "artefacts" / ".gitkeep").stat().st_size, 0)
        bootstrap.verify_tree(self.target, self.written)

    def test_an_invalid_package_json_fails(self) -> None:
        (self.target / "package.json").write_text("{not json\n", encoding="utf-8")
        self.assertIn("package.json is not valid JSON", self.fails())


if __name__ == "__main__":
    unittest.main()
