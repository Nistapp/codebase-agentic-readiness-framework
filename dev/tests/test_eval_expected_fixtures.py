# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture corpus's expected files agree with the engine's own matrix (S4.2.1).

``tools/eval/generate_fixture_expected.py`` wrote one ``schema/examples/eval-expected/fixtures/<fixture>.json``
per row of the engine's ``tests/test_fixture_matrix.py`` (``MATRIX``), running the real engine on a throwaway,
deterministically-committed copy of each fixture. Running the engine 89 times is too slow for this suite, so
this test does not regenerate anything — it loads the committed files and checks them against the matrix and
the expected-results schema directly. Regenerate with the script above after a matrix change. Standard
library only.
"""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from types import ModuleType

import _paths

TOOLS = _paths.TOOLS

import _jsonschema_subset as subset  # noqa: E402

RECIPES = TOOLS.parent
FIXTURES_DIR = RECIPES / "schema" / "examples" / "eval-expected" / "fixtures"
SCHEMA = json.loads((RECIPES / "schema" / "eval-expected.schema.json").read_text(encoding="utf-8"))


def engine_matrix() -> ModuleType:
    """The engine's own `test_fixture_matrix` module, which holds `MATRIX`."""
    eval_dir = str(TOOLS / "eval")
    if eval_dir not in sys.path:
        sys.path.insert(0, eval_dir)
    import engine as launcher

    launcher.load_engine()
    tests_dir = str(launcher.ENGINE_DIR / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    return importlib.import_module("test_fixture_matrix")


class EvalExpectedFixturesTests(unittest.TestCase):
    matrix: ModuleType
    validator: subset.SubsetValidator

    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = engine_matrix()
        cls.validator = subset.SubsetValidator(SCHEMA)

    def non_empty_fixtures(self) -> dict[str, dict[str, str]]:
        return {name: row for name, row in self.matrix.MATRIX.items() if row}

    def test_every_matrix_fixture_has_an_expected_file(self) -> None:
        declared = set(self.non_empty_fixtures())
        on_disk = {p.stem for p in FIXTURES_DIR.glob("*.json")}
        self.assertEqual(declared - on_disk, set(), "matrix fixtures with no expected file")
        self.assertEqual(on_disk - declared, set(), "expected files naming a fixture the matrix does not have")

    def test_every_expected_file_validates_and_agrees_with_the_matrix(self) -> None:
        for name, row in self.non_empty_fixtures().items():
            with self.subTest(fixture=name):
                path = FIXTURES_DIR / f"{name}.json"
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(self.validator.validate(document), [])
                self.assertEqual(document["repo_label"], name)
                checks = {entry["id"]: entry["acceptable_verdicts"] for entry in document["checks"]}
                self.assertEqual(set(checks), set(row), f"{name}: checks do not match the matrix row")
                for check_id, expected_verdict in row.items():
                    self.assertEqual(checks[check_id], [expected_verdict], f"{name}: {check_id}")

    def test_every_repo_sha_is_a_full_commit_id(self) -> None:
        for path in sorted(FIXTURES_DIR.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            sha = document["repo_sha"]
            self.assertRegex(sha, r"^[0-9a-f]{40}$", f"{path.name}: repo_sha is not a full commit id")


if __name__ == "__main__":
    unittest.main()
