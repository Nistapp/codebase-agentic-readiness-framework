# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""A repository that trips every loop in the engine still gives every finding an id of its own.

The fixture matrix holds each fixture's report to unique ids, but a fixture exercises one defect, and a check that
raises one finding for each of several things shows a repeated id only when there are several things. This
repository has all of them at once: every ecosystem the engine knows with no lockfile, competing and shadowed and
mis-cased instruction files, and an override below the root. The baseline ratchet compares ids, so a repeated one
is a regression it cannot see.
"""

from __future__ import annotations

import collections
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

BODY = "# Rules\n\n" + "Always run the tests before every commit.\n" * 20

MANIFESTS = {
    "package.json": '{"name": "x"}\n',
    "pyproject.toml": '[project]\nname = "x"\n',
    "Cargo.toml": '[package]\nname = "x"\n',
    "go.mod": "module x\n",
    "pom.xml": "<project/>\n",
    "build.gradle": "plugins {\n    id 'java'\n}\n",
    "Gemfile": "source 'https://rubygems.org'\n",
    "composer.json": "{}\n",
    "x.csproj": "<Project/>\n",
}

INSTRUCTION_FILES = {
    "AGENTS.md": BODY,
    "AGENTS.override.md": BODY,
    "sub/AGENTS.md": BODY,
    "sub/AGENTS.override.md": BODY,
    "CLAUDE.md": BODY,
    "GEMINI.md": BODY,
    ".cursorrules": BODY,
    "agents.md": BODY,
    ".github/copilot-instructions.md": BODY,
}


def write_all(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        support.write(root, rel, text)


class FindingIdTests(unittest.TestCase):
    def assert_unique(self, report: dict) -> None:
        ids = [f["id"] for f in report["findings"]]
        repeated = sorted(k for k, v in collections.Counter(ids).items() if v > 1)
        self.assertEqual(repeated, [], f"{len(ids)} findings, and these ids repeat")

    def test_every_ecosystem_without_a_lockfile_and_every_competing_instruction_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_all(root, {**MANIFESTS, **INSTRUCTION_FILES})
            report = support.run_audit(root)
        self.assertGreater(len(report["findings"]), 20, "the repository should trip many findings")
        self.assert_unique(report)
        for check in ("EXEC-01", "AGT-01", "AGT-08"):
            self.assertGreater(sum(1 for f in report["findings"] if f["check"] == check), 1, check)

    def test_the_same_repository_under_git_with_its_files_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            write_all(root, {**MANIFESTS, **INSTRUCTION_FILES, "artefacts/notes.md": "# x\n", ".gitignore": ".env\n"})
            git = shutil.which("git")
            self.assertIsNotNone(git)
            for args in (("init", "-q"), ("add", "-A"), ("add", "-f", "artefacts/notes.md")):
                self.assertEqual(subprocess.run([str(git), "-C", str(root), *args], capture_output=True).returncode, 0)
            report = support.run_audit(root)
        self.assert_unique(report)
        self.assertGreater(sum(1 for f in report["findings"] if f["check"] == "EXEC-02"), 1)


if __name__ == "__main__":
    unittest.main()
