# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Where the scaffolder reads its templates from, and how it fails when they are not there.

The precedence is `--templates`, then `AGENTIC_BOOTSTRAP_TEMPLATES`, then the in-repo `greenfield/templates/`.
A missing directory, or one without the three files a template set always has, exits 1. Standard library only.
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

from _bootstrap_support import IDENTITY, TEMPLATES, bootstrap, copy_templates, run_main

ENV = "AGENTIC_BOOTSTRAP_TEMPLATES"


@contextlib.contextmanager
def without_env() -> Iterator[None]:
    """The environment without the templates variable."""
    environ = {key: value for key, value in os.environ.items() if key != ENV}
    with mock.patch.dict(os.environ, environ, clear=True):
        yield


class PrecedenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.explicit = copy_templates(self.root / "explicit")
        self.from_env = copy_templates(self.root / "env")

    def test_the_default_is_the_in_repo_templates(self) -> None:
        self.assertEqual(bootstrap.DEFAULT_TEMPLATES, TEMPLATES)
        with without_env():
            self.assertEqual(bootstrap.resolve_templates(None), TEMPLATES)

    def test_the_variable_wins_over_the_default(self) -> None:
        with mock.patch.dict(os.environ, {ENV: str(self.from_env)}):
            self.assertEqual(bootstrap.resolve_templates(None), self.from_env.resolve())

    def test_the_flag_wins_over_the_variable(self) -> None:
        with mock.patch.dict(os.environ, {ENV: str(self.from_env)}):
            self.assertEqual(bootstrap.resolve_templates(str(self.explicit)), self.explicit.resolve())

    def test_an_empty_variable_falls_back_to_the_default(self) -> None:
        with mock.patch.dict(os.environ, {ENV: ""}):
            self.assertEqual(bootstrap.resolve_templates(None), TEMPLATES)

    def test_main_reports_the_templates_it_read(self) -> None:
        with mock.patch.dict(os.environ, {ENV: str(self.from_env)}):
            code, out, err = run_main([str(self.root / "t"), "--dry-run", "--name", "pkg", *IDENTITY])
            self.assertEqual(code, 0, err)
            self.assertIn(f"templates   {self.from_env.resolve()}", out)
            code, out, err = run_main(
                [str(self.root / "t"), "--dry-run", "--name", "pkg", "--templates", str(self.explicit), *IDENTITY]
            )
            self.assertEqual(code, 0, err)
            self.assertIn(f"templates   {self.explicit.resolve()}", out)


class MissingTemplatesTests(unittest.TestCase):
    def resolve_fails(self, explicit: str | None) -> str:
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            bootstrap.resolve_templates(explicit)
        self.assertEqual(raised.exception.code, 1)
        return err.getvalue()

    def test_a_missing_directory_from_the_flag_names_both_ways_to_fix_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nowhere"
            message = self.resolve_fails(str(missing))
        self.assertIn(f"template directory not found: {missing}", message)
        self.assertIn("--templates", message)
        self.assertIn(ENV, message)

    def test_a_missing_directory_from_the_variable_fails_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nowhere"
            with mock.patch.dict(os.environ, {ENV: str(missing)}):
                message = self.resolve_fails(None)
        self.assertIn(f"template directory not found: {missing}", message)

    def test_a_file_is_not_a_template_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file"
            path.write_text("", encoding="utf-8")
            self.assertIn("template directory not found", self.resolve_fails(str(path)))

    def test_a_directory_without_a_core_template_is_the_wrong_directory(self) -> None:
        for required in ("package.json", "AGENTS.md", "docs/STYLE_GUIDE.md"):
            with self.subTest(required=required), tempfile.TemporaryDirectory() as tmp:
                copy = copy_templates(Path(tmp))
                (copy / required).unlink()
                message = self.resolve_fails(str(copy))
                self.assertIn(f"is missing {required}", message)
                self.assertIn("wrong directory?", message)

    def test_main_fails_before_it_writes_anything(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            code, _, err = run_main(
                [str(target), "--name", "pkg", "--no-git", "--templates", str(Path(tmp) / "nowhere"), *IDENTITY]
            )
            self.assertEqual(code, 1)
            self.assertIn("template directory not found", err)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
