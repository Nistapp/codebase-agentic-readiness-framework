# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``skip_census.py``: what counts as a skip marker, the ratchet and the record verb."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import skip_census  # noqa: E402

REPO = Path(__file__).resolve().parents[2]

_TWO_SKIPS = textwrap.dedent(
    """\
    import unittest


    class T(unittest.TestCase):
        @unittest.skipIf(True, "why")
        def test_a(self):
            pass

        def test_b(self):
            self.skipTest("why")
    """
)


def _repo(tmp: str, source: str, baseline: int | None) -> Path:
    """A scratch repository with one test module in ``dev/tests`` and, when given, a skips baseline."""
    root = Path(tmp)
    (root / "dev" / "tests").mkdir(parents=True)
    (root / "dev" / "tests" / "test_x.py").write_text(source, encoding="utf-8")
    counts: dict[str, object] = {"ruff": {"count": 0}}
    if baseline is not None:
        counts["skips"] = {"count": baseline}
    (root / ".quality-baseline.json").write_text(json.dumps({"counts": counts}, indent=2) + "\n", encoding="utf-8")
    return root


def _run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = skip_census.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Markers(unittest.TestCase):
    def kinds(self, source: str) -> list[str]:
        return [m.kind for m in skip_census.markers_in(textwrap.dedent(source), "t.py")]

    def test_each_unittest_form_counts(self) -> None:
        source = """\
            import unittest
            from unittest import skip


            @unittest.skipUnless(False, "x")
            class A(unittest.TestCase):
                @skip("x")
                def test_a(self): ...

                @unittest.expectedFailure
                def test_b(self): ...

                def test_c(self):
                    self.skipTest("x")

                def test_d(self):
                    raise unittest.SkipTest("x")
            """
        self.assertEqual(
            sorted(self.kinds(source)),
            sorted(["@skipUnless", "@skip", "@expectedFailure", ".skipTest()", "raise SkipTest"]),
        )

    def test_pytest_forms_count(self) -> None:
        source = """\
            import pytest


            @pytest.mark.xfail
            def test_a(): ...


            @pytest.mark.skipif(True, reason="x")
            def test_b(): ...


            def test_c():
                pytest.skip("x")
            """
        self.assertEqual(sorted(self.kinds(source)), sorted(["@xfail", "@skipif", "pytest.skip()"]))

    def test_a_marker_inside_a_string_does_not_count(self) -> None:
        source = '''\
            FIXTURE = """
            @unittest.skip("flaky")
            def test_low(self):
                self.skipTest("x")
            """


            def skip_helper(skip=True):
                return "skip"
            '''
        self.assertEqual(self.kinds(source), [])

    def test_fixtures_folders_are_left_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "x = 1\n", baseline=0)
            fixture = root / "dev" / "tests" / "fixtures" / "case"
            fixture.mkdir(parents=True)
            (fixture / "test_y.py").write_text(_TWO_SKIPS, encoding="utf-8")
            self.assertEqual(skip_census.census(root), [])


class Check(unittest.TestCase):
    def test_a_planted_extra_skip_fails_and_lists_the_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, _TWO_SKIPS, baseline=1)
            code, out, err = _run("check", "--root", str(root))
        self.assertEqual(code, 1)
        self.assertIn("2 skip markers", err)
        self.assertIn("allows 1", err)
        self.assertIn("dev/tests/test_x.py:5: @skipIf", err)
        self.assertEqual(out, "")

    def test_an_equal_count_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, _TWO_SKIPS, baseline=2)
            code, out, _ = _run("check", "--root", str(root))
        self.assertEqual(code, 0)
        self.assertIn("holds at 2", out)

    def test_a_lower_count_passes_and_asks_for_a_lower_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, _TWO_SKIPS, baseline=5)
            code, out, _ = _run("check", "--root", str(root))
        self.assertEqual(code, 0)
        self.assertIn("down to 2", out)
        self.assertIn("make update-skip-baseline", out)

    def test_a_missing_entry_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, _TWO_SKIPS, baseline=None)
            code, _, err = _run("check", "--root", str(root))
        self.assertEqual(code, 2)
        self.assertIn("record", err)

    def test_a_file_that_does_not_parse_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "def (:\n", baseline=0)
            code, _, err = _run("check", "--root", str(root))
        self.assertEqual(code, 2)
        self.assertIn("cannot read a test file", err)


class Record(unittest.TestCase):
    def stored(self, root: Path) -> dict[str, Any]:
        data = json.loads((root / ".quality-baseline.json").read_text(encoding="utf-8"))
        counts: dict[str, Any] = data["counts"]
        return counts

    def test_record_creates_the_entry_and_keeps_the_others(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, _TWO_SKIPS, baseline=None)
            code, out, _ = _run("record", "--root", str(root))
            counts = self.stored(root)
        self.assertEqual(code, 0)
        self.assertIn("recorded 2", out)
        self.assertEqual(counts["ruff"], {"count": 0})
        self.assertEqual(counts["skips"]["count"], 2)

    def test_record_lowers_the_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, _TWO_SKIPS, baseline=5)
            code, _, _ = _run("record", "--root", str(root))
            self.assertEqual(code, 0)
            self.assertEqual(self.stored(root)["skips"]["count"], 2)

    def test_record_refuses_to_raise_the_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, _TWO_SKIPS, baseline=1)
            before = (root / ".quality-baseline.json").read_text(encoding="utf-8")
            code, _, err = _run("record", "--root", str(root))
            after = (root / ".quality-baseline.json").read_text(encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertIn("needs the owner", err)
        self.assertEqual(before, after)


class ThisRepository(unittest.TestCase):
    def test_the_test_trees_hold_no_more_skips_than_the_baseline(self) -> None:
        found = skip_census.census(REPO)
        baseline = skip_census.load_count(REPO / ".quality-baseline.json")
        if baseline is None:
            self.fail(".quality-baseline.json has no counts.skips entry; run `make update-skip-baseline`")
        listing = "\n".join(f"{m.path}:{m.line}: {m.kind}" for m in found)
        self.assertLessEqual(len(found), baseline, f"new skip markers; never skip a test to get green:\n{listing}")


if __name__ == "__main__":
    unittest.main()
