# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The release-please setup stays consistent with the version stamps and the changelog (ADR 0005, RELEASE_PROCESS.md).

release-please bumps the version in ``.release-please-manifest.json`` and in each of its ``extra-files``. These tests
fail when a version stamp drifts from the manifest (as the engine's did before release-please: it said 0.1.0 while
v0.3.0 was released, and the audit report's recipe version said 0.1.0 through v0.3.2), when a stamp line loses the
marker that release-please looks for or is not an ``extra-files`` entry, or when a hand-written ``[Unreleased]``
heading comes back into the changelog that release-please writes.

The stamps are the engine's ``__version__``, ``FRAMEWORK_RELEASE`` in ``report.py`` (the audit report's
``provenance.framework.release``) and ``FRAMEWORK_RELEASE`` in ``progress.py`` (the implement state's
``framework.release`` and ``last_framework.release``). The skill bundles' ``metadata.version``
is copied from the manifest at build time; ``test_build_skills`` checks it.
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
#: Every file that holds a copy of the release version, and the pattern of the one line that holds it.
STAMPS = {
    ENGINE_INIT: VERSION_LINE,
    "audit/tools/report.py": re.compile(r'^FRAMEWORK_RELEASE = "(?P<version>[^"]+)"(?P<rest>.*)$', re.MULTILINE),
    "implement/tools/progress.py": re.compile(r'^FRAMEWORK_RELEASE = "(?P<version>[^"]+)"(?P<rest>.*)$', re.MULTILINE),
}


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

    def stamp_lines(self) -> dict[str, re.Match[str]]:
        lines = {}
        for path, pattern in STAMPS.items():
            matches = list(pattern.finditer((REPO / path).read_text(encoding="utf-8")))
            self.assertEqual(len(matches), 1, f"{path}: expected one version line, found {len(matches)}")
            lines[path] = matches[0]
        return lines

    def test_every_stamp_matches_the_manifest(self) -> None:
        for path, line in self.stamp_lines().items():
            with self.subTest(path=path):
                self.assertEqual(line["version"], self.manifest["."])

    def test_every_stamp_line_carries_the_marker(self) -> None:
        for path, line in self.stamp_lines().items():
            with self.subTest(path=path):
                self.assertIn(MARKER, line["rest"])

    def test_every_stamp_file_is_an_extra_file(self) -> None:
        self.assertEqual(sorted(self.config["extra-files"]), sorted(STAMPS))

    def test_the_no_compatibility_policy_ends_before_1_0_0(self) -> None:
        # ADR 0008: the tools read only the current report and state schemas until the first outside user or 1.0.0.
        major = int(self.manifest["."].split(".")[0])
        self.assertLess(
            major,
            1,
            "release 1.0.0 ends the no-backward-compatibility policy of ADR 0008: decide which older report and state "
            "schemas the tools read, update docs/reference/versions.md and the ADR, then replace this test",
        )

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
