# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``new_check.py``: it refuses what it cannot scaffold, and its stubs fail the gate's tests.

The scaffold runs in a temporary copy of the sources it touches, never in this checkout. There, the catalogue test
and the fixture matrix test name the stub check as unfinished, and :func:`new_check.stubs_left` names each stub file.
In this checkout, no stub is left.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import new_check
from _dev_paths import REPO

STUB_ID = "SEC-04"
STUB_FIXTURE = "sec-04-stub"
MATRIX_RUN = (
    "import unittest, test_fixture_matrix as m\n"
    "keep = {name: row for name, row in m.MATRIX.items() if name == %r}\n"
    "m.MATRIX.clear()\n"
    "m.MATRIX.update(keep)\n"
    "test = m.FixtureMatrixTests('test_each_fixture_reports_its_documented_verdict_and_names_every_finding_once')\n"
    "result = unittest.TextTestRunner(verbosity=0).run(test)\n"
    "raise SystemExit(0 if result.wasSuccessful() and keep else 1)\n"
)


def copy_sources(root: Path) -> None:
    """The folders the scaffold and the tests it trips read: the audit folder, the spec and two dev scripts."""
    ignore = shutil.ignore_patterns("__pycache__", "dist", "*.pyc")
    shutil.copytree(REPO / "audit", root / "audit", symlinks=True, ignore=ignore)
    shutil.copytree(REPO / "spec", root / "spec", ignore=ignore)
    (root / "dev").mkdir()
    for script in ("new_check.py", "build_catalogue.py"):
        shutil.copy(REPO / "dev" / script, root / "dev" / script)


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *argv], cwd=str(cwd), text=True, capture_output=True, check=False)


class ThisCheckout(unittest.TestCase):
    def test_no_scaffold_stub_is_left(self) -> None:
        self.assertEqual(new_check.stubs_left(REPO), [], "finish or remove these new-check stubs")


class Refusals(unittest.TestCase):
    """Each refusal writes nothing: the copy stays as it was."""

    root: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(tempfile.mkdtemp())
        copy_sources(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.root)

    def run_main(self, *argv: str) -> tuple[int, str]:
        before = (self.root / new_check.OVERLAY).read_bytes()
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = new_check.main(list(argv), root=self.root)
        self.assertEqual((self.root / new_check.OVERLAY).read_bytes(), before)
        self.assertEqual(new_check.stubs_left(self.root), [])
        return code, err.getvalue()

    def test_a_malformed_id_is_bad_input(self) -> None:
        self.assertEqual(self.run_main("--id", "sec-4", "--title", "x")[0], 1)

    def test_a_title_with_a_pipe_is_bad_input(self) -> None:
        self.assertEqual(self.run_main("--id", STUB_ID, "--title", "a | b")[0], 1)

    def test_a_family_that_is_one_module_is_refused(self) -> None:
        code, err = self.run_main("--id", "AGT-14", "--title", "A new check")
        self.assertEqual(code, 2)
        self.assertIn("the AGT family is still one module", err)

    def test_a_taken_id_is_refused(self) -> None:
        code, err = self.run_main("--id", "SEC-03", "--title", "A new check")
        self.assertEqual(code, 2)
        self.assertIn("SEC-03 is taken", err)

    def test_a_number_below_the_last_of_its_family_is_refused(self) -> None:
        code, err = self.run_main("--id", "HYG-12", "--title", "A new check")
        self.assertEqual(code, 2)
        self.assertIn("take the next free number in HYG, above 13", err)

    def test_a_family_with_no_engine_package_is_refused(self) -> None:
        code, err = self.run_main("--id", "ZZZ-01", "--title", "A new check")
        self.assertEqual(code, 2)
        self.assertIn("no engine package", err)


class ScaffoldInACopy(unittest.TestCase):
    """The scaffold writes its stubs in a copy, and the gate's tests then name them as unfinished."""

    root: Path
    scaffold: subprocess.CompletedProcess[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(tempfile.mkdtemp())
        copy_sources(cls.root)
        argv = ["dev/new_check.py", "--id", STUB_ID, "--title", "A stub check", "--date", "2026-01-01"]
        cls.scaffold = run(argv, cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.root)

    def test_it_writes_the_stubs_and_prints_what_is_left(self) -> None:
        self.assertEqual(self.scaffold.returncode, 0, self.scaffold.stderr)
        self.assertIn(f"wrote the stubs of {STUB_ID}", self.scaffold.stdout)
        self.assertIn("Still to write:", self.scaffold.stdout)
        self.assertIn("spec/traceability.md", self.scaffold.stdout)

    def test_every_stub_is_named_as_unfinished(self) -> None:
        self.assertEqual(
            new_check.stubs_left(self.root),
            [
                "audit/engine/audit/rules/checks/sec/sec_04.py",
                f"audit/engine/tests/fixtures/{STUB_FIXTURE}/NEW-CHECK-STUB.md",
                "audit/engine/tests/packs/sec/matrix.py",
                "audit/checks/12-security-hygiene.md",
                "audit/catalogue-overlay.json",
                "audit/engine/docs/reference/changelog.md",
            ],
        )

    def test_the_catalogue_is_regenerated_with_the_stub(self) -> None:
        self.assertEqual(run(["dev/build_catalogue.py", "--check"], self.root).returncode, 0)
        catalogue = json.loads((self.root / new_check.CATALOGUE).read_text(encoding="utf-8"))
        ids = [check["id"] for check in catalogue["checks"]]
        self.assertEqual(ids[ids.index("SEC-03") + 1], STUB_ID)

    def test_the_catalogue_test_names_the_stub(self) -> None:
        proc = run(["-m", "unittest", "discover", "-s", "audit/tools/tests", "-p", "test_catalogue.py"], self.root)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(STUB_ID, proc.stderr)

    def test_the_fixture_matrix_test_names_the_stub(self) -> None:
        proc = run(["-c", MATRIX_RUN % STUB_FIXTURE], self.root / "audit" / "engine" / "tests")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn(f"{STUB_FIXTURE}: {STUB_ID} expected FAIL", proc.stderr)


if __name__ == "__main__":
    unittest.main()
