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
BR = rr.BR


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


def subsection(markdown: str, heading: str) -> str:
    """The text of the `### heading` block, up to the next heading of the second or third level."""
    found = markdown.split("\n")
    start = found.index(f"### {heading}")
    end = next((i for i in range(start + 1, len(found)) if found[i].startswith(("## ", "### "))), len(found))
    return "\n".join(found[start:end])


def cells(line: str) -> list[str]:
    """The cells of a table row, split at the pipes that are not escaped. A backslash escapes the next character."""
    body = line.strip()
    assert body.startswith("|") and body.endswith("|"), line
    body = body[1:-1]
    out: list[str] = []
    current = ""
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            current += body[index : index + 2]
            index += 2
            continue
        if char == "|":
            out.append(current.strip())
            current = ""
        else:
            current += char
        index += 1
    out.append(current.strip())
    return out


def table_blocks(text: str) -> list[list[list[str]]]:
    """Each table in `text` as its rows of cells, the header and the rule between the header and the body included."""
    blocks: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.split("\n") + [""]:
        if line.startswith("|"):
            current.append(cells(line))
        elif current:
            blocks.append(current)
            current = []
    return blocks


def rows_of(text: str) -> list[list[str]]:
    """The body rows of every table in `text`."""
    return [row for block in table_blocks(text) for row in block[2:]]


def table_dicts(text: str) -> list[dict[str, str]]:
    """The body rows of the first table in `text`, each as a dict from the header's cell to the row's cell."""
    found = table_blocks(text)
    if not found:
        return []
    header = found[0][0]
    return [dict(zip(header, body)) for body in found[0][2:]]


def attention(markdown: str, severity: str) -> list[dict[str, str]]:
    return table_dicts(subsection(markdown, f"{severity.capitalize()} checks"))


def listed_in(markdown: str, severity: str, check_id: str) -> bool:
    return any(r["Check"].startswith(f"`{check_id}`") for r in attention(markdown, severity))


def row(markdown: str, severity: str, check_id: str, finding_id: str | None = None) -> dict[str, str]:
    """The one row of a severity table for a check, or for one of its findings."""
    found = [
        r
        for r in attention(markdown, severity)
        if r["Check"].startswith(f"`{check_id}`") and (finding_id is None or f"finding `{finding_id}`" in r["Check"])
    ]
    assert len(found) == 1, f"{len(found)} rows for {check_id} {finding_id}"
    return found[0]


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
            "a\u202eb": "a{U+202E}b",
            "a\u200bb": "a{U+200B}b",
            "a\ufeffb": "a{U+FEFF}b",
            "a\u0085b": "a{U+0085}b",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=ascii(raw)):
                self.assertEqual(rr.clean(raw), expected)
        self.assertEqual(rr.clean("a\r\nb\rc\td\u2028e\u2029f"), "a\nb\nc\td\ne\nf")

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

    def test_a_table_can_align_its_columns(self) -> None:
        lines = rr.table(["A", "B", "C"], [["1", "2", "3"]], ["left", "center", "right"])
        self.assertEqual(lines[1], "|---|:---:|---:|")
        self.assertEqual(rr.table(["A"], [])[1], "|---|")

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


class ProvenanceTests(RenderCase):
    FIELDS = [
        "Target",
        "Commit",
        "Status",
        "Started",
        "Finalised",
        "Recipe",
        "Engine",
        "Framework revision",
        "Agent (self-reported)",
        "Probes",
        "Report schema",
    ]

    def provenance(self, report: dict[str, Any]) -> dict[str, str]:
        return {r[0]: r[1] for r in rows_of(section(self.render(report), "Provenance"))}

    def test_provenance_is_the_first_section_once_and_comes_after_the_title_and_the_banners(self) -> None:
        markdown = self.render(service())
        headings = [line for line in markdown.split("\n") if line.startswith("## ")]
        self.assertEqual(headings[0], "## Provenance")
        self.assertEqual(markdown.count("## Provenance"), 1)
        self.assertLess(markdown.index("# Agentic readiness audit"), markdown.index("> [!NOTE]"))
        self.assertLess(markdown.index("> [!NOTE]"), markdown.index("## Provenance"))
        self.assertLess(markdown.index("## Provenance"), markdown.index("## Readiness summary"))

    def test_the_table_is_a_field_and_value_table_with_one_row_for_each_fact_in_a_fixed_order(self) -> None:
        text = section(self.render(service()), "Provenance")
        self.assertEqual(table_dicts(text)[0].keys(), {"Field", "Value"})
        self.assertEqual([r[0] for r in rows_of(text)], self.FIELDS)

    def test_the_worked_example_says_what_was_audited_with_what_and_when(self) -> None:
        values = self.provenance(service())
        self.assertEqual(values["Target"], "`/work/example-service`")
        self.assertEqual(values["Commit"], "`deadbeefdead` on `main` — clean working tree")
        self.assertEqual(values["Status"], "final")
        self.assertEqual(values["Started"], "`2026-10-10T09:00:00+00:00`")
        self.assertEqual(values["Finalised"], "`2026-10-10T09:42:07+00:00`")
        self.assertEqual(values["Recipe"], "`brownfield-audit` 0.1.0, catalogue `0.1.0`")
        self.assertEqual(
            values["Engine"],
            "`python-agentic-audit` 0.1.0, ruleset `2026-09-28.13`, ruleset hash `a1b2a1b2a1b2a1b2`, "
            "scanned `2026-10-10T09:01:30+00:00`",
        )
        self.assertEqual(values["Framework revision"], "`cafecafecafe`")
        self.assertEqual(values["Agent (self-reported)"], "`claude-code` with `claude-sonnet-5-5`")
        self.assertEqual(values["Probes"], "none: no command of the target was run")
        self.assertEqual(values["Report schema"], "`0.1`")

    def test_a_dirty_working_tree_is_in_bold_and_an_unknown_one_says_nothing(self) -> None:
        report = service()
        target = report["provenance"]["target"]
        target["dirty"] = True
        self.assertEqual(self.provenance(report)["Commit"], "`deadbeefdead` on `main` — **dirty working tree**")
        target["dirty"] = None
        self.assertEqual(self.provenance(report)["Commit"], "`deadbeefdead` on `main`")
        target["branch"] = None
        self.assertEqual(self.provenance(report)["Commit"], "`deadbeefdead`")

    def test_a_target_with_no_commit_says_so(self) -> None:
        report = service()
        report["provenance"]["target"].update(git_sha=None, branch=None, dirty=None)
        self.assertEqual(self.provenance(report)["Commit"], "none recorded")

    def test_a_draft_has_no_finalised_time_and_an_eval_run_says_so_in_its_status(self) -> None:
        report = service()
        report["status"] = "draft"
        del report["provenance"]["finalised_at"]
        self.assertEqual(self.provenance(report)["Finalised"], "—")
        self.assertEqual(self.provenance(report)["Status"], "draft")
        report["run_context"]["eval_mode"] = True
        report["run_context"]["confirmation_policy"] = "defer-all"
        self.assertEqual(self.provenance(report)["Status"], "draft (evaluation run)")

    def test_an_engine_only_report_says_that_no_agent_took_part(self) -> None:
        report = service()
        report["provenance"]["agent"] = {"harness": "none", "model": "none"}
        self.assertEqual(self.provenance(report)["Agent (self-reported)"], "none: no agent took part")
        report["provenance"]["agent"] = {"harness": "none", "model": "claude-sonnet-5-5"}
        self.assertEqual(self.provenance(report)["Agent (self-reported)"], "`none` with `claude-sonnet-5-5`")
        report["provenance"]["agent"] = {"harness": "opencode", "model": "none"}
        self.assertEqual(self.provenance(report)["Agent (self-reported)"], "`opencode` with `none`")

    def test_probes_that_may_run_are_named_with_their_timeout(self) -> None:
        report = service()
        report["run_context"]["probes"] = {"allowed": ["test", "lint"], "timeout_s": 90}
        self.assertEqual(self.provenance(report)["Probes"], "`test`, `lint`, timeout 90 s")

    def test_a_report_with_no_engine_or_framework_revision_says_so(self) -> None:
        values = self.provenance(minimal())
        self.assertEqual(values["Engine"], "No engine report is part of this report.")
        self.assertEqual(values["Framework revision"], "—")

    def test_the_engine_row_names_only_what_the_report_records(self) -> None:
        report = service()
        engine = report["provenance"]["engine"]
        del engine["ruleset_revision"], engine["scanned_at"]
        self.assertEqual(
            self.provenance(report)["Engine"], "`python-agentic-audit` 0.1.0, ruleset hash `a1b2a1b2a1b2a1b2`"
        )
        engine["ruleset_revision"] = "2026-09-28.13"
        self.assertEqual(
            self.provenance(report)["Engine"],
            "`python-agentic-audit` 0.1.0, ruleset `2026-09-28.13`, ruleset hash `a1b2a1b2a1b2a1b2`",
        )


class BannerTests(RenderCase):
    NOTE = (
        "> [!NOTE]\n> This audit reports; it does not gate. A check that could not be settled is UNKNOWN: it earns no "
        "credit and is never shown as a pass."
    )

    def test_a_final_report_from_a_person_has_only_the_general_note(self) -> None:
        markdown = self.render(service())
        self.assertEqual(markdown.count(self.NOTE), 1)
        self.assertEqual(markdown.count("> [!"), 1)
        self.assertNotIn("**Draft.**", markdown)
        self.assertNotIn("Evaluation run", markdown)

    def test_an_eval_run_has_a_banner_that_names_the_policy(self) -> None:
        report = service()
        report["run_context"]["eval_mode"] = True
        report["run_context"]["confirmation_policy"] = "defer-all"
        markdown = self.render(report)
        self.assertIn(
            "> [!WARNING]\n> **Evaluation run.** This report was produced to measure the audit recipe, not to guide work "
            "on the repository. Its confirmation policy was `defer-all`, so no person decided on its findings, and it "
            "can never be final.\n",
            markdown,
        )
        self.assertLess(markdown.index("Evaluation run"), markdown.index("## Provenance"))

    def test_a_draft_has_a_banner_that_counts_the_findings_waiting_for_a_decision(self) -> None:
        report = service()
        report["status"] = "draft"
        banner = "> [!NOTE]\n> **Draft.** This report is not final and can still change. {} a decision.\n"
        self.assertIn(banner.format("0 findings await"), self.render(report))
        for finding_id in ("F-001", "F-002"):
            finding = finding_of(report, finding_id)
            finding["disposition"] = "pending"
            del finding["confirmed_via"]
        self.assertIn(banner.format("2 findings await"), self.render(report))
        finding_of(report, "F-001")["disposition"] = "rejected"
        finding_of(report, "F-001")["confirmed_via"] = "interactive"
        self.assertIn(banner.format("1 finding awaits"), self.render(report))

    def test_an_eval_draft_has_all_three_banners_with_the_warning_first_and_the_note_last(self) -> None:
        report = service()
        report["status"] = "draft"
        report["run_context"]["eval_mode"] = True
        report["run_context"]["confirmation_policy"] = "accept-all"
        markdown = self.render(report)
        self.assertEqual(markdown.count("> [!"), 3)
        self.assertLess(markdown.index("[!WARNING]"), markdown.index("**Draft.**"))
        self.assertLess(markdown.index("**Draft.**"), markdown.index(self.NOTE))

    def test_the_title_names_the_repository_and_nothing_else_is_on_its_line(self) -> None:
        self.assertEqual(self.render(service()).split("\n")[0], "# Agentic readiness audit: example-service")


class VerdictTableTests(RenderCase):
    def tables(self, report: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        text = section(self.render(report), "Checks by verdict and severity")
        first, second = text.split("\n\n| Severity")
        return table_dicts(first), table_dicts("| Severity" + second)

    def test_the_verdict_table_counts_every_check_and_says_what_each_verdict_earns(self) -> None:
        verdicts, _ = self.tables(service())
        self.assertEqual(
            [(v["Verdict"], v["Checks"], v["Credit"]) for v in verdicts],
            [
                ("PASS", "3", "1"),
                ("PARTIAL", "2", "0.5"),
                ("FAIL", "6", "0"),
                ("UNKNOWN", "1", "0"),
                ("NOT_APPLICABLE", "0", "outside the score"),
                ("**Total**", "**12**", ""),
            ],
        )
        for verdict in verdicts[:5]:
            self.assertEqual(verdict["Meaning"], rr.VERDICT_MEANINGS[verdict["Verdict"]])

    def test_the_credits_come_from_the_table_that_computes_the_score(self) -> None:
        with mock.patch.object(_summary, "HALF_CREDITS", {"PASS": 4, "PARTIAL": 3, "FAIL": 0, "UNKNOWN": 1}):
            verdicts, _ = self.tables(service())
        self.assertEqual([v["Credit"] for v in verdicts[:5]], ["2", "1.5", "0", "0.5", "outside the score"])

    def test_the_severity_table_counts_scored_checks_and_those_not_met(self) -> None:
        _, severities = self.tables(service())
        self.assertEqual(
            [(s["Severity"], s["Weight"], s["Scored checks"], s["Not met"]) for s in severities],
            [("BLOCKER", "3", "6", "4"), ("DEGRADER", "2", "6", "5"), ("COSMETIC", "1", "0", "0")],
        )
        for severity in severities:
            self.assertEqual(severity["Meaning"], rr.SEVERITY_MEANINGS[severity["Severity"]])

    def test_the_weights_come_from_the_shared_constants(self) -> None:
        with mock.patch.object(_summary, "WEIGHTS", {"BLOCKER": 9, "DEGRADER": 8, "COSMETIC": 7}):
            _, severities = self.tables(service())
        self.assertEqual([s["Weight"] for s in severities], ["9", "8", "7"])

    def test_a_check_that_is_not_scored_is_counted_in_the_verdicts_and_not_in_the_severities(self) -> None:
        report = service()
        check_of(report, "CMD-01")["scored"] = False
        verdicts, severities = self.tables(report)
        self.assertEqual(verdicts[2]["Checks"], "6")
        self.assertEqual((severities[0]["Scored checks"], severities[0]["Not met"]), ("5", "3"))

    def test_the_columns_that_hold_numbers_are_right_aligned(self) -> None:
        text = section(self.render(service()), "Checks by verdict and severity")
        self.assertIn("|---|---:|---:|---|", text.split("\n"))
        self.assertIn("|---|---:|---|---:|---:|", text.split("\n"))

    def test_a_report_with_no_check_has_zero_in_every_cell(self) -> None:
        report = service()
        report["checks"], report["findings"] = [], []
        verdicts, severities = self.tables(report)
        self.assertEqual([v["Checks"] for v in verdicts], ["0", "0", "0", "0", "0", "**0**"])
        self.assertEqual([(s["Scored checks"], s["Not met"]) for s in severities], [("0", "0")] * 3)


class AttentionTests(RenderCase):
    HEADER = ["Check", "Verdict", "What we found", "Evidence", "Fix", "Decision"]

    def test_there_is_a_table_for_each_severity_in_the_order_of_the_severities(self) -> None:
        markdown = self.render(service())
        self.assertEqual(
            [line for line in markdown.split("\n") if line.startswith("### ") and "checks" in line],
            ["### Blocker checks", "### Degrader checks", "### Cosmetic checks"],
        )
        text = subsection(markdown, "Blocker checks")
        self.assertEqual(list(table_dicts(text)[0]), self.HEADER)

    def test_the_blocker_table_has_a_row_for_each_finding_in_the_order_of_the_report(self) -> None:
        markdown = self.render(service())
        checks = [r["Check"] for r in attention(markdown, "BLOCKER")]
        self.assertEqual(
            [(c.split(BR)[0], c.split(BR)[1]) for c in checks],
            [
                ("`CMD-01` Seven verbs resolvable on one runner", "finding `F-001`"),
                ("`CMD-02` check composes the read-only verbs", "finding `F-002`"),
                ("`EXEC-01` Toolchain pinned / wrapper committed", "finding `F-003`"),
                ("`SEC-02` No key-shaped strings in tracked files", "finding `F-004`"),
                ("`SEC-02` No key-shaped strings in tracked files", "finding `F-005`"),
            ],
        )

    def test_a_row_shows_the_verdict_the_finding_the_evidence_the_fix_and_the_decision(self) -> None:
        found = row(self.render(service()), "BLOCKER", "CMD-01", "F-001")
        self.assertEqual(found["Verdict"], "**FAIL**")
        self.assertEqual(
            found["What we found"],
            "An agent cannot run the standardized command surface literally because 4 of 7 framework verbs are not "
            "defined on any runner (format:check, typecheck, check, security).",
        )
        self.assertEqual(found["Evidence"], "**tool** `package.json`")
        self.assertEqual(
            found["Fix"],
            "Define every verb as a script so an agent never has to invent a command."
            f"{BR}Playbook `define-command-surface` · Effort S · Touches `package.json`",
        )
        self.assertEqual(found["Decision"], "**Confirmed** (interactive)")

    def test_a_fix_with_no_playbook_effort_or_paths_is_its_summary_alone(self) -> None:
        found = row(self.render(service()), "BLOCKER", "SEC-02", "F-005")
        self.assertEqual(
            found["Fix"],
            "Remove the value from the file and its history, load it from the environment, and rotate the credential.",
        )
        report = service()
        finding_of(report, "F-001")["remediation"]["playbook"] = None
        self.assertNotIn("Playbook", row(self.render(report), "BLOCKER", "CMD-01", "F-001")["Fix"])

    def test_a_fix_names_what_it_depends_on(self) -> None:
        found = row(self.render(service()), "DEGRADER", "CI-04", "F-008")
        self.assertEqual(
            found["Fix"],
            "Make the workflow run the check verb once it exists."
            f"{BR}Playbook `add-ci-parity` · Effort M · Depends on `F-002` · Touches `.github/workflows/ci.yml`",
        )

    def test_a_later_finding_of_a_check_with_the_same_fix_says_so_and_does_not_repeat_it(self) -> None:
        report = service()
        for finding_id, scope in (("F-097", "a"), ("F-098", "b")):
            copied = copy.deepcopy(finding_of(report, "F-004"))
            copied.update(id=finding_id, key=f"SEC-02:{scope}")
            report["findings"].append(copied)
        markdown = self.render(report)
        first = row(markdown, "BLOCKER", "SEC-02", "F-004")["Fix"]
        self.assertIn("Remove the value from the file", first)
        self.assertEqual(row(markdown, "BLOCKER", "SEC-02", "F-097")["Fix"], "Same as `F-004`")
        self.assertEqual(row(markdown, "BLOCKER", "SEC-02", "F-098")["Fix"], "Same as `F-004`")
        self.assertIn("Remove the value from the file", row(markdown, "BLOCKER", "SEC-02", "F-005")["Fix"])

    def test_the_same_fix_on_another_check_is_not_collapsed(self) -> None:
        report = service()
        finding_of(report, "F-002")["remediation"] = copy.deepcopy(finding_of(report, "F-001")["remediation"])
        markdown = self.render(report)
        self.assertEqual(
            row(markdown, "BLOCKER", "CMD-02", "F-002")["Fix"], row(markdown, "BLOCKER", "CMD-01", "F-001")["Fix"]
        )

    def test_each_disposition_and_each_way_of_deciding_is_in_the_decision_cell(self) -> None:
        for disposition in ("confirmed", "rejected", "deferred", "edited"):
            for via in ("interactive", "batch", "policy"):
                with self.subTest(disposition=disposition, via=via):
                    report = service()
                    finding = finding_of(report, "F-001")
                    finding.update(disposition=disposition, confirmed_via=via)
                    found = row(self.render(report), "BLOCKER", "CMD-01", "F-001")
                    self.assertEqual(found["Decision"], f"**{disposition.capitalize()}** ({via})")

    def test_a_pending_finding_awaits_a_decision(self) -> None:
        report = service()
        finding = finding_of(report, "F-001")
        finding["disposition"] = "pending"
        del finding["confirmed_via"]
        self.assertEqual(row(self.render(report), "BLOCKER", "CMD-01", "F-001")["Decision"], "**Awaiting a decision**")

    def test_the_persons_note_is_on_a_second_line_of_the_decision_and_absent_when_there_is_none(self) -> None:
        markdown = self.render(service())
        self.assertEqual(
            row(markdown, "BLOCKER", "EXEC-01", "F-003")["Decision"],
            f"**Edited** (interactive){BR}Note: The owner pins Node 22 in .nvmrc and leaves the engines field alone.",
        )
        self.assertNotIn("Note", row(markdown, "BLOCKER", "CMD-01", "F-001")["Decision"])

    def test_the_decisions_are_explained_above_the_tables_in_the_renderers_own_words(self) -> None:
        text = section(self.render(service()), "Checks that need attention")
        for via, words in rr.DECIDED_BY.items():
            self.assertIn(f"- **{via}**: {words}", text.split("\n"))

    def test_a_finding_less_severe_than_its_check_is_in_its_checks_table_and_says_so(self) -> None:
        markdown = self.render(service())
        found = row(markdown, "DEGRADER", "AGT-08", "F-010")
        self.assertTrue(found["Check"].endswith("finding `F-010`, severity COSMETIC"))
        self.assertEqual(attention(markdown, "COSMETIC"), [])

    def test_an_agent_check_says_so_and_its_confidence(self) -> None:
        markdown = self.render(service())
        self.assertTrue(
            row(markdown, "DEGRADER", "AGT-11", "F-007")["Check"].endswith("finding `F-007` · agent, confidence medium")
        )
        report = service()
        del check_of(report, "AGT-11")["confidence"]
        self.assertTrue(row(self.render(report), "DEGRADER", "AGT-11", "F-007")["Check"].endswith(" · agent"))

    def test_a_check_with_no_finding_has_one_row_with_dashes_for_the_fix_and_the_decision(self) -> None:
        found = row(self.render(service()), "DEGRADER", "TST-02")
        self.assertEqual(found["Check"], "`TST-02` Suite status known")
        self.assertEqual(found["Verdict"], "**UNKNOWN**")
        self.assertEqual(found["What we found"], "probe not run: probes disabled (pass --run-gates)")
        self.assertEqual((found["Fix"], found["Decision"]), ("—", "—"))

    def test_an_empty_summary_is_a_dash(self) -> None:
        report = service()
        check_of(report, "TST-02")["summary"] = ""
        self.assertEqual(row(self.render(report), "DEGRADER", "TST-02")["What we found"], "—")

    def test_the_sentence_for_each_state_of_a_table(self) -> None:
        self.assertEqual(rr.attention_sentence("BLOCKER", 6, 4, 5), "4 of the 6 scored BLOCKER checks are not met.")
        self.assertEqual(rr.attention_sentence("BLOCKER", 1, 1, 1), "1 of the 1 scored BLOCKER check is not met.")
        self.assertEqual(
            rr.attention_sentence("DEGRADER", 3, 0, 0),
            "All 3 scored DEGRADER checks are met, and none was overridden, judged by the agent or the subject of a "
            "finding.",
        )
        self.assertEqual(
            rr.attention_sentence("DEGRADER", 1, 0, 0),
            "All 1 scored DEGRADER check is met, and none was overridden, judged by the agent or the subject of a "
            "finding.",
        )
        self.assertEqual(
            rr.attention_sentence("COSMETIC", 0, 0, 2),
            "There is no scored COSMETIC check; the table lists the checks that are not scored.",
        )
        self.assertEqual(rr.attention_sentence("COSMETIC", 0, 0, 0), "There is no COSMETIC check in this report.")

    def test_the_sentences_in_the_worked_example(self) -> None:
        markdown = self.render(service())
        self.assertIn("4 of the 6 scored BLOCKER checks are not met.", markdown.split("\n"))
        self.assertIn("5 of the 6 scored DEGRADER checks are not met.", markdown.split("\n"))
        self.assertIn("There is no COSMETIC check in this report.", subsection(markdown, "Cosmetic checks"))

    def test_a_table_for_a_severity_with_nothing_to_list_has_a_sentence_and_no_table(self) -> None:
        report = service()
        for check in report["checks"]:
            if check["severity"] == "BLOCKER":
                set_verdict(check, "PASS")
        report["findings"] = [f for f in report["findings"] if check_of(report, f["check"])["severity"] != "BLOCKER"]
        markdown = self.render(report)
        self.assertIn("- **0 blockers remaining**", markdown.split("\n"))
        text = subsection(markdown, "Blocker checks")
        self.assertIn(
            "All 6 scored BLOCKER checks are met, and none was overridden, judged by the agent or the subject of a finding.",
            text,
        )
        self.assertNotIn("|", text)

    def test_a_check_is_listed_when_it_is_not_met_overridden_judged_by_the_agent_or_has_a_finding(self) -> None:
        for verdict, listed in {
            "PARTIAL": True,
            "FAIL": True,
            "UNKNOWN": True,
            "PASS": False,
            "NOT_APPLICABLE": False,
        }.items():
            with self.subTest(verdict=verdict):
                report = service()
                report["findings"] = []
                set_verdict(check_of(report, "IDX-01"), verdict)
                self.assertEqual(listed_in(self.render(report), "BLOCKER", "IDX-01"), listed)
        report = service()
        check_of(report, "IDX-01")["method"] = "agent"
        del check_of(report, "IDX-01")["engine_verdict"]
        self.assertTrue(listed_in(self.render(report), "BLOCKER", "IDX-01"))
        report = service()
        finding = copy.deepcopy(finding_of(report, "F-001"))
        finding.update(id="F-099", key="IDX-01", check="IDX-01", disposition="rejected")
        report["findings"].append(finding)
        self.assertTrue(listed_in(self.render(report), "BLOCKER", "IDX-01"))
        report = service()
        check_of(report, "IDX-01")["engine_verdict"] = "FAIL"
        check_of(report, "IDX-01")["override_reason"] = "because"
        self.assertTrue(listed_in(self.render(report), "BLOCKER", "IDX-01"))

    def test_a_passing_check_that_a_tool_settled_has_no_row(self) -> None:
        markdown = self.render(service())
        self.assertFalse(listed_in(markdown, "BLOCKER", "IDX-01"))
        self.assertFalse(listed_in(markdown, "BLOCKER", "CI-01"))

    def test_a_check_that_is_not_scored_is_listed_and_says_so_and_is_left_out_of_the_sentence(self) -> None:
        report = service()
        check_of(report, "CMD-01")["scored"] = False
        markdown = self.render(report)
        self.assertEqual(row(markdown, "BLOCKER", "CMD-01", "F-001")["Verdict"], f"**FAIL**{BR}not scored")
        self.assertIn("3 of the 5 scored BLOCKER checks are not met.", markdown.split("\n"))

    def test_an_overridden_check_shows_the_engines_verdict_and_the_reason_on_its_first_row(self) -> None:
        found = row(self.render(service()), "DEGRADER", "TOOL-03", "F-009")
        self.assertEqual(found["Verdict"], f"**PASS**{BR}engine: PARTIAL")
        self.assertTrue(
            found["What we found"].endswith(
                f"{BR}**Overridden.** The engine's verdict was PARTIAL. Reason: tsconfig.json extends "
                "tsconfig.base.json, which sets strict: true; the engine reads only the leaf file."
            )
        )

    def test_the_override_is_said_once_for_a_check_with_two_findings_and_the_counter_evidence_only_there(self) -> None:
        report = service()
        second = copy.deepcopy(finding_of(report, "F-009"))
        second.update(id="F-099", key="TOOL-03:other", evidence=[])
        second["searches"] = []
        report["findings"].append(second)
        markdown = self.render(report)
        first, later = row(markdown, "DEGRADER", "TOOL-03", "F-009"), row(markdown, "DEGRADER", "TOOL-03", "F-099")
        self.assertIn("**Overridden.**", first["What we found"])
        self.assertNotIn("Overridden", later["What we found"])
        self.assertIn("**agent** `tsconfig.base.json:4`", first["Evidence"])
        self.assertEqual(
            later["Evidence"],
            "**agent** `tsconfig.base.json:4` (quote in Evidence in full)"
            + BR
            + "`tsconfig.json:2` (quote in Evidence in full)",
        )

    def test_only_the_agents_counter_evidence_joins_the_first_row_and_nothing_is_repeated(self) -> None:
        report = service()
        check = check_of(report, "TOOL-03")
        shared = check["evidence"][0]
        check["evidence"].append(
            {
                "kind": "file",
                "captured_by": "tool",
                "tool": "python-agentic-audit",
                "tool_version": "0.1.0",
                "path": "other.json",
            }
        )
        finding_of(report, "F-009")["evidence"].append(copy.deepcopy(shared))
        evidence = row(self.render(report), "DEGRADER", "TOOL-03", "F-009")["Evidence"]
        self.assertEqual(evidence.count("tsconfig.base.json:4"), 1)
        self.assertIn("`tsconfig.json:2`", evidence)
        self.assertNotIn("other.json", evidence)

    def test_the_agents_searches_for_an_override_join_the_first_row_once(self) -> None:
        report = service()
        check = check_of(report, "TOOL-03")
        shared = {"tool": "grep", "pattern": "strict", "scope": ".", "hits": 2}
        only_on_check = {"tool": "glob", "pattern": "tsconfig*.json", "scope": ".", "hits": 2}
        check["searches"] = [shared, only_on_check]
        finding_of(report, "F-009")["searches"] = [copy.deepcopy(shared)]
        evidence = row(self.render(report), "DEGRADER", "TOOL-03", "F-009")["Evidence"]
        self.assertEqual(evidence.count("`grep` for `strict`"), 1)
        self.assertEqual(evidence.count("`glob` for `tsconfig*.json`"), 1)

    def test_a_verdict_equal_to_the_engines_shows_no_engine_line(self) -> None:
        self.assertEqual(row(self.render(service()), "BLOCKER", "CMD-01", "F-001")["Verdict"], "**FAIL**")

    def test_findings_of_one_check_come_in_the_order_of_the_report(self) -> None:
        report = service()
        self.assertEqual(
            [r["Check"].split(BR)[1] for r in attention(self.render(report), "BLOCKER")][3:],
            ["finding `F-004`", "finding `F-005`"],
        )
        report["findings"].reverse()
        self.assertEqual(
            [r["Check"].split(BR)[1] for r in attention(self.render(report), "BLOCKER")][3:],
            ["finding `F-005`", "finding `F-004`"],
        )

    def test_every_finding_of_every_example_has_exactly_one_row_and_every_scored_unmet_check_is_listed(self) -> None:
        for path in [EXAMPLES / SERVICE, *drafts()]:
            with self.subTest(path=path.name):
                report = load(path)
                markdown = self.render(report)
                for finding in report["findings"]:
                    self.assertEqual(markdown.count(f"{BR}finding `{finding['id']}`"), 1, finding["id"])
                for check in _summary.scored_checks(report["checks"]):
                    if check["verdict"] != "PASS":
                        self.assertTrue(listed_in(markdown, check["severity"], check["id"]), check["id"])


class EvidenceCellTests(RenderCase):
    ENGINE = {"name": "python-agentic-audit", "version": "0.1.0"}

    def file_item(self, path: str, by: str = "tool", **extra: Any) -> dict[str, Any]:
        item: dict[str, Any] = {"kind": "file", "captured_by": by, "path": path}
        if by == "tool":
            item.update(tool="python-agentic-audit", tool_version="0.1.0")
        item.update(extra)
        return item

    def test_the_evidence_is_grouped_by_who_captured_it_with_the_tool_first(self) -> None:
        cell = rr.evidence_cell(
            [self.file_item("a.ts", "agent"), self.file_item("b.ts"), self.file_item("c.ts", lines="3-4", note="n")],
            [],
            self.ENGINE,
        )
        self.assertEqual(cell, f"**tool** `b.ts`{BR}`c.ts:3-4` (n){BR}**agent** `a.ts`")

    def test_a_tool_other_than_the_engine_is_named_and_the_engine_is_not(self) -> None:
        other = self.file_item("a.ts", tool="other-tool", tool_version="2.0")
        self.assertEqual(rr.evidence_cell([other], [], self.ENGINE), "**tool** (`other-tool 2.0`) `a.ts`")
        both = [other, self.file_item("b.ts", tool="another", tool_version="1")]
        self.assertEqual(
            rr.evidence_cell(both, [], self.ENGINE), f"**tool** (`another 1`, `other-tool 2.0`) `a.ts`{BR}`b.ts`"
        )
        self.assertEqual(rr.evidence_cell([self.file_item("a.ts")], [], self.ENGINE), "**tool** `a.ts`")
        self.assertEqual(
            rr.evidence_cell([self.file_item("a.ts")], [], None), "**tool** (`python-agentic-audit 0.1.0`) `a.ts`"
        )

    def test_an_agent_is_never_named_beyond_the_word_agent(self) -> None:
        self.assertEqual(rr.evidence_cell([self.file_item("a.ts", "agent")], [], None), "**agent** `a.ts`")

    def test_only_the_first_eight_items_of_a_group_are_shown_and_the_rest_are_counted(self) -> None:
        items = [self.file_item(f"f{n}.ts") for n in range(10)]
        lines = rr.evidence_cell(items, [], self.ENGINE).split(BR)
        self.assertEqual(len(lines), 9)
        self.assertEqual(lines[0], "**tool** `f0.ts`")
        self.assertEqual(lines[7], "`f7.ts`")
        self.assertEqual(lines[8], "and 2 more, in the JSON report")
        self.assertEqual(len(rr.evidence_cell(items[:8], [], self.ENGINE).split(BR)), 8)

    def test_each_group_is_capped_on_its_own(self) -> None:
        items = [self.file_item(f"t{n}.ts") for n in range(9)] + [self.file_item(f"a{n}.ts", "agent") for n in range(9)]
        lines = rr.evidence_cell(items, [], self.ENGINE).split(BR)
        self.assertEqual(lines.count("and 1 more, in the JSON report"), 2)

    def test_searches_are_listed_after_the_evidence_with_their_hits_and_capped_too(self) -> None:
        searches = [
            {"tool": "grep", "pattern": "never", "scope": "AGENTS.md", "hits": 0},
            {"tool": "glob", "pattern": "**/*.md", "scope": ".", "hits": 1},
            {"tool": "index", "pattern": "release", "scope": "src/", "hits": 3},
        ]
        lines = rr.evidence_cell([self.file_item("a.ts")], searches, self.ENGINE).split(BR)
        self.assertEqual(
            lines,
            [
                "**tool** `a.ts`",
                "**searches** `grep` for `never` in `AGENTS.md`: no hits",
                "`glob` for `**/*.md` in `.`: 1 hit",
                "`index` for `release` in `src/`: 3 hits",
            ],
        )
        many = [{"tool": "grep", "pattern": f"p{n}", "scope": ".", "hits": 1} for n in range(10)]
        self.assertEqual(rr.evidence_cell([], many, None).split(BR)[-1], "and 2 more, in the JSON report")

    def test_a_quote_and_command_output_are_pointed_to_and_not_printed_in_the_cell(self) -> None:
        quoted = self.file_item("a.ts", "agent", quote="the secret words", note="n")
        command = {
            "kind": "command",
            "captured_by": "tool",
            "tool": "python-agentic-audit",
            "tool_version": "0.1.0",
            "command": "make test",
            "exit_code": 1,
            "output_tail": "FAILED",
            "timed_out": False,
            "duration_s": 12.5,
            "redactions": 2,
        }
        cell = rr.evidence_cell([quoted, command], [], self.ENGINE)
        self.assertNotIn("the secret words", cell)
        self.assertNotIn("FAILED", cell)
        self.assertIn("`a.ts` (n; quote in Evidence in full)", cell)
        self.assertIn("command `make test` (exit 1; 12.5 s; 2 redactions; output in Evidence in full)", cell)

    def test_a_command_that_timed_out_and_one_that_exited_with_zero(self) -> None:
        base = {"kind": "command", "captured_by": "agent", "command": "make lint"}
        cell = rr.evidence_cell(
            [{**base, "exit_code": 0, "duration_s": 3.0}, {**base, "exit_code": None, "timed_out": True}], [], None
        )
        self.assertEqual(cell, f"**agent** command `make lint` (exit 0; 3 s){BR}command `make lint` (timed out)")

    def test_an_index_query_shows_the_query_the_tool_and_the_result(self) -> None:
        item = {
            "kind": "index_query",
            "captured_by": "agent",
            "index_tool": "search_graph",
            "query": "scripts",
            "result_summary": "7 scripts",
        }
        self.assertEqual(rr.evidence_cell([item], [], None), "**agent** `scripts` through `search_graph` (7 scripts)")
        del item["result_summary"]
        self.assertEqual(rr.evidence_cell([item], [], None), "**agent** `scripts` through `search_graph`")

    def test_nothing_gives_an_empty_cell(self) -> None:
        self.assertEqual(rr.evidence_cell([], [], None), "")

    def test_a_row_shows_the_findings_evidence_and_falls_back_to_the_checks(self) -> None:
        markdown = self.render(service())
        self.assertEqual(
            row(markdown, "BLOCKER", "SEC-02", "F-004")["Evidence"],
            "**tool** `src/config/constants.ts:12` (credential-shaped string)",
        )
        report = service()
        finding = finding_of(report, "F-004")
        finding["evidence"], finding["searches"] = [], []
        found = row(self.render(report), "BLOCKER", "SEC-02", "F-004")
        self.assertEqual(found["Evidence"].count(BR), 2)

    def test_a_path_with_backticks_and_a_scope_with_a_pipe_stay_in_their_cells(self) -> None:
        report = service()
        finding_of(report, "F-004")["evidence"][0]["path"] = "src/`rm -rf`.ts"
        finding_of(report, "F-007")["searches"] = [{"tool": "grep", "pattern": "a`b", "scope": "x``y|z", "hits": 1}]
        markdown = self.render(report)
        self.assertIn("**tool** ``src/`rm -rf`.ts:12`` (credential-shaped string)", markdown)
        self.assertIn("`grep` for ``a`b`` in ```x``y\\|z```: 1 hit", markdown)


class NoEvidenceTests(RenderCase):
    def evidence(self, report: dict[str, Any], severity: str, check_id: str, finding_id: str | None = None) -> str:
        return row(self.render(report), severity, check_id, finding_id)["Evidence"]

    def test_a_failed_or_unknown_check_with_no_evidence_and_no_searches_says_so(self) -> None:
        markdown = self.render(service())
        self.assertEqual(row(markdown, "DEGRADER", "TST-02")["Evidence"], rr.NO_EVIDENCE)
        self.assertEqual(row(markdown, "DEGRADER", "CI-04", "F-008")["Evidence"], rr.NO_EVIDENCE)

    def test_the_sentence_has_exactly_the_words_the_decision_gave(self) -> None:
        self.assertEqual(rr.NO_EVIDENCE, "We did not find any evidence.")

    def test_evidence_on_the_check_takes_the_sentence_away(self) -> None:
        report = service()
        check_of(report, "TST-02")["evidence"] = [{"kind": "file", "captured_by": "agent", "path": "Makefile"}]
        self.assertEqual(self.evidence(report, "DEGRADER", "TST-02"), "**agent** `Makefile`")

    def test_a_search_on_the_check_takes_the_sentence_away_and_is_listed(self) -> None:
        report = service()
        check_of(report, "CI-04")["searches"] = [
            {"tool": "grep", "pattern": "make check", "scope": ".github/", "hits": 0}
        ]
        self.assertEqual(
            self.evidence(report, "DEGRADER", "CI-04", "F-008"),
            "**searches** `grep` for `make check` in `.github/`: no hits",
        )

    def test_evidence_only_on_a_finding_also_takes_the_sentence_away(self) -> None:
        report = service()
        finding_of(report, "F-008")["evidence"] = [{"kind": "file", "captured_by": "agent", "path": ".github/ci.yml"}]
        self.assertEqual(self.evidence(report, "DEGRADER", "CI-04", "F-008"), "**agent** `.github/ci.yml`")

    def test_a_second_finding_with_nothing_of_its_own_is_not_told_that_nothing_was_found(self) -> None:
        report = service()
        second = copy.deepcopy(finding_of(report, "F-008"))
        second.update(id="F-099", key="CI-04:other")
        report["findings"].append(second)
        finding_of(report, "F-008")["evidence"] = [{"kind": "file", "captured_by": "agent", "path": "x.yml"}]
        self.assertEqual(self.evidence(report, "DEGRADER", "CI-04", "F-099"), "—")

    def test_a_search_only_on_a_finding_also_takes_the_sentence_away(self) -> None:
        report = service()
        finding_of(report, "F-008")["searches"] = [{"tool": "glob", "pattern": "*.yml", "scope": ".github/", "hits": 1}]
        self.assertNotEqual(self.evidence(report, "DEGRADER", "CI-04", "F-008"), rr.NO_EVIDENCE)

    def test_other_verdicts_never_get_the_sentence(self) -> None:
        for verdict in ("PASS", "PARTIAL", "NOT_APPLICABLE"):
            with self.subTest(verdict=verdict):
                report = service()
                set_verdict(check_of(report, "CI-04"), verdict)
                finding_of(report, "F-008")["disposition"] = "rejected"
                self.assertEqual(self.evidence(report, "DEGRADER", "CI-04", "F-008"), "—")

    def test_the_sentence_applies_to_an_automated_check_too(self) -> None:
        self.assertEqual(check_of(service(), "TST-02")["method"], "automated")
        self.assertEqual(self.evidence(service(), "DEGRADER", "TST-02"), rr.NO_EVIDENCE)


class EvidenceInFullTests(RenderCase):
    def test_a_quote_is_in_a_fenced_block_under_its_bullet_and_under_the_check_that_cites_it(self) -> None:
        text = subsection(self.render(service()), "AGT-11: Instructions are specific and not inferable")
        self.assertIn(
            "- `AGENTS.md:14-16` · captured by agent\n  ```text\n  Run `npm test` to run the tests. "
            "Run `npm run lint` to lint the code.\n  ```",
            text,
        )

    def test_the_section_holds_only_the_checks_that_cite_a_quote_or_output_in_severity_order(self) -> None:
        markdown = self.render(service())
        headings = [h for h in section(markdown, "Evidence in full").split("\n") if h.startswith("### ")]
        self.assertEqual(
            headings,
            ["### AGT-11: Instructions are specific and not inferable", "### TOOL-03: Type checker configured"],
        )

    def test_the_section_is_left_out_when_nothing_is_quoted(self) -> None:
        for path in drafts():
            with self.subTest(path=path.name):
                self.assertNotIn("## Evidence in full", self.render(load(path)))

    def test_it_comes_after_the_overrides_and_before_the_coverage(self) -> None:
        markdown = self.render(service())
        self.assertLess(markdown.index("## Overrides of the engine's verdicts"), markdown.index("## Evidence in full"))
        self.assertLess(markdown.index("## Evidence in full"), markdown.index("## Coverage"))

    def test_an_evidence_item_that_a_check_and_its_finding_share_is_printed_once(self) -> None:
        text = section(self.render(service()), "Evidence in full")
        self.assertEqual(text.count("`AGENTS.md:14-16` · captured by agent"), 1)

    def test_an_item_with_no_quote_is_not_repeated_here(self) -> None:
        text = section(self.render(service()), "Evidence in full")
        self.assertNotIn("tsconfig.json — strict is not set", text)
        self.assertNotIn("package.json", text)

    def test_a_quote_that_holds_backticks_gets_a_longer_fence_and_the_blocks_stay_balanced(self) -> None:
        report = service()
        check_of(report, "AGT-11")["evidence"][0]["quote"] = "before\n```\nafter\n````\nmore"
        finding_of(report, "F-007")["evidence"] = []
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
        text = subsection(self.render(report), "TST-02: Suite status known")
        self.assertIn(
            "- Command `make test` (exit 1, 12.5 s, 2 redactions) · captured by tool `python-agentic-audit` 0.1.0\n"
            "  ````text\n  FAILED (failures=2)\n  ```\n  last line\n  ````",
            text,
        )

    def test_a_note_on_a_quoted_item_follows_its_path_in_the_full_list(self) -> None:
        report = service()
        check_of(report, "AGT-11")["evidence"][0]["note"] = "a note"
        finding_of(report, "F-007")["evidence"] = []
        text = subsection(self.render(report), "AGT-11: Instructions are specific and not inferable")
        self.assertIn("- `AGENTS.md:14-16` — a note · captured by agent", text.split("\n"))

    def test_a_command_that_timed_out_says_so_in_the_full_list(self) -> None:
        report = service()
        check_of(report, "TST-02")["evidence"].append(
            {
                "kind": "command",
                "captured_by": "agent",
                "command": "make test",
                "exit_code": None,
                "output_tail": "partial output",
                "timed_out": True,
            }
        )
        text = subsection(self.render(report), "TST-02: Suite status known")
        self.assertIn("- Command `make test` (timed out) · captured by agent", text.split("\n"))
        self.assertIn("  partial output", text.split("\n"))

    def test_an_index_query_that_carries_a_quote_is_in_the_full_list_with_its_query_tool_and_result(self) -> None:
        report = service()
        check_of(report, "TST-02")["evidence"].append(
            {
                "kind": "index_query",
                "captured_by": "agent",
                "index_tool": "search_graph",
                "query": "scripts",
                "result_summary": "7 scripts",
                "quote": "the result",
            }
        )
        text = subsection(self.render(report), "TST-02: Suite status known")
        self.assertIn("- Index query `scripts` through `search_graph`: 7 scripts · captured by agent", text.split("\n"))
        self.assertIn("  the result", text.split("\n"))

    def test_an_item_that_the_check_and_its_finding_hold_with_the_keys_in_another_order_is_printed_once(self) -> None:
        report = service()
        finding_of(report, "F-007")["evidence"] = [reordered(item) for item in finding_of(report, "F-007")["evidence"]]
        text = section(self.render(report), "Evidence in full")
        self.assertEqual(text.count("`AGENTS.md:14-16` · captured by agent"), 1)

    def test_the_table_row_points_to_the_quote_and_does_not_hold_it(self) -> None:
        found = row(self.render(service()), "DEGRADER", "AGT-11", "F-007")
        self.assertIn("`AGENTS.md:14-16` (quote in Evidence in full)", found["Evidence"])
        self.assertNotIn("npm test", found["Evidence"])

    def test_every_fenced_block_of_every_example_is_closed(self) -> None:
        for path in [EXAMPLES / SERVICE, EXAMPLES / "minimal.json", *drafts()]:
            with self.subTest(path=path.name):
                list(scan(self.render(load(path))))


class OverrideTests(RenderCase):
    def test_an_override_is_in_the_table_next_to_the_engines_verdict_with_its_reason(self) -> None:
        text = section(self.render(service()), "Overrides of the engine's verdicts")
        self.assertEqual(
            table_dicts(text),
            [
                {
                    "Check": "`TOOL-03`",
                    "Engine's verdict": "PARTIAL",
                    "This report's verdict": "PASS",
                    "Reason": "tsconfig.json extends tsconfig.base.json, which sets strict: true; the engine reads only the leaf file.",
                }
            ],
        )

    def test_with_no_override_the_section_says_so(self) -> None:
        for report in (minimal(), load(next(iter(drafts())))):
            text = section(self.render(report), "Overrides of the engine's verdicts")
            self.assertIn("No engine verdict was overridden.", text)
            self.assertNotIn("| Check |", text)

    def test_the_section_points_to_where_the_counter_evidence_is(self) -> None:
        text = section(self.render(service()), "Overrides of the engine's verdicts")
        self.assertIn("the row of the check above shows both", text)
        self.assertIn("Evidence column or under Evidence in full", text)
        self.assertNotIn(
            "the row of the check above", section(self.render(minimal()), "Overrides of the engine's verdicts")
        )

    def test_a_verdict_equal_to_the_engines_is_not_an_override(self) -> None:
        markdown = self.render(service())
        self.assertEqual(len(table_dicts(section(markdown, "Overrides of the engine's verdicts"))), 1)
        self.assertEqual(markdown.count("**Overridden.**"), 1)


class AppendixTests(RenderCase):
    HEADER = ["Check", "Title", "Severity", "Method", "Scored", "Verdict", "Engine", "Summary"]

    def test_the_families_are_in_the_order_they_first_appear_and_each_has_its_own_table(self) -> None:
        text = section(self.render(service()), "Appendix — all checks")
        self.assertEqual(
            [h for h in text.split("\n") if h.startswith("### ")],
            ["### IDX", "### AGT", "### CMD", "### TOOL", "### CI", "### EXEC", "### SEC", "### TST"],
        )

    def test_every_check_of_every_example_has_a_row_in_report_order(self) -> None:
        for path in [EXAMPLES / SERVICE, EXAMPLES / "minimal.json", *drafts()]:
            with self.subTest(path=path.name):
                report = load(path)
                text = section(self.render(report), "Appendix — all checks")
                found = [r[0] for r in rows_of(text)]
                order: dict[str, int] = {}
                for check in report["checks"]:
                    order.setdefault(check["id"].split("-")[0], len(order))
                expected = sorted(report["checks"], key=lambda c: order[c["id"].split("-")[0]])
                self.assertEqual(found, [f"`{c['id']}`" for c in expected])
        self.assertEqual(len(rows_of(section(self.render(load(drafts()[0])), "Appendix — all checks"))), 69)

    def test_a_row_gives_the_severity_method_scoring_both_verdicts_and_the_summary(self) -> None:
        text = section(self.render(service()), "Appendix — all checks")
        found = {r[0]: r for r in rows_of(text)}
        self.assertEqual(
            found["`TOOL-03`"],
            [
                "`TOOL-03`",
                "Type checker configured",
                "DEGRADER",
                "automated",
                "yes",
                "PASS",
                "PARTIAL",
                "type checker configured and strict: tsconfig.base.json",
            ],
        )
        self.assertEqual(found["`AGT-11`"][3:7], ["agent", "yes", "PARTIAL", "—"])

    def test_a_check_that_is_not_scored_says_no_and_an_empty_summary_is_a_dash(self) -> None:
        report = service()
        check_of(report, "IDX-01")["scored"] = False
        check_of(report, "IDX-01")["summary"] = ""
        found = {r[0]: r for r in rows_of(section(self.render(report), "Appendix — all checks"))}
        self.assertEqual((found["`IDX-01`"][4], found["`IDX-01`"][7]), ("no", "—"))

    def test_a_report_with_no_check_says_so(self) -> None:
        report = service()
        report["checks"], report["findings"] = [], []
        self.assertIn("No check is recorded.", section(self.render(report), "Appendix — all checks").split("\n"))

    def test_the_appendix_says_that_the_engines_payloads_are_in_the_json(self) -> None:
        text = section(self.render(service()), "Appendix — all checks")
        self.assertIn("All 12 checks, grouped by family.", text)
        self.assertIn("The engine's structured payloads, such as the verb matrix, are in the JSON report.", text)


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

    def test_a_component_with_no_declarer_or_manifest_has_dashes(self) -> None:
        report = service()
        report["components"][0].update(declared=False, declared_by=None, manifest=None, agents_md="unknown")
        text = section(self.render(report), "Stack and components")
        self.assertIn("| (root) | `.` | no | — | — | unknown |", text.split("\n"))

    def test_the_run_context_states_the_policy_the_index_and_the_exposure_acknowledgement_and_not_the_probes(
        self,
    ) -> None:
        text = section(self.render(service()), "Run context")
        self.assertIn("| Confirmation policy | `interactive` |", text)
        self.assertIn("| Provider exposure acknowledged | yes: the model provider receives what the agent reads", text)
        self.assertIn("| Code index | `mcp` `codebase-memory-mcp` |", text)
        self.assertIn("| Stack profile | `typescript-node`, shipped, confirmed by the user |", text)
        self.assertNotIn("Probes", text)
        report = service()
        report["run_context"]["stack_profile"]["confirmed_by_user"] = False
        report["run_context"]["index"] = {"kind": "cli", "name": "gitnexus", "notes": "installed by the user"}
        text = section(self.render(report), "Run context")
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
                "## Provenance",
                "## Readiness summary",
                "## Checks by verdict and severity",
                "## Checks that need attention",
                "## Overrides of the engine's verdicts",
                "## Evidence in full",
                "## Coverage",
                "## Stack and components",
                "## Run context",
                "## Appendix — all checks",
            ],
        )
        self.assertTrue(markdown.startswith("# Agentic readiness audit: example-service\n"))
        self.assertTrue(markdown.endswith("The JSON report is the record.\n"))
        self.assertFalse(markdown.endswith("\n\n"))
        self.assertNotIn("\n\n\n", markdown)
        self.assertEqual(markdown.count("\n# "), 0)


HOSTILE = {
    "image": "![x](https://evil.example/p.png?q=1)",
    "html": "<img src=x onerror=alert(1)>",
    "link": "[click](javascript:alert(1))",
    "heading": "# Injected heading",
    "table": "| a | b |",
    "fence": "```\nbreak out",
    "bidi": "name\u202egnp.exe",
    "control": "bell\x07 escape\x1b[31m",
    "emphasis": "**bold** __bold__ _it_",
    "blockquote": "> a quotation",
    "linebreak": "one<br>two",
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
                    unspanned = re.sub(r"(`+).+?\1", "", line).replace(BR, "")
                    self.assertIsNone(re.search(r"(?<!\\)!\[", unspanned), line)
                    self.assertIsNone(re.search(r"(?<!\\)\]\(", unspanned), line)
                    self.assertIsNone(re.search(r"(?<!\\)<", unspanned), line)
                    self.assertFalse(
                        line.startswith(("> ", ">")) and not line.startswith(("> [!", "> **", "> This audit reports")),
                        line,
                    )

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

    def test_a_pipe_inside_a_code_span_in_a_table_cell_does_not_add_a_column(self) -> None:
        report = service()
        report["components"][0]["path"] = "a|b"
        report["components"][0]["manifest"] = "c|d"
        text = section(self.render(report), "Stack and components")
        found = next(line for line in text.split("\n") if line.startswith("| (root)"))
        self.assertEqual(unescaped_pipes(found), 7)

    def test_a_line_break_in_text_is_not_a_line_break_in_a_cell(self) -> None:
        report = service()
        finding_of(report, "F-001")["statement"] = "An agent cannot x because one<br>two"
        found = row(self.render(report), "BLOCKER", "CMD-01", "F-001")
        self.assertEqual(found["What we found"], "An agent cannot x because one\\<br>two")
        self.assertIsNone(re.search(r"(?<!\\)<br>", found["What we found"]))


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
                self.assertEqual(len(rows_of(section(markdown, "Appendix — all checks"))), 69)
                for finding in report["findings"]:
                    self.assertEqual(markdown.count(f"{BR}finding `{finding['id']}`"), 1)
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
