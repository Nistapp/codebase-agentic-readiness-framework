# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The prohibitions section, found once for every check that reads it (decision 0001).

``AGT-07``, ``CON-01`` and ``CON-02`` all ask :func:`prohibitions_section`, so what makes a heading a prohibitions
heading, where its section ends and what counts as naming a path cannot drift between them.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks._common import (  # noqa: E402
    PROHIBITION_HEADING_RE,
    Prohibitions,
    entry_instruction_file,
    prohibitions_section,
)
from audit.scan import build_inventory  # noqa: E402


def section(text: str) -> Prohibitions | None:
    return prohibitions_section(text)


class HeadingTests(unittest.TestCase):
    def test_the_accepted_headings(self):
        for heading in (
            "Do Not Do",
            "DO NOT DO",
            "Do-not-do",
            "Do not",
            "Don't",
            "Never",
            "Prohibited",
            "Prohibitions",
            "Forbidden",
            "Deny",
            "No-go",
            "No go",
            'Explicit "Do Not Do" Rules',
            "10. Explicit Do Not Do Rules",
            "What an agent must never do",
        ):
            with self.subTest(heading=heading):
                found = section(f"## {heading}\n- `dist/`\n")
                self.assertIsNotNone(found)
                self.assertEqual(found.headings, (heading,))

    def test_words_that_only_contain_the_heading_words_are_not_headings(self):
        for heading in ("Neverland", "Denying access", "Do nothing", "Donor notes", "Prohibit", "Allow list"):
            with self.subTest(heading=heading):
                expected_none = heading != "Prohibit"
                self.assertEqual(section(f"## {heading}\n- `dist/`\n") is None, expected_none)

    def test_the_heading_pattern_is_the_one_agt_07_always_used(self):
        self.assertEqual(
            PROHIBITION_HEADING_RE.pattern, r"(?i)\b(do[- ]?not|don't|prohibit\w*|deny|forbidden|never|no[- ]?go)\b"
        )

    def test_a_heading_needs_one_to_six_hashes_then_a_space(self):
        self.assertIsNone(section("Never\n- `dist/`\n"))
        self.assertIsNone(section("#Never\n- `dist/`\n"))
        self.assertIsNone(section("####### Never\n- `dist/`\n"))
        self.assertIsNone(section("    ## Never\n- `dist/`\n"))
        for hashes in ("#", "##", "###", "####", "#####", "######"):
            with self.subTest(hashes=hashes):
                self.assertIsNotNone(section(f"{hashes} Never\n- `dist/`\n"))

    def test_a_closing_run_of_hashes_is_not_part_of_the_heading(self):
        self.assertEqual(section("## Never ##\n").headings, ("Never",))
        self.assertEqual(section("## Never never #\n").headings, ("Never never",))
        self.assertEqual(section("## Never C#\n").headings, ("Never C#",))

    def test_a_file_with_no_such_heading_has_no_section(self):
        self.assertIsNone(section(""))
        self.assertIsNone(section("# Rules\n\nNever commit secrets.\n\n## Boundaries\n- `src/`\n"))


class ExtentTests(unittest.TestCase):
    TEXT = (
        "# Project\n"  # 1
        "\n"  # 2
        "## Do Not Do\n"  # 3
        "\n"  # 4
        "- Never edit `dist/`.\n"  # 5
        "### Tests\n"  # 6
        "- Do not touch `tests/`.\n"  # 7
        "## Commands\n"  # 8
        "- `make check`\n"  # 9
    )

    def test_the_section_runs_from_its_heading_to_the_next_heading_of_its_level_and_includes_subsections(self):
        found = section(self.TEXT)
        self.assertEqual(found.first_line, 3)
        self.assertEqual([number for number, _ in found.lines], [3, 4, 5, 6, 7])
        self.assertEqual(found.lines[0], (3, "## Do Not Do"))
        self.assertEqual(found.lines[-1], (7, "- Do not touch `tests/`."))

    def test_a_heading_of_a_higher_level_ends_it_too(self):
        found = section("## Never\n- `a/`\n# Top\n- `b/`\n")
        self.assertEqual([number for number, _ in found.lines], [1, 2])

    def test_a_deeper_heading_is_inside_it_and_a_lower_level_one_ends_it(self):
        found = section("### Never\n- `a/`\n#### Detail\n- `b/`\n### Next\n- `c/`\n")
        self.assertEqual([number for number, _ in found.lines], [1, 2, 3, 4])
        found = section("### Never\n- `a/`\n## Up\n- `c/`\n")
        self.assertEqual([number for number, _ in found.lines], [1, 2])

    def test_a_matching_heading_inside_the_section_does_not_start_another(self):
        found = section("## Do Not Do\n- `a/`\n### Never edit `b/`\n- `c/`\n## Other\n")
        self.assertEqual(found.headings, ("Do Not Do",))
        self.assertEqual([number for number, _ in found.lines], [1, 2, 3, 4])

    def test_it_runs_to_the_end_of_the_file_when_nothing_follows(self):
        found = section("## Never\n- `a/`\n\n- `b/`\n")
        self.assertEqual([number for number, _ in found.lines], [1, 2, 3, 4])

    def test_every_matching_section_counts_in_order_and_the_first_gives_the_line(self):
        found = section("# Intro\n## Never\n- `a/`\n## Mid\n- `x/`\n## Forbidden\n- `b/`\n")
        self.assertEqual(found.headings, ("Never", "Forbidden"))
        self.assertEqual(found.first_line, 2)
        self.assertEqual([number for number, _ in found.lines], [2, 3, 6, 7])

    def test_a_heading_with_nothing_under_it_is_a_section_of_one_line(self):
        found = section("## Never\n## Next\n")
        self.assertEqual(found.lines, ((1, "## Never"),))

    def test_the_first_line_is_one_based(self):
        self.assertEqual(section("## Never\n").first_line, 1)


class FenceTests(unittest.TestCase):
    def test_a_hash_line_in_a_fenced_block_is_not_a_heading(self):
        text = "# Rules\n\n```bash\n# Never run this\nrm -rf x\n```\n"
        self.assertIsNone(section(text))
        self.assertIsNone(section(text.replace("```", "~~~")))

    def test_a_fence_in_the_section_does_not_end_it_and_its_text_is_kept(self):
        text = "## Never\n- `a/`\n```sh\n# a comment\nls\n```\n- `b/`\n## Next\n"
        found = section(text)
        self.assertEqual([number for number, _ in found.lines], [1, 2, 3, 4, 5, 6, 7])

    def test_an_unclosed_fence_runs_to_the_end(self):
        found = section("## Never\n```sh\n## Never again\n- `a/`\n")
        self.assertEqual([number for number, _ in found.lines], [1, 2, 3, 4])

    def test_a_heading_after_a_closed_fence_is_a_heading_again(self):
        found = section("```sh\n# x\n```\n## Never\n- `a/`\n")
        self.assertEqual(found.first_line, 4)

    def test_an_indented_fence_opens_a_block(self):
        self.assertIsNone(section("  ```sh\n# Never\n  ```\n"))


class CodeSpanTests(unittest.TestCase):
    def spans(self, body: str):
        found = section("## Never\n" + body)
        return found.code_spans()

    def test_a_code_span_is_the_text_between_backticks_with_its_line_number(self):
        self.assertEqual(
            self.spans("- Never edit `dist/` or `tests/`.\n- No `*.pem`.\n"),
            ((2, "dist/"), (2, "tests/"), (3, "*.pem")),
        )

    def test_the_span_is_stripped_and_an_empty_one_is_not_a_span(self):
        self.assertEqual(self.spans("- `  dist/ ` and ` ` and ``\n"), ((2, "dist/"),))

    def test_double_and_triple_backticks_hold_a_single_one_and_pair_with_their_own_kind(self):
        self.assertEqual(self.spans("- ``a`b/`` and ```c/```\n"), ((2, "a`b/"), (2, "c/")))

    def test_an_unmatched_backtick_names_nothing(self):
        self.assertEqual(self.spans("- never `dist/\n- or tests/`\n"), ())

    def test_the_heading_line_is_part_of_the_section(self):
        found = section("## Never edit `dist/`\n- `tests/`\n")
        self.assertEqual(found.code_spans(), ((1, "dist/"), (2, "tests/")))

    def test_a_span_outside_the_section_is_not_named(self):
        found = section("## Commands\n- `make check`\n## Never\n- `dist/`\n## Other\n- `src/`\n")
        self.assertEqual(found.code_spans(), ((4, "dist/"),))

    def test_spans_do_not_cross_lines(self):
        self.assertEqual(self.spans("- `dist\n/`\n"), ())


class EntryFileTests(unittest.TestCase):
    def entry(self, files: dict[str, str]) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return entry_instruction_file(build_inventory(root))

    def test_the_canonical_file_wins_and_claude_md_is_the_fallback(self):
        self.assertEqual(self.entry({"AGENTS.md": "a\n", "CLAUDE.md": "c\n"}), ("AGENTS.md", "a\n"))
        self.assertEqual(self.entry({"CLAUDE.md": "c\n"}), ("CLAUDE.md", "c\n"))

    def test_an_empty_canonical_file_is_no_file(self):
        self.assertEqual(self.entry({"AGENTS.md": "", "CLAUDE.md": "c\n"}), ("CLAUDE.md", "c\n"))

    def test_no_instruction_file_is_an_empty_pair(self):
        self.assertEqual(self.entry({"README.md": "x\n"}), ("", ""))


if __name__ == "__main__":
    unittest.main()
