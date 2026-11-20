# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`HYG-01` reads a placeholder marker by where it stands, not only by whether it occurs (issue #51).

A full README failed `HYG-01` because one configuration-table row said an endpoint returns a "placeholder answer".
A marker anywhere still makes a short README (under 400 characters, the floor `AGT-01` uses) a stub, and filler text
(`lorem ipsum`, `<describe`) counts at any length. In a longer README a word marker counts only when it opens a line
and the line's end or punctuation follows it. The summary names the line. The check runs in-process here, so
coverage traces it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.hyg import check_hyg01  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

#: About 600 characters of real README prose with no marker.
BODY = (
    "# Widget Service\n\n"
    "Widget Service exposes a small HTTP API for managing widgets. It is written for teams that need a "
    "dependable, boring service they can extend without reading the whole repository first.\n\n"
    "## Running it\n\n"
    "Install Java 21, then start the service from a checkout with the Gradle wrapper. Configuration lives in "
    "environment variables, listed in the table below and in the example environment file.\n\n"
    "## Configuration\n\n"
    "| Variable | Meaning |\n"
    "|---|---|\n"
    "| `WIDGET_PORT` | The port the service listens on. |\n"
)


def _hyg01(text: str) -> tuple[str, str]:
    """``(verdict, summary)`` of `HYG-01` on a repository whose root README holds ``text``."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        support.write(root, "README.md", text)
        inventory = build_inventory(root)
        outcome = check_hyg01(
            spec=REGISTRY_BY_ID["HYG-01"],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=None,
            session=None,
        )
    return outcome.verdict.value, outcome.summary


class Hyg01MarkerTests(unittest.TestCase):
    def test_a_marker_word_inside_a_table_row_of_a_full_readme_passes(self):
        text = BODY + "| `ANSWER_MODE` | `stub` returns a placeholder answer, for local runs. |\n"
        self.assertEqual(_hyg01(text), ("PASS", "README.md present and non-placeholder"))

    def test_a_marker_word_mid_sentence_in_a_full_readme_passes(self):
        text = BODY + "\nThe todo list app in `examples/` shows the API in use.\n"
        self.assertEqual(_hyg01(text)[0], "PASS")

    def test_a_marker_that_opens_a_line_of_a_full_readme_fails_and_names_the_line(self):
        text = BODY + "\n## Deployment\n\nTODO: write the deployment steps.\n"
        verdict, summary = _hyg01(text)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("line 17 carries the placeholder marker 'todo': TODO: write the deployment steps.", summary)

    def test_a_marker_heading_and_a_marker_list_item_fail_a_full_readme(self):
        for line in ("## Coming soon", "- TBD", "- [ ] **TODO**: usage", "> Placeholder."):
            with self.subTest(line=line):
                self.assertEqual(_hyg01(BODY + "\n" + line + "\n")[0], "FAIL")

    def test_a_word_that_only_starts_with_a_marker_does_not_count(self):
        self.assertEqual(_hyg01(BODY + "\nTodoist users can import widgets.\n")[0], "PASS")

    def test_filler_text_fails_a_readme_of_any_length(self):
        verdict, summary = _hyg01(BODY + "\nLorem ipsum dolor sit amet, consectetur adipiscing elit.\n")
        self.assertEqual(verdict, "FAIL")
        self.assertIn("'lorem ipsum'", summary)

    def test_a_marker_anywhere_in_a_short_readme_still_fails(self):
        text = (
            "# App\n\n" + "This service answers widget queries for the shop front end. " * 4 + "It is a placeholder.\n"
        )
        self.assertLess(len(text.strip()), 400)
        verdict, summary = _hyg01(text)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("line 3 carries the placeholder marker 'placeholder'", summary)

    def test_a_long_marker_line_is_cut_in_the_summary(self):
        text = BODY + "\nTODO: " + "describe every endpoint " * 10 + "\n"
        summary = _hyg01(text)[1]
        self.assertTrue(summary.endswith("..."), summary)


if __name__ == "__main__":
    unittest.main()
