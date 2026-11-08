# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The release-please setup stays consistent with the engine and the changelog (ADR 0005, RELEASE_PROCESS.md).

release-please bumps the version in ``.release-please-manifest.json`` and in each of its ``extra-files``. These tests
fail when the engine's ``__version__`` drifts from the manifest (as it did before release-please: the engine said
0.1.0 while v0.3.0 was released), when the engine's version line loses the marker that release-please looks for, or
when a hand-written ``[Unreleased]`` heading comes back into the changelog that release-please writes.
"""

from __future__ import annotations

import json
import re
import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from _dev_paths import REPO

CONFIG = REPO / "release-please-config.json"
MANIFEST = REPO / ".release-please-manifest.json"
ENGINE_INIT = "audit/engine/audit/__init__.py"
MARKER = "x-release-please-version"
VERSION_LINE = re.compile(r'^__version__ = "(?P<version>[^"]+)"(?P<rest>.*)$', re.MULTILINE)


class ReleaseConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        match = VERSION_LINE.search((REPO / ENGINE_INIT).read_text(encoding="utf-8"))
        assert match is not None, f"{ENGINE_INIT}: no __version__ line"
        self.engine_line = match

    def test_engine_version_matches_the_manifest(self) -> None:
        self.assertEqual(self.engine_line["version"], self.manifest["."])

    def test_engine_version_line_carries_the_marker(self) -> None:
        self.assertIn(MARKER, self.engine_line["rest"])

    def test_engine_init_is_an_extra_file(self) -> None:
        self.assertIn(ENGINE_INIT, self.config["extra-files"])

    def test_one_root_package_with_plain_v_tags(self) -> None:
        self.assertEqual(list(self.config["packages"]), ["."])
        self.assertEqual(list(self.manifest), ["."])
        self.assertIs(self.config["include-component-in-tag"], False)
        self.assertIs(self.config["include-v-in-tag"], True)

    def test_pre_1_0_bumps_follow_the_release_process(self) -> None:
        # RELEASE_PROCESS.md: before 1.0.0 a breaking change bumps MINOR, any other change bumps PATCH.
        self.assertIs(self.config["bump-minor-pre-major"], True)
        self.assertIs(self.config["bump-patch-for-minor-pre-major"], True)

    def test_changelog_has_no_unreleased_heading(self) -> None:
        changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertNotRegex(changelog, re.compile(r"^## \[Unreleased\]", re.MULTILINE | re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
