# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`AGT-13` coding conventions written, in-process on built repositories, so coverage traces it.

Each verdict of PLAN.md 5.6.1 has a test here: a conventions file at `PASS` for the Java, Node and Python
keyword sets, a file missing items and a file with a stub word at `PARTIAL`, a section in `AGENTS.md` or
`CONTRIBUTING.md`, no conventions at `FAIL`, and `docs/STYLE_GUIDE.md` alone at `FAIL`. The one-defect fixture
`agt-13-no-conventions` runs end to end in `test_agt_pack.py` and the fixture matrix.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.rules.checks.agt import check_agt13  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

AGT13 = "AGT-13"
GREENFIELD_TEMPLATES = Path(__file__).resolve().parents[5] / "greenfield" / "templates"

JAVA = """# Coding conventions

## Naming

Classes use PascalCase. Methods and fields use camelCase. Packages are lower case.

## Layering

A controller calls a service, and a service calls a repository. A repository does not call a controller.

## Errors and logging

A service throws a domain exception that names the bad input. Log through SLF4J.

## Testing

JUnit 5 tests live in `src/test/java`, in the package of the class under test.

## Tools

Spotless and `config/checkstyle/checkstyle.xml` enforce the format. Read them, and do not copy them here.
"""

NODE = """# Code conventions

## 1. Naming

Source files use kebab-case. Functions and variables use camelCase.

## 2. Layering

Domain logic goes in `src/core/`. Argument parsing goes in `src/cli/`.

## 3. Errors and logging

Throw an `Error` subclass. Log through the injected logger, built on pino.

## 4. Testing

Vitest runs `test/**/*.test.ts`.

## 5. Tools

[`eslint.config.js`](eslint.config.js) and [`.prettierrc`](.prettierrc) hold the lint and format rules.
"""

PYTHON = """# Coding guidelines

- Naming: modules and functions use snake_case, as PEP 8 says.
- Package structure: handlers call services; services never import handlers.
- Raise a `ValueError` for bad input. Use the `logging` module, never `print`.
- pytest runs the tests under `tests/`.
- Ruff reads its rules from `pyproject.toml`.
"""

AGENTS_PREAMBLE = """# AGENTS.md

This file governs how AI coding agents work in this repository.

## Commands

Run `make check` before you propose a change.
"""


def body(text: str) -> str:
    """The text without its first heading, to put under a heading of a section."""
    return text.split("\n", 1)[1]


class Agt13ConventionsTests(unittest.TestCase):
    def check(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return self.check_root(root)

    def check_root(self, root: Path) -> dict:
        inventory = build_inventory(root)
        outcome = check_agt13(
            spec=REGISTRY_BY_ID[AGT13],
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
        spec = REGISTRY_BY_ID[AGT13]
        self.assertEqual(
            (spec.title, spec.severity.value, spec.tier, spec.scored, spec.status),
            ("Coding conventions written", "COSMETIC", "B", True, "implemented"),
        )

    # -- PASS -------------------------------------------------------------------------------------------------

    def test_a_file_that_covers_the_five_items_passes_for_each_stack(self):
        for stack, rel, text in (
            ("java", "CONVENTIONS.md", JAVA),
            ("node", "docs/coding-guidelines.md", NODE),
            ("python", ".github/CODE_STYLE.md", PYTHON),
        ):
            with self.subTest(stack=stack):
                check = self.check({rel: text})
                self.assertEqual(check["verdict"], "PASS", check["summary"])
                self.assertIn(f"conventions ({rel})", check["summary"])
                self.assertEqual(check["findings"], [])

    def test_the_file_names_match_in_any_case(self):
        for rel in ("conventions.md", "docs/Conventions", "CODING_STANDARDS.md", "docs/team/naming-convention.rst"):
            with self.subTest(rel=rel):
                self.assertEqual(self.check({rel: PYTHON})["verdict"], "PASS")

    def test_the_greenfield_conventions_template_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "templates"
            shutil.copytree(GREENFIELD_TEMPLATES, copy)
            check = self.check_root(copy)
        self.assertEqual(check["verdict"], "PASS", check["summary"])
        self.assertIn("CONVENTIONS.md", check["summary"])

    def test_aider_reading_the_file_does_not_matter(self):
        files = {"CONVENTIONS.md": PYTHON, ".aider.conf.yml": "read: [CONVENTIONS.md]\n"}
        self.assertEqual(self.check(files)["verdict"], "PASS")

    # -- PARTIAL ----------------------------------------------------------------------------------------------

    def test_a_file_missing_items_is_partial_and_names_them(self):
        text = "# Conventions\n\nClasses use PascalCase. Log through SLF4J and throw a domain exception.\n"
        check = self.check({"CONVENTIONS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn(
            "do not cover layering, testing, a link to the formatter or linter config", check["summary"]
        )
        self.assertEqual(
            check["findings"][0]["evidence"], [{"path": "CONVENTIONS.md", "line": 1, "note": "conventions file"}]
        )

    def test_errors_without_logging_leave_the_item_open(self):
        text = JAVA.replace("## Errors and logging", "## Errors").replace(" Log through SLF4J.", "")
        check = self.check({"CONVENTIONS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("do not cover error handling and logging", check["summary"])

    def test_a_stub_word_is_partial_and_cites_its_line(self):
        text = NODE + "\n## 6. Branching\n\nBranching model: TBD (for example GitFlow).\n"
        check = self.check({"CONVENTIONS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertEqual(
            check["summary"], "the conventions (CONVENTIONS.md) hold the stub word TBD at CONVENTIONS.md:25"
        )
        self.assertIn(
            {"path": "CONVENTIONS.md", "line": 25, "note": "stub word TBD"}, check["findings"][0]["evidence"]
        )

    def test_todo_is_a_stub_word_too(self):
        check = self.check({"CONVENTIONS.md": PYTHON + "- TODO: the API rules.\n"})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("stub word TODO at CONVENTIONS.md:8", check["summary"])

    def test_missing_items_and_a_stub_word_are_both_named(self):
        check = self.check({"CONVENTIONS.md": "# Conventions\n\nNaming: TBD.\n"})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("; they hold the stub word TBD at CONVENTIONS.md:3", check["summary"])

    def test_a_stub_word_must_be_a_whole_upper_case_word_outside_code(self):
        for extra in (
            "- A todo list has no place in a commit.\n",
            "- Name the flag `TODO_ENABLED`, and keep `TBD` out of code.\n",
            "```text\nTODO: an example of a comment we reject\n```\n",
            "- A TODOS file and a TBDX tag are not stub words.\n",
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.check({"CONVENTIONS.md": PYTHON + extra})["verdict"], "PASS")

    # -- sections in AGENTS.md and CONTRIBUTING.md -----------------------------------------------------------------

    def test_a_conventions_section_in_agents_md_counts(self):
        check = self.check({"AGENTS.md": AGENTS_PREAMBLE + "\n## Conventions\n\n" + body(PYTHON)})
        self.assertEqual(check["verdict"], "PASS", check["summary"])
        self.assertIn("AGENTS.md:9 § Conventions", check["summary"])

    def test_a_section_in_contributing_md_counts(self):
        for rel in ("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"):
            with self.subTest(rel=rel):
                check = self.check({rel: "# Contributing\n\n## 3. Code style\n" + body(JAVA).replace("## ", "### ")})
                self.assertEqual(check["verdict"], "PASS", check["summary"])
                self.assertIn(f"{rel}:3 § 3. Code style", check["summary"])

    def test_a_naming_section_alone_is_partial(self):
        text = AGENTS_PREAMBLE + "\n### Naming\n\nFunctions use camelCase.\n"
        check = self.check({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("AGENTS.md:9 § Naming", check["summary"])
        self.assertIn({"path": "AGENTS.md", "line": 9, "note": "section: Naming"}, check["findings"][0]["evidence"])

    def test_a_section_ends_at_the_next_heading_of_its_level(self):
        text = AGENTS_PREAMBLE + "\n## Coding standards\n\nUse snake_case.\n\n## Testing\n\npytest runs `tests/`.\n"
        check = self.check({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("testing", check["summary"])

    def test_a_subsection_belongs_to_its_section(self):
        text = AGENTS_PREAMBLE + "\n## Conventions\n\n### Rules\n" + body(PYTHON)
        self.assertEqual(self.check({"AGENTS.md": text})["verdict"], "PASS")

    def test_a_file_and_a_section_are_read_together(self):
        files = {
            "CONVENTIONS.md": "# Conventions\n\nUse snake_case. Handlers call services, which is the layering.\n",
            "CONTRIBUTING.md": "# Contributing\n\n## Code style\n\nRaise errors; log them. pytest tests. "
            "Ruff reads `pyproject.toml`.\n",
        }
        check = self.check(files)
        self.assertEqual(check["verdict"], "PASS", check["summary"])
        self.assertIn("conventions (CONVENTIONS.md; CONTRIBUTING.md:3 § Code style)", check["summary"])

    def test_a_stub_word_in_any_source_is_partial(self):
        files = {"CONVENTIONS.md": PYTHON, "AGENTS.md": AGENTS_PREAMBLE + "\n## Naming\n\nTBD\n"}
        check = self.check(files)
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertEqual(
            check["summary"],
            "the conventions (CONVENTIONS.md; AGENTS.md:9 § Naming) hold the stub word TBD at AGENTS.md:11",
        )

    # -- FAIL ------------------------------------------------------------------------------------------------

    def test_no_conventions_fails(self):
        check = self.check({"README.md": "# x\n", "src/conventions.md": PYTHON})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(len(check["findings"]), 1)
        self.assertIn("there is no conventions file", check["findings"][0]["statement"])
        self.assertEqual(check["findings"][0]["evidence"], [])

    def test_an_instruction_file_with_no_section_fails_and_is_cited(self):
        check = self.check({"AGENTS.md": AGENTS_PREAMBLE, "CONTRIBUTING.md": "# Contributing\n"})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(
            check["summary"], "there is no conventions file and AGENTS.md or CONTRIBUTING.md has no conventions section"
        )
        self.assertEqual(
            [e["path"] for e in check["findings"][0]["evidence"]], ["AGENTS.md", "CONTRIBUTING.md"]
        )

    def test_the_docs_style_guide_alone_fails(self):
        self.assertEqual(self.check({"docs/STYLE_GUIDE.md": "# Style guide\n\n" + body(PYTHON)})["verdict"], "FAIL")

    def test_headings_that_do_not_open_a_conventions_section(self):
        for heading in ("# Conventions", "## Git conventions", "## Commit conventions", "## Branch naming"):
            with self.subTest(heading=heading):
                text = AGENTS_PREAMBLE + f"\n{heading}\n\n" + body(PYTHON)
                self.assertEqual(self.check({"AGENTS.md": text})["verdict"], "FAIL")

    def test_a_heading_in_a_fenced_block_is_not_a_section(self):
        text = AGENTS_PREAMBLE + "\n```markdown\n## Conventions\n" + body(PYTHON) + "```\n"
        self.assertEqual(self.check({"AGENTS.md": text})["verdict"], "FAIL")

    def test_a_file_that_is_not_prose_does_not_count(self):
        self.assertEqual(self.check({".github/workflows/conventions.yml": PYTHON})["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
