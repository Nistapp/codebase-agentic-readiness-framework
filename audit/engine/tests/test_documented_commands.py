# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""A command written as inline code is documented, as one in a fenced block is (issue #8).

The rubrics of "`EXEC-03` Non-interactive setup path" and "`TST-04` Fast path documented" say an entry document
"shows" the command. Both checks read only fenced shell blocks, so a single-test command in a bullet
(`` - Run one test: `pytest -k name` ``) read as missing. `extract_documented_commands` returns the fenced commands
and then each inline code span outside a fence; each check's own pattern decides which spans are commands. The checks
run in-process here, so coverage traces them.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks._common import extract_documented_commands  # noqa: E402
from audit.rules.checks.execution import check_exec03  # noqa: E402
from audit.rules.checks.tst import check_tst04  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

#: A Python project with one test file and no setup artifact.
_BASE = {"pyproject.toml": '[project]\nname = "x"\n', "src/x.py": "x = 1\n", "tests/test_x.py": "def test_x(): pass\n"}


def _run(check, check_id: str, agents_md: str) -> tuple[str, str]:
    """``(verdict, summary)`` of one check on ``_BASE`` with ``agents_md`` as its AGENTS.md."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in {**_BASE, "AGENTS.md": agents_md}.items():
            support.write(root, rel, text)
        inventory = build_inventory(root)
        outcome = check(
            spec=REGISTRY_BY_ID[check_id],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=None,
            session=None,
        )
    return outcome.verdict.value, outcome.summary


class ExtractDocumentedCommandsTests(unittest.TestCase):
    def test_fenced_commands_come_first_then_inline_spans_outside_a_fence(self):
        text = (
            "Run `make setup` once.\n"
            "```bash\n"
            "$ make test  # the suite\n"
            "```\n"
            "```text\n"
            "`not a span` inside a fence\n"
            "```\n"
            "- One test: `$ pytest -k name` or ``pytest tests/test_x.py::test_x``\n"
        )
        self.assertEqual(
            extract_documented_commands(text),
            [
                ("bash", 3, "make test"),
                ("inline", 1, "make setup"),
                ("inline", 8, "pytest -k name"),
                ("inline", 8, "pytest tests/test_x.py::test_x"),
            ],
        )

    def test_an_empty_span_is_left_out(self):
        self.assertEqual(extract_documented_commands("A `  ` gap.\n"), [])


class InlineCommandCheckTests(unittest.TestCase):
    def test_tst04_accepts_a_single_test_command_in_a_bullet(self):
        verdict, summary = _run(check_tst04, "TST-04", "# Rules\n\n- Run one test: `pytest -k test_x`.\n")
        self.assertEqual(verdict, "PASS")
        self.assertEqual(
            summary, "fast path documented in an inline code span: AGENTS.md:3 `pytest -k test_x` (scope: AGENTS.md)"
        )

    def test_tst04_still_fails_on_a_full_suite_span(self):
        verdict, summary = _run(check_tst04, "TST-04", "# Rules\n\n- Run the suite: `pytest`.\n")
        self.assertEqual(verdict, "FAIL")
        self.assertIn("in fenced shell blocks or inline code spans", summary)

    def test_exec03_accepts_an_install_command_in_a_bullet(self):
        verdict, summary = _run(check_exec03, "EXEC-03", "# Setup\n\n- Install: `pip install -e .`\n")
        self.assertEqual((verdict, summary), ("PASS", "documented setup command: AGENTS.md: pip install -e ."))

    def test_exec03_ignores_a_span_that_is_not_an_install_command(self):
        verdict, _summary = _run(check_exec03, "EXEC-03", "# Setup\n\n- The config lives in `pyproject.toml`.\n")
        self.assertEqual(verdict, "FAIL")


if __name__ == "__main__":
    unittest.main()
