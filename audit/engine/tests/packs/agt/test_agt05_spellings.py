# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`AGT-05` reads a verb under each spelling the spec accepts, and under no other name (issue #8).

`spec/command-surface.md` § Spelling per runner spells each verb as its own name; only `format:check` has other
spellings (`format-check` on Make and the pyproject runners, `formatCheck` on Gradle). An instruction file that
writes `make format-check` names the verb. A runner script under another name (`type-check`) is not a verb, so
naming it does not name `typecheck`. The check runs in-process here, so coverage traces it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.agt import check_agt05  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

MAKEFILE = "".join(
    f"{target}:\n\t@true\n"
    for target in ("format", "format\\:check", "format-check", "lint", "typecheck", "test", "check", "security")
)


def _agt05(agents_md: str) -> tuple[str, str]:
    """``(verdict, summary)`` of `AGT-05` on a Make repository whose AGENTS.md is ``agents_md``."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        support.write(root, "Makefile", MAKEFILE)
        support.write(root, "AGENTS.md", agents_md)
        inventory = build_inventory(root)
        outcome = check_agt05(
            spec=REGISTRY_BY_ID["AGT-05"],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=None,
            session=None,
        )
    return outcome.verdict.value, outcome.summary


class Agt05SpellingTests(unittest.TestCase):
    def test_the_make_alias_of_format_check_names_the_verb(self):
        text = "# Commands\n\n`make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, " + (
            "`make check`, `make security`.\n"
        )
        self.assertEqual(_agt05(text), ("PASS", "all 7 verbs named in AGENTS.md and resolved on a runner"))

    def test_a_script_name_that_is_not_a_verb_spelling_does_not_name_the_verb(self):
        text = "# Commands\n\n`make format`, `make format-check`, `make lint`, `make type-check`, `make test`, " + (
            "`make check`, `make security`.\n"
        )
        self.assertEqual(_agt05(text), ("PARTIAL", "not named: typecheck"))


if __name__ == "__main__":
    unittest.main()
