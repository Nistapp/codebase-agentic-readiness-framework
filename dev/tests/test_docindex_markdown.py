# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the document index's Markdown parser: headings, fences, slugs, sections, hashes and line flags."""

from __future__ import annotations

import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from docindex import markdown, model
from docindex.markdown import Document, Section, parse

PATH = "docs/page.md"


def _sections(text: str) -> dict[str, Section]:
    return {section.address: section for section in parse(PATH, text).sections}


def _addresses(text: str) -> list[str]:
    return [section.address for section in parse(PATH, text).sections]


def _flags(document: Document, attribute: str) -> list[int]:
    return [line.number for line in document.lines if getattr(line, attribute)]


class HeadingTest(unittest.TestCase):
    def test_atx_headings_make_a_chain_of_slugs(self) -> None:
        text = "# Top\n\nintro\n\n## Child one\n\n### Grandchild\n\n## Child two\n\n# Second top\n"
        self.assertEqual(
            _addresses(text),
            [
                f"{PATH}#",
                f"{PATH}#top",
                f"{PATH}#top/child-one",
                f"{PATH}#top/child-one/grandchild",
                f"{PATH}#top/child-two",
                f"{PATH}#second-top",
            ],
        )
        sections = _sections(text)
        self.assertEqual(sections[f"{PATH}#top/child-one/grandchild"].parent, f"{PATH}#top/child-one")
        self.assertEqual(sections[f"{PATH}#top"].parent, f"{PATH}#")
        self.assertIsNone(sections[f"{PATH}#"].parent)
        self.assertEqual(sections[f"{PATH}#top/child-two"].level, 2)
        self.assertEqual(sections[f"{PATH}#top/child-two"].title, "Child two")

    def test_a_skipped_level_and_a_document_that_starts_low(self) -> None:
        self.assertEqual(
            _addresses("## Low\n\n# High\n\n### Deep\n"),
            [f"{PATH}#", f"{PATH}#low", f"{PATH}#high", f"{PATH}#high/deep"],
        )

    def test_a_heading_inside_a_fence_is_ignored(self) -> None:
        text = (
            "# Real\n\n"
            "```bash\n# a shell comment\n## another\n```\n\n"
            "~~~~\n# tilde fence\n~~~\n# still inside: the closing fence is too short\n~~~~\n\n"
            "````markdown\n```\n# nested fence text\n```\n````\n\n"
            "## After\n"
        )
        self.assertEqual(_addresses(text), [f"{PATH}#", f"{PATH}#real", f"{PATH}#real/after"])

    def test_a_fence_inside_a_list_item_hides_its_headings(self) -> None:
        text = "# Steps\n\n1. Run this:\n\n    ```bash\n    # not a heading\n    ```\n\n2. Done.\n"
        document = parse(PATH, text)
        self.assertEqual([s.address for s in document.sections], [f"{PATH}#", f"{PATH}#steps"])
        self.assertEqual(_flags(document, "fence"), [5, 6, 7])
        self.assertEqual(_flags(document, "list_item"), [3, 5, 6, 7, 9])

    def test_an_unclosed_fence_runs_to_the_end(self) -> None:
        self.assertEqual(_addresses("# A\n```\n# B\n"), [f"{PATH}#", f"{PATH}#a"])

    def test_a_fence_closes_only_on_the_same_character(self) -> None:
        self.assertEqual(_addresses("```\n~~~\n# no\n```\n# yes\n"), [f"{PATH}#", f"{PATH}#yes"])

    def test_what_is_not_an_atx_heading(self) -> None:
        text = "#hashtag\n\n    # indented code\n\n- # in a list item\n\n> # in a quote\n\n<!--\n# in a comment\n-->\n"
        self.assertEqual(_addresses(text), [f"{PATH}#"])

    def test_closing_hashes_are_dropped(self) -> None:
        sections = parse(PATH, "## Title ##\n### C# notes\n").sections
        self.assertEqual([s.title for s in sections[1:]], ["Title", "C# notes"])
        self.assertEqual(sections[1].address, f"{PATH}#title")

    def test_setext_headings(self) -> None:
        text = "Top title\n=========\n\nintro\n\nA child\nover two lines\n---\n\nbody\n"
        document = parse(PATH, text)
        sections = document.sections
        addresses = [f"{PATH}#", f"{PATH}#top-title", f"{PATH}#top-title/a-child-over-two-lines"]
        self.assertEqual([s.address for s in sections], addresses)
        self.assertEqual([(s.level, s.title) for s in sections[1:]], [(1, "Top title"), (2, "A child over two lines")])
        self.assertEqual((sections[2].start, sections[2].end), (6, 10))
        self.assertEqual(_flags(document, "heading"), [1, 2, 6, 7, 8])

    def test_a_setext_heading_right_after_an_atx_heading(self) -> None:
        self.assertEqual(_addresses("# A\nB\n-\n"), [f"{PATH}#", f"{PATH}#a", f"{PATH}#a/b"])

    def test_what_is_not_a_setext_heading(self) -> None:
        text = "text\n\n---\n\n- item\n---\n\n> quote\n---\n\n| a | b |\n|---|---|\n| 1 | 2 |\n---\n\n    code\n---\n"
        self.assertEqual(_addresses(text), [f"{PATH}#"])


class SlugTest(unittest.TestCase):
    def test_slugify_matches_the_github_rule(self) -> None:
        cases = {
            "Hello, World!": "hello-world",
            "The `make check` gate": "the-make-check-gate",
            "snake_case and kebab-case": "snake_case-and-kebab-case",
            "A — B": "a--b",
            "Trailing ?": "trailing-",
            "See [the guide](docs/guide.md)": "see-the-guide",
            "Ünïcode Wörds": "ünïcode-wörds",
            "1.2 Step": "12-step",
        }
        for heading, slug in cases.items():
            with self.subTest(heading=heading):
                self.assertEqual(markdown.slugify(heading), slug)

    def test_duplicate_slugs_get_a_suffix_in_document_order(self) -> None:
        text = "# Notes\n## Example\n# Other\n## Example\n## Example\n"
        self.assertEqual(
            _addresses(text),
            [
                f"{PATH}#",
                f"{PATH}#notes",
                f"{PATH}#notes/example",
                f"{PATH}#other",
                f"{PATH}#other/example-1",
                f"{PATH}#other/example-2",
            ],
        )

    def test_a_generated_slug_is_remembered(self) -> None:
        slugger = markdown.Slugger()
        slugs = [slugger.slug(heading) for heading in ("Foo", "Foo", "Foo 1", "Foo")]
        self.assertEqual(slugs, ["foo", "foo-1", "foo-1-1", "foo-2"])

    def test_every_address_in_a_file_is_unique(self) -> None:
        text = "# A\n## A\n# A\n## A 1\n# A-1\n"
        addresses = _addresses(text)
        self.assertEqual(len(addresses), len(set(addresses)))


class FrontmatterTest(unittest.TestCase):
    TEXT = "---\nname: page\n# not: a heading\ntitle: x\n---\n\nPreamble.\n\n# Title\n"

    def test_frontmatter_holds_no_heading_and_is_not_body_text(self) -> None:
        document = parse(PATH, self.TEXT)
        self.assertEqual([s.address for s in document.sections], [f"{PATH}#", f"{PATH}#title"])
        self.assertEqual(_flags(document, "frontmatter"), [1, 2, 3, 4, 5])
        preamble = document.sections[0]
        self.assertEqual(preamble.start, 6)
        self.assertNotIn("name: page", preamble.own_text)
        self.assertEqual(preamble.own_hash, parse(PATH, "\nPreamble.\n\n# Title\n").sections[0].own_hash)
        self.assertIsNone(document.section_of(2))
        self.assertIs(document.section_of(7), preamble)

    def test_a_frontmatter_change_does_not_change_a_hash(self) -> None:
        before = parse(PATH, self.TEXT).sections
        after = parse(PATH, self.TEXT.replace("title: x", "title: y")).sections
        self.assertEqual([(s.own_hash, s.tree_hash) for s in before], [(s.own_hash, s.tree_hash) for s in after])

    def test_an_unclosed_frontmatter_is_a_thematic_break(self) -> None:
        document = parse(PATH, "---\n# Title\n")
        self.assertEqual(_flags(document, "frontmatter"), [])
        self.assertEqual([s.address for s in document.sections], [f"{PATH}#", f"{PATH}#title"])

    def test_a_rule_later_in_the_file_is_not_frontmatter(self) -> None:
        self.assertEqual(_flags(parse(PATH, "# A\n---\nx\n---\n"), "frontmatter"), [])


class SectionTest(unittest.TestCase):
    def test_an_empty_section(self) -> None:
        sections = _sections("# Parent\n## Empty\n## Full\n\ntext\n")
        empty = sections[f"{PATH}#parent/empty"]
        self.assertEqual((empty.start, empty.end, empty.tree_end), (2, 2, 2))
        self.assertEqual(empty.own_text, "## Empty")
        self.assertEqual(empty.own_hash, model.content_hash("## Empty"))
        self.assertEqual(empty.own_hash, empty.tree_hash)
        parent = sections[f"{PATH}#parent"]
        self.assertEqual((parent.start, parent.end, parent.tree_end), (1, 1, 5))

    def test_the_file_level_section_is_empty_when_the_file_starts_with_a_heading(self) -> None:
        file_section = parse(PATH, "# A\n\ntext\n").sections[0]
        self.assertEqual((file_section.address, file_section.level, file_section.title), (f"{PATH}#", 0, ""))
        self.assertEqual((file_section.start, file_section.end, file_section.tree_end), (1, 0, 3))
        self.assertEqual(file_section.own_text, "")
        self.assertEqual(file_section.own_hash, model.content_hash(""))

    def test_a_file_with_no_heading(self) -> None:
        document = parse(PATH, "Just text.\n\n- a list\n")
        self.assertEqual(len(document.sections), 1)
        only = document.sections[0]
        self.assertEqual((only.address, only.start, only.end, only.tree_end), (f"{PATH}#", 1, 3, 3))
        self.assertEqual(only.own_text, "Just text.\n\n- a list")
        self.assertEqual(only.own_hash, only.tree_hash)
        self.assertIs(document.section_of(3), only)

    def test_an_empty_file(self) -> None:
        document = parse(PATH, "")
        self.assertEqual(document.lines, ())
        self.assertEqual([s.address for s in document.sections], [f"{PATH}#"])

    def test_section_of_a_line(self) -> None:
        document = parse(PATH, "intro\n# A\ntext a\n## B\ntext b\n")
        self.assertEqual(
            [getattr(document.section_of(n), "address", None) for n in range(1, 6)],
            [f"{PATH}#", f"{PATH}#a", f"{PATH}#a", f"{PATH}#a/b", f"{PATH}#a/b"],
        )
        with self.assertRaises(IndexError):
            document.line(6)

    def test_line_endings_do_not_matter(self) -> None:
        text = "# A\n\nSome text.\n\n## B\n\nMore.\n"
        unix = parse(PATH, text)
        for name, ending in (("CRLF", "\r\n"), ("CR", "\r")):
            other = text.replace("\n", ending)
            with self.subTest(ending=name):
                parsed = parse(PATH, other)
                self.assertEqual(parsed.lines, unix.lines)
                self.assertEqual(parsed.sections, unix.sections)


class HashTest(unittest.TestCase):
    TEXT = (
        "# Guide\n\n"
        "The first paragraph says what the guide is for and who reads it.\n\n"
        "- A list item that is long enough to wrap\n  onto a second line.\n\n"
        "## Step\n\nRun the gate before you propose a change.\n"
    )

    def test_a_rewrapped_paragraph_keeps_both_hashes(self) -> None:
        rewrapped = self.TEXT.replace(
            "says what the guide is for and who reads it.", "says what the guide\nis for   and who\treads it.  "
        ).replace("long enough to wrap\n  onto a second line.", "long enough\n  to wrap onto a second line.")
        self.assertNotEqual(rewrapped, self.TEXT)
        before, after = _sections(self.TEXT), _sections(rewrapped)
        for address in before:
            with self.subTest(address=address):
                self.assertEqual(before[address].own_hash, after[address].own_hash)
                self.assertEqual(before[address].tree_hash, after[address].tree_hash)

    def test_blank_lines_and_trailing_spaces_do_not_matter(self) -> None:
        spaced = self.TEXT.replace("\n\n", "\n\n\n\n").replace("reads it.", "reads it.   ")
        self.assertEqual(
            [(s.own_hash, s.tree_hash) for s in parse(PATH, self.TEXT).sections],
            [(s.own_hash, s.tree_hash) for s in parse(PATH, spaced).sections],
        )

    def test_a_changed_word_changes_both_hashes(self) -> None:
        before = _sections(self.TEXT)[f"{PATH}#guide"]
        after = _sections(self.TEXT.replace("who reads it", "who writes it"))[f"{PATH}#guide"]
        self.assertNotEqual(before.own_hash, after.own_hash)
        self.assertNotEqual(before.tree_hash, after.tree_hash)

    def test_a_child_edit_changes_the_parent_tree_hash_only(self) -> None:
        before = _sections(self.TEXT)
        after = _sections(self.TEXT.replace("before you propose", "after you propose"))
        parent, child = f"{PATH}#guide", f"{PATH}#guide/step"
        self.assertEqual(before[parent].own_hash, after[parent].own_hash)
        self.assertNotEqual(before[parent].tree_hash, after[parent].tree_hash)
        self.assertNotEqual(before[child].own_hash, after[child].own_hash)
        self.assertNotEqual(before[f"{PATH}#"].tree_hash, after[f"{PATH}#"].tree_hash)

    def test_a_split_list_item_changes_the_hash(self) -> None:
        before = _sections("- one two\n")[f"{PATH}#"]
        after = _sections("- one\n- two\n")[f"{PATH}#"]
        self.assertNotEqual(before.own_hash, after.own_hash)

    def test_a_fenced_block_keeps_its_inner_whitespace(self) -> None:
        text = "# Code\n\n```python\nif x:\n    y()\n```\n"
        before = _sections(text)[f"{PATH}#code"]
        after = _sections(text.replace("    y()", "  y()"))[f"{PATH}#code"]
        self.assertNotEqual(before.own_hash, after.own_hash)

    def test_a_tree_hash_is_the_hash_of_the_normalised_tree(self) -> None:
        text = "# A\n\none\ntwo\n\n## B\n\n- x\n  y\n"
        section = _sections(text)[f"{PATH}#a"]
        self.assertEqual(section.tree_hash, model.content_hash("# A\n\none two\n\n## B\n\n- x y"))
        self.assertEqual(section.own_hash, model.content_hash("# A\n\none two"))

    def test_normalise_keeps_blocks_apart(self) -> None:
        text = (
            "Para one\ncontinues.\n> quote\n> goes on\n| a | b |\n|---|---|\n|  1 |  2 |\n"
            "1. item\n   more\n   - nested\n```\n  keep   this  \n\n\n```\n<!-- note -->\n"
        )
        document = parse(PATH, text)
        self.assertEqual(
            markdown.normalise(document.lines),
            "Para one continues.\n> quote goes on\n| a | b |\n|---|---|\n| 1 | 2 |\n1. item more\n   - nested\n"
            "```\n  keep   this\n\n\n```\n<!-- note -->",
        )


class LineFlagTest(unittest.TestCase):
    def test_table_rows(self) -> None:
        text = "text\n\n| a | b |\n| :-- | --: |\n| 1 | 2 |\nlazy row\n\nnot a row | here\n"
        document = parse(PATH, text)
        self.assertEqual(_flags(document, "table_row"), [3, 4, 5, 6])

    def test_a_header_whose_cell_count_does_not_match_is_not_a_table(self) -> None:
        self.assertEqual(_flags(parse(PATH, "| a | b |\n|---|\n"), "table_row"), [])

    def test_a_table_in_a_list_item(self) -> None:
        document = parse(PATH, "- item\n\n  | a |\n  |---|\n  | 1 |\n")
        self.assertEqual(_flags(document, "table_row"), [3, 4, 5])
        self.assertEqual(_flags(document, "list_item"), [1, 3, 4, 5])

    def test_list_items_and_their_continuations(self) -> None:
        text = (
            "Intro\n\n- first\n  continues\nlazy\n- second\n  - nested\n\n    still nested\n\nafter the list\n"
            "\n1. one\n2) two\n\n* * *\n"
        )
        document = parse(PATH, text)
        self.assertEqual(_flags(document, "list_item"), [3, 4, 5, 6, 7, 9, 13, 14])

    def test_a_marker_that_cannot_interrupt_a_paragraph(self) -> None:
        document = parse(PATH, "The year\n2026. was long\nand\n-\n")
        self.assertEqual(_flags(document, "list_item"), [])
        self.assertEqual([s.title for s in document.sections[1:]], ["The year 2026. was long and"])

    def test_html_comments(self) -> None:
        document = parse(PATH, "<!-- one line -->\ntext\n<!--\n# hidden\n-->\n# Shown\n")
        self.assertEqual(_flags(document, "comment"), [1, 3, 4, 5])
        self.assertEqual([s.address for s in document.sections], [f"{PATH}#", f"{PATH}#shown"])

    def test_the_line_numbers_and_texts(self) -> None:
        document = parse(PATH, "a\n\nb")
        self.assertEqual([(line.number, line.text) for line in document.lines], [(1, "a"), (2, ""), (3, "b")])


if __name__ == "__main__":
    unittest.main()
