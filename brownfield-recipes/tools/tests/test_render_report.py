# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The renderer: one report gives one Markdown text, nothing in the report can become markup, and the command line
never replaces a file or writes inside the target.

The reports are the examples in `schema/examples/`, copied and changed one field at a time, so that a test names the
field it breaks. The golden files are the Markdown that sits beside two of those examples; to change one on purpose,
delete it, run `render_report.py` on the JSON next to it, and read the diff before committing it. Credential-shaped
strings are built at run time, so that the secrets scan finds nothing in this file. Standard library only.
"""

from __future__ import annotations

import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence
from unittest import mock

import _paths
import _common
import _summary
import render_report as rr
import validate_report as vr

TOOLS = _paths.TOOLS
EXAMPLES = TOOLS.parent / "schema" / "examples"
REALISTIC = EXAMPLES / "realistic"
SERVICE = "example-service.audit-report.20261010T094207Z.json"


def load(path: Path | str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return document


def service() -> dict[str, Any]:
    """The worked example: final, with an override, an agent check with evidence, and every kind of decision."""
    return load(EXAMPLES / SERVICE)


def minimal() -> dict[str, Any]:
    return load(EXAMPLES / "minimal.json")


def drafts() -> list[Path]:
    return sorted(REALISTIC.glob("*.audit-draft.*.json"))


def check_of(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    check: dict[str, Any] = next(c for c in report["checks"] if c["id"] == check_id)
    return check


def set_verdict(check: dict[str, Any], verdict: str) -> None:
    """Change a verdict and, where the engine gave one, make it the same, so that the report is not an override."""
    check["verdict"] = verdict
    if "engine_verdict" in check:
        check["engine_verdict"] = verdict


def finding_of(report: dict[str, Any], finding_id: str) -> dict[str, Any]:
    finding: dict[str, Any] = next(f for f in report["findings"] if f["id"] == finding_id)
    return finding


def section(markdown: str, heading: str) -> str:
    """The text of the `## heading` section, up to the next second-level heading."""
    lines = markdown.split("\n")
    start = lines.index(f"## {heading}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def details_of(markdown: str, check_id: str) -> str:
    """The block of one check in "Check details": from its heading to the next heading of any level."""
    lines = markdown.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith(f"#### {check_id}: "))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    return "\n".join(lines[start:end])


def scan(markdown: str) -> Iterator[tuple[str, bool]]:
    """Each line with whether it is inside a fenced block, by the CommonMark rule: only a run of backticks at least
    as long as the opener closes a fence, and an opener's info string holds no backtick."""
    opener = 0
    for line in markdown.split("\n"):
        found = re.match(r"^(`{3,})(.*)$", line.lstrip(" "))
        if opener == 0:
            if found and "`" not in found.group(2):
                opener = len(found.group(1))
                yield line, True
                continue
            yield line, False
        else:
            yield line, True
            if found and not found.group(2).strip() and len(found.group(1)) >= opener:
                opener = 0
    if opener:
        raise AssertionError("a fenced block is never closed")


def outside_fences(markdown: str) -> list[str]:
    return [line for line, fenced in scan(markdown) if not fenced]


def unescaped_pipes(line: str) -> int:
    """How many `|` in a line are cell separators: a backslash escapes the character after it."""
    pipes, index = 0, 0
    while index < len(line):
        if line[index] == "\\":
            index += 2
            continue
        pipes += line[index] == "|"
        index += 1
    return pipes


def reordered(value: Any) -> Any:
    """The same JSON with the keys of every object in the opposite order."""
    if isinstance(value, dict):
        return {key: reordered(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [reordered(item) for item in value]
    return value


class RenderCase(unittest.TestCase):
    def render(self, report: dict[str, Any]) -> str:
        return rr.render(report)


class TextTests(unittest.TestCase):
    def test_text_escapes_what_could_become_markup(self) -> None:
        cases = {
            "a|b": r"a\|b",
            "[x](y)": r"\[x\](y)",
            "<script>": r"\<script>",
            "*bold*": r"\*bold\*",
            "`code`": r"\`code\`",
            "a\\b": "a\\\\b",
            "![x](https://evil.example/p.png)": r"!\[x\](https://evil.example/p.png)",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(rr.text(raw), expected)

    def test_an_underscore_is_escaped_unless_it_sits_between_letters_or_digits(self) -> None:
        cases = {
            "snake_case": "snake_case",
            "a_b_c": "a_b_c",
            "pull_request": "pull_request",
            "v1_2": "v1_2",
            "__init__": r"\_\_init\_\_",
            "src/__tests__/a.ts": r"src/\_\_tests\_\_/a.ts",
            "_x": r"\_x",
            "x_": r"x\_",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(rr.text(raw), expected)

    def test_a_character_that_only_matters_at_a_line_start_is_left_alone_inside_a_line(self) -> None:
        for raw in ("format -> package.json", "~/.config/x", "a > b", "50% # 3", "x - y", "1. one"):
            with self.subTest(raw=raw):
                self.assertEqual(rr.text(raw), raw)

    def test_white_space_is_collapsed_to_one_line(self) -> None:
        self.assertEqual(rr.text("a\n  b\t c\r\n\r\nd"), "a b c d")
        self.assertEqual(rr.text("  padded  "), "padded")

    def test_prose_also_escapes_a_first_character_that_would_start_a_block(self) -> None:
        cases = {
            "# Title": r"\# Title",
            "> quote": r"\> quote",
            "- item": r"\- item",
            "+ item": r"\+ item",
            "--- rule": r"\--- rule",
            "=== rule": r"\=== rule",
            "~~~ fence": r"\~~~ fence",
            "1. one": r"1\. one",
            "20) two": r"20\) two",
            "plain": "plain",
            "a - b": "a - b",
            "a # b": "a # b",
            "see 1. below": "see 1. below",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(rr.prose(raw), expected)

    def test_control_and_format_characters_are_written_out(self) -> None:
        cases = {
            "a\x00b": "a{U+0000}b",
            "\x1b[31m": "{U+001B}[31m",
            "a‮b": "a{U+202E}b",
            "a​b": "a{U+200B}b",
            "a﻿b": "a{U+FEFF}b",
            "a\u0085b": "a{U+0085}b",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=ascii(raw)):
                self.assertEqual(rr.clean(raw), expected)
        self.assertEqual(rr.clean("a\r\nb\rc\td e f"), "a\nb\nc\td\ne\nf")

    def test_a_code_span_has_a_delimiter_longer_than_any_run_of_backticks_inside(self) -> None:
        self.assertEqual(rr.code("src/a.ts"), "`src/a.ts`")
        self.assertEqual(rr.code("a`b"), "``a`b``")
        self.assertEqual(rr.code("a``b"), "```a``b```")
        self.assertEqual(rr.code("`x`"), "`` `x` ``")
        self.assertEqual(rr.code("  a \n b  "), "`a b`")
        self.assertEqual(rr.code("a`"), "`` a` ``")
        self.assertEqual(rr.code("`a"), "`` `a ``")
        self.assertEqual(rr.code("a``"), "``` a`` ```")
        self.assertEqual(rr.code(""), "—")
        self.assertEqual(rr.code("   "), "—")

    def test_a_fenced_block_is_longer_than_any_run_of_backticks_inside_and_never_shorter_than_three(self) -> None:
        self.assertEqual(rr.fenced("x"), ["```text", "x", "```"])
        self.assertEqual(rr.fenced("a\n```\nb"), ["````text", "a", "```", "b", "````"])
        self.assertEqual(rr.fenced("a ````` b")[0], "``````text")
        self.assertEqual(rr.fenced("a\n\nb"), ["```text", "a", "", "b", "```"])
        self.assertEqual(rr.fenced("a\r\nb\n\n"), ["```text", "a", "b", "```"])
        self.assertEqual(rr.fenced("ends with X\n"), ["```text", "ends with X", "```"])

    def test_a_fenced_block_is_indented_to_sit_inside_a_list_item_and_a_blank_value_gives_nothing(self) -> None:
        self.assertEqual(rr.fenced("a\n\nb", indent="  "), ["  ```text", "  a", "", "  b", "  ```"])
        for blank in ("", "  \n ", "\n\n"):
            with self.subTest(blank=blank):
                self.assertEqual(rr.fenced(blank), [])

    def test_a_cell_escapes_a_bare_pipe_and_keeps_one_that_is_already_escaped(self) -> None:
        self.assertEqual(rr.cell("a|b"), r"a\|b")
        self.assertEqual(rr.cell(r"a\|b"), r"a\|b")
        self.assertEqual(rr.cell("a\\\\|b"), "a\\\\\\|b")
        self.assertEqual(rr.cell("`a|b`"), r"`a\|b`")
        self.assertEqual(rr.cell("plain"), "plain")
        self.assertEqual(rr.cell("ends with a backslash\\"), "ends with a backslash\\")

    def test_a_table_has_one_header_one_rule_and_one_line_for_each_row_with_pipes_escaped(self) -> None:
        lines = rr.table(["A", "B"], [["1", "x|y"], ["2", "z"]])
        self.assertEqual(lines, ["| A | B |", "|---|---|", r"| 1 | x\|y |", "| 2 | z |"])

    def test_blocks_are_separated_by_one_blank_line_and_empty_blocks_vanish(self) -> None:
        self.assertEqual(rr.blocks(["a"], [], ["b", "c"], [], ["d"]), ["a", "", "b", "c", "", "d"])
        self.assertEqual(rr.blocks([], []), [])

    def test_the_score_is_shown_to_two_places_rounded_half_up(self) -> None:
        cases: dict[float, str] = {
            0.125: "0.13",
            0.6667: "0.67",
            1.0: "1.00",
            0.0: "0.00",
            0.005: "0.01",
            0.0049: "0.00",
            0.5: "0.50",
            0.3333: "0.33",
            0.9999: "1.00",
        }
        for score, expected in cases.items():
            with self.subTest(score=score):
                self.assertEqual(rr.score_text(score), expected)
        self.assertEqual(rr.score_text(1), "1.00")

    def test_a_count_agrees_with_its_noun(self) -> None:
        self.assertEqual(rr.count(0, "check"), "0 checks")
        self.assertEqual(rr.count(1, "check"), "1 check")
        self.assertEqual(rr.count(2, "check"), "2 checks")


class SummaryTests(RenderCase):
    def test_the_headline_has_the_score_the_blockers_and_the_unattested_list_together(self) -> None:
        text = section(self.render(service()), "Readiness summary")
        self.assertIn("- **Phase-1 score: 0.33**, over 12 scored checks", text)
        self.assertIn("- **4 blockers remaining: 4 FAIL**", text)
        self.assertIn("- **Unattested:** 5 requirements that no check settles, listed below", text)
        for requirement in ("REQ-SH-004", "REQ-BF-004", "REQ-SH-050", "REQ-SH-020", "REQ-SH-026"):
            self.assertIn(f"| `{requirement}` | attested |", text)

    def test_the_blockers_sentence_follows_the_spec_and_agrees_with_its_count(self) -> None:
        self.assertEqual(
            rr.blockers_phrase({"total": 7, "fail": 5, "partial": 1, "unknown": 1}),
            "7 blockers remaining: 5 FAIL, 1 PARTIAL, 1 UNKNOWN",
        )
        self.assertEqual(
            rr.blockers_phrase({"total": 1, "fail": 0, "partial": 1, "unknown": 0}), "1 blocker remaining: 1 PARTIAL"
        )
        self.assertEqual(
            rr.blockers_phrase({"total": 3, "fail": 0, "partial": 2, "unknown": 1}),
            "3 blockers remaining: 2 PARTIAL, 1 UNKNOWN",
        )
        self.assertEqual(
            rr.blockers_phrase({"total": 0, "fail": 0, "partial": 0, "unknown": 0}), "0 blockers remaining"
        )

    def test_a_report_without_open_blockers_says_so(self) -> None:
        report = service()
        for check in report["checks"]:
            if check["severity"] == "BLOCKER":
                set_verdict(check, "PASS")
        markdown = self.render(report)
        self.assertIn("- **0 blockers remaining**", markdown)
        self.assertEqual(section(markdown, "Blockers remaining").split("\n")[2], "No scored BLOCKER check is open.")

    def test_the_summary_is_computed_from_the_checks_and_never_taken_from_the_file(self) -> None:
        report = service()
        report["summary"]["phase1_score"] = 0.9999
        report["summary"]["blockers_remaining"] = {"total": 99, "fail": 99, "partial": 0, "unknown": 0}
        report["summary"]["scored_checks"] = 99
        markdown = self.render(report)
        self.assertIn("**Phase-1 score: 0.33**, over 12 scored checks", markdown)
        self.assertIn("**4 blockers remaining: 4 FAIL**", markdown)
        self.assertNotIn("99", markdown)
        self.assertNotIn("1.00", markdown)

    def test_the_renderer_calls_the_code_that_the_validator_uses_for_the_summary(self) -> None:
        with mock.patch.object(_summary, "compute_summary", wraps=_summary.compute_summary) as computed:
            self.render(service())
        self.assertEqual(computed.call_count, 1)

    def test_the_blockers_table_lists_the_scored_blocker_checks_that_are_not_met_with_their_summaries(self) -> None:
        text = section(self.render(service()), "Blockers remaining")
        rows = [line for line in text.split("\n") if line.startswith("| `")]
        self.assertEqual([row.split("|")[1].strip() for row in rows], ["`CMD-01`", "`CMD-02`", "`EXEC-01`", "`SEC-02`"])
        self.assertIn("| FAIL | unpinned: node |", text)
        self.assertNotIn("IDX-01", text)

    def test_unknown_scored_checks_are_counted_and_explained(self) -> None:
        text = section(self.render(service()), "Readiness summary")
        self.assertIn(
            "1 of the 12 scored checks is UNKNOWN. An UNKNOWN check earns no credit, so the score understates what is "
            "true of the repository and does not certify it. No agent finding is waiting for a person's decision.",
            text.split("\n"),
        )
        self.assertIn("understates what is true of the repository and does not certify it", text)
        report = service()
        set_verdict(check_of(report, "CI-01"), "UNKNOWN")
        self.assertIn("2 of the 12 scored checks are UNKNOWN.", self.render(report))
        for check in report["checks"]:
            if check["verdict"] == "UNKNOWN":
                set_verdict(check, "FAIL")
        self.assertIn("No scored check is UNKNOWN.", self.render(report))

    def test_agent_findings_that_wait_for_a_person_are_counted(self) -> None:
        report = service()
        self.assertIn("No agent finding is waiting for a person's decision.", self.render(report))
        for finding_id in ("F-007", "F-008"):
            finding = finding_of(report, finding_id)
            finding["disposition"] = "pending"
            del finding["confirmed_via"]
        self.assertTrue(
            any(
                line.endswith(" 2 agent findings still await a person's decision.")
                for line in self.render(report).split("\n")
            )
        )
        finding_of(report, "F-007")["disposition"] = "confirmed"
        finding_of(report, "F-007")["confirmed_via"] = "batch"
        self.assertTrue(
            any(
                line.endswith(" 1 agent finding still awaits a person's decision.")
                for line in self.render(report).split("\n")
            )
        )

    def test_an_automated_finding_that_is_pending_is_not_counted_among_the_agent_findings(self) -> None:
        report = service()
        finding = finding_of(report, "F-001")
        finding["disposition"] = "pending"
        del finding["confirmed_via"]
        self.assertIn("No agent finding is waiting", self.render(report))

    def test_the_weights_and_the_credits_are_stated_from_the_shared_constants(self) -> None:
        text = section(self.render(service()), "Readiness summary")
        self.assertIn("The weights are BLOCKER 3, DEGRADER 2, COSMETIC 1", text)
        with mock.patch.object(_summary, "WEIGHTS", {"BLOCKER": 9, "DEGRADER": 8, "COSMETIC": 7}):
            self.assertIn("The weights are BLOCKER 9, DEGRADER 8, COSMETIC 7", self.render(service()))

    def test_the_summary_defines_no_level_grade_or_pass_mark(self) -> None:
        text = self.render(service()).lower()
        self.assertIsNone(re.search(r"\b(maturity|grade|level|ready for agents)\b", text))
        self.assertIn("the framework sets no pass mark", text)

    def test_the_unattested_list_has_a_row_for_each_item_and_a_dash_for_a_missing_property(self) -> None:
        report = service()
        del report["unattested"][0]["property"]
        text = section(self.render(report), "Readiness summary")
        self.assertIn(
            "| `REQ-SH-004` | attested | — | Whether the codebase index is actually used during agent work. |", text
        )
        self.assertEqual(len([line for line in text.split("\n") if line.startswith("| `REQ-")]), 5)

    def test_an_empty_unattested_list_says_so_and_the_headline_still_counts_it(self) -> None:
        markdown = self.render(minimal())
        self.assertIn("- **Unattested:** 0 requirements that no check settles, listed below", markdown)
        self.assertIn("No unattested requirement is recorded in this report.", markdown)

    def test_a_requirement_is_listed_once_in_the_summary_section_only(self) -> None:
        markdown = self.render(service())
        self.assertEqual(markdown.count("REQ-SH-004"), 1)


class BannerTests(RenderCase):
    def test_a_final_report_from_a_person_has_no_banner(self) -> None:
        markdown = self.render(service())
        self.assertNotIn("[!WARNING]", markdown)
        self.assertNotIn("[!NOTE]", markdown)
        self.assertNotIn("**Draft.**", markdown)
        self.assertNotIn("Evaluation run", markdown)

    def test_an_eval_run_has_a_banner_that_names_the_policy(self) -> None:
        report = service()
        report["run_context"]["eval_mode"] = True
        report["run_context"]["confirmation_policy"] = "defer-all"
        markdown = self.render(report)
        self.assertIn("> [!WARNING]\n> **Evaluation run.**", markdown)
        self.assertIn(
            "> **Evaluation run.** This report was produced to measure the audit recipe, not to guide work on the "
            "repository. Its confirmation policy was `defer-all`, so no person decided on its findings, and it can "
            "never be final.\n",
            markdown,
        )
        self.assertLess(markdown.index("Evaluation run"), markdown.index("## Readiness summary"))

    def test_a_draft_has_a_banner_that_counts_the_findings_waiting_for_a_decision(self) -> None:
        report = service()
        report["status"] = "draft"
        self.assertIn(
            "> [!NOTE]\n> **Draft.** This report is not final and can still change. 0 findings await",
            self.render(report),
        )
        for finding_id in ("F-001", "F-002"):
            finding = finding_of(report, finding_id)
            finding["disposition"] = "pending"
            del finding["confirmed_via"]
        self.assertIn("2 findings await a decision.", self.render(report))
        finding_of(report, "F-001")["disposition"] = "rejected"
        finding_of(report, "F-001")["confirmed_via"] = "interactive"
        self.assertIn("1 finding awaits a decision.", self.render(report))

    def test_an_eval_draft_has_both_banners_with_the_warning_first(self) -> None:
        report = service()
        report["status"] = "draft"
        report["run_context"]["eval_mode"] = True
        report["run_context"]["confirmation_policy"] = "accept-all"
        markdown = self.render(report)
        self.assertLess(markdown.index("[!WARNING]"), markdown.index("[!NOTE]"))

    def test_the_title_says_when_the_report_was_finalised_or_started_and_where_the_commit_is(self) -> None:
        markdown = self.render(service())
        self.assertIn(
            "Repository `example-service` at commit `deadbeefdead` on branch `main` (clean working tree). "
            "Finalised `2026-10-10T09:42:07+00:00`.",
            markdown,
        )
        report = service()
        report["status"] = "draft"
        del report["provenance"]["finalised_at"]
        target = report["provenance"]["target"]
        target.update(git_sha=None, branch=None, dirty=None)
        self.assertIn(
            "Repository `example-service` with no commit recorded. Started `2026-10-10T09:00:00+00:00`.",
            self.render(report),
        )
        target.update(git_sha="a" * 40, branch="dev", dirty=True)
        self.assertIn("at commit `aaaaaaaaaaaa` on branch `dev` (uncommitted changes).", self.render(report))


class EvidenceTests(RenderCase):
    def test_a_quote_is_in_a_fenced_block_under_its_bullet_and_never_inline(self) -> None:
        details = details_of(self.render(service()), "AGT-11")
        self.assertIn(
            "- `AGENTS.md:14-16` · captured by agent\n  ```text\n  Run `npm test` to run the tests. "
            "Run `npm run lint` to lint the code.\n  ```",
            details,
        )

    def test_every_item_says_who_captured_it(self) -> None:
        markdown = self.render(service())
        self.assertIn(
            "- `package.json` · captured by tool `python-agentic-audit` 0.1.0", details_of(markdown, "CMD-01")
        )
        self.assertIn("· captured by agent", details_of(markdown, "TOOL-03"))
        for check_id in ("AGT-11", "TOOL-03", "SEC-02", "CMD-01"):
            for line in details_of(markdown, check_id).split("\n"):
                if line.startswith("- ") and "search for" not in line:
                    self.assertIn(" · captured by ", line, line)

    def test_a_quote_that_holds_backticks_gets_a_longer_fence_and_the_blocks_stay_balanced(self) -> None:
        report = service()
        check_of(report, "AGT-11")["evidence"][0]["quote"] = "before\n```\nafter\n````\nmore"
        markdown = self.render(report)
        self.assertIn("  `````text\n  before\n  ```\n  after\n  ````\n  more\n  `````", markdown)
        list(scan(markdown))

    def test_a_command_shows_its_exit_code_time_and_redactions_and_its_output_in_a_fence(self) -> None:
        report = service()
        check_of(report, "TST-02")["evidence"].append(
            {
                "kind": "command",
                "captured_by": "tool",
                "tool": "python-agentic-audit",
                "tool_version": "0.1.0",
                "command": "make test",
                "exit_code": 1,
                "output_tail": "FAILED (failures=2)\n```\nlast line",
                "timed_out": False,
                "duration_s": 12.5,
                "redactions": 2,
            }
        )
        details = details_of(self.render(report), "TST-02")
        self.assertIn(
            "- Command `make test` (exit 1, 12.5 s, 2 redactions) · captured by tool `python-agentic-audit` 0.1.0\n"
            "  ````text\n  FAILED (failures=2)\n  ```\n  last line\n  ````",
            details,
        )

    def test_a_command_that_timed_out_says_so_and_a_zero_exit_code_is_shown(self) -> None:
        report = service()
        base = {"kind": "command", "captured_by": "agent", "command": "make lint"}
        check_of(report, "TST-02")["evidence"] += [
            {**base, "exit_code": 0, "duration_s": 3.0},
            {**base, "exit_code": None, "timed_out": True, "redactions": 0},
        ]
        details = details_of(self.render(report), "TST-02")
        self.assertIn("- Command `make lint` (exit 0, 3 s) · captured by agent", details)
        self.assertIn("- Command `make lint` (timed out) · captured by agent", details)

    def test_an_index_query_shows_the_tool_the_query_and_the_result(self) -> None:
        details = details_of(self.render(service()), "AGT-11")
        self.assertIn(
            "- Index query `scripts defined in package.json` through `search_graph`: "
            "7 scripts; 4 are named in AGENTS.md with no added context · captured by agent",
            details,
        )

    def test_a_note_on_evidence_is_text_and_a_path_with_lines_is_code(self) -> None:
        self.assertIn(
            "- `src/config/constants.ts:12` — credential-shaped string · captured by tool", self.render(service())
        )

    def test_searches_say_how_many_hits_they_had(self) -> None:
        report = service()
        check_of(report, "AGT-11")["searches"] = [
            {"tool": "grep", "pattern": "never", "scope": "AGENTS.md", "hits": 0},
            {"tool": "glob", "pattern": "**/*.md", "scope": ".", "hits": 1},
            {"tool": "index", "pattern": "release", "scope": "src/", "hits": 3},
        ]
        details = details_of(self.render(report), "AGT-11")
        lines = details.split("\n")
        self.assertIn("- `grep` search for `never` in `AGENTS.md`: no hits", lines)
        self.assertIn("- `glob` search for `**/*.md` in `.`: 1 hit", lines)
        self.assertIn("- `index` search for `release` in `src/`: 3 hits", lines)

    def test_every_fenced_block_of_every_example_is_closed(self) -> None:
        for path in [EXAMPLES / SERVICE, EXAMPLES / "minimal.json", *drafts()]:
            with self.subTest(path=path.name):
                list(scan(self.render(load(path))))


class OverrideTests(RenderCase):
    def test_an_override_is_in_the_table_next_to_the_engines_verdict_with_its_reason(self) -> None:
        text = section(self.render(service()), "Overrides of the engine's verdicts")
        self.assertIn("| `TOOL-03` | PARTIAL | PASS | tsconfig.json extends tsconfig.base.json,", text)
        self.assertEqual(len([line for line in text.split("\n") if line.startswith("| `")]), 1)

    def test_the_checks_table_shows_both_verdicts_on_the_row(self) -> None:
        text = section(self.render(service()), "Checks")
        row = next(line for line in text.split("\n") if line.startswith("| `TOOL-03`"))
        cells = [c.strip() for c in row.strip("|").split("|")]
        self.assertEqual(cells[5:7], ["PASS", "PARTIAL"])

    def test_the_check_block_says_what_the_engine_said_what_this_report_says_and_why(self) -> None:
        details = details_of(self.render(service()), "TOOL-03")
        self.assertIn(
            "**Overridden.** The engine's verdict was **PARTIAL**. This report says **PASS**. Reason: "
            "tsconfig.json extends tsconfig.base.json, which sets strict: true; the engine reads only the leaf file.",
            details,
        )
        self.assertIn("captured by agent", details)

    def test_a_verdict_equal_to_the_engines_is_not_an_override(self) -> None:
        markdown = self.render(service())
        self.assertNotIn("**Overridden.**", details_of(markdown, "CMD-01"))
        self.assertEqual(markdown.count("**Overridden.**"), 1)

    def test_with_no_override_the_section_says_so(self) -> None:
        for report in (minimal(), load(next(iter(drafts())))):
            text = section(self.render(report), "Overrides of the engine's verdicts")
            self.assertIn("No engine verdict was overridden.", text)
            self.assertNotIn("| Check |", text)

    def test_an_automated_pass_with_an_override_gets_a_block_and_a_plain_pass_does_not(self) -> None:
        markdown = self.render(service())
        self.assertIn("#### TOOL-03:", markdown)
        self.assertNotIn("#### IDX-01:", markdown)
        self.assertNotIn("#### CI-01:", markdown)


class NoEvidenceTests(RenderCase):
    SENTENCE = "**Evidence.** We did not find any evidence."

    def test_a_failed_or_unknown_check_with_no_evidence_and_no_searches_says_so(self) -> None:
        markdown = self.render(service())
        self.assertIn(self.SENTENCE, details_of(markdown, "TST-02"))
        self.assertIn(self.SENTENCE, details_of(markdown, "CI-04"))
        self.assertEqual(markdown.count(self.SENTENCE), 2)

    def test_the_sentence_has_exactly_the_words_the_decision_gave(self) -> None:
        self.assertEqual(rr.NO_EVIDENCE, "We did not find any evidence.")

    def test_evidence_on_the_check_takes_the_sentence_away(self) -> None:
        report = service()
        check_of(report, "TST-02")["evidence"] = [{"kind": "file", "captured_by": "agent", "path": "Makefile"}]
        details = details_of(self.render(report), "TST-02")
        self.assertNotIn(self.SENTENCE, details)
        self.assertIn("**Evidence**\n\n- `Makefile` · captured by agent", details)

    def test_a_search_on_the_check_takes_the_sentence_away_and_is_listed(self) -> None:
        report = service()
        check_of(report, "CI-04")["searches"] = [
            {"tool": "grep", "pattern": "make check", "scope": ".github/", "hits": 0}
        ]
        details = details_of(self.render(report), "CI-04")
        self.assertNotIn(self.SENTENCE, details)
        self.assertIn("**Searches**\n\n- `grep` search for `make check` in `.github/`: no hits\n", details)

    def test_evidence_only_on_a_finding_also_takes_the_sentence_away(self) -> None:
        report = service()
        finding_of(report, "F-008")["evidence"] = [
            {"kind": "file", "captured_by": "agent", "path": ".github/workflows/ci.yml"}
        ]
        details = details_of(self.render(report), "CI-04")
        self.assertNotIn(self.SENTENCE, details)
        self.assertIn("Evidence for F-008:", details)

    def test_a_search_only_on_a_finding_also_takes_the_sentence_away(self) -> None:
        report = service()
        finding_of(report, "F-008")["searches"] = [{"tool": "glob", "pattern": "*.yml", "scope": ".github/", "hits": 1}]
        self.assertNotIn(self.SENTENCE, details_of(self.render(report), "CI-04"))

    def test_other_verdicts_never_get_the_sentence(self) -> None:
        for verdict in ("PASS", "PARTIAL", "NOT_APPLICABLE"):
            with self.subTest(verdict=verdict):
                report = service()
                check = check_of(report, "CI-04")
                set_verdict(check, verdict)
                finding_of(report, "F-008")["disposition"] = "rejected"
                self.assertNotIn(self.SENTENCE, details_of(self.render(report), "CI-04"))

    def test_the_sentence_applies_to_an_automated_check_too(self) -> None:
        report = service()
        self.assertEqual(check_of(report, "TST-02")["method"], "automated")
        self.assertIn(self.SENTENCE, details_of(self.render(report), "TST-02"))


class FindingTests(RenderCase):
    def test_a_finding_shows_its_statement_fix_and_everything_the_fix_names(self) -> None:
        details = details_of(self.render(service()), "CI-04")
        self.assertIn("**F-008** · DEGRADER · key `CI-04`", details)
        self.assertIn("An agent cannot trust a green CI run to mean the local gate passed because", details)
        self.assertIn("**Fix.** Make the workflow run the check verb once it exists.", details)
        self.assertIn(
            "Playbook `add-ci-parity` · Effort M · Depends on `F-002` · Touches `.github/workflows/ci.yml`", details
        )

    def test_a_fix_that_names_nothing_but_its_summary_has_no_details_line(self) -> None:
        details = details_of(self.render(service()), "TOOL-03")
        self.assertIn("**Fix.** Turn on strict mode.", details)
        self.assertNotIn("Playbook", details)
        report = service()
        finding_of(report, "F-001")["remediation"]["playbook"] = None
        self.assertNotIn("Playbook", details_of(self.render(report), "CMD-01"))

    def test_a_finding_lower_than_its_check_says_so(self) -> None:
        details = details_of(self.render(service()), "AGT-08")
        self.assertIn("**F-010** · COSMETIC · key `AGT-08` · on a DEGRADER check", details)
        self.assertNotIn("on a BLOCKER check", details_of(self.render(service()), "CMD-01"))

    def test_each_disposition_and_each_way_of_deciding_has_its_own_words(self) -> None:
        wording = {
            "interactive": "Decided by the person, on this finding alone.",
            "batch": "Decided by the person, as one of a group of findings that are not blockers.",
            "policy": "Set by the confirmation policy, not by a person.",
        }
        for disposition in ("confirmed", "rejected", "deferred", "edited"):
            for via, words in wording.items():
                with self.subTest(disposition=disposition, via=via):
                    report = service()
                    finding = finding_of(report, "F-001")
                    finding.update(disposition=disposition, confirmed_via=via)
                    finding.pop("disposition_note", None)
                    self.assertIn(f"**{disposition.capitalize()}.** {words}\n", self.render(report))

    def test_a_pending_finding_awaits_a_decision_and_shows_no_way_of_deciding(self) -> None:
        report = service()
        finding = finding_of(report, "F-001")
        finding["disposition"] = "pending"
        del finding["confirmed_via"]
        details = details_of(self.render(report), "CMD-01")
        self.assertIn("**Awaiting a decision.**", details.split("\n"))
        self.assertNotIn("Decided by", details)

    def test_the_persons_note_is_shown_and_absent_when_there_is_none(self) -> None:
        markdown = self.render(service())
        self.assertIn(
            "**Edited.** Decided by the person, on this finding alone. Note: The owner pins Node 22", markdown
        )
        self.assertNotIn("Note:", details_of(markdown, "CMD-01"))

    def test_evidence_equal_to_the_checks_is_not_printed_twice(self) -> None:
        details = details_of(self.render(service()), "CMD-01")
        self.assertIn("Evidence: the same as under the check.", details)
        self.assertNotIn("Evidence for F-001", details)
        self.assertEqual(details.count("- `package.json` · captured by"), 1)

    def test_evidence_that_differs_from_the_checks_is_printed_under_the_finding(self) -> None:
        details = details_of(self.render(service()), "SEC-02")
        self.assertIn("Evidence for F-004:", details)
        self.assertIn("Evidence for F-005:", details)
        self.assertNotIn("the same as under the check", details)

    def test_searches_equal_to_the_checks_are_not_printed_twice_and_different_ones_are(self) -> None:
        details = details_of(self.render(service()), "AGT-11")
        self.assertIn("Searches: the same as under the check.", details)
        report = service()
        finding_of(report, "F-007")["searches"] = [{"tool": "grep", "pattern": "x", "scope": ".", "hits": 2}]
        details = details_of(self.render(report), "AGT-11")
        self.assertIn("Searches for F-007:\n\n- `grep` search for `x` in `.`: 2 hits", details)

    def test_every_finding_of_every_example_appears_once_under_its_check(self) -> None:
        for path in [EXAMPLES / SERVICE, *drafts()]:
            with self.subTest(path=path.name):
                report = load(path)
                markdown = self.render(report)
                for finding in report["findings"]:
                    self.assertEqual(markdown.count(f"**{finding['id']}** · "), 1, finding["id"])
                    self.assertIn(finding["id"], details_of(markdown, finding["check"]).replace("**", ""))

    def test_findings_of_one_check_come_in_the_order_of_the_report(self) -> None:
        details = details_of(self.render(service()), "SEC-02")
        self.assertLess(details.index("**F-004**"), details.index("**F-005**"))
        report = service()
        report["findings"].reverse()
        details = details_of(self.render(report), "SEC-02")
        self.assertLess(details.index("**F-005**"), details.index("**F-004**"))


class DetailsTests(RenderCase):
    def test_checks_are_grouped_by_severity_in_the_order_of_the_report(self) -> None:
        markdown = self.render(service())
        self.assertEqual(
            [line for line in markdown.split("\n") if line.startswith("#### ")],
            [
                "#### CMD-01: Seven verbs resolvable on one runner",
                "#### CMD-02: check composes the read-only verbs",
                "#### EXEC-01: Toolchain pinned / wrapper committed",
                "#### SEC-02: No key-shaped strings in tracked files",
                "#### AGT-07: Do-not-do / deny rules present",
                "#### AGT-08: No competing instruction files, and the reach matrix is stated",
                "#### AGT-11: Instructions are specific and not inferable",
                "#### TOOL-03: Type checker configured",
                "#### CI-04: CI enforces the same gate as the local check",
                "#### TST-02: Suite status known",
            ],
        )
        self.assertIn("### BLOCKER checks", markdown)
        self.assertIn("### DEGRADER checks", markdown)
        self.assertNotIn("### COSMETIC checks", markdown)

    def test_a_check_gets_a_block_when_it_is_not_met_overridden_judged_by_the_agent_or_has_a_finding(self) -> None:
        cases = {
            "PARTIAL": True,
            "FAIL": True,
            "UNKNOWN": True,
            "PASS": False,
            "NOT_APPLICABLE": False,
        }
        for verdict, expected in cases.items():
            with self.subTest(verdict=verdict):
                report = service()
                report["findings"] = []
                check = check_of(report, "IDX-01")
                check["verdict"], check["engine_verdict"] = verdict, verdict
                self.assertEqual("#### IDX-01:" in self.render(report), expected)
        report = service()
        check_of(report, "IDX-01")["method"] = "agent"
        del check_of(report, "IDX-01")["engine_verdict"]
        self.assertIn("#### IDX-01:", self.render(report))
        report = service()
        finding = copy.deepcopy(finding_of(report, "F-001"))
        finding.update(id="F-099", key="IDX-01", check="IDX-01", disposition="rejected")
        report["findings"].append(finding)
        self.assertIn("#### IDX-01:", self.render(report))

    def test_the_block_names_the_verdict_severity_method_scoring_and_confidence(self) -> None:
        markdown = self.render(service())
        self.assertIn("**PARTIAL** · DEGRADER · agent · scored · confidence medium", details_of(markdown, "AGT-11"))
        self.assertIn("**FAIL** · BLOCKER · automated · scored\n", details_of(markdown, "CMD-01"))
        report = service()
        check_of(report, "CMD-01")["scored"] = False
        self.assertIn(
            "**FAIL** · BLOCKER · automated · not scored", details_of(self.render(report), "CMD-01").split("\n")
        )

    def test_an_engine_payload_is_named_and_left_in_the_json(self) -> None:
        details = details_of(self.render(service()), "CMD-01")
        self.assertIn("The engine's payload for this check, of kind `verb_surface`, is in the JSON report.", details)
        self.assertNotIn("resolved_count", details)
        self.assertNotIn("The engine's payload", details_of(self.render(service()), "AGT-11"))

    def test_with_no_check_that_needs_a_block_the_section_says_so(self) -> None:
        self.assertIn("#### AGT-11:", section(self.render(minimal()), "Check details"))
        report = service()
        report["checks"] = [check_of(report, "IDX-01")]
        report["findings"] = []
        text = section(self.render(report), "Check details")
        self.assertIn("No check needs detail.", text.split("\n"))
        self.assertNotIn("####", text)

    def test_the_checks_table_has_a_row_for_every_check_in_report_order_with_the_scored_flag(self) -> None:
        for path in [EXAMPLES / SERVICE, EXAMPLES / "minimal.json", *drafts()]:
            with self.subTest(path=path.name):
                report = load(path)
                text = section(self.render(report), "Checks")
                rows = [line for line in text.split("\n") if line.startswith("| `")]
                self.assertEqual(
                    [row.split("|")[1].strip() for row in rows], [f"`{c['id']}`" for c in report["checks"]]
                )
        text = section(self.render(service()), "Checks")
        self.assertEqual(text.split("\n")[2], "12 checks: 3 PASS, 2 PARTIAL, 6 FAIL, 1 UNKNOWN.")

    def test_a_check_that_does_not_count_toward_the_score_says_no_in_the_table(self) -> None:
        report = service()
        check_of(report, "IDX-01")["scored"] = False
        row = next(line for line in section(self.render(report), "Checks").split("\n") if line.startswith("| `IDX-01`"))
        self.assertEqual([c.strip() for c in row.strip("|").split("|")][4], "no")

    def test_the_legend_explains_every_verdict_and_severity_from_the_renderer_not_the_json(self) -> None:
        text = section(self.render(service()), "Checks")
        for name, meaning in {**rr.VERDICT_MEANINGS, **rr.SEVERITY_MEANINGS}.items():
            self.assertIn(f"- **{name}**: {meaning}", text)
        self.assertEqual(set(rr.VERDICT_MEANINGS), set(rr.VERDICTS))
        self.assertEqual(set(rr.SEVERITY_MEANINGS), set(rr.SEVERITIES))

    def test_an_empty_summary_is_a_dash_in_the_blockers_table_and_the_checks_table(self) -> None:
        report = service()
        check_of(report, "CMD-01")["summary"] = ""
        markdown = self.render(report)
        blockers = section(markdown, "Blockers remaining").split("\n")
        self.assertIn("| `CMD-01` | Seven verbs resolvable on one runner | FAIL | — |", blockers)
        row = next(line for line in section(markdown, "Checks").split("\n") if line.startswith("| `CMD-01`"))
        self.assertTrue(row.endswith("| FAIL | FAIL | — |"), row)
        block = details_of(markdown, "CMD-01").split("\n")
        self.assertEqual(block[:4], ["#### CMD-01: Seven verbs resolvable on one runner", "", block[2], ""])
        self.assertTrue(block[4].startswith("**Evidence**"))

    def test_a_report_with_no_check_says_so_in_every_section_that_lists_checks(self) -> None:
        report = service()
        report["checks"], report["findings"] = [], []
        markdown = self.render(report)
        self.assertIn("No check is recorded.", section(markdown, "Checks").split("\n"))
        self.assertIn("No scored BLOCKER check is open.", markdown.split("\n"))
        self.assertIn("- **Phase-1 score: 0.00**, over 0 scored checks", markdown.split("\n"))
        self.assertIn("No check needs detail.", markdown.split("\n"))

    def test_an_engine_payload_without_a_kind_is_still_pointed_to(self) -> None:
        report = service()
        check_of(report, "CMD-01")["data"] = {"verbs": []}
        details = details_of(self.render(report), "CMD-01")
        self.assertIn("The engine's payload for this check is in the JSON report.", details.split("\n"))
        check_of(report, "CMD-01").pop("data")
        self.assertNotIn("payload", details_of(self.render(report), "CMD-01"))


class OtherSectionTests(RenderCase):
    def test_coverage_lists_what_was_examined_and_skipped_and_the_inventory(self) -> None:
        text = section(self.render(service()), "Coverage")
        self.assertIn("**Examined:** `.`", text)
        self.assertIn("| `dist/` | excluded at intake |", text)
        self.assertIn("**Files:** 84 files inspected, 0 skipped; the scan was not cut short.", text)

    def test_coverage_says_when_nothing_was_skipped_and_when_the_scan_was_cut_short(self) -> None:
        report = service()
        report["coverage"]["scopes_skipped"] = []
        report["coverage"]["inventory"].update(files_inspected=1, truncated=True)
        text = section(self.render(report), "Coverage")
        self.assertIn("No scope was skipped.", text)
        self.assertIn("1 file inspected, 0 skipped; the scan was cut short.", text)
        del report["coverage"]["inventory"]
        self.assertNotIn("**Files:**", section(self.render(report), "Coverage"))
        report["coverage"]["scopes_examined"] = []
        self.assertIn("nothing is recorded", section(self.render(report), "Coverage"))

    def test_the_stack_and_the_components_are_listed_with_dashes_for_what_is_empty(self) -> None:
        text = section(self.render(service()), "Stack and components")
        self.assertIn("| Ecosystems | `node` |", text)
        self.assertIn("| Hook managers | — |", text)
        self.assertIn("| (root) | `.` | yes | implicit | `package.json` | present |", text)
        report = service()
        report["components"] = []
        report["stack"]["notes"] = ["Monorepo with two packages", "# not a heading"]
        text = section(self.render(report), "Stack and components")
        self.assertIn("No component is recorded.", text)
        self.assertIn("- Monorepo with two packages\n- \\# not a heading", text)

    def test_the_provenance_names_the_commit_the_engine_and_the_agent_as_self_reported(self) -> None:
        text = section(self.render(service()), "Provenance")
        self.assertIn("| Commit | `deadbeefdeadbeefdeadbeefdeadbeefdeadbeef` |", text)
        self.assertIn(
            "| Engine | `python-agentic-audit` 0.1.0, ruleset `2026-09-28.13`, ruleset hash `a1b2a1b2a1b2a1b2`, "
            "scanned `2026-10-10T09:01:30+00:00` |",
            text,
        )
        self.assertIn("| Agent (self-reported) | `claude-code` with `claude-sonnet-5-5` |", text)
        self.assertIn("| Framework revision | `cafecafecafe` |", text)
        self.assertIn("| Report status | final |", text)

    def test_a_report_with_no_engine_and_no_commit_says_so(self) -> None:
        text = section(self.render(minimal()), "Provenance")
        self.assertIn("| Engine | No engine report is part of this report. |", text)
        report = minimal()
        report["provenance"]["target"].update(git_sha=None, branch=None, dirty=None)
        report["provenance"]["framework_revision"] = None
        text = section(self.render(report), "Provenance")
        self.assertIn("| Commit | none recorded |", text)
        self.assertIn("| Framework revision | — |", text)
        self.assertIn("| Finalised | — |", text)

    def test_the_run_context_states_the_policy_the_index_the_probes_and_the_exposure_acknowledgement(self) -> None:
        text = section(self.render(service()), "Run context")
        self.assertIn("| Confirmation policy | `interactive` |", text)
        self.assertIn("| Provider exposure acknowledged | yes: the model provider receives what the agent reads", text)
        self.assertIn("| Code index | `mcp` `codebase-memory-mcp` |", text)
        self.assertIn("| Probes | none: no command of the target was run |", text)
        self.assertIn("| Stack profile | `typescript-node`, shipped, confirmed by the user |", text)
        report = service()
        report["run_context"]["probes"] = {"allowed": ["test", "lint"], "timeout_s": 90}
        report["run_context"]["stack_profile"]["confirmed_by_user"] = False
        report["run_context"]["index"] = {"kind": "cli", "name": "gitnexus", "notes": "installed by the user"}
        text = section(self.render(report), "Run context")
        self.assertIn("| Probes | `test`, `lint`, timeout 90 s |", text)
        self.assertIn("not confirmed by the user", text)
        self.assertIn("| Code index | `cli` `gitnexus` — installed by the user |", text)
        del report["run_context"]["stack_profile"]
        self.assertIn("| Stack profile | — |", section(self.render(report), "Run context"))

    def test_the_sections_come_in_a_fixed_order_and_the_file_ends_with_one_newline(self) -> None:
        markdown = self.render(service())
        headings = [line for line in markdown.split("\n") if line.startswith("## ")]
        self.assertEqual(
            headings,
            [
                "## Readiness summary",
                "## Blockers remaining",
                "## Overrides of the engine's verdicts",
                "## Checks",
                "## Check details",
                "## Coverage",
                "## Stack and components",
                "## Provenance",
                "## Run context",
            ],
        )
        self.assertTrue(markdown.startswith("# Agentic readiness audit: example-service\n"))
        self.assertTrue(markdown.endswith("The JSON report is the record.\n"))
        self.assertFalse(markdown.endswith("\n\n"))
        self.assertNotIn("\n\n\n", markdown)
        self.assertEqual(markdown.count("\n# "), 0)

    def test_a_component_with_no_declarer_or_manifest_has_dashes(self) -> None:
        report = service()
        report["components"][0].update(declared=False, declared_by=None, manifest=None, agents_md="unknown")
        text = section(self.render(report), "Stack and components")
        self.assertIn("| (root) | `.` | no | — | — | unknown |", text.split("\n"))

    def test_the_engine_row_names_only_what_the_report_records(self) -> None:
        report = service()
        engine = report["provenance"]["engine"]
        del engine["ruleset_revision"], engine["scanned_at"]
        row = "| Engine | `python-agentic-audit` 0.1.0, ruleset hash `a1b2a1b2a1b2a1b2` |"
        self.assertIn(row, section(self.render(report), "Provenance").split("\n"))
        engine["ruleset_revision"] = "2026-09-28.13"
        row = "| Engine | `python-agentic-audit` 0.1.0, ruleset `2026-09-28.13`, ruleset hash `a1b2a1b2a1b2a1b2` |"
        self.assertIn(row, section(self.render(report), "Provenance").split("\n"))


HOSTILE = {
    "image": "![x](https://evil.example/p.png?q=1)",
    "html": "<img src=x onerror=alert(1)>",
    "link": "[click](javascript:alert(1))",
    "heading": "# Injected heading",
    "table": "| a | b |",
    "fence": "```\nbreak out",
    "bidi": "name‮gnp.exe",
    "control": "bell\x07 escape\x1b[31m",
    "emphasis": "**bold** __bold__ _it_",
    "blockquote": "> a quotation",
}


class InjectionTests(RenderCase):
    """Free text comes from a repository, through a model: whatever it holds, it must not become markup."""

    def hostile_report(self, kind: str) -> dict[str, Any]:
        payload = HOSTILE[kind]
        report = service()
        report["provenance"]["target"]["label"] = "example-service"
        for check in report["checks"]:
            check["summary"] = payload
            check["title"] = payload
            if "override_reason" in check:
                check["override_reason"] = payload
            for item in check["evidence"]:
                item["note"] = payload
                if item["kind"] == "file":
                    item["quote"] = payload[:300]
            for search in check["searches"]:
                search["pattern"] = payload
        for finding in report["findings"]:
            finding["statement"] = "An agent cannot x because " + payload
            finding["remediation"]["summary"] = payload
            if "disposition_note" in finding:
                finding["disposition_note"] = payload
            for item in finding["evidence"]:
                item["note"] = payload
        for item in report["unattested"]:
            item["why"] = payload
        report["coverage"]["scopes_skipped"][0]["reason"] = payload
        report["components"][0]["name"] = payload
        report["stack"]["notes"] = [payload]
        report["run_context"]["index"]["notes"] = payload
        return report

    def test_no_text_becomes_an_image_a_link_a_tag_or_a_heading(self) -> None:
        for kind in HOSTILE:
            with self.subTest(kind=kind):
                markdown = self.render(self.hostile_report(kind))
                lines = outside_fences(markdown)
                self.assertEqual(
                    [line for line in lines if line.startswith("# ")], ["# Agentic readiness audit: example-service"]
                )
                for line in lines:
                    unspanned = re.sub(r"(`+).+?\1", "", line)
                    self.assertIsNone(re.search(r"(?<!\\)!\[", unspanned), line)
                    self.assertIsNone(re.search(r"(?<!\\)\]\(", unspanned), line)
                    self.assertIsNone(re.search(r"(?<!\\)<", unspanned), line)
                    self.assertFalse(line.startswith(("> ", ">")) and not line.startswith(("> [!", "> **")), line)

    def test_no_text_adds_a_column_or_a_row_to_a_table(self) -> None:
        for kind in HOSTILE:
            with self.subTest(kind=kind):
                markdown = self.render(self.hostile_report(kind))
                block: list[str] = []
                for line in outside_fences(markdown) + [""]:
                    if line.startswith("|"):
                        block.append(line)
                        continue
                    if block:
                        self.assertEqual({unescaped_pipes(row) for row in block}, {unescaped_pipes(block[0])}, block)
                        block = []

    def test_no_fenced_block_can_be_closed_from_inside(self) -> None:
        for kind in HOSTILE:
            with self.subTest(kind=kind):
                list(scan(self.render(self.hostile_report(kind))))

    def test_no_control_or_format_character_reaches_the_output(self) -> None:
        for kind in HOSTILE:
            with self.subTest(kind=kind):
                markdown = self.render(self.hostile_report(kind))
                for char in markdown:
                    if char not in "\n\t":
                        self.assertNotIn(unicodedata.category(char), ("Cc", "Cf"), repr(char))
        self.assertIn("{U+202E}", self.render(self.hostile_report("bidi")))
        self.assertIn("{U+0007}", self.render(self.hostile_report("control")))

    def test_hostile_text_is_still_shown_so_that_nothing_is_hidden(self) -> None:
        markdown = self.render(self.hostile_report("image"))
        self.assertIn("evil.example/p.png", markdown)
        self.assertIn(r"!\[x\](https://evil.example/p.png?q=1)", markdown)

    def test_a_path_a_command_and_a_scope_with_backticks_stay_in_their_spans(self) -> None:
        report = service()
        check_of(report, "SEC-02")["evidence"][0]["path"] = "src/`rm -rf`.ts"
        check_of(report, "AGT-11")["searches"] = [
            {"tool": "grep", "pattern": "a`b", "scope": "x``y|z", "hits": 1},
        ]
        markdown = self.render(report)
        self.assertIn("- ``src/`rm -rf`.ts:12`` — credential-shaped string", markdown)
        self.assertIn("`grep` search for ``a`b`` in ```x``y|z```: 1 hit", markdown)

    def test_a_pipe_inside_a_code_span_in_a_table_cell_does_not_add_a_column(self) -> None:
        report = service()
        report["components"][0]["path"] = "a|b"
        report["components"][0]["manifest"] = "c|d"
        text = section(self.render(report), "Stack and components")
        row = next(line for line in text.split("\n") if line.startswith("| (root)"))
        self.assertEqual(unescaped_pipes(row), 7)


class PurityTests(RenderCase):
    def every_example(self) -> list[dict[str, Any]]:
        return [service(), minimal(), *(load(path) for path in drafts())]

    def test_one_report_gives_one_text(self) -> None:
        for report in self.every_example():
            with self.subTest(report=report["provenance"]["target"]["label"]):
                self.assertEqual(self.render(report), self.render(report))

    def test_the_text_is_the_same_after_a_trip_through_json(self) -> None:
        for report in self.every_example():
            with self.subTest(report=report["provenance"]["target"]["label"]):
                self.assertEqual(self.render(report), self.render(json.loads(json.dumps(report))))

    def test_the_order_of_the_keys_does_not_matter(self) -> None:
        for report in self.every_example():
            with self.subTest(report=report["provenance"]["target"]["label"]):
                self.assertEqual(self.render(report), self.render(reordered(report)))

    def test_the_report_is_not_changed(self) -> None:
        for report in self.every_example():
            with self.subTest(report=report["provenance"]["target"]["label"]):
                before = copy.deepcopy(report)
                self.render(report)
                self.assertEqual(report, before)

    def test_it_touches_no_file_and_no_clock(self) -> None:
        report = service()
        with (
            mock.patch("builtins.open", side_effect=AssertionError("opened a file")),
            mock.patch("os.open", side_effect=AssertionError("opened a file")),
            mock.patch("time.time", side_effect=AssertionError("read the clock")),
            mock.patch("time.monotonic", side_effect=AssertionError("read the clock")),
            mock.patch("subprocess.run", side_effect=AssertionError("ran a process")),
        ):
            self.assertIn("# Agentic readiness audit", rr.render(report))

    def test_the_text_does_not_say_when_it_was_made_or_by_which_version(self) -> None:
        markdown = self.render(service())
        footer = markdown.rsplit("\n---\n", 1)[1]
        self.assertEqual(
            footer.strip(), "Rendered from the JSON report by `render_report.py`. The JSON report is the record."
        )
        self.assertIsNone(re.search(r"\d", footer))


class GoldenTests(RenderCase):
    def assert_golden(self, json_path: Path, golden: Path) -> None:
        self.assertTrue(golden.is_file(), f"the golden file {golden} is missing")
        expected = golden.read_text(encoding="utf-8")
        actual = self.render(load(json_path))
        self.assertEqual(
            actual,
            expected,
            f"{golden.name} differs from the rendering of {json_path.name}. If the change is deliberate, delete "
            f"{golden.name}, run render_report.py on {json_path.name} with --out {golden}, and read the diff.",
        )

    def test_the_smallest_report_renders_to_its_golden_file(self) -> None:
        self.assert_golden(EXAMPLES / "minimal.json", EXAMPLES / "minimal.md")

    def test_the_worked_example_renders_to_its_golden_file_under_the_same_name(self) -> None:
        self.assert_golden(EXAMPLES / SERVICE, (EXAMPLES / SERVICE).with_suffix(".md"))

    def test_the_golden_files_are_what_the_command_line_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "worked.md"
            done = subprocess.run(
                [sys.executable, str(TOOLS / "render_report.py"), str(EXAMPLES / SERVICE), "--out", str(out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(out.read_bytes(), (EXAMPLES / SERVICE).with_suffix(".md").read_bytes())

    def test_every_realistic_draft_renders_with_every_check_and_every_finding(self) -> None:
        self.assertEqual(len(drafts()), 3)
        for path in drafts():
            with self.subTest(path=path.name):
                report = load(path)
                markdown = self.render(report)
                rows = [line for line in section(markdown, "Checks").split("\n") if line.startswith("| `")]
                self.assertEqual(len(rows), 69)
                for finding in report["findings"]:
                    self.assertEqual(markdown.count(f"**{finding['id']}** · "), 1)
                self.assertIn("> [!NOTE]\n> **Draft.**", markdown)

    def test_the_displayed_score_equals_the_engines_own_score_to_two_places(self) -> None:
        for path in drafts():
            with self.subTest(path=path.name):
                engine = load(str(path).replace(".audit-draft.", ".engine-report."))
                shown = f"**Phase-1 score: {rr.score_text(engine['summary']['phase1_score'])}**"
                self.assertIn(shown, self.render(load(path)))


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    """Run the tool in process, as a recipe sees it: the exit code, the envelope and what went to stderr."""
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(rr.INFO, rr.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(root.rglob("*"))}


class CliCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / "service"
        self.target.mkdir()
        (self.target / "README.md").write_text("target file", encoding="utf-8")
        self.outdir = self.root / "out"
        self.outdir.mkdir()

    def write_report(self, report: dict[str, Any] | None = None, name: str = "report.json") -> Path:
        document = report if report is not None else service()
        document["provenance"]["target"]["path"] = str(self.target)
        path = self.root / name
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return path


class CliTests(CliCase):
    def test_it_writes_the_markdown_the_function_returns_and_reports_where(self) -> None:
        report = self.write_report()
        out = self.outdir / "report.md"
        code, envelope, stderr = call([str(report), "--out", str(out)])
        self.assertEqual(code, 0, envelope)
        expected = rr.render(load(report))
        self.assertEqual(out.read_text(encoding="utf-8"), expected)
        data = envelope["data"]
        self.assertEqual(data["markdown"], str(out))
        self.assertEqual(data["report"], str(report))
        self.assertEqual(data["status"], "final")
        self.assertEqual(data["lines"], len(expected.splitlines()))
        self.assertEqual(data["bytes"], len(expected.encode("utf-8")))
        self.assertEqual(
            (envelope["tool"], envelope["ok"], envelope["warnings"], envelope["truncated"]),
            ("render_report", True, [], False),
        )
        self.assertEqual(stderr, f"render_report: wrote report.md ({data['lines']} lines)\n")

    def test_it_never_replaces_a_file_that_is_there(self) -> None:
        report = self.write_report()
        out = self.outdir / "report.md"
        out.write_text("somebody else's text", encoding="utf-8")
        code, envelope, _ = call([str(report), "--out", str(out)])
        self.assertEqual(code, 1)
        self.assertIn("already exists", envelope["data"]["error"])
        self.assertEqual(out.read_text(encoding="utf-8"), "somebody else's text")
        self.assertEqual(sorted(p.name for p in self.outdir.iterdir()), ["report.md"])

    def test_it_refuses_a_directory_a_symlink_and_the_report_itself(self) -> None:
        report = self.write_report()
        (self.outdir / "dir.md").mkdir()
        elsewhere = self.root / "elsewhere.txt"
        elsewhere.write_text("kept", encoding="utf-8")
        refused = [self.outdir / "dir.md", report]
        try:
            (self.outdir / "link.md").symlink_to(elsewhere)
            (self.outdir / "dangling.md").symlink_to(self.root / "nowhere.txt")
            refused += [self.outdir / "link.md", self.outdir / "dangling.md"]
        except (OSError, NotImplementedError):
            pass
        before = report.read_bytes()
        for out in refused:
            with self.subTest(out=out.name):
                code, _, _ = call([str(report), "--out", str(out)])
                self.assertEqual(code, 1)
        self.assertEqual(elsewhere.read_text(encoding="utf-8"), "kept")
        self.assertFalse((self.root / "nowhere.txt").exists())
        self.assertEqual(report.read_bytes(), before)

    def test_it_refuses_a_missing_folder_and_creates_nothing(self) -> None:
        report = self.write_report()
        code, envelope, _ = call([str(report), "--out", str(self.root / "nowhere" / "report.md")])
        self.assertEqual(code, 1)
        self.assertEqual(envelope["data"]["error"], f"the folder for --out does not exist: {self.root / 'nowhere'}")
        self.assertFalse((self.root / "nowhere").exists())

    def test_it_never_writes_inside_the_target(self) -> None:
        report = self.write_report()
        (self.target / "sub").mkdir()
        for out in (self.target / "report.md", self.target / "sub" / ".." / "report.md", self.target / "sub" / "r.md"):
            with self.subTest(out=str(out)):
                before = tree_state(self.target)
                code, envelope, _ = call([str(report), "--out", str(out)])
                self.assertEqual(code, 1)
                self.assertEqual(
                    envelope["data"]["error"], f"refusing to write inside the target: {out.parent.resolve()}"
                )
                self.assertEqual(tree_state(self.target), before)

    def test_a_folder_that_reaches_the_target_through_a_symlink_is_refused_too(self) -> None:
        report = self.write_report()
        link = self.root / "alias"
        try:
            link.symlink_to(self.target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        code, _, _ = call([str(report), "--out", str(link / "report.md")])
        self.assertEqual(code, 1)
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ["README.md"])

    def test_a_target_that_is_not_on_this_machine_does_not_stop_a_render_elsewhere(self) -> None:
        document = service()
        document["provenance"]["target"]["path"] = "/work/example-service"
        report = self.root / "report.json"
        report.write_text(json.dumps(document), encoding="utf-8")
        code, _, _ = call([str(report), "--out", str(self.outdir / "report.md")])
        self.assertEqual(code, 0)

    def test_it_leaves_the_report_alone(self) -> None:
        report = self.write_report()
        before = (report.read_bytes(), report.stat().st_mtime_ns)
        call([str(report), "--out", str(self.outdir / "report.md")])
        self.assertEqual((report.read_bytes(), report.stat().st_mtime_ns), before)

    def test_a_draft_renders_with_its_banner(self) -> None:
        document = service()
        document["status"] = "draft"
        del document["provenance"]["finalised_at"]
        for finding in document["findings"]:
            if finding["id"] == "F-001":
                finding["disposition"] = "pending"
                del finding["confirmed_via"]
        report = self.write_report(document)
        code, envelope, _ = call([str(report), "--out", str(self.outdir / "draft.md")])
        self.assertEqual(code, 0, envelope)
        self.assertIn("**Draft.**", (self.outdir / "draft.md").read_text(encoding="utf-8"))
        self.assertEqual(envelope["data"]["status"], "draft")

    def test_a_report_that_is_missing_or_not_a_file_is_exit_1(self) -> None:
        for argument in (str(self.root / "missing.json"), str(self.root)):
            with self.subTest(argument=argument):
                code, _, _ = call([argument, "--out", str(self.outdir / "x.md")])
                self.assertEqual(code, 1)
        self.assertEqual(list(self.outdir.iterdir()), [])

    def test_a_file_that_is_not_json_or_not_a_report_is_exit_2_and_writes_nothing(self) -> None:
        broken = self.root / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        code, envelope, _ = call([str(broken), "--out", str(self.outdir / "x.md")])
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", envelope["data"]["error"])
        schema_bad = service()
        schema_bad["status"] = "pending"
        code, envelope, _ = call([str(self.write_report(schema_bad, "bad.json")), "--out", str(self.outdir / "x.md")])
        self.assertEqual(code, 2)
        self.assertRegex(
            envelope["data"]["error"],
            r"^the report is not valid, so it was not rendered: [0-9]+ errors? in the (schema|rules) stage$",
        )
        self.assertTrue(envelope["data"]["errors"][0].startswith("schema: "))
        self.assertEqual(list(self.outdir.iterdir()), [])

    def test_a_report_that_breaks_a_rule_is_exit_2_with_the_rule_and_writes_nothing(self) -> None:
        def duplicate_check(document: dict[str, Any]) -> None:
            document["checks"].append(copy.deepcopy(document["checks"][0]))

        def tamper_with_summary(document: dict[str, Any]) -> None:
            document["summary"]["phase1_score"] = 0.99

        cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
            ("duplicate check", duplicate_check, "rule 1"),
            ("tampered summary", tamper_with_summary, "rule 10"),
        ]
        for name, change, rule in cases:
            with self.subTest(name=name):
                document = service()
                change(document)
                code, envelope, _ = call(
                    [str(self.write_report(document, f"{name}.json")), "--out", str(self.outdir / "x.md")]
                )
                self.assertEqual(code, 2)
                self.assertTrue(any(e.startswith(rule) for e in envelope["data"]["errors"]), envelope["data"]["errors"])
        self.assertEqual(list(self.outdir.iterdir()), [])

    def test_warnings_from_the_validator_are_passed_on(self) -> None:
        document = service()
        document["provenance"]["catalogue_version"] = "9.9.9"
        code, envelope, _ = call([str(self.write_report(document)), "--out", str(self.outdir / "x.md")])
        self.assertEqual(code, 0)
        self.assertEqual(len(envelope["warnings"]), 1)
        self.assertIn("catalogue", envelope["warnings"][0])

    def test_a_missing_or_abbreviated_or_unknown_argument_is_exit_1(self) -> None:
        report = str(self.write_report())
        out = str(self.outdir / "x.md")
        for argv in ([report], ["--out", out], [report, "--ou", out], [report, "--out", out, "--force"], []):
            with self.subTest(argv=argv):
                code, _, _ = call(argv)
                self.assertEqual(code, 1)
        self.assertEqual(list(self.outdir.iterdir()), [])

    def test_a_failed_write_leaves_no_partial_file(self) -> None:
        report = self.write_report()
        with mock.patch("os.fsync", side_effect=OSError(28, "No space left on device")):
            code, envelope, _ = call([str(report), "--out", str(self.outdir / "x.md")])
        self.assertEqual(code, 1)
        self.assertEqual(envelope["data"]["error"], f"cannot write {self.outdir / 'x.md'}: No space left on device")
        self.assertEqual(list(self.outdir.iterdir()), [])

    def test_describe_says_it_writes_one_new_file_and_nothing_inside_the_target(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        data = envelope["data"]
        self.assertEqual((data["name"], data["network"], data["writes_inside_target"]), ("render_report", False, False))
        self.assertEqual(data["synopsis"], ["render_report.py <report> --out <md>"])
        self.assertEqual(
            data["summary"], "Render an audit report to Markdown. The Markdown is a pure function of the JSON report."
        )
        self.assertEqual(
            data["writes"],
            "<md>, the path given by --out: a new file, never a replacement, and never inside the audited target. "
            "The report is only read.",
        )

    def test_it_runs_as_a_script_from_any_directory_and_prints_one_envelope(self) -> None:
        report = self.write_report()
        out = self.outdir / "script.md"
        done = subprocess.run(
            [sys.executable, str(TOOLS / "render_report.py"), str(report), "--out", str(out)],
            capture_output=True,
            text=True,
            cwd="/",
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        envelope = json.loads(done.stdout)
        self.assertEqual(list(envelope), ["tool", "version", "ok", "data", "warnings", "truncated"])
        self.assertEqual(out.read_text(encoding="utf-8"), rr.render(load(report)))
        self.assertEqual(done.stderr, f"render_report: wrote script.md ({envelope['data']['lines']} lines)\n")

    def test_the_markdown_does_not_depend_on_the_working_directory_or_the_report_path(self) -> None:
        first = self.write_report(name="one.json")
        elsewhere = self.root / "deeper"
        elsewhere.mkdir()
        second = elsewhere / "two.json"
        second.write_bytes(first.read_bytes())
        call([str(first), "--out", str(self.outdir / "a.md")])
        call([str(second), "--out", str(self.outdir / "b.md")])
        self.assertEqual((self.outdir / "a.md").read_bytes(), (self.outdir / "b.md").read_bytes())

    def test_a_report_too_big_to_read_is_exit_1(self) -> None:
        report = self.write_report()
        with mock.patch.object(vr, "MAX_REPORT_BYTES", 10):
            code, _, _ = call([str(report), "--out", str(self.outdir / "x.md")])
        self.assertEqual(code, 1)

    def test_help_prints_the_usage_and_what_each_argument_means(self) -> None:
        done = subprocess.run(
            [sys.executable, str(TOOLS / "render_report.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "COLUMNS": "200"},
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("usage: render_report.py [-h] --out OUT report", done.stdout)
        self.assertRegex(done.stdout, r"(?m)^  report +the audit report, draft or final, to render$")
        self.assertRegex(done.stdout, r"(?m)^  --out OUT +the Markdown file to create; it must not exist$")
        self.assertRegex(
            done.stdout,
            r"(?m)^Render an audit report to Markdown\. The Markdown is a pure function of the JSON report\.$",
        )


if __name__ == "__main__":
    unittest.main()
