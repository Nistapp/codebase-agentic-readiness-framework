# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The ruleset changelog agrees with ``__ruleset_revision__`` and names each revision once.

Engine branches reserve revision numbers (``2026-11-19.11``) before they merge. When two branches took the same
number, git merged the identical table rows without a conflict and left two rows with one revision. These tests read
the changelog's revision table (``docs/reference/changelog.md``, newest first) and the self-audit page's ruleset row,
and fail on a repeated, misordered or stale revision.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
REPO = ENGINE.parent.parent
sys.path.insert(0, str(ENGINE))

from audit import __ruleset_revision__  # noqa: E402

CHANGELOG = ENGINE / "docs" / "reference" / "changelog.md"
SELF_AUDIT = REPO / "docs" / "reference" / "self-audit.md"

_ROW = re.compile(r"^\| `(\d{4}-\d{2}-\d{2}\.[1-9]\d*)` \|", re.MULTILINE)
_SELF_AUDIT_ROW = re.compile(r"^\| Ruleset \| `([^`]+)`", re.MULTILINE)


def table_revisions(text: str) -> list[str]:
    """The revisions of the changelog table, in page order."""
    return _ROW.findall(text)


def revision_key(revision: str) -> tuple[str, int]:
    """Sort key: the date, then the number within the day (``.10`` comes after ``.9``)."""
    day, number = revision.split(".")
    return day, int(number)


def problems(revisions: list[str], current: str) -> list[str]:
    """What is wrong with a newest-first revision list whose head must be ``current``; empty when nothing is."""
    found = []
    seen: set[str] = set()
    for revision in revisions:
        if revision in seen:
            found.append(f"revision {revision} has more than one row")
        seen.add(revision)
    for newer, older in zip(revisions, revisions[1:]):
        if revision_key(newer) <= revision_key(older) and newer != older:
            found.append(f"revision {newer} is listed above {older}, which is not older")
    if not revisions:
        found.append("the changelog lists no revision")
    elif revisions[0] != current:
        found.append(f"the newest row is {revisions[0]}, but __ruleset_revision__ is {current}")
    return found


class RulesetChangelogTests(unittest.TestCase):
    def test_the_changelog_names_each_revision_once_newest_first_ending_at_the_current_one(self):
        revisions = table_revisions(CHANGELOG.read_text(encoding="utf-8"))
        self.assertEqual(problems(revisions, __ruleset_revision__), [])

    def test_the_self_audit_page_states_the_current_revision(self):
        stated = _SELF_AUDIT_ROW.findall(SELF_AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(stated, [__ruleset_revision__])


class ProblemsTests(unittest.TestCase):
    def test_a_clean_list_has_no_problem(self):
        self.assertEqual(problems(["2026-11-20.10", "2026-11-20.9", "2026-11-19.17"], "2026-11-20.10"), [])

    def test_a_duplicate_row_is_reported(self):
        self.assertEqual(
            problems(["2026-11-19.12", "2026-11-19.11", "2026-11-19.11", "2026-11-19.10"], "2026-11-19.12"),
            ["revision 2026-11-19.11 has more than one row"],
        )

    def test_an_older_revision_above_a_newer_one_is_reported(self):
        self.assertEqual(
            problems(["2026-11-20.9", "2026-11-20.10"], "2026-11-20.9"),
            ["revision 2026-11-20.9 is listed above 2026-11-20.10, which is not older"],
        )

    def test_a_stale_head_is_reported(self):
        self.assertEqual(
            problems(["2026-11-20.14"], "2026-11-20.15"),
            ["the newest row is 2026-11-20.14, but __ruleset_revision__ is 2026-11-20.15"],
        )

    def test_an_empty_table_is_reported(self):
        self.assertEqual(problems([], "2026-11-20.15"), ["the changelog lists no revision"])

    def test_the_rows_are_read_from_the_table_only(self):
        text = "| `2026-11-20.2` | 2026-11-20 | 61 | x |\n## `2026-11-05.4`\n| `AGT-01` | y |\n"
        self.assertEqual(table_revisions(text), ["2026-11-20.2"])


if __name__ == "__main__":
    unittest.main()
