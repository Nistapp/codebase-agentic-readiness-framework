# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine's `DOC-05` prose reader counts what ``prose_check.py`` reports, page by page.

The engine may not import dev code, so it carries its own port of the three rules
(``audit/engine/audit/rules/checks/_prose.py``). This test holds the two in step on every Markdown page of this
repository's ``docs/``: the engine's long sentences are ``PL001``, its vague words are ``PL002``, and its pages that
need a diagram and have none are ``PL003``.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import unittest
from typing import Any

import _dev_paths
import prose_check as pc

ENGINE = _dev_paths.REPO / "audit" / "engine"


def _engine_prose() -> Any:
    if str(ENGINE) not in sys.path:
        sys.path.insert(0, str(ENGINE))
    return importlib.import_module("audit.rules.checks._prose")


def _docs_pages() -> list[str]:
    listed = subprocess.run(
        ["git", "-C", str(_dev_paths.REPO), "ls-files", "docs/*.md", "docs/**/*.md"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    return sorted(set(listed.split()))


class EngineParity(unittest.TestCase):
    def test_the_engine_counts_what_the_prose_check_reports_on_every_docs_page(self) -> None:
        prose = _engine_prose()
        pages = _docs_pages()
        self.assertGreater(len(pages), 10)
        for rel in pages:
            text = (_dev_paths.REPO / rel).read_text(encoding="utf-8")
            issues = pc.check_text(rel, text)
            counts, has_mermaid = prose.measure(rel, text)
            with self.subTest(page=rel):
                self.assertEqual(counts.long_sentences, sum(1 for i in issues if i.code == "PL001"))
                self.assertEqual(counts.vague_words, sum(1 for i in issues if i.code == "PL002"))
                engine_wants = prose.needs_diagram(rel) and not has_mermaid
                self.assertEqual(engine_wants, any(i.code == "PL003" for i in issues))

    def test_the_two_hold_the_same_limits_and_words(self) -> None:
        prose = _engine_prose()
        self.assertEqual((prose.MAX_WORDS, prose.MAX_WORDS_STEP), (pc.MAX_WORDS, pc.MAX_WORDS_STEP))
        self.assertEqual(prose.VAGUE, pc.VAGUE)


if __name__ == "__main__":
    unittest.main()
