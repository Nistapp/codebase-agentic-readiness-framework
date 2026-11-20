# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""One root README finder for every check (issue #6).

HYG-01 found a root ``README`` with no extension while EXEC-03, EXEC-06, TST-04 and the BASE checks looked for
``README.md`` only, so one report said the README both existed and did not. They now share
:func:`audit.rules.checks._common.root_readme`.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks._common import README, at_root, entry_documents, root_readme  # noqa: E402
from audit.scan import build_inventory  # noqa: E402


def _inventory(files: dict[str, str]):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        return build_inventory(root)


class RootReadmeTests(unittest.TestCase):
    def test_readme_md_comes_first_in_any_case(self):
        self.assertEqual(root_readme(_inventory({"README": "x", "readme.MD": "x", "README.rst": "x"})), "readme.MD")

    def test_without_readme_md_the_lowest_name_wins(self):
        self.assertEqual(root_readme(_inventory({"README.rst": "x", "README": "x"})), "README")

    def test_a_readme_below_the_root_is_not_the_root_readme(self):
        self.assertIsNone(root_readme(_inventory({"docs/README.md": "x", "src/a.py": "x"})))

    def test_entry_documents_name_the_readme_by_its_own_name_and_keep_every_other_name(self):
        inventory = _inventory({"README": "x"})
        self.assertEqual(entry_documents(inventory, (README, "AGENTS.md")), ["README", "AGENTS.md"])
        self.assertEqual(entry_documents(_inventory({}), (README,)), ["README.md"])

    def test_at_root_refuses_a_copy_below_the_root(self):
        inventory = _inventory({"packages/app/README.md": "x", "AGENTS.md": "x"})
        self.assertTrue(inventory.has("README.md"))
        self.assertFalse(at_root(inventory, "README.md"))
        self.assertTrue(at_root(inventory, "AGENTS.md"))


class ReadmeVerdictTests(unittest.TestCase):
    def test_exec_06_reads_the_fences_of_a_readme_with_no_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            support.write(root, "package.json", '{"name": "x", "version": "0.0.0", "scripts": {"lint": "eslint ."}}\n')
            support.write(root, "README", "# x\n\n```bash\nnpm run not-a-script\n```\n")
            report = support.run_audit(root)
        check = next(c for c in report["checks"] if c["id"] == "EXEC-06")
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("not-a-script", check["summary"])

    def test_tst_04_does_not_cite_a_readme_that_exists_only_below_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            support.write(root, "pyproject.toml", '[project]\nname = "x"\nversion = "0"\n')
            support.write(root, "tests/test_a.py", "def test_a():\n    assert True\n")
            support.write(root, "packages/app/README.md", "# app\n\n```bash\npytest -k test_a\n```\n")
            report = support.run_audit(root)
        check = next(c for c in report["checks"] if c["id"] == "TST-04")
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("(none present)", check["summary"])
        cited = [e["path"] for f in report["findings"] if f["check"] == "TST-04" for e in f["evidence"]]
        self.assertNotIn("README.md", cited)


if __name__ == "__main__":
    unittest.main()
