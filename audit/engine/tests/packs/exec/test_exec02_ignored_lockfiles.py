# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC-02` finds a tracked lockfile that the walk's ignore rules hide (issue #21).

A Node repository ignores `package-lock.json` at its root and re-includes each app's lockfile with `!` lines. The
walk reads the root ignore file without its `!` lines (ADR-0006), so it left out both tracked lockfiles, and
`EXEC-02` reported "no lockfile" (`FAIL`). The rubric says a lockfile found only below the root is tracked and its
consistency is unverified (`PARTIAL`). The check now adds each tracked lockfile the walk left out. The check runs
in-process here, so coverage traces it; git builds the tracked set in a temporary repository.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.execution import check_exec02  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from audit.target import resolve_target  # noqa: E402

NODE = json.dumps({"name": "app", "dependencies": {"left-pad": "1.0.0"}}) + "\n"
LOCK = (
    json.dumps(
        {
            "name": "app",
            "lockfileVersion": 3,
            "packages": {"": {"dependencies": {"left-pad": "1.0.0"}}, "node_modules/left-pad": {"version": "1.0.0"}},
        }
    )
    + "\n"
)
IGNORE = "node_modules/\npackage-lock.json\n!apps/web/package-lock.json\n!apps/api/package-lock.json\n"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class Exec02IgnoredLockfileTests(unittest.TestCase):
    def exec02(self, files: dict[str, str]):
        """The `EXEC-02` outcome of a git repository built from ``files``, all of them staged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            self.assertEqual(_git(root, "init", "-q").returncode, 0)
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
            inventory = build_inventory(root)
            return check_exec02(
                spec=REGISTRY_BY_ID["EXEC-02"],
                target=resolve_target(root),
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )

    def test_nested_lockfiles_re_included_by_negation_are_tracked_and_unverified(self):
        files = {".gitignore": IGNORE, "package.json": NODE}
        for app in ("web", "api"):
            files |= {f"apps/{app}/package.json": NODE, f"apps/{app}/package-lock.json": LOCK}
        outcome = self.exec02(files)
        self.assertEqual(
            (outcome.verdict.value, outcome.summary, outcome.findings),
            ("PARTIAL", "consistency unverified: apps/api/package-lock.json", []),
        )

    def test_a_force_tracked_lockfile_in_node_modules_is_not_read(self):
        files = {
            ".gitignore": "package-lock.json\n",
            "package.json": NODE,
            "node_modules/dep/package-lock.json": LOCK,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            self.assertEqual(_git(root, "init", "-q").returncode, 0)
            self.assertEqual(_git(root, "add", "-A", "-f").returncode, 0)
            inventory = build_inventory(root)
            outcome = check_exec02(
                spec=REGISTRY_BY_ID["EXEC-02"],
                target=resolve_target(root),
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertTrue(outcome.summary.startswith("no lockfile: node"), outcome.summary)


if __name__ == "__main__":
    unittest.main()
