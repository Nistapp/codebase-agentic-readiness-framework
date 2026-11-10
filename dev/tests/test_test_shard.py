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
    """Each check runs for every suite in ``SUITES``, with its committed weights."""

    def suites(self) -> list[tuple[str, list[str], dict[str, float]]]:
        weights = test_shard.load_weights()
        return [
            (name, test_shard.suite_modules(root / start), weights.get(name, {}))
            for name, (root, start) in test_shard.SUITES.items()
        ]

    def test_every_suite_has_modules_and_weights(self) -> None:
        self.assertEqual(sorted(test_shard.SUITES), ["audit-tools", "dev", "engine"])
        for name, modules, weights in self.suites():
            with self.subTest(suite=name):
                self.assertGreater(len(modules), 10)
                self.assertTrue(weights, "run dev/test_shard.py --suite <suite> --measure")

    def test_every_module_is_in_exactly_one_shard(self) -> None:
        for name, modules, weights in self.suites():
            for count in range(1, 5):
                with self.subTest(suite=name, count=count):
                    shards = test_shard.assign(modules, weights, count)
                    self.assertEqual(len(shards), count)
                    assigned = [module for shard in shards for module in shard]
                    self.assertEqual(sorted(assigned), sorted(modules), "a module is missing or in two shards")

    def test_modules_in_packages_are_found_and_fixture_folders_are_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test_top.py").write_text("", encoding="utf-8")
            (root / "packs" / "agt").mkdir(parents=True)
            (root / "packs" / "__init__.py").write_text("", encoding="utf-8")
            (root / "packs" / "agt" / "__init__.py").write_text("", encoding="utf-8")
            (root / "packs" / "agt" / "test_agt.py").write_text("", encoding="utf-8")
            (root / "fixtures" / "repo" / "tests").mkdir(parents=True)
            (root / "fixtures" / "repo" / "tests" / "test_app.py").write_text("", encoding="utf-8")
            self.assertEqual(test_shard.suite_modules(root), ["test_agt", "test_top"])

    def test_a_module_without_a_weight_is_still_assigned(self) -> None:
        for name, modules, weights in self.suites():
            with self.subTest(suite=name):
                shards = test_shard.assign([*modules, "test_brand_new"], weights, 2)
                self.assertEqual(sum(shard.count("test_brand_new") for shard in shards), 1)

    def test_the_weights_name_only_modules_that_exist(self) -> None:
        # A stale weight means a module was renamed or deleted; `--measure` rewrites the suite's weights.
        self.assertEqual(sorted(set(test_shard.load_weights()) - set(test_shard.SUITES)), [])
        for name, modules, weights in self.suites():
            with self.subTest(suite=name):
                self.assertEqual(sorted(set(weights) - set(modules)), [], "run dev/test_shard.py --measure")

    def test_the_assignment_is_balanced_and_stable(self) -> None:
        for name, modules, weights in self.suites():
            with self.subTest(suite=name):
                shards = test_shard.assign(modules, weights, 2)
                self.assertEqual(shards, test_shard.assign(list(reversed(modules)), weights, 2))
                loads = [sum(weights.get(m, test_shard.DEFAULT_WEIGHT) for m in shard) for shard in shards]
                self.assertLess(max(loads) - min(loads), max(weights.values()), "the shards are out of balance")

    def test_the_shard_argument(self) -> None:
        self.assertEqual(test_shard.parse_shard("2/3"), (2, 3))
        for text in ("0/2", "3/2", "1", "a/2", "1/0", "-1/2"):
            with self.subTest(text=text), self.assertRaises(argparse.ArgumentTypeError):
                test_shard.parse_shard(text)


class LoadBeforeRun(unittest.TestCase):
    """A test may put another folder first on ``sys.path``; a module imported after it would come from there.

    ``audit/tools/tests/test_import_fixture_matrix.py`` adds the engine's tests folder, which holds modules with the
    same names as the audit tools' tests (``test_output_files``). The runner imports every module of a shard before
    any test runs, as ``unittest discover`` does, so the order of the modules cannot matter.
    """

    def setUp(self) -> None:
        self.path, self.tmp = list(sys.path), tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "tests").mkdir()
        (root / "other").mkdir()
        (root / "tests" / "test_a.py").write_text(
            "import sys, unittest\n\n\nclass A(unittest.TestCase):\n"
            f"    def test_moves_the_path(self):\n        sys.path.insert(0, {str(root / 'other')!r})\n",
            encoding="utf-8",
        )
        for folder in ("tests", "other"):
            (root / folder / "test_b.py").write_text(
                "import unittest\n\n\nclass B(unittest.TestCase):\n    def test_b(self):\n        pass\n",
                encoding="utf-8",
            )
        self.root = root

    def tearDown(self) -> None:
        sys.path[:] = self.path
        for name in ("test_a", "test_b"):
            sys.modules.pop(name, None)
        self.tmp.cleanup()

    def test_a_shard_imports_every_module_before_it_runs_one(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = test_shard.run(self.root, "tests", ["test_a", "test_b"])
        self.assertEqual(code, 0, err.getvalue())

    def test_measure_imports_every_module_before_it_times_one(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            times = test_shard.measure(self.root, "tests", ["test_a", "test_b"])
        self.assertIsNotNone(times, err.getvalue())


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
