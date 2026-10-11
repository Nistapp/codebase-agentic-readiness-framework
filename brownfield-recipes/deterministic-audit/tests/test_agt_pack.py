# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT content-contract checks (AGT-03, 04, 06, 07, 09) against their one-defect fixtures.

Each fixture is a minimal repository that fails exactly one check; `governed-minimal` passes all
five. The audit is run as a subprocess through `tests/support.py`, so the fixtures exercise the real
end-to-end path, not the check functions in isolation.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks.agt import MIN_INSTRUCTION_CHARS, _trivial_reason  # noqa: E402

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "agt-03-incomplete": ("AGT-03", "PARTIAL"),
    "agt-04-missing": ("AGT-04", "FAIL"),
    "agt-06-thin": ("AGT-06", "PARTIAL"),
    "agt-07-missing-deny": ("AGT-07", "PARTIAL"),
    "agt-09-no-release": ("AGT-09", "PARTIAL"),
}

CONTENT_CHECKS = ("AGT-03", "AGT-04", "AGT-06", "AGT-07", "AGT-09")
AGT_CHECKS = tuple(f"AGT-{i:02d}" for i in range(1, 11))


class AgtFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = {cid for cid in AGT_CHECKS if verdicts[cid] == "FAIL"}
                expected_failing = {check} if expected == "FAIL" else set()
                self.assertEqual(
                    failing, expected_failing, f"{name}: unexpected AGT content FAILs {failing - expected_failing}"
                )

    def test_governed_minimal_passes_all_five(self):
        report = support.run_audit(support.fixture("governed-minimal"))
        verdicts = support.verdicts(report)
        for check in CONTENT_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"governed-minimal: {check}")


FILLER = "x" * MIN_INSTRUCTION_CHARS + "\n"


class StubReasonTests(unittest.TestCase):
    def reason(self, text: str) -> str | None:
        return _trivial_reason(FILLER + text + "\n")

    def test_a_word_that_opens_a_line_as_a_marker_is_a_stub(self):
        for text, word in (
            ("TODO: describe how agents work here", "todo"),
            ("todo", "todo"),
            ("- TODO", "todo"),
            ("* TBD", "tbd"),
            ("# TBD", "tbd"),
            ("> placeholder", "placeholder"),
            ("<!-- TODO -->", "todo"),
            ("[TBD]", "tbd"),
            ("1. Placeholder - fill in", "placeholder"),
            ("\u2022 todo", "todo"),
            ("TBD \u2013 later", "tbd"),
            ("TBD \u2014 later", "tbd"),
            ("(TODO)", "todo"),
        ):
            with self.subTest(text=text):
                self.assertEqual(self.reason(text), f"contains the placeholder marker {word!r}")

    def test_a_word_in_brackets_is_a_stub_wherever_it_stands(self):
        self.assertEqual(self.reason("see (todo) here"), "contains the placeholder marker 'todo'")
        self.assertEqual(self.reason("see [ tbd ] here"), "contains the placeholder marker 'tbd'")
        self.assertEqual(self.reason("the <placeholder> text"), "contains the placeholder marker 'placeholder'")

    def test_a_word_in_a_sentence_is_a_word(self):
        for text in (
            "Never commit placeholder values.",
            "Leave no TODO in a commit.",
            "A TODO: inside a sentence is prose.",
            "Placeholders must be replaced.",
            "The mastodon and the photodo are not markers, nor is tbdx.",
            "Wrapped prose that says leave no\nTODO markers behind.",
            "A placeholder-free file.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(self.reason(text))

    def test_a_template_phrase_is_a_stub_wherever_it_stands(self):
        for text, phrase in (
            ("Some Lorem Ipsum text.", "lorem ipsum"),
            ("Write <describe the project> here.", "<describe"),
            ("The rules are Coming Soon, we hope.", "coming soon"),
            ("Please fill this in later.", "fill this in"),
        ):
            with self.subTest(text=text):
                self.assertEqual(self.reason(text), f"contains the placeholder marker {phrase!r}")

    def test_the_phrases_are_checked_before_the_words(self):
        self.assertEqual(self.reason("TODO\ncoming soon"), "contains the placeholder marker 'coming soon'")

    def test_the_first_word_marker_in_the_file_is_the_one_named_for_each_pattern(self):
        self.assertEqual(self.reason("TBD\nTODO"), "contains the placeholder marker 'tbd'")
        self.assertEqual(self.reason("see (tbd) and [todo]"), "contains the placeholder marker 'tbd'")

    def test_the_minimum_length_is_four_hundred_characters_of_text(self):
        self.assertEqual(MIN_INSTRUCTION_CHARS, 400)
        self.assertIsNone(_trivial_reason("x" * 400))
        self.assertEqual(_trivial_reason("x" * 399), "only 399 characters (minimum 400)")
        self.assertIsNone(_trivial_reason("\n  " + "x" * 400 + "  \n"))

    def test_a_short_file_is_a_stub_before_its_words_are_read(self):
        self.assertEqual(_trivial_reason("TODO"), "only 4 characters (minimum 400)")


class Agt01ProseTests(unittest.TestCase):
    def test_a_finished_file_that_uses_the_marker_words_in_sentences_passes(self):
        report = support.run_audit(support.fixture("agt-01-marker-words-in-prose"))
        self.assertEqual(support.verdicts(report)["AGT-01"], "PASS")
        self.assertEqual([f for f in report["findings"] if f["check"] == "AGT-01"], [])

    def test_a_template_that_was_never_filled_in_is_still_a_stub(self):
        report = support.run_audit(support.fixture("agt-01-stub"))
        self.assertEqual(support.verdicts(report)["AGT-01"], "FAIL")


if __name__ == "__main__":
    unittest.main()
