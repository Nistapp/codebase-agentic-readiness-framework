# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Nested ignore files and negation (ADR-0009): the matcher, then DOC-03, CON-03, SEC-01 and SEC-03 through it.

Every directory is built in a temp dir, never in the audit repository.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.ignore import IgnoreRule, decide, load_scoped_rules  # noqa: E402


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def rules(self, files: dict[str, str]) -> list[IgnoreRule]:
        for rel, text in files.items():
            support.write(self.root, rel, text)
        nested = [rel for rel in files if "/" in rel]
        return load_scoped_rules(self.root, nested)

    def test_a_nested_file_is_scoped_to_its_directory(self):
        rules = self.rules({".gitignore": "", "artefacts/.gitignore": "*\n"})
        self.assertTrue(decide("artefacts/notes.md", rules).ignored)
        self.assertTrue(decide("artefacts/deep/er/x", rules).ignored)
        self.assertFalse(decide("notes.md", rules).ignored)
        self.assertFalse(decide("other/notes.md", rules).ignored)

    def test_negation_re_includes_and_says_so(self):
        rules = self.rules({"artefacts/.gitignore": "*\n!README.md\n"})
        kept = decide("artefacts/README.md", rules)
        self.assertFalse(kept.ignored)
        self.assertTrue(kept.reincluded)
        self.assertTrue(decide("artefacts/other.md", rules).ignored)

    def test_a_negation_alone_is_not_a_re_inclusion(self):
        rules = self.rules({".gitignore": "!keep.txt\n"})
        self.assertFalse(decide("keep.txt", rules).reincluded)

    def test_the_last_line_and_the_deeper_file_win(self):
        rules = self.rules({".gitignore": "*.log\n", "sub/.gitignore": "!keep.log\n"})
        self.assertTrue(decide("a.log", rules).ignored)
        self.assertFalse(decide("sub/keep.log", rules).ignored)
        self.assertTrue(decide("sub/other.log", rules).ignored)

    def test_a_file_cannot_be_re_included_from_an_ignored_directory(self):
        rules = self.rules({".gitignore": "build/\n!build/keep.txt\n"})
        self.assertTrue(decide("build/keep.txt", rules).ignored)

    def test_anchoring_directory_only_and_double_star(self):
        rules = self.rules({".gitignore": "/dist\nlogs/\n**/cache\nsrc/**/gen\n*.t?t\n"})
        self.assertTrue(decide("dist", rules, is_dir=True).ignored)
        self.assertFalse(decide("pkg/dist", rules, is_dir=True).ignored)
        self.assertTrue(decide("logs/a", rules).ignored)
        self.assertFalse(decide("logs", rules).ignored)
        self.assertTrue(decide("logs", rules, is_dir=True).ignored)
        self.assertTrue(decide("a/b/cache", rules).ignored)
        self.assertTrue(decide("src/x/y/gen", rules).ignored)
        self.assertFalse(decide("lib/gen", rules).ignored)
        self.assertTrue(decide("a/b.txt", rules).ignored)
        self.assertFalse(decide("a/b.text", rules).ignored)

    def test_a_nested_file_in_a_directory_the_scan_did_not_see_is_not_read(self):
        support.write(self.root, "ghost/.gitignore", "*\n")
        self.assertEqual(load_scoped_rules(self.root, []), [])


class _Repo(unittest.TestCase):
    def build(self, files: dict[str, str], *, add_all: bool = True) -> Path:
        tmp = tempfile.mkdtemp(prefix="audit-nested-ignore-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        self.assertEqual(_git(root, "init").returncode, 0)
        if add_all:
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
        return root

    def verdicts(self, root: Path) -> dict[str, str]:
        return support.verdicts(support.run_audit(root))

    def summary(self, root: Path, check: str) -> str:
        report = support.run_audit(root)
        return next(c["summary"] for c in report["checks"] if c["id"] == check)


class ScratchDirectoryTests(_Repo):
    NESTED = {
        "README.md": "# t\n",
        "artefacts/.gitignore": "*\n!.gitignore\n!README.md\n",
        "artefacts/README.md": "# scratch\n",
    }

    def test_a_scratch_directory_that_ignores_itself_passes_doc03_and_con03(self):
        root = self.build({**self.NESTED, "artefacts/plan.md": "# plan\n"})
        verdicts = self.verdicts(root)
        self.assertEqual((verdicts["DOC-03"], verdicts["CON-03"]), ("PASS", "PASS"))
        self.assertIn("artefacts/.gitignore", self.summary(root, "DOC-03"))
        self.assertEqual(
            _git(root, "ls-files", "artefacts").stdout.split(), ["artefacts/.gitignore", "artefacts/README.md"]
        )

    def test_excluding_the_scratch_directory_does_not_hide_the_rule_that_ignores_it(self):
        root = self.build({**self.NESTED, "artefacts/plan.md": "# plan\n"})
        report = support.run_audit(root, extra_args=("--exclude", "artefacts/**"))
        verdicts = support.verdicts(report)
        self.assertEqual((verdicts["DOC-03"], verdicts["CON-03"]), ("PASS", "PASS"))

    def test_the_directorys_own_ignore_file_counts_when_it_does_not_re_include_itself(self):
        root = self.build({"README.md": "# t\n", "artefacts/.gitignore": "*\n"}, add_all=False)
        self.assertEqual(_git(root, "add", "-f", "artefacts/.gitignore").returncode, 0)
        verdicts = self.verdicts(root)
        self.assertEqual((verdicts["DOC-03"], verdicts["CON-03"]), ("PASS", "PASS"))

    def test_a_tracked_scratch_file_the_ignore_file_does_not_re_include_still_fails(self):
        root = self.build(self.NESTED)
        support.write(root, "artefacts/plan.md", "# plan\n")
        self.assertEqual(_git(root, "add", "-f", "artefacts/plan.md").returncode, 0)
        verdicts = self.verdicts(root)
        self.assertEqual((verdicts["DOC-03"], verdicts["CON-03"]), ("FAIL", "FAIL"))

    def test_an_ignore_file_that_covers_nothing_leaves_the_directory_uncovered(self):
        root = self.build(
            {"README.md": "# t\n", "artefacts/.gitignore": "*.tmp\n", "artefacts/a.md": "x\n"}, add_all=False
        )
        self.assertEqual(self.verdicts(root)["DOC-03"], "FAIL")

    def test_without_git_the_parser_still_credits_the_nested_rule_but_cannot_clear_tracking(self):
        tmp = tempfile.mkdtemp(prefix="audit-nested-ignore-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        root = Path(tmp)
        for rel, text in {**self.NESTED, "artefacts/plan.md": "x\n"}.items():
            support.write(root, rel, text)
        verdicts = self.verdicts(root)
        self.assertEqual((verdicts["DOC-03"], verdicts["CON-03"]), ("UNKNOWN", "UNKNOWN"))


class SecretShapeTests(_Repo):
    SHAPES = ".env\n.env.*\n!.env.example\n*.pem\n*.key\n*.p12\n*.pfx\n*.keystore\nid_rsa*\n*.crt\n*.cer\n.aws/*\n"

    def sec03(self, extra: str, nested: dict[str, str] | None = None) -> tuple[str, str]:
        root = self.build({"app.py": "x = 1\n", ".gitignore": self.SHAPES + extra, **(nested or {})})
        report = support.run_audit(root)
        check = next(c for c in report["checks"] if c["id"] == "SEC-03")
        return check["verdict"], check["summary"]

    def test_an_exception_for_another_name_leaves_the_shape_covered(self):
        verdict, _ = self.sec03("!public.crt\n")
        self.assertEqual(verdict, "PASS")

    def test_an_exception_for_the_shape_itself_uncovers_it(self):
        verdict, summary = self.sec03("!server.crt\n")
        self.assertEqual(verdict, "PARTIAL")
        self.assertIn("certificate (.crt)", summary)

    def test_a_shape_ignored_only_by_a_nested_file_is_not_credited_at_the_root(self):
        root = self.build({"app.py": "x = 1\n", ".gitignore": "", "pkg/.gitignore": self.SHAPES})
        report = support.run_audit(root)
        check = next(c for c in report["checks"] if c["id"] == "SEC-03")
        self.assertNotEqual(check["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
