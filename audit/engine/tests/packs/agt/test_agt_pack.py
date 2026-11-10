# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT content-contract checks (AGT-03, 04, 06, 07, 09, 12) against their one-defect fixtures.

Each fixture is a minimal repository that fails exactly one check; `governed-minimal` passes all
six. The audit is run as a subprocess through `tests/support.py`, so the fixtures exercise the real
end-to-end path, not the check functions in isolation. `AGT-12` is also run in-process on built repositories,
so coverage traces it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.rules.checks.agt import MIN_INSTRUCTION_CHARS, _trivial_reason  # noqa: E402
from audit.rules.checks.agt import check_agt12 as CHECK_AGT12  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "agt-03-incomplete": ("AGT-03", "PARTIAL"),
    "agt-04-missing": ("AGT-04", "FAIL"),
    "agt-06-thin": ("AGT-06", "PARTIAL"),
    "agt-07-missing-deny": ("AGT-07", "PARTIAL"),
    "agt-09-no-release": ("AGT-09", "PARTIAL"),
    "agt-09-ruleset-branch-unnamed": ("AGT-09", "PARTIAL"),
    "agt-12-no-rules": ("AGT-12", "FAIL"),
}

CONTENT_CHECKS = ("AGT-03", "AGT-04", "AGT-06", "AGT-07", "AGT-09", "AGT-12")
#: Every engine AGT check; AGT-11 is judged by an agent and has no engine rule.
AGT_CHECKS = tuple(f"AGT-{i:02d}" for i in range(1, 13) if i != 11)


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

    def test_governed_minimal_passes_all_six(self):
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


class FindingIdTests(unittest.TestCase):
    """A finding's id is its check and a path, and the baseline ratchet compares ids, so two findings need two ids."""

    def ids(self, fixture: str, *checks: str) -> list[str]:
        report = support.run_audit(support.fixture(fixture))
        return sorted(f["id"] for f in report["findings"] if f["check"] in checks)

    def test_agt_08_names_each_of_its_findings(self):
        self.assertEqual(
            self.ids("agt-08-competitor", "AGT-08"),
            ["AGT-08:CLAUDE.md>AGENTS.md", "AGT-08:harness-reach", "AGT-08:vendor-files"],
        )

    def test_a_shadowed_pair_is_named_by_the_pair(self):
        self.assertEqual(
            self.ids("agt-01-shadowed", "AGT-08"), ["AGT-08:AGENTS.override.md>AGENTS.md", "AGT-08:harness-reach"]
        )

    def test_agt_01_names_the_file_a_finding_is_about(self):
        self.assertEqual(self.ids("agt-01-stub", "AGT-01"), ["AGT-01:AGENTS.md"])
        self.assertEqual(self.ids("agt-01-shadowed", "AGT-01"), ["AGT-01:AGENTS.override.md"])
        self.assertEqual(self.ids("agt-01-mis-cased", "AGT-01"), ["AGT-01:agents.md", "AGT-01:vendor-only"])

    def test_with_no_instruction_file_the_one_finding_has_the_plain_id(self):
        self.assertEqual(self.ids("agt-01-missing", "AGT-01"), ["AGT-01"])


class Agt08StatedHarnessesTests(unittest.TestCase):
    """AGT-08 takes a line of AGENTS.md that states the supported harnesses as the answer to the reach gap."""

    def reach_findings(self, agents_md: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            support.write(Path(tmp), "AGENTS.md", agents_md)
            report = support.run_audit(Path(tmp))
            return sorted(f["id"] for f in report["findings"] if f["check"] == "AGT-08")

    def test_without_a_statement_the_reach_gap_is_reported(self):
        self.assertEqual(self.reach_findings(FILLER), ["AGT-08:harness-reach"])

    def test_a_read_by_line_naming_harnesses_closes_the_gap(self):
        text = FILLER + "This file is read by Claude Code, opencode, Codex, Gemini CLI and Cursor.\n"
        self.assertEqual(self.reach_findings(text), [])

    def test_a_supported_harnesses_line_closes_the_gap(self):
        self.assertEqual(self.reach_findings(FILLER + "Supported harnesses: Cursor, Zed.\n"), [])

    def test_a_line_naming_no_known_harness_does_not(self):
        self.assertEqual(self.reach_findings(FILLER + "This file is read by humans.\n"), ["AGT-08:harness-reach"])

    def test_a_harness_name_without_the_phrase_does_not(self):
        self.assertEqual(self.reach_findings(FILLER + "We like Cursor.\n"), ["AGT-08:harness-reach"])


class Agt07SectionTests(unittest.TestCase):
    """AGT-07 finds the section through the helper that CON-01 and CON-02 share, and still scans the whole file."""

    BODY = "x" * 400 + "\n"

    def audit(self, text: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "AGENTS.md", text)
            report = support.run_audit(root)
        return next(c for c in report["checks"] if c["id"] == "AGT-07")

    def test_a_prohibitions_heading_that_only_stands_in_a_fenced_block_is_no_heading(self):
        check = self.audit(self.BODY + "```bash\n# Never run this\n```\n")
        self.assertEqual((check["verdict"], check["summary"]), ("FAIL", "no prohibitions section"))

    def test_the_four_concerns_are_still_found_anywhere_in_the_file(self):
        text = (
            self.BODY
            + "## Do Not Do\n- Never skip tests.\n## Elsewhere\n- Never edit generated files.\n"
            + "- Never push to main.\n- Never commit a secret.\n"
        )
        check = self.audit(text)
        self.assertEqual(
            (check["verdict"], check["summary"]),
            ("PASS", "prohibitions cover tests, generated files, the default branch and secrets"),
        )

    def test_a_file_with_no_such_heading_says_so(self):
        check = self.audit(self.BODY + "- Never skip tests.\n")
        self.assertEqual((check["verdict"], check["summary"]), ("FAIL", "no prohibitions section"))


class Agt01ProseTests(unittest.TestCase):
    def test_a_finished_file_that_uses_the_marker_words_in_sentences_passes(self):
        report = support.run_audit(support.fixture("agt-01-marker-words-in-prose"))
        self.assertEqual(support.verdicts(report)["AGT-01"], "PASS")
        self.assertEqual([f for f in report["findings"] if f["check"] == "AGT-01"], [])

    def test_a_template_that_was_never_filled_in_is_still_a_stub(self):
        report = support.run_audit(support.fixture("agt-01-stub"))
        self.assertEqual(support.verdicts(report)["AGT-01"], "FAIL")


# -- AGT-12: communication rules stated, in-process ---------------------------------------------------

AGT12 = "AGT-12"

PREAMBLE = """# AGENTS.md

This file governs how AI coding agents work in this repository. Treat it as authoritative.

## Commands

Run `make check` before you propose a change.
"""

SECTION = """
## How to write for people

- Write for a new engineer who knows Python but not this repository.
- Put the bottom line first. A done report says what changed and how it was checked.
- For a decision, give the options, your recommendation and the default.
"""

RULES_FILE = """# Communication rules

Write for a new engineer. Put the bottom line first in every report.
When the reader must decide, give the options, a recommendation and a default.
"""


class Agt12CommunicationRulesTests(unittest.TestCase):
    def check(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
            outcome = CHECK_AGT12(
                spec=REGISTRY_BY_ID[AGT12],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        return {
            "verdict": outcome.verdict.value,
            "summary": outcome.summary,
            "findings": [finding.to_dict() for finding in outcome.findings],
        }

    def test_registered_as_a_scored_cosmetic_content_check(self):
        spec = REGISTRY_BY_ID[AGT12]
        self.assertEqual(
            (spec.severity.value, spec.tier, spec.scored, spec.status), ("COSMETIC", "B", True, "implemented")
        )

    def test_no_instruction_file_is_unknown(self):
        check = self.check({"README.md": "# x\n"})
        self.assertEqual(check["verdict"], "UNKNOWN")
        self.assertIn("AGT-01", check["summary"])

    def test_no_section_and_no_rules_file_fails(self):
        check = self.check({"AGENTS.md": PREAMBLE})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(len(check["findings"]), 1)
        self.assertIn("has no section on writing for people", check["findings"][0]["statement"])

    def test_a_section_that_names_all_three_passes(self):
        check = self.check({"AGENTS.md": PREAMBLE + SECTION})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("AGENTS.md § How to write for people", check["summary"])
        self.assertEqual(check["findings"], [])

    def test_other_heading_words_open_a_section(self):
        for heading in ("Communication", "Reporting to the owner", "Talking to the user", "Writing for humans"):
            with self.subTest(heading=heading):
                text = PREAMBLE + SECTION.replace("How to write for people", heading)
                self.assertEqual(self.check({"AGENTS.md": text})["verdict"], "PASS")

    def test_the_section_ends_at_the_next_heading_of_its_level(self):
        text = PREAMBLE + "\n## Communication\n\nWrite for a new engineer.\n\n## Reviews\n\nReport each decision.\n"
        check = self.check({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("how to report, how to ask for a decision", check["summary"])

    def test_a_subsection_belongs_to_its_section(self):
        text = PREAMBLE + "\n## Communication\n\nWrite for a new engineer.\n\n### Layouts\n\nReport the decision.\n"
        self.assertEqual(self.check({"AGENTS.md": text})["verdict"], "PASS")

    def test_a_heading_in_a_fenced_block_is_not_a_section(self):
        text = PREAMBLE + "\n```markdown\n## How to write for people\nWrite for a reader. Report a decision.\n```\n"
        self.assertEqual(self.check({"AGENTS.md": text})["verdict"], "FAIL")

    def test_a_section_missing_one_element_is_partial(self):
        text = PREAMBLE + "\n## How to write for people\n\nWrite for a new engineer. Put the bottom line first.\n"
        check = self.check({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("do not say how to ask for a decision", check["summary"])
        self.assertEqual(check["findings"][0]["evidence"][0]["line"], 9)

    def test_a_linked_rules_file_alone_passes(self):
        text = PREAMBLE + "\nFollow [the rules](docs/COMMUNICATION_RULES.md) when you write.\n"
        check = self.check({"AGENTS.md": text, "docs/COMMUNICATION_RULES.md": RULES_FILE})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("docs/COMMUNICATION_RULES.md", check["summary"])

    def test_a_rules_file_named_in_a_code_span_counts(self):
        text = PREAMBLE + "\nFollow `./docs/communication.md#rules` when you write.\n"
        check = self.check({"AGENTS.md": text, "docs/communication.md": RULES_FILE})
        self.assertEqual(check["verdict"], "PASS")

    def test_the_section_and_the_named_file_are_read_together(self):
        section = "\n## How to write for people\n\nSee [the rules](docs/COMMUNICATION_RULES.md).\n"
        rules = "# Rules\n\nWrite for a new engineer. Report the status.\n"
        check = self.check({"AGENTS.md": PREAMBLE + section, "docs/COMMUNICATION_RULES.md": rules})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("how to ask for a decision", check["summary"])
        notes = [e.get("note") for e in check["findings"][0]["evidence"]]
        self.assertIn("section: How to write for people", notes)
        self.assertIn("rules file named at AGENTS.md:11", notes)

    def test_a_named_rules_file_that_does_not_exist_is_partial(self):
        text = PREAMBLE + SECTION + "\nThe long form is in `docs/COMMUNICATION_RULES.md`.\n"
        check = self.check({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("names docs/COMMUNICATION_RULES.md, which does not exist", check["summary"])

    def test_only_a_missing_rules_file_is_partial_not_fail(self):
        text = PREAMBLE + "\nFollow `docs/COMMUNICATION_RULES.md`.\n"
        check = self.check({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("the named rules file", check["summary"])

    def test_claude_md_is_the_fallback(self):
        check = self.check({"CLAUDE.md": PREAMBLE + SECTION})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("CLAUDE.md §", check["summary"])


if __name__ == "__main__":
    unittest.main()
