# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The scaffolder's input checks: package names, the Node version, the scoped name, the target and `--dry-run`.

A bad input exits 1 with a message on stderr and writes nothing. Standard library only.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from _bootstrap_support import IDENTITY, TEMPLATES, bootstrap, run_main


def refused(function: object, value: str) -> tuple[int | str | None, str]:
    """Call a validator that must refuse ``value``; return its exit code and its message."""
    assert callable(function)
    err = io.StringIO()
    with redirect_stderr(err):
        try:
            function(value)
        except SystemExit as exc:
            return exc.code, err.getvalue()
    raise AssertionError(f"{value!r} was accepted")


class PackageNameTests(unittest.TestCase):
    def test_valid_names_are_returned_unchanged(self) -> None:
        for name in ("my-pkg", "a", "pkg.js", "a~b", "a_b", "0x", "@scope/pkg", "@my-org/my.pkg", "x" * 214):
            with self.subTest(name=name):
                self.assertEqual(bootstrap.validate_package_name(name), name)

    def test_invalid_names_exit_1_with_a_reason(self) -> None:
        cases = {
            "My-Pkg": "lowercase",
            "@Scope/pkg": "lowercase",
            "x" * 215: "214-character",
            ".hidden": "invalid package name",
            "_private": "invalid package name",
            "has space": "invalid package name",
            "a/b": "contains '/'",
            "@scope": "must be '@scope/name'",
            "@/pkg": "invalid scope",
            "@scope/": "invalid name",
            "@scope/.pkg": "invalid name",
            "@.scope/pkg": "invalid scope",
            "": "invalid package name",
        }
        for name, reason in cases.items():
            with self.subTest(name=name):
                code, message = refused(bootstrap.validate_package_name, name)
                self.assertEqual(code, 1)
                self.assertIn(reason, message)


class NodeVersionTests(unittest.TestCase):
    def test_a_major_version_is_accepted(self) -> None:
        for value in ("8", "24", "99"):
            with self.subTest(value=value):
                self.assertEqual(bootstrap.validate_node_version(value), value)

    def test_anything_but_a_major_version_exits_1(self) -> None:
        for value in ("", "v24", "24.1", "124", "lts"):
            with self.subTest(value=value):
                code, message = refused(bootstrap.validate_node_version, value)
                self.assertEqual(code, 1)
                self.assertIn("major version", message)

    def test_main_refuses_a_bad_node_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_main([tmp, "--dry-run", "--name", "pkg", "--node", "v24", *IDENTITY])
        self.assertEqual(code, 1)
        self.assertIn("--node 'v24'", err)


class PrettyNameTests(unittest.TestCase):
    def test_the_bare_name_becomes_title_case_words(self) -> None:
        self.assertEqual(bootstrap.pretty_name("@acme/my-cool_pkg.js"), "My Cool Pkg Js")
        self.assertEqual(bootstrap.pretty_name("pkg"), "Pkg")
        self.assertEqual(bootstrap.pretty_name("a--b"), "A B")


class ArgumentParsingTests(unittest.TestCase):
    def test_defaults(self) -> None:
        args = bootstrap.parse_args([])
        self.assertEqual(args.target, ".")
        self.assertEqual(args.node_version, "24")
        self.assertFalse(args.with_cli)
        self.assertFalse(args.with_infra)
        self.assertTrue(args.git)
        self.assertTrue(args.verify)
        self.assertFalse(args.install)
        self.assertFalse(args.dry_run)
        self.assertFalse(args.force)
        self.assertIsNone(args.templates)

    def test_the_last_of_cli_and_lib_wins(self) -> None:
        self.assertTrue(bootstrap.parse_args(["--lib", "--cli"]).with_cli)
        self.assertFalse(bootstrap.parse_args(["--cli", "--lib"]).with_cli)

    def test_negative_flags(self) -> None:
        args = bootstrap.parse_args(["--no-git", "--no-verify"])
        self.assertFalse(args.git)
        self.assertFalse(args.verify)


class ResolvedNameTests(unittest.TestCase):
    """How `--name`, `--org` and the target directory make the package name (read from the dry-run header)."""

    def header_name(self, *argv: str, target: str = "my-target") -> str:
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_main([str(Path(tmp) / target), "--dry-run", *IDENTITY, *argv])
        self.assertEqual(code, 0, err)
        first = next(line for line in out.splitlines() if "agentic bootstrap" in line)
        return first.rsplit("·", 1)[-1].strip()

    def test_the_target_directory_names_the_package_by_default(self) -> None:
        self.assertEqual(self.header_name(), "my-target")

    def test_name_and_org_make_a_scoped_name(self) -> None:
        self.assertEqual(self.header_name("--name", "pkg", "--org", "acme"), "@acme/pkg")

    def test_a_scoped_name_ignores_org(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run_main([tmp, "--dry-run", "--name", "@x/y", "--org", "z", *IDENTITY])
        self.assertEqual(code, 0)
        self.assertIn("already scoped; ignoring --org", out)
        self.assertIn("agentic bootstrap  ·  @x/y", out)

    def test_an_invalid_resolved_name_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_main([tmp, "--dry-run", "--name", "Bad", *IDENTITY])
        self.assertEqual(code, 1)
        self.assertIn("must be lowercase", err)


class TargetTests(unittest.TestCase):
    def test_a_non_empty_target_is_refused_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "keep.txt").write_text("mine\n", encoding="utf-8")
            code, _, err = run_main([tmp, "--name", "pkg", "--no-git", *IDENTITY])
            self.assertEqual(code, 1)
            self.assertIn("is not empty", err)
            self.assertIn("--force", err)
            self.assertEqual(sorted(p.name for p in target.iterdir()), ["keep.txt"])
            self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "mine\n")

    def test_force_writes_into_a_non_empty_target_and_keeps_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "keep.txt").write_text("mine\n", encoding="utf-8")
            code, _, err = run_main([tmp, "--name", "pkg", "--no-git", "--force", *IDENTITY])
            self.assertEqual(code, 0, err)
            self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "mine\n")
            self.assertTrue((target / "package.json").is_file())


class DryRunTests(unittest.TestCase):
    def test_dry_run_into_a_missing_directory_creates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "new"
            code, out, err = run_main([str(target), "--dry-run", "--name", "pkg", *IDENTITY])
            self.assertEqual(code, 0, err)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertIn("plan (dry run, nothing written)", out)

    def test_dry_run_into_an_empty_directory_leaves_it_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_main([tmp, "--dry-run", "--name", "pkg", "--cli", "--with-infra", *IDENTITY])
            self.assertEqual(code, 0, err)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_dry_run_lists_every_planned_target_path(self) -> None:
        plan = bootstrap.build_plan(TEMPLATES, with_cli=False, with_infra=False)
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run_main([tmp, "--dry-run", "--name", "pkg", *IDENTITY])
        self.assertEqual(code, 0)
        listed = [line.strip() for line in out.split("plan (dry run, nothing written):", 1)[1].splitlines()]
        self.assertEqual([line for line in listed if line], [rel for _, rel in plan])
        self.assertIn(f"files       {len(plan) + 2} ({len(plan)} from templates, 2 .gitkeep)", out)


if __name__ == "__main__":
    unittest.main()
