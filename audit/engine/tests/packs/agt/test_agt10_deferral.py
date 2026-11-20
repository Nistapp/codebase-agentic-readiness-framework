# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`AGT-10`'s deferral half, run in-process: a deferral names a path from the root, and a dot folder keeps its dot."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.rules.checks.agt import check_agt10  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

RULES = "# Rules\n\n- Run the tests before you commit.\n"


def run(files: dict[str, str]) -> tuple[str, list[str]]:
    """`AGT-10`'s verdict on a repository built from `files`, and the evidence notes of its findings."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        inventory = build_inventory(root)
        outcome = check_agt10(
            spec=REGISTRY_BY_ID["AGT-10"],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=None,
            session=None,
        )
        notes = [e.note for f in outcome.findings for e in f.evidence]
        return outcome.verdict.value, notes


def defers_to(reference: str) -> str:
    return f"# AGENTS.md\n\nFirst read `{reference}` for the coding rules.\n"


class DotFolderDeferralTests(unittest.TestCase):
    def test_a_deferral_to_a_dot_folder_file_no_config_names_fails(self):
        verdict, notes = run({"AGENTS.md": defers_to(".agents/rules.md"), ".agents/rules.md": RULES})
        self.assertEqual(verdict, "FAIL")
        self.assertEqual(notes, ["deferral found: .agents/rules.md"])

    def test_a_leading_dot_slash_goes_and_the_dot_folder_keeps_its_dot(self):
        verdict, notes = run({"AGENTS.md": defers_to("./.agents/rules.md"), ".agents/rules.md": RULES})
        self.assertEqual(verdict, "FAIL")
        self.assertEqual(notes, ["deferral found: .agents/rules.md"])

    def test_a_dot_folder_file_a_config_names_is_no_deferral(self):
        for pointer in ("./.agents/rules.md", ".agents/rules.md"):
            with self.subTest(pointer=pointer):
                verdict, notes = run(
                    {
                        "AGENTS.md": defers_to(".agents/rules.md"),
                        ".agents/rules.md": RULES,
                        "opencode.json": f'{{"instructions": ["{pointer}"]}}\n',
                    }
                )
                self.assertEqual(verdict, "PASS")
                self.assertEqual(notes, [])

    def test_the_folder_without_its_dot_is_not_the_dot_folder(self):
        verdict, notes = run({"AGENTS.md": defers_to(".agents/rules.md"), "agents/rules.md": RULES})
        self.assertEqual(verdict, "PASS")
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
