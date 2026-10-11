# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine adapter as a function: an engine report goes in, the parts of a draft come out, and nothing is read or written.

Each test builds an engine report by hand (`_engine_reports`) and calls `convert`, so that a mapping rule is tested
alone. The adapter is run on the engine's real reports, and through the command, in `test_import_engine.py`.
Standard library only.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import importlib
import re
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import _engine_reports as er
import _paths  # noqa: F401
import _common
import _engine_adapter as adapter
import engine as engine_launcher
import validate_report as vr

CATALOGUE = vr.load_catalogue()
TARGET = Path("/work/service")


def convert(report: Any, **options: Any) -> adapter.Conversion:
    return adapter.convert(report, catalogue=CATALOGUE, **options)


def refused(test: unittest.TestCase, report: Any, **options: Any) -> _common.ValidationFailed:
    with test.assertRaises(_common.ValidationFailed) as caught:
        convert(report, **options)
    return caught.exception


class LocateTests(unittest.TestCase):
    def assert_located(self, text: str, path: str, note: str | None) -> None:
        self.assertEqual(adapter.locate(text), adapter.Located(path, note), text)

    def test_a_path_is_carried_as_it_is(self) -> None:
        for text in (
            "src/a.ts",
            "AGENTS.md",
            "docs/",
            ".opencode/",
            "my docs/file name.md",
            ".github/workflows/ci.yml",
        ):
            with self.subTest(text=text):
                self.assert_located(text, text, None)

    def test_surrounding_whitespace_is_not_part_of_the_path(self) -> None:
        self.assert_located("  src/a.ts \n", "src/a.ts", None)

    def test_a_file_and_a_key_are_split_at_the_first_colon(self) -> None:
        self.assert_located("package.json:lint", "package.json", "lint")
        self.assert_located("tsconfig.json:strict", "tsconfig.json", "strict")
        self.assert_located("Makefile:format:check", "Makefile", "format:check")

    def test_a_colon_in_a_directory_name_is_read_as_a_key(self) -> None:
        """The known limit of the rule: the engine's text does not say which colon is which."""
        self.assert_located("docs/a:b/c.md", "docs/a", "b/c.md")

    def test_a_colon_with_nothing_on_one_side_splits_nothing(self) -> None:
        self.assert_located("a.ts:", "a.ts:", None)
        self.assert_located(":key", ":key", None)

    def test_a_file_and_a_bracketed_tag_are_split(self) -> None:
        self.assert_located("pyproject.toml [mypy/pyright]", "pyproject.toml", "mypy/pyright")
        self.assert_located("setup.cfg [mypy]", "setup.cfg", "mypy")

    def test_a_space_without_a_tag_is_part_of_the_path(self) -> None:
        self.assert_located("docs/my file [draft].md", "docs/my file [draft].md", None)
        self.assert_located("a [b] [c]", "a [b] [c]", None)

    def test_a_placeholder_names_no_file_and_is_dropped_quietly(self) -> None:
        for text in ("<repository>", "(no example file)", "<>", "()", "", "   ", "\n"):
            with self.subTest(text=text):
                found = adapter.locate(text)
                self.assertIsInstance(found, adapter.NotCarried)
                assert isinstance(found, adapter.NotCarried)
                self.assertTrue(found.quiet)
                self.assertEqual(found.reason, "it is a placeholder, and names no file")

    def test_a_text_that_only_starts_or_ends_like_a_placeholder_is_a_path(self) -> None:
        for text in ("(a)b", "a(b)", "<a>b", "b<a>", "<a><b>"):
            with self.subTest(text=text):
                self.assertIsInstance(adapter.locate(text), adapter.Located)

    def test_a_path_outside_the_repository_is_dropped_and_says_why(self) -> None:
        cases = {
            "/home/kc/.cache/codebase-memory-mcp": "the path is absolute, so it is outside the repository",
            "C:\\Users\\kc\\index": "the path is absolute, so it is outside the repository",
            "../other/file": "the path climbs out of the target, so it is outside the repository",
            "a/../../b": "the path climbs out of the target, so it is outside the repository",
            "a\x00b": "the path contains a NUL character, so it is outside the repository",
            "/etc/passwd:key": "the path is absolute, so it is outside the repository",
        }
        for text, reason in cases.items():
            with self.subTest(text=text):
                found = adapter.locate(text)
                self.assertEqual(found, adapter.NotCarried(reason))
                assert isinstance(found, adapter.NotCarried)
                self.assertFalse(found.quiet)

    def test_a_file_that_leaves_the_repository_before_the_colon_is_dropped_though_the_whole_looks_inside(self) -> None:
        """Read whole, `a/../..:key` ends in one odd name inside the repository, so the head is checked after the split."""
        self.assertEqual(
            adapter.locate("a/../..:key"),
            adapter.NotCarried("the path climbs out of the target, so it is outside the repository"),
        )

    def test_a_path_inside_the_repository_that_goes_through_dotdot_is_carried(self) -> None:
        self.assert_located("a/../b/c.ts", "a/../b/c.ts", None)


class SafeKeyTests(unittest.TestCase):
    def test_an_id_without_whitespace_is_unchanged(self) -> None:
        self.assertEqual(adapter.safe_key("SEC-02:src/a.ts"), "SEC-02:src/a.ts")

    def test_each_whitespace_character_is_written_in_hexadecimal(self) -> None:
        self.assertEqual(adapter.safe_key("SEC-02:a b"), "SEC-02:a%20b")
        self.assertEqual(adapter.safe_key("SEC-02:a\tb\nc"), "SEC-02:a%09b%0Ac")
        self.assertEqual(adapter.safe_key("SEC-02:a\u00a0b"), "SEC-02:a%C2%A0b")
        self.assertEqual(adapter.safe_key("SEC-02:a  b"), "SEC-02:a%20%20b")

    def test_a_percent_sign_is_left_alone(self) -> None:
        self.assertEqual(adapter.safe_key("SEC-02:a%20b"), "SEC-02:a%20b")


class FitTests(unittest.TestCase):
    def test_a_text_within_the_limit_is_unchanged(self) -> None:
        self.assertEqual(adapter.fit("abc", 3), "abc")
        self.assertEqual(adapter.fit("", 3), "")

    def test_a_longer_text_is_cut_to_the_limit_with_a_mark(self) -> None:
        cut = adapter.fit("abcd", 3)
        self.assertEqual((cut, len(cut)), ("ab\u2026", 3))


class LimitTests(unittest.TestCase):
    """The limits are read from the report schema, so a change there is a change here."""

    def test_the_limits_are_the_report_schemas(self) -> None:
        self.assertEqual(adapter.maximum("check", "summary"), 500)
        self.assertEqual(adapter.maximum("check", "title"), 200)
        self.assertEqual(adapter.maximum("check", "evidence", "maxItems"), 50)
        self.assertEqual(adapter.maximum("finding", "evidence", "maxItems"), 50)
        self.assertEqual(adapter.maximum("finding", "statement"), 600)
        self.assertEqual(adapter.maximum("remediation", "summary"), 600)
        self.assertEqual(adapter.maximum("evidence", "note"), 300)

    def test_a_limit_behind_a_reference_is_found(self) -> None:
        self.assertEqual(adapter.maximum("evidence", "path"), 500)
        self.assertEqual(adapter.maximum("finding", "key"), 400)


class ChecksTests(unittest.TestCase):
    def one(self, engine_check: dict[str, Any], findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return convert(er.report(TARGET, [engine_check], findings or [])).checks[0]

    def test_a_check_is_the_engines_with_its_verdict_twice_and_the_method_automated(self) -> None:
        check = self.one(er.check("TOOL-01", "FAIL", summary="No formatter."))
        self.assertEqual(
            check,
            {
                "id": "TOOL-01",
                "title": CATALOGUE_TITLE["TOOL-01"],
                "phase": 1,
                "severity": CATALOGUE_SEVERITY["TOOL-01"],
                "scored": CATALOGUE_SCORED["TOOL-01"],
                "method": "automated",
                "verdict": "FAIL",
                "engine_verdict": "FAIL",
                "summary": "No formatter.",
                "evidence": [],
                "searches": [],
            },
        )
        self.assertEqual(
            list(check),
            [
                "id",
                "title",
                "phase",
                "severity",
                "scored",
                "method",
                "verdict",
                "engine_verdict",
                "summary",
                "evidence",
                "searches",
            ],
        )

    def test_every_verdict_the_engine_gives_a_check_is_carried(self) -> None:
        for verdict in ("PASS", "PARTIAL", "FAIL", "UNKNOWN"):
            with self.subTest(verdict=verdict):
                check = self.one(er.check("TOOL-01", verdict))
                self.assertEqual((check["verdict"], check["engine_verdict"]), (verdict, verdict))

    def test_a_check_the_engine_ran_is_scored_as_the_engine_scores_it(self) -> None:
        for status in ("implemented", "planned"):
            for scored in (True, False):
                with self.subTest(scored=scored, status=status):
                    self.assertIs(self.one(er.check("TOOL-01", scored=scored, status=status))["scored"], scored)

    def test_a_check_the_engine_blocked_is_unknown_and_scored_as_the_catalogue_scores_it(self) -> None:
        # What an engine before ruleset 2026-10-11.1 reported for CON-01: blocked, unscored, UNKNOWN.
        blocked = er.check("CON-01", "UNKNOWN", scored=False, status="blocked", summary="blocked: no contract")
        conversion = convert(er.report(TARGET, [blocked]))
        check = conversion.checks[0]
        self.assertEqual(
            (check["verdict"], check["engine_verdict"], check["scored"], check["summary"]),
            ("UNKNOWN", "UNKNOWN", True, "The engine did not evaluate this check: its ruleset had blocked it."),
        )
        self.assertEqual(
            conversion.warnings,
            [
                "CON-01: the engine's ruleset did not evaluate it, so it is recorded as UNKNOWN and is scored as the "
                "catalogue scores it"
            ],
        )

    def test_a_blocked_check_that_the_catalogue_does_not_score_stays_unscored(self) -> None:
        for scored in (True, False):
            with self.subTest(scored=scored):
                check = self.one(er.check("NAV-04", "UNKNOWN", scored=scored, status="blocked"))
                self.assertIs(check["scored"], False)

    def test_only_a_blocked_check_draws_the_warning_and_the_summary(self) -> None:
        conversion = convert(er.report(TARGET, [er.check("TOOL-01", "PASS", summary="fine")]))
        self.assertEqual((conversion.checks[0]["summary"], conversion.warnings), ("fine", []))

    def test_the_engines_checks_come_in_the_engines_order(self) -> None:
        engine = er.report(TARGET, [er.check("TOOL-02"), er.check("AGT-01"), er.check("TOOL-01")])
        self.assertEqual([c["id"] for c in convert(engine).checks], ["TOOL-02", "AGT-01", "TOOL-01"])

    def test_a_payload_is_carried_unchanged_and_apart_from_the_input(self) -> None:
        payload = {"kind": "command_surface", "rows": [{"verb": "test", "runner": "npm"}]}
        engine = er.report(TARGET, [er.check("CMD-01", data=payload)])
        check = convert(engine).checks[0]
        self.assertEqual(check["data"], payload)
        self.assertEqual(list(check)[-1], "data")
        check["data"]["rows"].append("changed")
        self.assertEqual(payload["rows"], [{"verb": "test", "runner": "npm"}])

    def test_an_empty_or_absent_payload_is_left_out(self) -> None:
        engine_check = er.check("CMD-01")
        del engine_check["data"]
        self.assertNotIn("data", self.one(engine_check))
        self.assertNotIn("data", self.one(er.check("CMD-01", data={})))

    def test_a_payload_with_no_kind_is_refused(self) -> None:
        error = refused(self, er.report(TARGET, [er.check("CMD-01", data={"rows": []})]))
        self.assertEqual(error.errors, ["engine report: /checks/0/data: the payload of CMD-01 has no kind"])

    def test_a_long_title_and_summary_are_cut_with_a_warning_each(self) -> None:
        engine = er.report(TARGET, [er.check("TOOL-01", title="t" * 201, summary="s" * 501)])
        conversion = convert(engine)
        check = conversion.checks[0]
        self.assertEqual((len(check["title"]), check["title"][-1]), (200, "\u2026"))
        self.assertEqual((len(check["summary"]), check["summary"][-1]), (500, "\u2026"))
        self.assertEqual(
            conversion.warnings,
            [
                "TOOL-01: the title is 201 characters and the report allows 200, so it was cut",
                "TOOL-01: the summary is 501 characters and the report allows 500, so it was cut",
            ],
        )

    def test_a_title_and_summary_at_the_limit_are_not_cut(self) -> None:
        conversion = convert(er.report(TARGET, [er.check("TOOL-01", title="t" * 200, summary="s" * 500)]))
        self.assertEqual((conversion.checks[0]["title"], conversion.checks[0]["summary"]), ("t" * 200, "s" * 500))
        self.assertEqual(conversion.warnings, [])

    def test_a_check_that_only_an_agent_can_judge_is_refused(self) -> None:
        error = refused(self, er.report(TARGET, [er.check("AGT-11")]))
        self.assertEqual(
            error.errors,
            [
                "engine report: /checks/0/id: AGT-11 is a check that only an agent can judge, "
                "so the engine cannot report it"
            ],
        )

    def test_a_check_the_catalogue_does_not_have_is_refused(self) -> None:
        engine_check = er.check("TOOL-01")
        engine_check["id"] = "ZZZ-99"
        error = refused(self, er.report(TARGET, [engine_check]))
        self.assertEqual(error.errors, ["engine report: /checks/0/id: ZZZ-99 is not a check in catalogue.json"])

    def test_a_check_listed_twice_is_refused_once(self) -> None:
        error = refused(self, er.report(TARGET, [er.check("TOOL-01"), er.check("TOOL-01"), er.check("TOOL-02")]))
        self.assertEqual(
            error.errors, ["engine report: TOOL-01 appears more than once among the checks and not_applicable"]
        )

    def test_a_check_that_is_also_not_applicable_is_refused(self) -> None:
        error = refused(self, er.report(TARGET, [er.check("TOOL-01")], not_applicable=["TOOL-01"]))
        self.assertEqual(
            error.errors, ["engine report: TOOL-01 appears more than once among the checks and not_applicable"]
        )

    def test_every_problem_is_listed_and_counted(self) -> None:
        engine = er.report(
            TARGET, [er.check("AGT-11"), er.check("TOOL-01"), er.check("TOOL-01"), er.check("CMD-01", data={"x": 1})]
        )
        error = refused(self, engine)
        self.assertEqual(len(error.errors), 3)
        self.assertIn("3 problems", str(error))
        error = refused(self, er.report(TARGET, [er.check("AGT-11")]))
        self.assertTrue(str(error).endswith("1 problem"), str(error))


class NotApplicableTests(unittest.TestCase):
    def test_the_summary_of_a_check_that_does_not_apply_is_this_sentence(self) -> None:
        self.assertEqual(
            adapter.NOT_APPLICABLE_SUMMARY,
            "The engine did not run this check: it does not apply to the detected stack.",
        )

    def test_a_check_the_engine_left_out_is_the_catalogues_with_no_verdict_of_its_own(self) -> None:
        conversion = convert(er.report(TARGET, [er.check("TOOL-01")], not_applicable=["TOOL-02"]))
        self.assertEqual([c["id"] for c in conversion.checks], ["TOOL-01", "TOOL-02"])
        self.assertEqual(
            conversion.checks[1],
            {
                "id": "TOOL-02",
                "title": CATALOGUE_TITLE["TOOL-02"],
                "phase": 1,
                "severity": CATALOGUE_SEVERITY["TOOL-02"],
                "scored": CATALOGUE_SCORED["TOOL-02"],
                "method": "automated",
                "verdict": "NOT_APPLICABLE",
                "engine_verdict": "NOT_APPLICABLE",
                "summary": adapter.NOT_APPLICABLE_SUMMARY,
                "evidence": [],
                "searches": [],
            },
        )

    def test_the_checks_come_in_the_order_the_engine_listed_them(self) -> None:
        conversion = convert(er.report(TARGET, not_applicable=["TOOL-03", "AGT-01", "TOOL-01"]))
        self.assertEqual([c["id"] for c in conversion.checks], ["TOOL-03", "AGT-01", "TOOL-01"])

    def test_a_check_the_catalogue_does_not_have_is_refused(self) -> None:
        error = refused(self, er.report(TARGET, not_applicable=["ZZZ-99"]))
        self.assertEqual(error.errors, ["engine report: /not_applicable/0: ZZZ-99 is not a check in catalogue.json"])

    def test_a_check_that_only_an_agent_can_judge_is_refused(self) -> None:
        error = refused(self, er.report(TARGET, not_applicable=["TOOL-01", "AGT-11"]))
        self.assertEqual(
            error.errors,
            [
                "engine report: /not_applicable/1: AGT-11 is a check that only an agent can judge, "
                "so the engine cannot report it"
            ],
        )


class FindingsTests(unittest.TestCase):
    def converted(self, *findings: dict[str, Any], checks: list[dict[str, Any]] | None = None, **options: Any) -> Any:
        engine_checks = checks if checks is not None else [er.check("SEC-02", "FAIL"), er.check("AGT-08", "FAIL")]
        return convert(er.report(TARGET, engine_checks, list(findings)), **options)

    def test_a_finding_is_the_engines_with_a_key_and_a_summary_of_its_remediation(self) -> None:
        conversion = self.converted(
            er.finding(
                "SEC-02",
                "src/a.ts",
                severity="DEGRADER",
                statement="An agent cannot keep credentials out because a.ts has one.",
                remediation="Rotate it.",
                evidence=[er.evidence("src/a.ts", 5, "credential-shaped string")],
            )
        )
        self.assertEqual(
            conversion.findings,
            [
                {
                    "key": "SEC-02:src/a.ts",
                    "check": "SEC-02",
                    "severity": "DEGRADER",
                    "statement": "An agent cannot keep credentials out because a.ts has one.",
                    "evidence": [
                        {
                            "kind": "file",
                            "captured_by": "tool",
                            "tool": "python-agentic-audit",
                            "tool_version": "0.1.0",
                            "path": "src/a.ts",
                            "lines": "5",
                            "note": "credential-shaped string",
                        }
                    ],
                    "searches": [],
                    "remediation": {"summary": "Rotate it."},
                }
            ],
        )
        self.assertEqual(
            list(conversion.findings[0]),
            ["key", "check", "severity", "statement", "evidence", "searches", "remediation"],
        )
        self.assertEqual(
            list(conversion.findings[0]["evidence"][0]),
            ["kind", "captured_by", "tool", "tool_version", "path", "lines", "note"],
        )

    def test_the_findings_come_in_the_engines_order(self) -> None:
        conversion = self.converted(er.finding("SEC-02", "b"), er.finding("AGT-08"), er.finding("SEC-02", "a"))
        self.assertEqual([f["key"] for f in conversion.findings], ["SEC-02:b", "AGT-08", "SEC-02:a"])

    def test_no_decision_is_made_for_the_builder(self) -> None:
        finding = self.converted(er.finding("AGT-08")).findings[0]
        self.assertEqual(set(finding) & {"id", "disposition", "confirmed_via", "disposition_note"}, set())

    def test_a_finding_without_a_path_has_the_check_id_for_a_key(self) -> None:
        self.assertEqual(self.converted(er.finding("AGT-08")).findings[0]["key"], "AGT-08")

    def test_a_second_finding_with_the_same_id_takes_the_next_number(self) -> None:
        conversion = self.converted(er.finding("AGT-08"), er.finding("AGT-08"), er.finding("AGT-08"))
        self.assertEqual([f["key"] for f in conversion.findings], ["AGT-08", "AGT-08:2", "AGT-08:3"])

    def test_a_key_the_draft_already_holds_is_not_used_again(self) -> None:
        conversion = self.converted(er.finding("AGT-08"), er.finding("AGT-08"), taken_keys=["AGT-08", "AGT-08:2"])
        self.assertEqual([f["key"] for f in conversion.findings], ["AGT-08:3", "AGT-08:4"])

    def test_an_id_that_equals_a_number_given_to_an_earlier_finding_is_numbered_too(self) -> None:
        conversion = self.converted(er.finding("AGT-08"), er.finding("AGT-08"), er.finding("AGT-08", "2"))
        self.assertEqual([f["key"] for f in conversion.findings], ["AGT-08", "AGT-08:2", "AGT-08:2:2"])

    def test_whitespace_in_a_path_is_written_out_in_the_key(self) -> None:
        conversion = self.converted(er.finding("SEC-02", "docs/my file.md"))
        self.assertEqual(conversion.findings[0]["key"], "SEC-02:docs/my%20file.md")

    def test_a_key_is_cut_to_leave_room_for_a_number(self) -> None:
        path = "d/" * 300
        conversion = self.converted(er.finding("SEC-02", path), er.finding("SEC-02", path))
        first, second = (f["key"] for f in conversion.findings)
        self.assertEqual(len(first), 392)
        self.assertEqual(second, first + ":2")
        self.assertLessEqual(len(second), 400)

    def test_the_sentence_for_a_missing_remediation_is_this_one(self) -> None:
        self.assertEqual(adapter.NO_REMEDIATION, "The engine gave no remediation for this finding.")

    def test_a_remediation_the_engine_did_not_give_is_said_so(self) -> None:
        for given in (None, ""):
            with self.subTest(given=given):
                finding = self.converted(er.finding("AGT-08", remediation=given)).findings[0]
                self.assertEqual(finding["remediation"], {"summary": adapter.NO_REMEDIATION})
        engine_finding = er.finding("AGT-08")
        del engine_finding["remediation"]
        self.assertEqual(self.converted(engine_finding).findings[0]["remediation"], {"summary": adapter.NO_REMEDIATION})

    def test_a_long_statement_and_remediation_are_cut_with_a_warning_each(self) -> None:
        statement = "An agent cannot " + "x" * 600 + " because y."
        conversion = self.converted(er.finding("AGT-08", statement=statement, remediation="r" * 601))
        finding = conversion.findings[0]
        self.assertEqual((len(finding["statement"]), finding["statement"][-1]), (600, "\u2026"))
        self.assertEqual(
            (len(finding["remediation"]["summary"]), finding["remediation"]["summary"][-1]), (600, "\u2026")
        )
        self.assertEqual(
            conversion.warnings,
            [
                f"AGT-08: the statement is {len(statement)} characters and the report allows 600, so it was cut",
                "AGT-08: the remediation is 601 characters and the report allows 600, so it was cut",
            ],
        )

    def test_a_statement_and_remediation_at_the_limit_are_not_cut(self) -> None:
        statement = "An agent cannot " + "x" * 573 + " because y."
        conversion = self.converted(er.finding("AGT-08", statement=statement, remediation="r" * 600))
        self.assertEqual(len(conversion.findings[0]["statement"]), 600)
        self.assertEqual(conversion.warnings, [])

    def test_a_finding_of_a_check_the_report_does_not_hold_is_refused(self) -> None:
        error = refused(self, er.report(TARGET, [er.check("AGT-08")], [er.finding("SEC-02")]))
        self.assertEqual(error.errors, ["engine report: /findings/0/check: SEC-02 is not a check in this report"])

    def test_a_finding_whose_id_does_not_start_with_its_check_is_refused(self) -> None:
        error = refused(self, er.report(TARGET, [er.check("AGT-08")], [er.finding("AGT-08", id="SEC-02:a")]))
        self.assertEqual(
            error.errors, ["engine report: /findings/0/id: SEC-02:a does not start with its check, AGT-08"]
        )

    def test_a_check_and_a_finding_can_be_wrong_together_and_both_are_listed(self) -> None:
        engine = er.report(TARGET, [er.check("AGT-11")], [er.finding("AGT-08")])
        error = refused(self, engine)
        self.assertEqual(len(error.errors), 2)


class EvidenceTests(unittest.TestCase):
    def evidence(self, *items: dict[str, Any], check_id: str = "SEC-02") -> adapter.Conversion:
        return convert(er.report(TARGET, [er.check(check_id, "FAIL")], [er.finding(check_id, evidence=list(items))]))

    def test_a_line_becomes_a_string_and_no_line_leaves_the_field_out(self) -> None:
        conversion = self.evidence(
            er.evidence("a.ts", 5),
            er.evidence("b.ts"),
            er.evidence("c.ts", 0),
            er.evidence("d.ts", -3),
            er.evidence("e.ts", 1),
        )
        items = conversion.findings[0]["evidence"]
        self.assertEqual([i.get("lines") for i in items], ["5", None, None, None, "1"])

    def test_a_note_is_carried_and_an_absent_or_empty_note_is_left_out(self) -> None:
        conversion = self.evidence(er.evidence("a.ts", None, "why"), er.evidence("b.ts"), er.evidence("c.ts", None, ""))
        items = conversion.findings[0]["evidence"]
        self.assertEqual([i.get("note") for i in items], ["why", None, None])

    def test_a_key_in_the_path_becomes_the_note_and_comes_before_the_engines_own(self) -> None:
        conversion = self.evidence(er.evidence("package.json:lint"), er.evidence("README.md:docs/", 3, "kept"))
        items = conversion.findings[0]["evidence"]
        self.assertEqual(
            [(i["path"], i.get("note"), i.get("lines")) for i in items],
            [("package.json", "lint", None), ("README.md", "docs/: kept", "3")],
        )

    def test_a_long_note_is_cut_with_a_warning(self) -> None:
        conversion = self.evidence(er.evidence("a.ts", None, "n" * 301))
        note = conversion.findings[0]["evidence"][0]["note"]
        self.assertEqual((len(note), note[-1]), (300, "\u2026"))
        self.assertEqual(
            conversion.warnings, ["SEC-02: the note is 301 characters and the report allows 300, so it was cut"]
        )

    def test_the_tool_and_its_version_are_the_engines(self) -> None:
        report = er.report(TARGET, [er.check("SEC-02", "FAIL")], [er.finding("SEC-02", evidence=[er.evidence("a.ts")])])
        report["provenance"].update(tool="other-engine", version="9.8.7")
        item = convert(report).findings[0]["evidence"][0]
        self.assertEqual((item["captured_by"], item["tool"], item["tool_version"]), ("tool", "other-engine", "9.8.7"))

    def test_a_path_outside_the_repository_is_not_carried_and_is_warned_about_and_counted(self) -> None:
        conversion = self.evidence(er.evidence("/home/kc/.cache/index"), er.evidence("a.ts"))
        self.assertEqual([i["path"] for i in conversion.findings[0]["evidence"]], ["a.ts"])
        self.assertEqual(
            conversion.warnings,
            [
                "SEC-02: the evidence path '/home/kc/.cache/index' is not carried: "
                "the path is absolute, so it is outside the repository"
            ],
        )
        self.assertEqual(conversion.evidence_not_carried, 1)

    def test_a_placeholder_is_not_carried_and_needs_no_warning_and_is_not_counted(self) -> None:
        conversion = self.evidence(er.evidence("<repository>"), er.evidence("(no example file)"))
        self.assertEqual(conversion.findings[0]["evidence"], [])
        self.assertEqual((conversion.warnings, conversion.evidence_not_carried), ([], 0))

    def test_a_path_too_long_for_the_report_is_not_carried(self) -> None:
        conversion = self.evidence(er.evidence("p" * 501), er.evidence("p" * 500))
        self.assertEqual([len(i["path"]) for i in conversion.findings[0]["evidence"]], [500])
        self.assertEqual(
            conversion.warnings,
            [f"SEC-02: the evidence path {'p' * 501!r} is not carried: the path is 501 characters long"],
        )
        self.assertEqual(conversion.evidence_not_carried, 1)

    def test_a_finding_keeps_the_first_fifty_items_and_says_what_it_left_out(self) -> None:
        conversion = self.evidence(*[er.evidence(f"f{n}.ts") for n in range(53)])
        items = conversion.findings[0]["evidence"]
        self.assertEqual((len(items), items[0]["path"], items[-1]["path"]), (50, "f0.ts", "f49.ts"))
        self.assertEqual(
            conversion.warnings, ["SEC-02: 53 evidence items, and the report allows 50, so the rest are left out"]
        )
        self.assertEqual(conversion.evidence_not_carried, 3)

    def test_exactly_fifty_items_are_all_kept(self) -> None:
        conversion = self.evidence(*[er.evidence(f"f{n}.ts") for n in range(50)])
        self.assertEqual((len(conversion.findings[0]["evidence"]), conversion.warnings), (50, []))

    def test_a_check_gathers_the_evidence_of_its_findings_in_order(self) -> None:
        report = er.report(
            TARGET,
            [er.check("SEC-02", "FAIL"), er.check("AGT-08", "FAIL")],
            [
                er.finding("SEC-02", "a", evidence=[er.evidence("a.ts", 1), er.evidence("a2.ts")]),
                er.finding("AGT-08", evidence=[er.evidence("x.md")]),
                er.finding("SEC-02", "b", evidence=[er.evidence("b.ts", 2)]),
            ],
        )
        conversion = convert(report)
        sec, agt = conversion.checks
        self.assertEqual([i["path"] for i in sec["evidence"]], ["a.ts", "a2.ts", "b.ts"])
        self.assertEqual([i["path"] for i in agt["evidence"]], ["x.md"])

    def test_the_check_evidence_is_a_copy_of_the_findings(self) -> None:
        conversion = self.evidence(er.evidence("a.ts"))
        conversion.checks[0]["evidence"][0]["path"] = "changed.ts"
        self.assertEqual(conversion.findings[0]["evidence"][0]["path"], "a.ts")

    def test_a_check_without_findings_has_no_evidence(self) -> None:
        self.assertEqual(convert(er.report(TARGET, [er.check("SEC-02", "PASS")])).checks[0]["evidence"], [])

    def test_a_check_keeps_the_first_fifty_items_of_its_findings_too(self) -> None:
        report = er.report(
            TARGET,
            [er.check("SEC-02", "FAIL")],
            [
                er.finding("SEC-02", "a", evidence=[er.evidence(f"a{n}.ts") for n in range(30)]),
                er.finding("SEC-02", "b", evidence=[er.evidence(f"b{n}.ts") for n in range(30)]),
            ],
        )
        conversion = convert(report)
        evidence = conversion.checks[0]["evidence"]
        self.assertEqual((len(evidence), evidence[-1]["path"]), (50, "b19.ts"))
        self.assertEqual(
            conversion.warnings, ["SEC-02: 60 evidence items, and the report allows 50, so the rest are left out"]
        )
        self.assertEqual(conversion.evidence_not_carried, 10)


MEANINGS = {
    "index-in-use": "Whether the index is used.",
    "baseline-adequacy": "Whether the baseline is adequate.",
    "suite-trustworthiness": "Whether the suite catches regressions.",
    "doc-accuracy": "Whether the docs are accurate.",
    "gate-honoured": "Whether the gate is honoured.",
}
SPEC = Path(__file__).resolve().parents[3] / "spec"


class UnattestedTests(unittest.TestCase):
    def converted(self, unattested: list[str], **options: Any) -> adapter.Conversion:
        return convert(er.report(TARGET, unattested=unattested), **options)

    def test_each_fixed_item_becomes_the_attested_requirement_it_stands_for(self) -> None:
        conversion = self.converted(list(MEANINGS), meanings=MEANINGS)
        self.assertEqual(
            [(u["requirement"], u["property"]) for u in conversion.unattested],
            [
                ("REQ-SH-004", "index-in-use"),
                ("REQ-BF-004", "baseline-adequacy"),
                ("REQ-SH-050", "suite-trustworthiness"),
                ("REQ-SH-020", "doc-accuracy"),
                ("REQ-SH-026", "gate-honoured"),
            ],
        )
        self.assertEqual({u["method"] for u in conversion.unattested}, {"attested"})
        self.assertEqual([u["why"] for u in conversion.unattested], list(MEANINGS.values()))
        self.assertEqual(list(conversion.unattested[0]), ["requirement", "method", "property", "why"])

    def test_the_items_come_in_the_engines_order_and_only_those_the_engine_lists_are_carried(self) -> None:
        conversion = self.converted(["gate-honoured", "index-in-use"], meanings=MEANINGS)
        self.assertEqual([u["property"] for u in conversion.unattested], ["gate-honoured", "index-in-use"])
        self.assertEqual(self.converted([]).unattested, [])

    def test_an_item_with_no_words_of_the_engines_gets_a_plain_sentence(self) -> None:
        for meanings in (None, {}, {"index-in-use": ""}):
            with self.subTest(meanings=meanings):
                conversion = self.converted(["index-in-use"], meanings=meanings)
                self.assertEqual(conversion.unattested[0]["why"], "The engine cannot settle index-in-use by scanning.")

    def test_a_long_description_is_cut_with_a_warning(self) -> None:
        conversion = self.converted(["doc-accuracy"], meanings={"doc-accuracy": "w" * 301})
        why = conversion.unattested[0]["why"]
        self.assertEqual((len(why), why[-1]), (300, "\u2026"))
        self.assertEqual(
            conversion.warnings,
            ["doc-accuracy: the description is 301 characters and the report allows 300, so it was cut"],
        )

    def test_an_item_the_adapter_has_no_requirement_for_is_said_and_left_out(self) -> None:
        conversion = self.converted(["index-in-use", "something-new", "doc-accuracy"], meanings=MEANINGS)
        self.assertEqual([u["property"] for u in conversion.unattested], ["index-in-use", "doc-accuracy"])
        self.assertEqual(
            conversion.warnings,
            [
                "the engine lists the unattested item 'something-new', which maps to no requirement, so it is not carried"
            ],
        )


class UnattestedDriftTests(unittest.TestCase):
    """The table of items and requirements is the adapter's own, so these hold it to its sources."""

    def test_the_table_has_the_engines_five_items_and_no_other(self) -> None:
        engine_launcher.load_engine()
        evaluate = importlib.import_module("audit.evaluate")
        self.assertEqual(set(adapter.UNATTESTED_REQUIREMENTS), set(evaluate.UNATTESTED_ITEMS))

    def test_the_engine_has_words_for_each_item(self) -> None:
        engine_launcher.load_engine()
        presentation = importlib.import_module("audit.report.presentation")
        self.assertEqual(set(adapter.UNATTESTED_REQUIREMENTS), set(presentation.UNATTESTED_MEANINGS))

    def test_the_requirements_are_those_the_spec_traces_the_items_to(self) -> None:
        text = (SPEC / "traceability.md").read_text(encoding="utf-8")
        traced = dict(
            (item, requirement)
            for requirement, item in re.findall(
                r"\[(REQ-[A-Z]+-[0-9]+)\][^\n]*the engine's unattested item `([a-z-]+)`", text
            )
        )
        self.assertEqual(traced, adapter.UNATTESTED_REQUIREMENTS)


class AttestTests(unittest.TestCase):
    def catalogue_with(self, check_id: str, req_ids: list[str]) -> dict[str, Any]:
        catalogue = copy.deepcopy(dict(CATALOGUE))
        next(c for c in catalogue["checks"] if c["id"] == check_id)["req_ids"] = req_ids
        return catalogue

    def test_a_check_marked_attest_has_no_verdict_and_its_requirements_are_listed(self) -> None:
        catalogue = self.catalogue_with("TOOL-01", ["REQ-SH-027", "REQ-SH-028"])
        engine = er.report(
            TARGET, [er.check("TOOL-01", "ATTEST", summary="Only a person can say."), er.check("TOOL-02")]
        )
        conversion = adapter.convert(engine, catalogue=catalogue)
        self.assertEqual([c["id"] for c in conversion.checks], ["TOOL-02"])
        self.assertEqual(
            conversion.unattested,
            [
                {
                    "requirement": "REQ-SH-027",
                    "method": "attested",
                    "property": "tool-01",
                    "why": "Only a person can say.",
                },
                {
                    "requirement": "REQ-SH-028",
                    "method": "attested",
                    "property": "tool-01",
                    "why": "Only a person can say.",
                },
            ],
        )

    def test_the_why_is_the_title_when_the_engine_gave_no_summary_and_is_cut_when_long(self) -> None:
        conversion = convert(er.report(TARGET, [er.check("TOOL-01", "ATTEST", summary="")]))
        self.assertEqual(conversion.unattested[0]["why"], CATALOGUE_TITLE["TOOL-01"])
        conversion = convert(er.report(TARGET, [er.check("TOOL-01", "ATTEST", summary="s" * 301)]))
        self.assertEqual(len(conversion.unattested[0]["why"]), 300)
        self.assertEqual(
            conversion.warnings, ["TOOL-01: the summary is 301 characters and the report allows 300, so it was cut"]
        )

    def test_the_fixed_items_come_before_the_checks_marked_attest(self) -> None:
        engine = er.report(TARGET, [er.check("TOOL-01", "ATTEST")], unattested=["doc-accuracy"])
        conversion = convert(engine)
        self.assertEqual([u["property"] for u in conversion.unattested], ["doc-accuracy", "tool-01"])

    def test_a_check_marked_attest_that_holds_findings_is_refused(self) -> None:
        engine = er.report(TARGET, [er.check("TOOL-01", "ATTEST")], [er.finding("TOOL-01")])
        error = refused(self, engine)
        self.assertEqual(
            error.errors,
            [
                "engine report: /findings/0/check: TOOL-01 has the verdict ATTEST, which is no verdict, "
                "so it holds no findings"
            ],
        )

    def test_a_check_marked_attest_that_the_catalogue_does_not_have_or_only_an_agent_judges_is_refused(self) -> None:
        unknown = er.check("TOOL-01", "ATTEST")
        unknown["id"] = "ZZZ-99"
        error = refused(self, er.report(TARGET, [unknown, er.check("AGT-11", "ATTEST")]))
        self.assertEqual(
            error.errors,
            [
                "engine report: /checks/0/id: ZZZ-99 is not a check in catalogue.json",
                "engine report: /checks/1/id: AGT-11 is a check that only an agent can judge",
            ],
        )


class ProbeTests(unittest.TestCase):
    def tst02(self, *probes: dict[str, Any], findings: list[dict[str, Any]] | None = None) -> adapter.Conversion:
        return convert(
            er.report(TARGET, [er.check("TST-02", "PASS")], findings or [], probes=list(probes)),
        )

    def test_a_probe_that_ran_is_command_evidence_on_the_check_that_ran_it(self) -> None:
        conversion = self.tst02(er.probe(command=("npm", "run", "test"), exit_code=1, output_tail="1 failed\n"))
        self.assertEqual(
            conversion.checks[0]["evidence"],
            [
                {
                    "kind": "command",
                    "captured_by": "tool",
                    "tool": "python-agentic-audit",
                    "tool_version": "0.1.0",
                    "command": "npm run test",
                    "exit_code": 1,
                    "output_tail": "1 failed\n",
                    "timed_out": False,
                    "duration_s": 1.234,
                    "redactions": 0,
                }
            ],
        )
        self.assertEqual(
            list(conversion.checks[0]["evidence"][0]),
            [
                "kind",
                "captured_by",
                "tool",
                "tool_version",
                "command",
                "exit_code",
                "output_tail",
                "timed_out",
                "duration_s",
                "redactions",
            ],
        )
        self.assertEqual((conversion.probes_carried, conversion.warnings), (1, []))

    def test_the_command_is_written_as_a_shell_would_read_it(self) -> None:
        conversion = self.tst02(er.probe(command=("sh", "-c", "echo 'hi there'")))
        self.assertEqual(conversion.checks[0]["evidence"][0]["command"], "sh -c 'echo '\"'\"'hi there'\"'\"''")

    def test_a_probe_the_engine_refused_ran_nothing_and_is_not_carried_and_needs_no_warning(self) -> None:
        conversion = self.tst02(er.refused_probe())
        self.assertEqual(conversion.checks[0]["evidence"], [])
        self.assertEqual((conversion.probes_carried, conversion.warnings, conversion.evidence_not_carried), (0, [], 0))

    def test_a_probe_that_timed_out_is_carried_with_no_exit_code(self) -> None:
        conversion = self.tst02(er.probe(exit_code=None, timed_out=True))
        item = conversion.checks[0]["evidence"][0]
        self.assertEqual((item["exit_code"], item["timed_out"]), (None, True))

    def test_an_empty_or_missing_output_and_missing_redactions_are_left_out(self) -> None:
        cases: list[dict[str, Any]] = [{"output_tail": ""}, {}]
        for changes in cases:
            with self.subTest(changes=changes):
                probe = er.probe(**changes)
                if not changes:
                    del probe["output_tail"], probe["redactions"]
                item = self.tst02(probe).checks[0]["evidence"][0]
                self.assertNotIn("output_tail", item)
        self.assertNotIn("redactions", item)
        self.assertEqual(self.tst02(er.probe(redactions=2)).checks[0]["evidence"][0]["redactions"], 2)

    def test_the_end_of_a_long_output_is_kept(self) -> None:
        tail = "a" * 100 + "b" * 2000
        conversion = self.tst02(er.probe(output_tail=tail))
        kept = conversion.checks[0]["evidence"][0]["output_tail"]
        self.assertEqual((len(kept), kept[0], kept[1:]), (2000, "\u2026", "b" * 1999))
        self.assertEqual(
            conversion.warnings,
            ["probe test: the output is 2100 characters and the report allows 2000, so its start was cut"],
        )

    def test_an_output_at_the_limit_is_kept_whole(self) -> None:
        conversion = self.tst02(er.probe(output_tail="b" * 2000))
        self.assertEqual((conversion.checks[0]["evidence"][0]["output_tail"], conversion.warnings), ("b" * 2000, []))

    def test_a_long_command_is_cut_with_a_warning(self) -> None:
        conversion = self.tst02(er.probe(command=("x" * 501,)))
        command = conversion.checks[0]["evidence"][0]["command"]
        self.assertEqual((len(command), command[-1]), (500, "\u2026"))
        self.assertEqual(
            conversion.warnings, ["probe test: the command is 501 characters and the report allows 500, so it was cut"]
        )

    def test_a_probe_with_no_command_is_not_carried(self) -> None:
        conversion = self.tst02(er.probe(command=()))
        self.assertEqual(conversion.checks[0]["evidence"], [])
        self.assertEqual(conversion.warnings, ["probe test: the engine gave no command, so the probe is not carried"])
        self.assertEqual(conversion.probes_carried, 0)

    def test_a_probe_no_check_is_known_to_run_is_said_and_left_out(self) -> None:
        conversion = self.tst02(er.probe("lint"))
        self.assertEqual(conversion.checks[0]["evidence"], [])
        self.assertEqual(conversion.warnings, ["probe lint: no check is known to run it, so it is not carried"])

    def test_a_probe_whose_check_is_not_in_the_report_is_said_and_left_out(self) -> None:
        conversion = convert(er.report(TARGET, [er.check("TOOL-01")], probes=[er.probe()]))
        self.assertEqual(conversion.probes_carried, 0)
        self.assertEqual(
            conversion.warnings, ["probe: TST-02 ran it, and the report holds no such check, so it is not carried"]
        )

    def test_a_probe_whose_check_the_engine_left_out_is_said_and_left_out(self) -> None:
        conversion = convert(er.report(TARGET, not_applicable=["TST-02"], probes=[er.probe()]))
        self.assertEqual(conversion.probes_carried, 0)
        self.assertEqual(len(conversion.warnings), 1)
        self.assertEqual(conversion.checks[0]["evidence"], [])

    def test_the_probe_follows_the_files_the_checks_findings_cite(self) -> None:
        findings = [er.finding("TST-02", evidence=[er.evidence("package.json", None, "npm test")])]
        conversion = self.tst02(er.probe(exit_code=1), findings=findings)
        self.assertEqual([i["kind"] for i in conversion.checks[0]["evidence"]], ["file", "command"])

    def test_the_findings_do_not_get_the_probe(self) -> None:
        conversion = self.tst02(er.probe(exit_code=1), findings=[er.finding("TST-02")])
        self.assertEqual(conversion.findings[0]["evidence"], [])

    def test_several_probes_for_one_check_are_all_carried_in_order(self) -> None:
        with mock.patch.dict(adapter.PROBE_CHECKS, {"check": "TST-02"}):
            conversion = self.tst02(er.probe(command=("one",)), er.probe("check", command=("two",)))
        self.assertEqual([i["command"] for i in conversion.checks[0]["evidence"]], ["one", "two"])
        self.assertEqual(conversion.probes_carried, 2)

    def test_the_probe_keeps_its_place_when_the_files_fill_the_check(self) -> None:
        findings = [er.finding("TST-02", evidence=[er.evidence(f"f{n}.ts") for n in range(50)])]
        conversion = self.tst02(er.probe(), findings=findings)
        evidence = conversion.checks[0]["evidence"]
        self.assertEqual((len(evidence), evidence[-1]["kind"], evidence[-2]["path"]), (50, "command", "f48.ts"))
        self.assertEqual(
            conversion.warnings, ["TST-02: 50 evidence items, and the report allows 49, so the rest are left out"]
        )

    def test_the_input_probe_is_not_changed(self) -> None:
        probe = er.probe()
        before = copy.deepcopy(probe)
        self.tst02(probe)
        self.assertEqual(probe, before)

    def test_a_probe_missing_a_field_or_of_the_wrong_kind_is_refused(self) -> None:
        for name in ("verb", "command", "exit_code", "duration_s", "timed_out"):
            with self.subTest(missing=name):
                probe = er.probe()
                del probe[name]
                errors = refused(self, er.report(TARGET, probes=[probe])).errors
                self.assertEqual(errors, [f"engine report: /probes/0: missing the required property '{name}'"])
        bad: list[dict[str, Any]] = [
            {"command": "npm test"},
            {"exit_code": "0"},
            {"duration_s": "1"},
            {"timed_out": 0},
            {"redactions": 1.5},
            {"output_tail": 5},
            {"refused_reason": 5},
        ]
        for changes in bad:
            with self.subTest(changes=changes):
                probe = er.probe()
                probe.update(changes)
                errors = refused(self, er.report(TARGET, probes=[probe])).errors
                self.assertTrue(errors[0].startswith("engine report: /probes/0/"), errors)

    def test_a_report_without_probes_is_refused(self) -> None:
        report = er.report(TARGET)
        del report["probes"]
        self.assertIn("'probes'", " ".join(refused(self, report).errors))


class ProbeDriftTests(unittest.TestCase):
    """The table of verbs and checks is the adapter's own, so this holds it to the engine's source."""

    def checks_that_run_probes(self) -> dict[str, str]:
        found: dict[str, str] = {}
        folder = engine_launcher.ENGINE_DIR / "audit" / "rules" / "checks"
        for source in sorted(folder.glob("*.py")):
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.FunctionDef):
                    continue
                named = re.fullmatch(r"check_([a-z]+)([0-9]+)", node.name)
                if named is None:
                    continue
                verbs: list[str] = []
                for call in ast.walk(node):
                    if not (isinstance(call, ast.Call) and getattr(call.func, "id", "") == "ProbePlan"):
                        continue
                    for keyword in call.keywords:
                        value = keyword.value
                        if keyword.arg == "verb" and isinstance(value, ast.Constant) and isinstance(value.value, str):
                            verbs.append(value.value)
                for verb in verbs:
                    found[verb] = f"{named.group(1).upper()}-{named.group(2)}"
        return found

    def test_the_table_is_the_checks_that_build_a_probe_plan(self) -> None:
        self.assertEqual(self.checks_that_run_probes(), adapter.PROBE_CHECKS)

    def test_the_search_finds_something(self) -> None:
        self.assertTrue(self.checks_that_run_probes())


def with_stack(**changes: Any) -> dict[str, Any]:
    stack = dict(er.report(TARGET)["stack"])
    stack.update(changes)
    return stack


class StackTests(unittest.TestCase):
    def stack(self, **changes: Any) -> adapter.Conversion:
        return convert(er.report(TARGET, stack=with_stack(**changes)))

    def test_what_the_scan_detected_is_carried_under_the_engines_names_in_the_schemas_order(self) -> None:
        conversion = self.stack(
            ecosystems=["node"],
            package_managers=["npm", "pnpm"],
            ci_providers=["github"],
            test_frameworks=["vitest"],
            hook_managers=["husky"],
            notes=["root has no manifest"],
        )
        self.assertEqual(
            conversion.stack,
            {
                "ecosystems": ["node"],
                "package_managers": ["npm", "pnpm"],
                "ci_providers": ["github"],
                "test_frameworks": ["vitest"],
                "hook_managers": ["husky"],
                "notes": ["root has no manifest"],
            },
        )
        self.assertEqual(
            list(conversion.stack),
            ["ecosystems", "package_managers", "ci_providers", "test_frameworks", "hook_managers", "notes"],
        )

    def test_notes_are_left_out_when_there_are_none(self) -> None:
        self.assertNotIn("notes", self.stack().stack)
        stack = with_stack()
        del stack["notes"]
        self.assertNotIn("notes", convert(er.report(TARGET, stack=stack)).stack)

    def test_a_field_of_the_engines_stack_that_the_report_has_no_place_for_is_ignored(self) -> None:
        self.assertEqual(set(self.stack(new_field=["x"]).stack), set(adapter.STACK_LISTS))

    def test_a_name_and_a_note_over_the_limit_are_cut_with_a_warning_each(self) -> None:
        conversion = self.stack(ecosystems=["e" * 101], notes=["n" * 301])
        self.assertEqual((len(conversion.stack["ecosystems"][0]), len(conversion.stack["notes"][0])), (100, 300))
        self.assertEqual(
            conversion.warnings,
            [
                "stack ecosystems: the name is 101 characters and the report allows 100, so it was cut",
                "stack notes: the note is 301 characters and the report allows 300, so it was cut",
            ],
        )

    def test_a_name_and_a_note_at_the_limit_are_not_cut(self) -> None:
        conversion = self.stack(ecosystems=["e" * 100], notes=["n" * 300])
        self.assertEqual((conversion.stack["ecosystems"], conversion.warnings), (["e" * 100], []))

    def test_a_list_over_fifty_names_or_notes_keeps_the_first_fifty(self) -> None:
        conversion = self.stack(package_managers=[f"m{n}" for n in range(51)], notes=[f"n{n}" for n in range(51)])
        self.assertEqual(
            (len(conversion.stack["package_managers"]), conversion.stack["package_managers"][-1]), (50, "m49")
        )
        self.assertEqual((len(conversion.stack["notes"]), conversion.stack["notes"][-1]), (50, "n49"))
        self.assertEqual(
            conversion.warnings,
            [
                "stack package_managers: 51 names, and the report allows 50, so the rest are left out",
                "stack notes: 51 notes, and the report allows 50, so the rest are left out",
            ],
        )

    def test_the_input_is_not_shared_with_the_result(self) -> None:
        stack = with_stack(ecosystems=["node"])
        conversion = convert(er.report(TARGET, stack=stack))
        conversion.stack["ecosystems"].append("changed")
        self.assertEqual(stack["ecosystems"], ["node"])


class ComponentsTests(unittest.TestCase):
    def components(self, declared: list[dict[str, Any]], candidates: list[str] | None = None) -> adapter.Conversion:
        return convert(er.report(TARGET, components=declared, candidate_components=candidates or []))

    def test_a_declared_component_keeps_the_engines_fields_in_the_order_of_the_schema(self) -> None:
        raw = {
            "name": "api",
            "path": "services/api",
            "declared": True,
            "declared_by": "package.json workspaces",
            "manifest": "services/api/package.json",
            "agents_md": "missing",
        }
        conversion = self.components([raw])
        self.assertEqual(conversion.components, [raw])
        self.assertEqual(
            list(conversion.components[0]), ["name", "path", "declared", "declared_by", "manifest", "agents_md"]
        )

    def test_a_field_the_engine_left_out_is_left_out_and_declared_is_true_by_default(self) -> None:
        conversion = self.components([{"name": "(root)", "path": "."}])
        self.assertEqual(conversion.components, [{"name": "(root)", "path": ".", "declared": True}])

    def test_a_null_manifest_and_declared_by_are_carried(self) -> None:
        conversion = self.components([{"name": "a", "path": "a", "declared_by": None, "manifest": None}])
        self.assertEqual((conversion.components[0]["declared_by"], conversion.components[0]["manifest"]), (None, None))

    def test_what_the_engine_says_about_declared_is_carried(self) -> None:
        self.assertIs(self.components([{"name": "a", "path": "a", "declared": False}]).components[0]["declared"], False)

    def test_a_candidate_is_a_component_nothing_declares_named_by_its_path(self) -> None:
        conversion = self.components([{"name": "(root)", "path": "."}], ["tools/x", "tools/y"])
        self.assertEqual(
            conversion.components[1:],
            [
                {"name": "tools/x", "path": "tools/x", "declared": False},
                {"name": "tools/y", "path": "tools/y", "declared": False},
            ],
        )
        self.assertEqual(list(conversion.components[1]), ["name", "path", "declared"])

    def test_a_long_name_and_manifest_and_declaration_are_cut_with_a_warning_each(self) -> None:
        conversion = self.components(
            [{"name": "n" * 201, "path": "p", "manifest": "m" * 301, "declared_by": "d" * 101}]
        )
        component = conversion.components[0]
        self.assertEqual(
            (len(component["name"]), len(component["manifest"]), len(component["declared_by"])), (200, 300, 100)
        )
        self.assertEqual(
            conversion.warnings,
            [
                "p: the component name is 201 characters and the report allows 200, so it was cut",
                "p: the declared_by is 101 characters and the report allows 100, so it was cut",
                "p: the manifest is 301 characters and the report allows 300, so it was cut",
            ],
        )

    def test_the_first_five_hundred_are_kept_declared_ones_first(self) -> None:
        declared = [{"name": f"d{n}", "path": f"d{n}"} for n in range(400)]
        conversion = self.components(declared, [f"c{n}" for n in range(150)])
        self.assertEqual((len(conversion.components), conversion.components[-1]["path"]), (500, "c99"))
        self.assertEqual(
            conversion.warnings, ["components: 550 components, and the report allows 500, so the rest are left out"]
        )

    def test_the_input_is_not_shared_with_the_result(self) -> None:
        raw = {"name": "a", "path": "a"}
        conversion = self.components([raw])
        conversion.components[0]["name"] = "changed"
        self.assertEqual(raw["name"], "a")


class InventoryTests(unittest.TestCase):
    def test_the_counts_are_carried_in_the_order_of_the_schema(self) -> None:
        conversion = convert(
            er.report(TARGET, inventory={"truncated": False, "files_skipped": 3, "files_inspected": 149, "extra": 1})
        )
        self.assertEqual(conversion.inventory, {"files_inspected": 149, "files_skipped": 3, "truncated": False})
        self.assertEqual(list(conversion.inventory), ["files_inspected", "files_skipped", "truncated"])
        self.assertEqual(conversion.warnings, [])

    def test_a_scan_the_engine_cut_short_is_said(self) -> None:
        conversion = convert(
            er.report(TARGET, inventory={"files_inspected": 5000, "files_skipped": 0, "truncated": True})
        )
        self.assertTrue(conversion.inventory["truncated"])
        self.assertEqual(
            conversion.warnings, ["the engine's scan was cut short, so what it did not reach is not in the report"]
        )


class EngineScoreTests(unittest.TestCase):
    def test_the_engines_score_is_read_from_its_summary(self) -> None:
        engine = er.report(TARGET, summary={"phase1_score": 0.7311, "blockers": 4})
        self.assertEqual(convert(engine).engine_score, 0.7311)

    def test_a_missing_or_null_score_is_none(self) -> None:
        for summary in ({}, {"phase1_score": None}):
            with self.subTest(summary=summary):
                self.assertIsNone(convert(er.report(TARGET, summary=summary)).engine_score)
        engine = er.report(TARGET)
        del engine["summary"]
        self.assertIsNone(convert(engine).engine_score)

    def test_a_score_that_is_not_a_number_is_refused(self) -> None:
        error = refused(self, er.report(TARGET, summary={"phase1_score": "high"}))
        self.assertTrue(error.errors[0].startswith("engine report: /summary/phase1_score:"), error.errors)


class ShapeTests(unittest.TestCase):
    def test_a_scan_fact_missing_or_of_the_wrong_kind_is_refused(self) -> None:
        cases: list[tuple[str, Any, str]] = [
            ("stack", {"ecosystems": []}, "/stack"),
            ("stack", with_stack(ecosystems="node"), "/stack/ecosystems"),
            ("stack", with_stack(notes=[1]), "/stack/notes/0"),
            ("inventory", {"files_inspected": 1, "files_skipped": 0}, "/inventory"),
            (
                "inventory",
                {"files_inspected": "1", "files_skipped": 0, "truncated": False},
                "/inventory/files_inspected",
            ),
            ("inventory", {"files_inspected": 1, "files_skipped": 0, "truncated": 0}, "/inventory/truncated"),
            ("components", [{"path": "a"}], "/components/0"),
            ("components", [{"name": "a", "path": "a", "declared": "yes"}], "/components/0/declared"),
            ("components", [{"name": "a", "path": "a", "manifest": 3}], "/components/0/manifest"),
            ("components", [{"name": "a", "path": "a", "declared_by": 3}], "/components/0/declared_by"),
            ("components", [{"name": "a", "path": "a", "agents_md": 3}], "/components/0/agents_md"),
            ("candidate_components", [5], "/candidate_components/0"),
        ]
        for name, value, pointer in cases:
            with self.subTest(field=name, pointer=pointer):
                errors = refused(self, er.report(TARGET, **{name: value})).errors
                self.assertTrue(errors[0].startswith(f"engine report: {pointer}"), errors)

    def test_a_report_without_the_lists_the_adapter_reads_is_refused(self) -> None:
        for name in (
            "stack",
            "inventory",
            "components",
            "candidate_components",
            "checks",
            "findings",
            "not_applicable",
        ):
            with self.subTest(missing=name):
                report = er.report(TARGET)
                del report[name]
                self.assertIn(f"'{name}'", " ".join(refused(self, report).errors))

    def test_a_check_missing_a_field_is_named(self) -> None:
        for name in ("id", "title", "severity", "phase", "scored", "status", "verdict", "summary"):
            with self.subTest(missing=name):
                engine_check = er.check("TOOL-01")
                del engine_check[name]
                errors = refused(self, er.report(TARGET, [engine_check])).errors
                self.assertEqual(errors, [f"engine report: /checks/0: missing the required property '{name}'"])

    def test_a_finding_missing_a_field_is_named(self) -> None:
        for name in ("id", "check", "severity", "statement", "evidence"):
            with self.subTest(missing=name):
                engine_finding = er.finding("TOOL-01")
                del engine_finding[name]
                errors = refused(self, er.report(TARGET, [er.check("TOOL-01")], [engine_finding])).errors
                self.assertEqual(errors, [f"engine report: /findings/0: missing the required property '{name}'"])

    def test_a_value_of_the_wrong_kind_is_refused(self) -> None:
        cases: list[tuple[str, dict[str, Any], str]] = [
            ("verdict", er.check("TOOL-01", "MAYBE"), "/checks/0/verdict"),
            ("severity", er.check("TOOL-01", severity="HIGH"), "/checks/0/severity"),
            ("scored", er.check("TOOL-01", scored="yes"), "/checks/0/scored"),
            ("phase", er.check("TOOL-01", phase=True), "/checks/0/phase"),
            ("data", er.check("TOOL-01", data=[]), "/checks/0/data"),
        ]
        for name, engine_check, pointer in cases:
            with self.subTest(field=name):
                errors = refused(self, er.report(TARGET, [engine_check])).errors
                self.assertTrue(errors[0].startswith(f"engine report: {pointer}:"), errors)

    def test_an_evidence_item_of_the_wrong_kind_is_refused(self) -> None:
        bad: list[dict[str, Any]] = [
            {"line": 1},
            {"path": 5},
            {"path": "a", "line": True},
            {"path": "a", "line": "1"},
            {"path": "a", "note": 3},
        ]
        for item in bad:
            with self.subTest(item=item):
                report = er.report(TARGET, [er.check("TOOL-01", "FAIL")], [er.finding("TOOL-01", evidence=[item])])
                self.assertTrue(refused(self, report).errors[0].startswith("engine report: /findings/0/evidence/0"))

    def test_a_remediation_that_is_not_text_is_refused(self) -> None:
        report = er.report(TARGET, [er.check("TOOL-01", "FAIL")], [er.finding("TOOL-01", remediation=5)])
        self.assertTrue(refused(self, report).errors[0].startswith("engine report: /findings/0/remediation"))


class MessageTests(unittest.TestCase):
    """What a person reads when an engine report is refused, word for word."""

    def test_a_report_that_is_not_an_object(self) -> None:
        error = refused(self, [])
        self.assertEqual(str(error), "the engine report is not a JSON object")
        self.assertEqual(error.errors, ["engine report: the top level must be an object"])

    def test_a_schema_version_other_than_2(self) -> None:
        report = er.report(TARGET)
        report["schema_version"] = "1"
        error = refused(self, report)
        self.assertEqual(str(error), "the engine report has schema_version '1', and the adapter reads only '2'")
        self.assertEqual(error.errors, ["engine report: /schema_version: expected '2', found '1'"])

    def test_a_phase_other_than_1(self) -> None:
        error = refused(self, er.report(TARGET, provenance=er.provenance(TARGET, phase=2)))
        self.assertEqual(str(error), "the engine report is for phase 2, and a 0.1 report covers phase 1")
        self.assertEqual(error.errors, ["engine report: /provenance/phase: expected 1, found 2"])

    def test_the_wrong_shape_with_one_error_and_with_two(self) -> None:
        report = er.report(TARGET)
        report["provenance"]["tool"] = 1
        self.assertEqual(str(refused(self, report)), "the engine report has the wrong shape: 1 error")
        report["provenance"]["version"] = 2
        self.assertEqual(str(refused(self, report)), "the engine report has the wrong shape: 2 errors")

    def test_problems_with_one_and_with_several(self) -> None:
        self.assertEqual(
            str(refused(self, er.report(TARGET, [er.check("AGT-11")]))),
            "the engine report cannot be imported: 1 problem",
        )
        engine = er.report(TARGET, [er.check("AGT-11"), er.check("TOOL-01"), er.check("TOOL-01")])
        self.assertEqual(str(refused(self, engine)), "the engine report cannot be imported: 2 problems")


class ValueTests(unittest.TestCase):
    """What the adapter hands back is not changed afterwards by anyone who holds it."""

    def test_a_located_path_a_dropped_path_and_a_conversion_are_frozen(self) -> None:
        conversion = convert(er.report(TARGET))
        for value, name in (
            (adapter.Located("a", None), "path"),
            (adapter.NotCarried("why"), "reason"),
            (conversion, "warnings"),
        ):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(value, name, "changed")


class PurityTests(unittest.TestCase):
    def report(self) -> dict[str, Any]:
        return er.report(
            TARGET,
            [er.check("SEC-02", "FAIL", data={"kind": "k", "rows": [1]}), er.check("TOOL-01")],
            [er.finding("SEC-02", "a b", evidence=[er.evidence("a.ts", 1, "n"), er.evidence("/abs")])],
            not_applicable=["TOOL-02"],
        )

    def test_the_input_is_not_changed(self) -> None:
        report = self.report()
        before = copy.deepcopy(report)
        convert(report)
        self.assertEqual(report, before)

    def test_the_same_report_converts_to_the_same_parts(self) -> None:
        self.assertEqual(convert(self.report()), convert(self.report()))

    def test_the_catalogue_given_is_not_changed(self) -> None:
        before = copy.deepcopy(CATALOGUE)
        convert(self.report())
        self.assertEqual(CATALOGUE, before)


CATALOGUE_TITLE = {entry["id"]: entry["title"] for entry in CATALOGUE["checks"]}
CATALOGUE_SEVERITY = {entry["id"]: entry["severity"] for entry in CATALOGUE["checks"]}
CATALOGUE_SCORED = {entry["id"]: entry["scored"] for entry in CATALOGUE["checks"]}


if __name__ == "__main__":
    unittest.main()
