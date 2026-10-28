# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""What AGT-01 and AGT-08 say, exactly, for each finding they can raise.

Both checks can raise several findings with no one path, and gave them one id (S2.6 item 10). Each now has an id of
its own, and these tests pin the id, the severity and every word a person reads.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

BODY = "# Rules\n\n" + "Always run the tests before every commit.\n" * 20


def audit(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        return support.run_audit(root)


def check_of(report: dict, check_id: str) -> dict:
    return next(c for c in report["checks"] if c["id"] == check_id)


def findings_of(report: dict, check_id: str) -> list[dict]:
    return sorted((f for f in report["findings"] if f["check"] == check_id), key=lambda f: f["id"])


def summary_of(finding: dict) -> tuple:
    return (finding["id"], finding["severity"], finding["verdict"], finding["statement"], finding["remediation"])


def evidence_of(finding: dict) -> list[tuple]:
    return [(e["path"], e["line"], e["note"]) for e in finding["evidence"]]


class Agt01Tests(unittest.TestCase):
    def test_no_instruction_file_is_one_finding_with_the_plain_id(self):
        report = audit({"README.md": "# x\n"})
        self.assertEqual((check_of(report, "AGT-01")["verdict"], check_of(report, "AGT-01")["summary"]), ("FAIL", ""))
        (finding,) = findings_of(report, "AGT-01")
        self.assertEqual(
            summary_of(finding),
            (
                "AGT-01",
                "BLOCKER",
                "FAIL",
                "An agent cannot learn the project's conventions because no agent-instruction file exists anywhere "
                "in the repository.",
                "Create AGENTS.md at the repository root using the framework template "
                "(codebase-agentic-readiness-framework templates/AGENTS.md).",
            ),
        )
        self.assertEqual(evidence_of(finding), [])

    def test_a_stub_names_why_and_counts_its_rule_lines(self):
        report = audit({"AGENTS.md": "# Rules\n\nBe good.\n\n> a quote\n\n| --- |\n"})
        (finding,) = findings_of(report, "AGT-01")
        self.assertEqual(
            summary_of(finding),
            (
                "AGT-01:AGENTS.md",
                "BLOCKER",
                "FAIL",
                "An agent cannot work to this project's conventions because AGENTS.md exists but is a stub — only 37 "
                "characters (minimum 400).",
                "Fill AGENTS.md from the framework template: verbs, boundaries, definition of done, prohibitions.",
            ),
        )
        self.assertEqual(evidence_of(finding), [("AGENTS.md", None, "1 rule lines")])

    def test_an_instruction_file_that_cannot_be_read_is_an_empty_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_bytes(b"abc\x00def")
            report = support.run_audit(root)
        (finding,) = findings_of(report, "AGT-01")
        self.assertIn("exists but is a stub — only 0 characters (minimum 400).", finding["statement"])
        self.assertEqual(evidence_of(finding), [("AGENTS.md", None, "0 rule lines")])

    def test_a_marker_in_a_long_file_is_a_stub_too(self):
        report = audit({"AGENTS.md": BODY + "\nTODO: more\n"})
        (finding,) = findings_of(report, "AGT-01")
        self.assertIn("exists but is a stub — contains the placeholder marker 'todo'.", finding["statement"])

    def test_a_file_that_differs_only_by_case_is_a_blocker_named_by_its_path(self):
        report = audit({"agents.md": BODY})
        (finding,) = [f for f in findings_of(report, "AGT-01") if f["severity"] == "BLOCKER"]
        self.assertEqual(
            summary_of(finding),
            (
                "AGT-01:agents.md",
                "BLOCKER",
                "FAIL",
                "An agent cannot rely on the instruction file being found because agents.md differs from AGENTS.md "
                "only by case, and case-sensitive filesystems will not find it.",
                "Rename to AGENTS.md exactly (Warp also requires ALL CAPS).",
            ),
        )
        self.assertEqual(evidence_of(finding), [("agents.md", None, None)])

    def test_several_files_that_differ_only_by_case_are_one_finding_named_by_the_first(self):
        # The variant tables know one such spelling today, so the helper is made to name two.
        from audit.rules.checks.agt import check_agt01
        from audit.rules.registry import REGISTRY_BY_ID
        from audit.scan import build_inventory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "AGENTS.md", BODY)
            with mock.patch(
                "audit.rules.checks.agt.V.mis_cased_canonical_candidates", return_value=["Agents.md", "agents.md"]
            ):
                outcome = check_agt01(
                    spec=REGISTRY_BY_ID["AGT-01"],
                    target=None,
                    inventory=build_inventory(root),
                    stack=None,
                    components=None,
                    session=None,
                )
        (finding,) = outcome.findings
        self.assertEqual(finding.id, "AGT-01:Agents.md")
        self.assertIn("because Agents.md, agents.md differs from AGENTS.md only by case", finding.statement)
        self.assertEqual([e.path for e in finding.evidence], ["Agents.md", "agents.md"])

    def test_content_only_in_vendor_files_is_one_finding_naming_the_files_and_who_reads_them(self):
        report = audit({"GEMINI.md": BODY, "AGENT.md": BODY})
        (finding,) = [f for f in findings_of(report, "AGT-01") if f["id"] == "AGT-01:vendor-only"]
        self.assertEqual(
            summary_of(finding),
            (
                "AGT-01:vendor-only",
                "DEGRADER",
                "PARTIAL",
                "An agent cannot share one set of project rules across harnesses because instruction content lives "
                "only in vendor-specific files (AGENT.md, GEMINI.md) that Devin, Roo Code, Zed reads.",
                "Add AGENTS.md as the canonical file and reduce vendor files to a one-line pointer, or a symlink "
                "where the harness supports it.",
            ),
        )
        self.assertEqual(evidence_of(finding), [])

    def test_with_only_vendor_files_that_no_alias_table_names_one_harness_reads_them(self):
        report = audit({"GEMINI.md": BODY})
        (finding,) = [f for f in findings_of(report, "AGT-01") if f["id"] == "AGT-01:vendor-only"]
        self.assertIn("(GEMINI.md) that one harness reads.", finding["statement"])

    def test_a_canonical_file_beside_vendor_files_raises_no_vendor_only_finding(self):
        report = audit({"AGENTS.md": BODY, "GEMINI.md": BODY})
        self.assertEqual([f["id"] for f in findings_of(report, "AGT-01")], [])

    def test_only_a_nested_canonical_file_is_a_nested_file_and_not_a_vendor_finding(self):
        report = audit({"sub/AGENTS.md": BODY})
        self.assertEqual(
            (check_of(report, "AGT-01")["verdict"], check_of(report, "AGT-01")["summary"]),
            ("PASS", "1 nested instruction file(s)"),
        )
        self.assertEqual(findings_of(report, "AGT-01"), [])

    def test_a_root_file_with_nested_files_counts_only_the_nested_ones(self):
        report = audit({"AGENTS.md": BODY, "a/AGENTS.md": BODY, "b/AGENTS.md": BODY})
        self.assertEqual(check_of(report, "AGT-01")["summary"], "2 nested instruction file(s)")

    def test_a_governed_root_file_alone_says_nothing(self):
        report = audit({"AGENTS.md": BODY})
        self.assertEqual((check_of(report, "AGT-01")["verdict"], check_of(report, "AGT-01")["summary"]), ("PASS", ""))

    def test_an_override_is_named_by_its_own_path_and_its_harness_when_it_is_at_the_root(self):
        report = audit({"AGENTS.md": BODY, "AGENTS.override.md": BODY})
        (finding,) = findings_of(report, "AGT-01")
        self.assertEqual(
            summary_of(finding),
            (
                "AGT-01:AGENTS.override.md",
                "DEGRADER",
                "PARTIAL",
                "An agent cannot rely on AGENTS.md in every directory because AGENTS.override.md is present for "
                "OpenAI Codex CLI and makes the AGENTS.md beside it inert.",
                "Delete the override, or make it a deliberate, documented superset.",
            ),
        )
        self.assertEqual(evidence_of(finding), [("AGENTS.override.md", None, None)])

    def test_two_overrides_are_two_findings(self):
        report = audit({"AGENTS.md": BODY, "AGENTS.override.md": BODY, "sub/AGENTS.override.md": BODY})
        self.assertEqual(
            [f["id"] for f in findings_of(report, "AGT-01")],
            ["AGT-01:AGENTS.override.md", "AGT-01:sub/AGENTS.override.md"],
        )
        nested = findings_of(report, "AGT-01")[1]
        self.assertIn("because sub/AGENTS.override.md is present for some harness and makes", nested["statement"])


def vendor_files(count: int) -> dict[str, str]:
    names = [
        ".augment-guidelines",
        ".clinerules",
        ".cursorrules",
        ".goosehints",
        ".roorules",
        ".voidrules",
        ".windsurfrules",
        "AmazonQ.md",
        "CLAUDE.md",
        "CRUSH.md",
        "GEMINI.md",
        "QWEN.md",
        "WARP.md",
        "replit.md",
    ]
    return {name: BODY for name in names[:count]}


class Agt08Tests(unittest.TestCase):
    def test_a_harness_that_no_file_reaches_is_one_cosmetic_finding_with_a_count_and_the_names(self):
        report = audit({"AGENTS.md": BODY})
        check = check_of(report, "AGT-08")
        self.assertEqual((check["verdict"], check["summary"]), ("PARTIAL", "19/27 harnesses reached"))
        self.assertEqual(
            check["data"],
            {
                "kind": "harness_matrix",
                "reached": 19,
                "total": 27,
                "reached_tools": [
                    "Augment Code",
                    "Bolt (StackBlitz)",
                    "Charm Crush",
                    "Cline",
                    "Cursor",
                    "Devin (Cognition)",
                    "Firebase Studio (ex-IDX)",
                    "GitHub Copilot / VS Code",
                    "Goose (Block)",
                    "JetBrains Junie",
                    "Jules (Google)",
                    "Kiro (AWS)",
                    "OpenAI Codex CLI",
                    "Roo Code",
                    "Trae",
                    "Warp",
                    "Windsurf / Devin Desktop",
                    "Zed",
                    "opencode",
                ],
                "unreached_tools": [
                    "Aider",
                    "Amazon Q Developer",
                    "Anthropic Claude Code",
                    "Continue",
                    "Google Gemini CLI",
                    "Qwen Code",
                    "Replit Agent",
                    "Void",
                ],
            },
        )
        (finding,) = findings_of(report, "AGT-08")
        self.assertEqual(
            summary_of(finding),
            (
                "AGT-08:harness-reach",
                "COSMETIC",
                "PARTIAL",
                "An agent cannot assume every harness on the team sees the project rules because 19 of 27 known "
                "harnesses reach an instruction file; Aider, Amazon Q Developer, Anthropic Claude Code, Continue, "
                "Google Gemini CLI, Qwen Code, Replit Agent, Void reach nothing.",
                "Either state the supported harnesses in AGENTS.md, or add the vendor pointer files for the "
                "harnesses in use.",
            ),
        )
        self.assertEqual(evidence_of(finding), [])

    def test_more_than_eight_unreached_harnesses_are_cut_with_an_ellipsis(self):
        report = audit({"GEMINI.md": BODY})
        check = check_of(report, "AGT-08")
        unreached = check["data"]["unreached_tools"]
        self.assertGreater(len(unreached), 8)
        finding = next(f for f in findings_of(report, "AGT-08") if f["id"] == "AGT-08:harness-reach")
        reached = check["data"]["reached"]
        self.assertTrue(
            finding["statement"].endswith(
                f"because {reached} of {reached + len(unreached)} known harnesses reach an instruction file; "
                + ", ".join(unreached[:8])
                + "… reach nothing."
            ),
            finding["statement"],
        )

    def test_with_no_instruction_file_at_all_the_reach_is_not_a_finding(self):
        report = audit({"README.md": "# x\n"})
        check = check_of(report, "AGT-08")
        self.assertEqual((check["verdict"], check["summary"]), ("PASS", "0/27 harnesses reached"))
        self.assertEqual(findings_of(report, "AGT-08"), [])

    def test_vendor_files_beside_the_canonical_one_are_a_fail_that_names_eight_and_cites_twelve(self):
        for count, listed, dots, evidence in (
            (3, ".augment-guidelines, .clinerules, .cursorrules", "", 3),
            (8, None, "", 8),
            (9, None, "…", 9),
            (13, None, "…", 12),
        ):
            with self.subTest(count=count):
                report = audit({"AGENTS.md": BODY, **vendor_files(count)})
                finding = next(f for f in findings_of(report, "AGT-08") if f["id"] == "AGT-08:vendor-files")
                shown = ", ".join(sorted(vendor_files(count))[:8])
                self.assertEqual(
                    finding["statement"],
                    f"An agent cannot know which instruction file is authoritative because {count} vendor-specific "
                    f"instruction files exist alongside the canonical one ({shown}{dots}).",
                )
                self.assertEqual((finding["severity"], finding["verdict"]), ("DEGRADER", "FAIL"))
                self.assertEqual(len(finding["evidence"]), evidence)
                self.assertEqual(
                    finding["remediation"],
                    "Keep AGENTS.md canonical; reduce each vendor file to a pointer at it, or delete it if the "
                    "harness reads AGENTS.md natively.",
                )
                self.assertEqual(check_of(report, "AGT-08")["verdict"], "FAIL")

    def test_vendor_files_without_a_canonical_one_still_draw_the_reach_finding(self):
        report = audit({"GEMINI.md": BODY})
        ids = [f["id"] for f in findings_of(report, "AGT-08")]
        self.assertEqual(ids, ["AGT-08:harness-reach", "AGT-08:vendor-files"])

    def test_a_file_that_shadows_another_is_named_by_the_pair(self):
        report = audit({"AGENTS.md": BODY, "AGENTS.override.md": BODY})
        finding = next(f for f in findings_of(report, "AGT-08") if f["id"].endswith("AGENTS.md") and ">" in f["id"])
        self.assertEqual(
            summary_of(finding),
            (
                "AGT-08:AGENTS.override.md>AGENTS.md",
                "DEGRADER",
                "PARTIAL",
                "An agent cannot be sure that both files are read because AGENTS.override.md shadows AGENTS.md for the "
                "harness that defines the pair, so only one of the two is ever loaded.",
                "Reconcile the two files, or delete the shadowed one — a file nobody reads still gets edited.",
            ),
        )
        self.assertEqual(evidence_of(finding), [("AGENTS.override.md", None, None), ("AGENTS.md", None, None)])

    def test_the_unreached_harnesses_are_cut_after_eight_and_not_before(self):
        from audit.rules.checks.agt import check_agt08
        from audit.rules.registry import REGISTRY_BY_ID
        from audit.scan import build_inventory

        for count, ellipsis in ((8, ""), (9, "…")):
            with self.subTest(count=count):
                missed = [f"h{n}" for n in range(count)]
                classified = {
                    "vendor_only": [],
                    "shadowed": [],
                    "harnesses_reached": ["r"],
                    "harnesses_missed": missed,
                }
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    support.write(root, "AGENTS.md", BODY)
                    with mock.patch("audit.rules.checks.agt.V.classify_present", return_value=classified):
                        outcome = check_agt08(
                            spec=REGISTRY_BY_ID["AGT-08"],
                            target=None,
                            inventory=build_inventory(root),
                            stack=None,
                            components=None,
                            session=None,
                        )
                (finding,) = outcome.findings
                self.assertTrue(
                    finding.statement.endswith(
                        f"because 1 of {count + 1} known harnesses reach an instruction file; "
                        f"{', '.join(missed[:8])}{ellipsis} reach nothing."
                    ),
                    finding.statement,
                )

    def test_a_verdict_is_pass_with_no_finding_fail_with_a_fail_and_partial_otherwise(self):
        self.assertEqual(check_of(audit({"README.md": "x\n"}), "AGT-08")["verdict"], "PASS")
        self.assertEqual(check_of(audit({"AGENTS.md": BODY}), "AGT-08")["verdict"], "PARTIAL")
        self.assertEqual(check_of(audit({"AGENTS.md": BODY, "CLAUDE.md": BODY}), "AGT-08")["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
