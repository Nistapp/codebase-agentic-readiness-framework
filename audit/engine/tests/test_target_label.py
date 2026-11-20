# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`--target-label` writes a neutral `provenance.target`, so a committed report names no local folder (issue #49)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.cli import AuditUsageError, build_parser, check_target_label  # noqa: E402
from audit.evaluate import provenance  # noqa: E402
from audit.target import resolve_target  # noqa: E402


class TargetLabelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target = resolve_target(support.fixture("cmd-ok-make"))

    def test_without_the_option_the_target_is_the_absolute_path(self) -> None:
        args = build_parser().parse_args([str(self.target.path)])
        self.assertIsNone(args.target_label)
        self.assertEqual(provenance(self.target, args)["target"], str(self.target.path))

    def test_the_label_replaces_the_path(self) -> None:
        args = build_parser().parse_args([str(self.target.path), "--target-label", "."])
        record = provenance(self.target, args)
        self.assertEqual(record["target"], ".")
        self.assertEqual(record["git_sha"], self.target.git_sha)

    def test_a_label_that_is_empty_too_long_or_holds_a_control_character_is_refused(self) -> None:
        for label, message in (
            ("", "must not be empty"),
            ("  ", "must not be empty"),
            ("x" * 201, "at most 200 characters"),
            ("a\nb", "control character"),
            ("a\x7fb", "control character"),
        ):
            with self.subTest(label=label), self.assertRaisesRegex(AuditUsageError, message):
                check_target_label(label)
        check_target_label(None)
        check_target_label("<repository>")

    def test_a_run_with_the_label_writes_it_and_changes_nothing_else(self) -> None:
        target = support.fixture("cmd-ok-make")
        plain = support.run_audit(target)
        labelled = support.run_audit(target, extra_args=("--target-label", "."))
        self.assertEqual(labelled["provenance"]["target"], ".")
        self.assertNotIn(str(target.resolve()), str(labelled))
        self.assertEqual(support.verdicts(plain), support.verdicts(labelled))
        self.assertEqual(plain["findings"], labelled["findings"])

    def test_a_bad_label_is_a_usage_error_before_anything_is_written(self) -> None:
        proc, out = support.run_audit_process(support.fixture("cmd-ok-make"), extra_args=("--target-label", ""))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--target-label must not be empty", proc.stderr)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
