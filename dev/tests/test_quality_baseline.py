# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``quality_baseline.py``: the parsers, the comparison and the exit codes."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import quality_baseline  # noqa: E402


def _baseline(directory: str, **counts: int) -> Path:
    path = Path(directory) / "baseline.json"
    path.write_text(json.dumps({"counts": {k: {"count": v} for k, v in counts.items()}}), encoding="utf-8")
    return path


def _emit(text: str) -> list[str]:
    """A command that prints ``text`` and exits 1, like a linter that found violations."""
    return [sys.executable, "-c", f"import sys; sys.stdout.write({text!r}); sys.exit(1)"]


class Parsers(unittest.TestCase):
    def test_ruff_counts_diagnostics(self) -> None:
        self.assertEqual(quality_baseline.count_ruff("[]"), 0)
        self.assertEqual(quality_baseline.count_ruff('[{"code":"F401"},{"code":"E402"}]'), 2)

    def test_ruff_rejects_non_list(self) -> None:
        with self.assertRaises(ValueError):
            quality_baseline.count_ruff("{}")

    def test_mypy_counts_errors_not_notes(self) -> None:
        out = "a.py:1: error: x  [misc]\na.py:1: note: y\nb.py:2: error: z  [misc]\nFound 2 errors in 2 files\n"
        self.assertEqual(quality_baseline.count_mypy(out), 2)
        self.assertEqual(quality_baseline.count_mypy("Success: no issues found in 3 source files\n"), 0)

    def test_markdownlint_summary(self) -> None:
        self.assertEqual(
            quality_baseline.count_markdownlint("Linting: 3 files\nSummary: 735 issues in 88 files\n"), 735
        )
        self.assertEqual(quality_baseline.count_markdownlint("Summary: 1 issue in 1 file\n"), 1)
        self.assertEqual(quality_baseline.count_markdownlint("Linting: 3 files\nSummary: 0 error(s)\n"), 0)

    def test_markdownlint_without_summary_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            quality_baseline.count_markdownlint("npm ERR! network\n")

    def test_prose_is_advisory_and_has_no_count(self) -> None:
        self.assertNotIn("prose", quality_baseline.TOOLS)
        self.assertNotIn("prose", quality_baseline.PARSERS)


class Compare(unittest.TestCase):
    def test_up_fails_naming_the_tool(self) -> None:
        code, message = quality_baseline.compare("ruff", 3, 2)
        self.assertEqual(code, 1)
        self.assertIn("ruff", message)
        self.assertIn("3", message)

    def test_equal_passes(self) -> None:
        self.assertEqual(quality_baseline.compare("mypy", 0, 0)[0], 0)

    def test_down_passes_and_asks_for_a_lower_baseline(self) -> None:
        code, message = quality_baseline.compare("markdownlint", 700, 735)
        self.assertEqual(code, 0)
        self.assertIn("Lower", message)


class Main(unittest.TestCase):
    def test_count_above_baseline_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _baseline(tmp, mypy=0)
            argv = ["check", "mypy", "--baseline", str(path), "--", *_emit("a.py:1: error: x\n")]
            self.assertEqual(quality_baseline.main(argv), 1)

    def test_count_at_baseline_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _baseline(tmp, mypy=1)
            argv = ["check", "mypy", "--baseline", str(path), "--", *_emit("a.py:1: error: x\n")]
            self.assertEqual(quality_baseline.main(argv), 0)

    def test_missing_entry_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _baseline(tmp, ruff=0)
            argv = ["check", "mypy", "--baseline", str(path), "--", *_emit("")]
            self.assertEqual(quality_baseline.main(argv), 2)

    def test_unrunnable_command_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _baseline(tmp, ruff=0)
            argv = ["check", "ruff", "--baseline", str(path), "--", "no-such-tool-for-quality-baseline"]
            self.assertEqual(quality_baseline.main(argv), 2)

    def test_unreadable_output_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _baseline(tmp, markdownlint=0)
            argv = ["check", "markdownlint", "--baseline", str(path), "--", *_emit("boom")]
            self.assertEqual(quality_baseline.main(argv), 2)

    def test_no_command_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _baseline(tmp, ruff=0)
            self.assertEqual(quality_baseline.main(["check", "ruff", "--baseline", str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
