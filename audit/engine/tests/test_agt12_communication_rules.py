# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`AGT-12` reads the rules for writing to people: a section of the instruction file or a rules file it names.

The rules must name the reader, how to report and how to ask for a decision. The tests run the check in-process, so
coverage traces it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

from audit.rules.checks.agt import check_agt12 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "AGT-12"

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
            outcome = CHECK(
                spec=REGISTRY_BY_ID[CHECK_ID],
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
        spec = REGISTRY_BY_ID[CHECK_ID]
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
