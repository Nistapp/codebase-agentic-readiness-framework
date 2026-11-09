# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Hygiene presence is repository-level (ADR-0008): the root, `.github/`, `.gitlab/` and `docs/`."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from scope_support import MAKE  # noqa: E402


class HygienePresenceTests(unittest.TestCase):
    """``HYG-02/03/05/06/08/09`` count a file at the root or under ``.github/``, ``.gitlab/`` or ``docs/``."""

    def verdicts(self, files: dict[str, str]) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.verdicts(support.run_audit(root))

    def test_a_template_beside_a_bare_repository_earns_no_hygiene_credit(self):
        verdicts = self.verdicts(
            {
                "Makefile": MAKE,
                "templates/CODEOWNERS": "* @a\n",
                "templates/CONTRIBUTING.md": "x",
                "templates/SECURITY.md": "x",
                "templates/RELEASE_PROCESS.md": "x",
                "templates/github/dependabot.yml": "x",
                "templates/github/PULL_REQUEST_TEMPLATE.md": "x",
            }
        )
        for check in ("HYG-02", "HYG-03", "HYG-05", "HYG-06", "HYG-08", "HYG-09"):
            self.assertEqual(verdicts[check], "FAIL", check)

    def test_a_component_directorys_hygiene_file_is_not_the_repositorys(self):
        verdicts = self.verdicts(
            {
                "Makefile": MAKE,
                "packages/web/CODEOWNERS": "* @a\n",
                "packages/web/CONTRIBUTING.md": "x",
                "packages/web/SECURITY.md": "x",
                "packages/web/PULL_REQUEST_TEMPLATE.md": "x",
                "packages/web/RELEASE.md": "x",
                "packages/web/.github/dependabot.yml": "x",
            }
        )
        for check in ("HYG-02", "HYG-03", "HYG-05", "HYG-06", "HYG-08", "HYG-09"):
            self.assertEqual(verdicts[check], "FAIL", check)

    def test_the_conventional_locations_still_pass(self):
        verdicts = self.verdicts(
            {
                "Makefile": MAKE,
                ".github/CODEOWNERS": "* @a\n",
                ".github/pull_request_template.md": "x",
                ".github/dependabot.yml": "version: 2\nupdates:\n  - package-ecosystem: github-actions\n",
                "CONTRIBUTING.md": "x",
                "docs/SECURITY.md": "x",
                "docs/how-to/release-process.md": "x",
            }
        )
        for check in ("HYG-02", "HYG-03", "HYG-05", "HYG-06", "HYG-08", "HYG-09"):
            self.assertEqual(verdicts[check], "PASS", check)

    def test_a_gitlab_codeowners_still_passes(self):
        self.assertEqual(self.verdicts({"Makefile": MAKE, ".gitlab/CODEOWNERS": "* @a\n"})["HYG-02"], "PASS")


if __name__ == "__main__":
    unittest.main()
