# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Report rendering tests — schema v2, the JSON↔Markdown contract.

The load-bearing property: the Markdown artifact is a pure function of the JSON report dict. These
tests render from the in-memory dict and from a JSON round-trip of that same dict and require the
two to be byte-identical, so a saved report can always be re-rendered.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import support
from audit.report.md_writer import render_markdown_from_report

CHECK_KEYS = {"id", "pack", "title", "tier", "severity", "phase", "scored", "status", "verdict", "summary", "data"}


def _target() -> Path:
    """A throwaway repo with a runner (so CMD-01 has a surface) and a credential-shaped line."""
    tmp = Path(tempfile.mkdtemp(prefix="render-"))
    support.write(
        tmp,
        "package.json",
        json.dumps(
            {
                "name": "demo",
                "scripts": {"format": "prettier --write .", "lint": "eslint .", "test": "jest"},
            },
            indent=2,
        ),
    )
    support.write(tmp, "src/a.ts", "export const apiKey = 'sk-abcdefghijklmnopqrstuvwxyz01';\n")
    return tmp


class SchemaV2Tests(unittest.TestCase):
    def test_schema_version_and_check_shape(self):
        report = support.run_audit(_target())
        self.assertEqual(report["schema_version"], "2")
        self.assertTrue(report["checks"])
        for check in report["checks"]:
            self.assertEqual(set(check.keys()), CHECK_KEYS, check["id"])

    def test_detail_is_gone(self):
        report = support.run_audit(_target())
        for check in report["checks"]:
            self.assertNotIn("detail", check)

    def test_structured_payloads_are_present(self):
        report = support.run_audit(_target())
        by_id = {c["id"]: c for c in report["checks"]}
        self.assertEqual(by_id["CMD-01"]["data"]["kind"], "verb_surface")
        self.assertEqual(by_id["SEC-02"]["data"]["kind"], "credential_matrix")
        self.assertTrue(by_id["SEC-02"]["data"]["total"] >= 1)


class RenderFromJsonTests(unittest.TestCase):
    def test_markdown_is_a_pure_function_of_the_report_dict(self):
        report = support.run_audit(_target())
        in_memory = render_markdown_from_report(report)
        round_tripped = render_markdown_from_report(json.loads(json.dumps(report)))
        self.assertEqual(in_memory, round_tripped)

    def test_render_is_deterministic(self):
        report = support.run_audit(_target())
        self.assertEqual(render_markdown_from_report(report), render_markdown_from_report(report))

    def test_every_check_appears_in_the_appendix(self):
        report = support.run_audit(_target())
        markdown = render_markdown_from_report(report)
        for check in report["checks"]:
            self.assertIn(f"`{check['id']}`", markdown)

    def test_special_blocks_render_when_payloads_exist(self):
        report = support.run_audit(_target())
        markdown = render_markdown_from_report(report)
        self.assertIn("## Command surface", markdown)
        self.assertIn("## Credential-shaped lines", markdown)
        self.assertIn("## Missing secret-shape ignore rules", markdown)

    def test_unknown_ecosystem_omits_the_command_surface_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = support.run_audit(Path(tmp))
            markdown = render_markdown_from_report(report)
            self.assertNotIn("## Command surface", markdown)


def _section(markdown: str, heading: str) -> list[str]:
    """The lines of the `## heading` section, up to the next second-level heading."""
    lines = markdown.split("\n")
    start = lines.index(f"## {heading}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def _action_rows(markdown: str) -> list[list[str]]:
    rows = [line for line in _section(markdown, "Bottom line") if line.startswith("| ") and line[2].isdigit()]
    return [[cell.strip() for cell in row.strip("|").split(" | ")] for row in rows]


class BottomLineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = support.run_audit(_target())

    def test_it_is_the_first_section_and_terms_is_the_last(self):
        headings = [line for line in render_markdown_from_report(self.report).split("\n") if line.startswith("## ")]
        self.assertEqual(headings[:2], ["## Bottom line", "## Provenance"])
        self.assertEqual(headings[-1], "## Terms")

    def test_it_counts_the_blocker_findings(self):
        blockers = sum(1 for f in self.report["findings"] if f["severity"] == "BLOCKER")
        self.assertGreater(blockers, 0)
        noun = "finding" if blockers == 1 else "findings"
        section = "\n".join(_section(render_markdown_from_report(self.report), "Bottom line"))
        self.assertIn(f"- **{blockers} blocker {noun}.**", section)

    def test_the_first_actions_are_three_findings_in_severity_then_check_order(self):
        order = ["BLOCKER", "DEGRADER", "COSMETIC"]
        expected = sorted(self.report["findings"], key=lambda f: (order.index(f["severity"]), f["check"], f["id"]))[:3]
        rows = _action_rows(render_markdown_from_report(self.report))
        self.assertEqual([row[1] for row in rows], [f"`{f['check']}`" for f in expected])
        self.assertEqual([row[0] for row in rows], ["1", "2", "3"])

    def test_it_lists_five_unknown_checks_then_a_count(self):
        report = json.loads(json.dumps(self.report))
        for check in report["checks"]:
            check["verdict"] = "UNKNOWN"
        text = "\n".join(_section(render_markdown_from_report(report), "Bottom line"))
        self.assertIn(f"{len(report['checks'])} checks are UNKNOWN: ", text)
        self.assertIn(f" and {len(report['checks']) - 5} more.", text)

    def test_no_finding_means_no_first_actions(self):
        report = json.loads(json.dumps(self.report))
        report["findings"] = []
        report["summary"]["blockers"] = 0
        section = _section(render_markdown_from_report(report), "Bottom line")
        self.assertIn("**First actions:** none. The scan raised no finding.", section)
        self.assertEqual(_action_rows("\n".join(section)), [])

    def test_repository_text_in_an_action_is_escaped(self):
        report = json.loads(json.dumps(self.report))
        first = sorted(
            report["findings"],
            key=lambda f: (["BLOCKER", "DEGRADER", "COSMETIC"].index(f["severity"]), f["check"], f["id"]),
        )[0]
        first["statement"] = "An agent cannot X because src/__tests__/[a](b) <i>."
        row = _action_rows(render_markdown_from_report(report))[0]
        self.assertEqual(row[3], r"An agent cannot X because src/\_\_tests\_\_/\[a\](b) \<i\>.")

    def test_the_terms_name_every_verdict_and_severity(self):
        terms = _section(render_markdown_from_report(self.report), "Terms")
        for word in ("PASS", "PARTIAL", "FAIL", "UNKNOWN", "ATTEST", "BLOCKER", "DEGRADER", "COSMETIC"):
            self.assertTrue(any(line.startswith(f"| {word} |") for line in terms), word)


if __name__ == "__main__":
    unittest.main()
