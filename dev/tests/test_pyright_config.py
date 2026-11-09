# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""``pyrightconfig.json`` lets a language server resolve the same imports as the ``mypy`` gate.

A language server (pyright, basedpyright, or Serena on top of one) gives an agent definitions, references and
type errors after an edit. It is an aid only: ``make typecheck`` (mypy strict) stays the gate. The tools import
each other by module name across folders, so without the same search paths as ``mypy.ini`` the server reports
hundreds of unresolved imports and the agent chases them.
"""

from __future__ import annotations

import configparser
import json
import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from _dev_paths import REPO

PYRIGHT = REPO / "pyrightconfig.json"
MYPY = REPO / "mypy.ini"


def pyright() -> dict[str, object]:
    data: dict[str, object] = json.loads(PYRIGHT.read_text(encoding="utf-8"))
    return data


class PyrightFollowsMypy(unittest.TestCase):
    def test_extra_paths_cover_the_mypy_path(self) -> None:
        mypy = configparser.ConfigParser()
        mypy.read(MYPY, encoding="utf-8")
        mypy_paths = set(mypy["mypy"]["mypy_path"].split(":"))
        extra = pyright()["extraPaths"]
        assert isinstance(extra, list)
        self.assertLessEqual(mypy_paths, set(extra))
        self.assertIn("audit/engine", extra, "the engine package `audit` resolves from audit/engine")

    def test_python_version_matches(self) -> None:
        mypy = configparser.ConfigParser()
        mypy.read(MYPY, encoding="utf-8")
        self.assertEqual(pyright()["pythonVersion"], mypy["mypy"]["python_version"])

    def test_every_extra_path_exists(self) -> None:
        extra = pyright()["extraPaths"]
        assert isinstance(extra, list)
        for path in extra:
            with self.subTest(path=path):
                self.assertTrue((REPO / path).is_dir())


if __name__ == "__main__":
    unittest.main()
