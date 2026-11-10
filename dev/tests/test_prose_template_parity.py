# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The playbook template ``docs_prose_check.py`` reports what ``prose_check.py`` reports, page by page.

The template (``implement/playbooks/templates/``) is the copy that ``establish-docs-contract`` puts in a target
repository; ``dev/prose_check.py`` is this repository's own check. Both carry the same three rules, so a rule change
edits both files and this test fails until they match. The engine's ``DOC-05`` port is held to ``prose_check.py`` by
``test_prose_engine_parity.py``.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import unittest

import _dev_paths
import docs_prose_check as template
import prose_check as pc


def _markdown_pages() -> list[str]:
    listed = subprocess.run(
        ["git", "-C", str(_dev_paths.REPO), "ls-files", "*.md"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    return sorted(p for p in set(listed.split()) if "/fixtures/" not in p and "/testdata/" not in p)


class TemplateParity(unittest.TestCase):
    def test_the_template_reports_what_the_prose_check_reports_on_every_page(self) -> None:
        pages = _markdown_pages()
        self.assertGreater(len(pages), 50)
        # This repository's check also wants diagrams in the engine's architecture folders.
        dirs = pc._DIAGRAM_DIRS
        for rel in pages:
            text = (_dev_paths.REPO / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                self.assertEqual(
                    [str(i) for i in template.check_text(rel, text, dirs)],
                    [str(i) for i in pc.check_text(rel, text)],
                )

    def test_the_two_hold_the_same_limits_words_and_default_folders(self) -> None:
        self.assertEqual(
            (template.MAX_WORDS, template.MAX_WORDS_STEP, template.MAX_WORDS_WARNING),
            (pc.MAX_WORDS, pc.MAX_WORDS_STEP, pc.MAX_WORDS_WARNING),
        )
        self.assertEqual(template.VAGUE, pc.VAGUE)
        self.assertEqual(template.DIAGRAM_DIRS, pc._DIAGRAM_DIRS[: len(template.DIAGRAM_DIRS)])

    def test_the_template_reads_the_engines_diagram_folders_by_default(self) -> None:
        engine = str(_dev_paths.REPO / "audit" / "engine")
        if engine not in sys.path:
            sys.path.insert(0, engine)
        prose = importlib.import_module("audit.rules.checks._prose")
        self.assertEqual(template.DIAGRAM_DIRS, prose.DIAGRAM_DIRS)


if __name__ == "__main__":
    unittest.main()
