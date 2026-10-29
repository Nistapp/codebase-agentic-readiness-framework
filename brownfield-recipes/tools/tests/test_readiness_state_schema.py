# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The readiness-state schema accepts its examples and refuses each planted breakage with a known message.

`schema/readiness-state.schema.json` is the format of the state `tools/progress.py` writes. A breakage the schema can
express (a bad status, an unknown theme, an extra key, a bad SHA, a missing field) is refused by the schema; one it
cannot (a missing reason, a repeated finding, a theme list out of order) is refused by `progress.state_rule_errors`.
Standard library only.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any, Callable

import _paths
import _jsonschema_subset as subset
import progress

SCHEMA_DIR = _paths.TOOLS.parent / "schema"
SCHEMA_PATH = SCHEMA_DIR / "readiness-state.schema.json"
EXAMPLES = (
    SCHEMA_DIR / "examples" / "readiness-state.example-service.json",
    SCHEMA_DIR / "examples" / "readiness-state.example-service.in-progress.json",
)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def item(state: dict[str, Any], finding: str) -> dict[str, Any]:
    found: dict[str, Any] = next(entry for entry in state["items"] if entry["finding"] == finding)
    return found


class ReadinessStateSchemaCase(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = load(SCHEMA_PATH)
        self.example = load(EXAMPLES[1])

    def schema_messages(self, document: Any) -> list[str]:
        return [str(found) for found in subset.SubsetValidator(self.schema).validate(document)]

    def broken(self, change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        document: dict[str, Any] = copy.deepcopy(self.example)
        change(document)
        return document

    def test_the_schema_is_in_the_subset_and_names_its_version(self) -> None:
        self.assertEqual(subset.lint_schema(self.schema), [])
        self.assertEqual(self.schema["$id"], "urn:codebase-agentic-readiness-framework:readiness-state:0.1")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], progress.SCHEMA_VERSION)

    def test_every_example_is_valid(self) -> None:
        for path in EXAMPLES:
            with self.subTest(path.name):
                self.assertEqual(progress.state_errors(load(path)), [])

    def test_the_status_lists_match_the_tool(self) -> None:
        item_schema = self.schema["$defs"]["item"]["properties"]
        self.assertEqual(tuple(item_schema["status"]["enum"]), progress.ITEM_STATUSES)
        self.assertEqual(tuple(self.schema["$defs"]["themeId"]["enum"]), progress.THEME_IDS)

    def test_the_schema_refuses_each_planted_breakage(self) -> None:
        cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
            ("bad status", lambda d: item(d, "F-001").update(status="finished"), "/items/0/status: expected one of"),
            ("unknown theme", lambda d: item(d, "F-001").update(theme="T9"), "/items/0/theme: expected one of"),
            ("extra key", lambda d: d.update(extra=1), "/: unexpected property: 'extra'"),
            ("extra item key", lambda d: item(d, "F-001").update(owner="x"), "/items/0: unexpected property: 'owner'"),
            (
                "short sha",
                lambda d: item(d, "F-001").update(commits=["abc"]),
                "/items/0/commits/0: does not match the pattern",
            ),
            ("upper-case sha", lambda d: d["source_reports"][0].update(git_sha="A" * 40), "/source_reports/0/git_sha"),
            (
                "missing reason key",
                lambda d: item(d, "F-001").pop("reason"),
                "/items/0: missing the required property 'reason'",
            ),
            ("bad date", lambda d: d["log"][0].update(date="29/10/2026"), "/log/0/date: does not match the pattern"),
            ("wrong version", lambda d: d.update(schema_version="0.2"), '/schema_version: expected "0.1"'),
            ("negative debt", lambda d: item(d, "F-001")["debt"][0].update(count=-1), "/items/0/debt/0/count"),
            (
                "agent preference",
                lambda d: d["preferences"][0].update(by="agent"),
                '/preferences/0/by: expected "owner"',
            ),
            ("no report", lambda d: d.update(source_reports=[]), "/source_reports: 0 items is below the minimum"),
            ("seven themes", lambda d: d["themes"].pop(), "/themes: 7 items is below the minimum"),
            ("absolute path", lambda d: d["source_reports"][0].update(path="/abs"), "/source_reports/0/path"),
        ]
        for name, change, expected in cases:
            with self.subTest(name):
                found = self.schema_messages(self.broken(change))
                self.assertTrue(any(message.startswith(expected) for message in found), found)

    def test_the_tool_refuses_what_the_schema_cannot_express(self) -> None:
        cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
            ("skipped without reason", lambda d: item(d, "F-004").update(reason=None), "status skipped needs a reason"),
            ("blocked without reason", lambda d: item(d, "F-003").update(status="blocked"), "status blocked needs"),
            ("agent skip", lambda d: item(d, "F-004").update(by="agent"), "only the owner sets status skipped"),
            ("done with debt", lambda d: item(d, "F-001").update(status="done"), "partial, never done"),
            ("repeated finding", lambda d: d["items"].append(copy.deepcopy(d["items"][0])), "already at /items/0"),
            ("rejected and queued", lambda d: d["not_queued"][0].update(finding="F-001"), "already at /items/0"),
            ("themes out of order", lambda d: d["themes"].reverse(), "/themes: must be T1"),
            (
                "repeated preference",
                lambda d: d["preferences"].append(copy.deepcopy(d["preferences"][0])),
                "already set",
            ),
        ]
        for name, change, expected in cases:
            with self.subTest(name):
                document = self.broken(change)
                self.assertEqual(self.schema_messages(document), [])
                errors = progress.state_errors(document)
                self.assertTrue(any(expected in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
