# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""``dev/test_shard.py`` puts every test module in exactly one shard and fails a shard that runs nothing.

CI runs the engine's suite in shards. A module that falls out of every shard would never run in CI, and nothing else
would notice, so these tests check the assignment for the real suite and the committed weights.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import test_shard


class Assignment(unittest.TestCase):
    def setUp(self) -> None:
        root, start = test_shard.SUITES["engine"]
        self.modules = test_shard.suite_modules(root / start)
        self.weights = test_shard.load_weights()["engine"]

    def test_the_engine_suite_has_modules(self) -> None:
        self.assertGreater(len(self.modules), 10)

    def test_every_module_is_in_exactly_one_shard(self) -> None:
        for count in range(1, 5):
            with self.subTest(count=count):
                shards = test_shard.assign(self.modules, self.weights, count)
                self.assertEqual(len(shards), count)
                assigned = [module for shard in shards for module in shard]
                self.assertEqual(sorted(assigned), sorted(self.modules), "a module is missing or in two shards")

    def test_a_module_without_a_weight_is_still_assigned(self) -> None:
        modules = [*self.modules, "test_brand_new"]
        shards = test_shard.assign(modules, self.weights, 2)
        self.assertEqual(sum(shard.count("test_brand_new") for shard in shards), 1)

    def test_the_weights_name_only_modules_that_exist(self) -> None:
        # A stale weight means a module was renamed or deleted; `--measure` rewrites the file.
        self.assertEqual(sorted(set(self.weights) - set(self.modules)), [], "run dev/test_shard.py --measure")
        self.assertEqual(sorted(set(test_shard.load_weights()) - set(test_shard.SUITES)), [])

    def test_the_assignment_is_balanced_and_stable(self) -> None:
        shards = test_shard.assign(self.modules, self.weights, 2)
        self.assertEqual(shards, test_shard.assign(list(reversed(self.modules)), self.weights, 2))
        loads = [sum(self.weights.get(m, test_shard.DEFAULT_WEIGHT) for m in shard) for shard in shards]
        self.assertLess(max(loads) - min(loads), max(self.weights.values()), "the shards are out of balance")

    def test_the_shard_argument(self) -> None:
        self.assertEqual(test_shard.parse_shard("2/3"), (2, 3))
        for text in ("0/2", "3/2", "1", "a/2", "1/0", "-1/2"):
            with self.subTest(text=text), self.assertRaises(argparse.ArgumentTypeError):
                test_shard.parse_shard(text)


class EmptyShard(unittest.TestCase):
    def test_a_shard_with_no_module_fails(self) -> None:
        cwd, path = os.getcwd(), list(sys.path)
        try:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = test_shard.main(["--suite", "engine", "--shard", "500/500"])
        finally:
            os.chdir(cwd)
            sys.path[:] = path
        self.assertEqual(code, 1)
        self.assertIn("hold no test", err.getvalue())

    def test_a_shard_whose_modules_hold_no_test_fails(self) -> None:
        path = list(sys.path)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            (Path(tmp) / "tests" / "test_nothing.py").write_text("X = 1\n", encoding="utf-8")
            try:
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    code = test_shard.run(Path(tmp), "tests", ["test_nothing"])
            finally:
                sys.path[:] = path
                sys.modules.pop("test_nothing", None)
        self.assertEqual(code, 1)
        self.assertIn("hold no test", err.getvalue())


if __name__ == "__main__":
    unittest.main()
