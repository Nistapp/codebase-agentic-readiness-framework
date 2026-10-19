# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The report validator: each rule of schema/SCHEMA.md, "Rules beyond the schema", has a report that passes it and
one that breaks it, and the tool honours the contract (envelope, exit codes, bounded output, nothing written).

Reports are built by changing the worked example, which is final, holds an override and has tool-captured and
agent-captured evidence. A test names the rule it breaks and asserts that no other rule fires, so a rule that
misfires shows up as a failure in someone else's test. Credential-shaped strings are built at run time, so that
the secrets scan finds nothing in this file. Standard library only.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Sequence
from unittest import mock

import _paths
import _common
import _summary
import validate_report as vr

TOOLS = _paths.TOOLS
EXAMPLES = TOOLS.parent / "schema" / "examples"
WORKED = next(EXAMPLES.glob("example-service.audit-report.*.json"))
FAKE_SHA = "deadbeef" * 5


def base() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(WORKED.read_text(encoding="utf-8"))
    return document


def draft() -> dict[str, Any]:
    report = base()
    report["status"] = "draft"
    del report["provenance"]["finalised_at"]
    return report


def check_of(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(c for c in report["checks"] if c["id"] == check_id)
    return found


def finding_of(report: dict[str, Any], finding_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(f for f in report["findings"] if f["id"] == finding_id)
    return found


def rule_number(error: str) -> int:
    """The rule an error names, or 0 for a schema error."""
    found = re.match(r"rule (\d+):", error)
    return int(found.group(1)) if found else 0


def rules_in(outcome: vr.Outcome) -> set[int]:
    """The rule numbers of the errors, with 0 for a schema error.

    Rule 10 is left out. A test that changes a verdict leaves the stored summary stale on purpose, and Rule10Tests
    covers the summary on its own.
    """
    return {rule_number(error) for error in outcome.errors} - {10}


def tool_evidence(path: str) -> dict[str, Any]:
    return {"kind": "file", "captured_by": "tool", "tool": "engine", "tool_version": "0.1.0", "path": path}


class ExamplesTests(unittest.TestCase):
    def test_every_example_passes_every_rule(self) -> None:
        examples = [EXAMPLES / "minimal.json", WORKED, *sorted(EXAMPLES.rglob("*.audit-draft.*.json"))]
        self.assertGreaterEqual(len(examples), 5)
        for path in examples:
            with self.subTest(example=path.name):
                outcome = vr.validate_document(json.loads(path.read_text(encoding="utf-8")))
                self.assertEqual((outcome.errors, outcome.warnings), ([], []))

    def test_the_raw_engine_reports_fail_at_the_schema_stage(self) -> None:
        raw = sorted(EXAMPLES.rglob("*.engine-report.*.json"))
        self.assertTrue(raw)
        outcome = vr.validate_document(json.loads(raw[0].read_text(encoding="utf-8")))
        self.assertEqual(outcome.stage, "schema")
        self.assertTrue(outcome.errors)


class SchemaStageTests(unittest.TestCase):
    def test_a_schema_error_is_returned_alone_and_the_rules_do_not_run(self) -> None:
        report = base()
        check_of(report, "AGT-07")["verdict"] = "MAYBE"
        report["checks"][1]["id"] = report["checks"][0]["id"]  # a rule-1 defect as well
        outcome = vr.validate_document(report)
        self.assertEqual(outcome.stage, "schema")
        self.assertEqual(rules_in(outcome), {0})
        self.assertTrue(any("/checks/1/verdict" in error for error in outcome.errors))

    def test_a_document_that_is_not_an_object_is_a_schema_error(self) -> None:
        outcome = vr.validate_document([])
        self.assertEqual(outcome.errors, ["schema: /: expected object, got array"])

    def test_a_report_with_a_version_this_tool_does_not_know_is_refused(self) -> None:
        report = base()
        report["schema_version"] = "0.2"
        self.assertTrue(any("/schema_version" in error for error in vr.validate_document(report).errors))

    def test_the_schema_errors_are_capped(self) -> None:
        report = base()
        report["checks"] = [{} for _ in range(600)]
        outcome = vr.validate_document(report)
        self.assertEqual(len(outcome.errors), vr.MAX_SCHEMA_ERRORS + 1)
        self.assertIn("stopped after 500 errors", outcome.errors[-1])


class Rule1Tests(unittest.TestCase):
    def test_a_report_with_a_chain_and_a_diamond_of_dependencies_has_no_cycle(self) -> None:
        report = base()
        finding_of(report, "F-007")["remediation"]["depends_on"] = ["F-001", "F-002"]
        self.assertEqual(vr.validate_document(report).errors, [])

    def test_a_repeated_check_id_is_an_error(self) -> None:
        report = base()
        report["checks"][1]["id"] = "IDX-01"
        outcome = vr.validate_document(report)
        self.assertTrue(
            any(e.startswith("rule 1: /checks/1/id:") and "already used at /checks/0" in e for e in outcome.errors)
        )

    def test_a_repeated_finding_id_is_an_error(self) -> None:
        report = base()
        finding_of(report, "F-002")["id"] = "F-001"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {1})
        self.assertTrue(any("/findings/1/id" in e and "already used at /findings/0" in e for e in outcome.errors))

    def test_a_repeated_finding_key_is_an_error(self) -> None:
        report = base()
        finding_of(report, "F-005")["key"] = finding_of(report, "F-004")["key"]
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {1})
        self.assertTrue(any("/findings/4/key" in e and "already used at /findings/3" in e for e in outcome.errors))

    def test_a_finding_on_a_check_the_report_lacks_is_an_error(self) -> None:
        report = base()
        finding_of(report, "F-001")["check"] = "XXX-99"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {1})
        self.assertTrue(any("XXX-99 is not a check in this report" in e for e in outcome.errors))

    def test_a_key_must_start_with_its_whole_check_id(self) -> None:
        report = base()
        finding_of(report, "F-006")["key"] = "AGT-070"  # starts with "AGT-07" as text, and names another check
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {1})
        self.assertTrue(any("does not start with its check, AGT-07" in e for e in outcome.errors))

    def test_a_dependency_on_a_finding_the_report_lacks_is_an_error(self) -> None:
        report = base()
        finding_of(report, "F-002")["remediation"]["depends_on"] = ["F-099"]
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {1})
        self.assertTrue(any("depends_on/0" in e and "F-099" in e for e in outcome.errors))

    def test_a_dependency_cycle_is_an_error_and_is_named(self) -> None:
        report = base()
        finding_of(report, "F-001")["remediation"]["depends_on"] = ["F-002"]
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {1})
        self.assertTrue(any("cycle: F-001 -> F-002 -> F-001" in e for e in outcome.errors))

    def test_a_finding_that_depends_on_itself_is_a_cycle(self) -> None:
        report = base()
        finding_of(report, "F-001")["remediation"]["depends_on"] = ["F-001"]
        outcome = vr.validate_document(report)
        self.assertTrue(any("cycle: F-001 -> F-001" in e for e in outcome.errors))

    def test_a_long_dependency_chain_does_not_exhaust_the_stack(self) -> None:
        findings = [{"id": f"F-{n:04d}", "remediation": {"depends_on": [f"F-{n + 1:04d}"]}} for n in range(5000)]
        findings.append({"id": "F-5000", "remediation": {}})
        self.assertEqual(list(vr.dependency_cycles(findings)), [])
        findings[-1]["remediation"] = {"depends_on": ["F-0000"]}
        self.assertEqual(len(list(vr.dependency_cycles(findings))), 1)


class Rule2Tests(unittest.TestCase):
    def test_a_check_the_catalogue_lacks_is_an_error(self) -> None:
        report = base()
        report["checks"][0]["id"] = "ZZZ-99"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {2})
        self.assertTrue(any("ZZZ-99 is not in the catalogue" in e for e in outcome.errors))

    def test_each_field_that_differs_from_the_catalogue_is_an_error(self) -> None:
        changes: dict[str, Any] = {
            "title": "Something else",
            "phase": 2,
            "severity": "DEGRADER",
            "scored": False,
            "method": "agent",
        }
        for name, value in changes.items():
            with self.subTest(field=name):
                report = base()
                report["checks"][0][name] = value
                outcome = vr.validate_document(report)
                self.assertTrue(any(e.startswith(f"rule 2: /checks/0/{name}:") for e in outcome.errors), outcome.errors)

    def test_a_playbook_the_catalogue_does_not_name_is_an_error(self) -> None:
        report = base()
        finding_of(report, "F-001")["remediation"]["playbook"] = "not-a-playbook"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {2})

    def test_a_playbook_the_catalogue_names_needs_no_file_and_a_null_playbook_is_fine(self) -> None:
        report = base()
        finding_of(report, "F-001")["remediation"]["playbook"] = "register-index"
        finding_of(report, "F-002")["remediation"]["playbook"] = None
        self.assertEqual(vr.validate_document(report).errors, [])

    def test_a_catalogue_of_another_major_or_minor_version_is_a_warning_only(self) -> None:
        for version, warned in (("0.2.0", False), ("0.2.7", False), ("0.1.0", True), ("0.3.0", True), ("1.2.0", True)):
            with self.subTest(version=version):
                report = base()
                report["provenance"]["catalogue_version"] = version
                outcome = vr.validate_document(report)
                self.assertEqual(outcome.errors, [])
                self.assertEqual(len(outcome.warnings), 1 if warned else 0)


class Rule3Tests(unittest.TestCase):
    def evidence_errors(self, evidence: dict[str, Any]) -> list[str]:
        report = base()
        report["checks"][0]["evidence"].append(evidence)  # IDX-01: automated, no findings
        outcome = vr.validate_document(report)
        self.assertLessEqual(rules_in(outcome), {3})
        return outcome.errors

    def test_file_evidence_needs_a_path(self) -> None:
        errors = self.evidence_errors({"kind": "file", "captured_by": "agent"})
        self.assertEqual(len(errors), 1)
        self.assertIn("file evidence needs 'path'", errors[0])

    def test_command_evidence_needs_a_command(self) -> None:
        errors = self.evidence_errors({"kind": "command", "captured_by": "agent"})
        self.assertIn("command evidence needs 'command'", errors[0])
        self.assertEqual(self.evidence_errors({"kind": "command", "captured_by": "agent", "command": "make test"}), [])

    def test_index_evidence_needs_a_tool_and_a_query(self) -> None:
        errors = self.evidence_errors({"kind": "index_query", "captured_by": "agent"})
        self.assertEqual(len(errors), 2)
        done = {"kind": "index_query", "captured_by": "agent", "index_tool": "search_graph", "query": "x"}
        self.assertEqual(self.evidence_errors(done), [])

    def test_lines_need_a_path(self) -> None:
        errors = self.evidence_errors({"kind": "command", "captured_by": "agent", "command": "ls", "lines": "1-2"})
        self.assertEqual(len(errors), 1)
        self.assertIn("'lines' is given without a 'path'", errors[0])

    def test_a_path_that_leaves_the_target_is_an_error(self) -> None:
        for path in ("/etc/hosts", "../outside", "a/../../outside", "..", "C:\\Users\\x", "c:/x", "src\\..\\..\\x"):
            with self.subTest(path=path):
                errors = self.evidence_errors({"kind": "file", "captured_by": "agent", "path": path})
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("/path:", errors[0])

    def test_a_path_inside_the_target_is_accepted(self) -> None:
        for path in (
            "a/../b",
            "./src/x.py",
            "src/dir with space/x.py",
            "src\\win\\x.py",
            ".github/workflows/ci.yml",
            "..hidden",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.evidence_errors({"kind": "file", "captured_by": "agent", "path": path}), [])

    def test_findings_evidence_is_held_to_the_same_rule(self) -> None:
        report = base()
        finding_of(report, "F-001")["evidence"].append({"kind": "file", "captured_by": "agent", "path": "/etc/hosts"})
        outcome = vr.validate_document(report)
        self.assertTrue(any(e.startswith("rule 3: /findings/0/evidence/") for e in outcome.errors))


class Rule4Tests(unittest.TestCase):
    def test_evidence_captured_by_a_tool_names_the_tool_and_its_version(self) -> None:
        for name in ("tool", "tool_version"):
            with self.subTest(missing=name):
                report = base()
                del check_of(report, "AGT-07")["evidence"][0][name]
                outcome = vr.validate_document(report)
                self.assertEqual(rules_in(outcome), {4})
                self.assertIn(f"must name {name!r}", outcome.errors[0])

    def test_evidence_captured_by_the_agent_names_neither(self) -> None:
        for name in ("tool", "tool_version"):
            with self.subTest(named=name):
                report = base()
                check_of(report, "AGT-11")["evidence"][0][name] = "engine"
                outcome = vr.validate_document(report)
                self.assertEqual(rules_in(outcome), {4})
                self.assertIn(f"must not name '{name}'", outcome.errors[0])


class Rule5Tests(unittest.TestCase):
    def test_an_agent_check_with_no_evidence_may_fail_and_say_nothing_more(self) -> None:
        check = check_of(base(), "CI-04")
        self.assertEqual(
            (check["method"], check["verdict"], check["evidence"], check["searches"]), ("agent", "FAIL", [], [])
        )
        self.assertEqual(vr.validate_document(base()).errors, [])

    def test_an_automated_check_needs_no_evidence_of_its_own(self) -> None:
        check = check_of(base(), "IDX-01")
        self.assertEqual((check["method"], check["evidence"]), ("automated", []))
        self.assertEqual(vr.validate_document(base()).errors, [])

    def test_an_agent_check_has_no_engine_verdict(self) -> None:
        report = base()
        check_of(report, "AGT-11")["engine_verdict"] = "PARTIAL"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {5})
        self.assertIn("its method must be 'automated'", outcome.errors[0])

    def test_an_engine_verdict_needs_the_engine_in_the_provenance(self) -> None:
        report = base()
        del report["provenance"]["engine"]
        outcome = vr.validate_document(report)
        self.assertEqual(
            outcome.errors, ["rule 5: /provenance: a check has an engine_verdict, so provenance.engine must be present"]
        )

    def test_an_agent_check_that_passes_or_is_partial_needs_evidence(self) -> None:
        report = base()
        check_of(report, "AGT-11")["evidence"] = []  # PARTIAL
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {5})
        self.assertIn("agent check with the verdict PARTIAL and has no evidence", outcome.errors[0])
        for verdict in ("PASS", "PARTIAL"):
            with self.subTest(verdict=verdict):
                report = draft()
                check = check_of(report, "CI-04")
                check["verdict"] = verdict
                for finding in report["findings"]:
                    if finding["check"] == "CI-04":
                        finding["disposition"] = "rejected" if verdict == "PASS" else finding["disposition"]
                self.assertIn(5, rules_in(vr.validate_document(report)))


class Rule6Tests(unittest.TestCase):
    def test_an_override_needs_a_reason(self) -> None:
        report = base()
        del check_of(report, "TOOL-03")["override_reason"]
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {6})
        self.assertIn("gives no override_reason", outcome.errors[0])

    def test_an_override_needs_evidence_the_agent_captured(self) -> None:
        report = base()
        for item in check_of(report, "TOOL-03")["evidence"]:
            item.update({"captured_by": "tool", "tool": "engine", "tool_version": "0.1.0"})
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {6})
        self.assertIn("no evidence that the agent captured", outcome.errors[0])

    def test_a_reason_without_an_override_is_an_error(self) -> None:
        report = base()
        check_of(report, "TOOL-03")["verdict"] = "PARTIAL"  # now the engine's own verdict
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {6})
        self.assertIn("its verdict matches the engine's", outcome.errors[0])

    def test_a_reason_on_a_check_the_engine_did_not_run_is_an_error(self) -> None:
        report = base()
        check_of(report, "AGT-11")["override_reason"] = "because"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {6})
        self.assertIn("no engine_verdict to override", outcome.errors[0])

    def test_a_checked_override_is_accepted(self) -> None:
        check = check_of(base(), "TOOL-03")
        self.assertNotEqual(check["verdict"], check["engine_verdict"])
        self.assertEqual(vr.validate_document(base()).errors, [])


class Rule7Tests(unittest.TestCase):
    def test_a_finding_may_be_less_severe_than_its_check_and_not_more(self) -> None:
        report = draft()
        self.assertEqual(finding_of(report, "F-010")["severity"], "COSMETIC")  # its check is a DEGRADER
        self.assertEqual(vr.validate_document(report).errors, [])
        finding_of(report, "F-010")["severity"] = "BLOCKER"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {7})
        self.assertIn("BLOCKER is higher than AGT-08's DEGRADER", outcome.errors[0])

    def test_a_finding_on_a_passing_check_must_be_rejected(self) -> None:
        report = base()
        self.assertEqual(finding_of(report, "F-009")["disposition"], "rejected")  # TOOL-03 passes
        finding_of(report, "F-009")["disposition"] = "confirmed"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {7})
        self.assertIn("TOOL-03 is PASS, so its finding must be rejected", outcome.errors[0])

    def test_a_finding_on_a_check_that_does_not_apply_must_be_rejected(self) -> None:
        report = draft()
        check_of(report, "AGT-08")["verdict"] = "NOT_APPLICABLE"
        outcome = vr.validate_document(report)
        self.assertTrue(any("AGT-08 is NOT_APPLICABLE" in e for e in outcome.errors))

    def test_a_decided_finding_says_how_it_was_decided(self) -> None:
        report = base()
        del finding_of(report, "F-006")["confirmed_via"]
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {7})
        self.assertIn("a confirmed finding needs confirmed_via", outcome.errors[0])

    def test_a_pending_finding_has_no_way_of_being_decided(self) -> None:
        report = draft()
        finding_of(report, "F-010")["disposition"] = "pending"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {7})
        self.assertIn("a pending finding has no confirmed_via", outcome.errors[0])
        del finding_of(report, "F-010")["confirmed_via"]
        self.assertEqual(vr.validate_document(report).errors, [])


class Rule8Tests(unittest.TestCase):
    def test_a_final_report_needs_the_time_it_was_finalised(self) -> None:
        report = base()
        del report["provenance"]["finalised_at"]
        outcome = vr.validate_document(report)
        self.assertEqual(outcome.errors, ["rule 8: /provenance: a final report needs finalised_at"])

    def test_a_final_report_is_never_an_eval_run(self) -> None:
        report = base()
        report["run_context"]["eval_mode"] = True
        report["run_context"]["confirmation_policy"] = "defer-all"
        outcome = vr.validate_document(report)
        self.assertEqual(outcome.errors, ["rule 8: /run_context/eval_mode: an eval-mode report is never final"])

    def test_a_final_report_has_no_pending_finding(self) -> None:
        report = base()
        finding = finding_of(report, "F-010")
        finding["disposition"] = "pending"
        del finding["confirmed_via"]
        outcome = vr.validate_document(report)
        self.assertEqual(outcome.errors, ["rule 8: /findings/9/disposition: a final report has no pending finding"])

    def test_every_blocker_finding_of_a_final_report_was_confirmed_interactively(self) -> None:
        for finding_id in ("F-001", "F-005"):  # F-005 is a rejected BLOCKER; it counts too
            with self.subTest(finding=finding_id):
                report = base()
                finding_of(report, finding_id)["confirmed_via"] = "batch"
                outcome = vr.validate_document(report)
                self.assertEqual(rules_in(outcome), {8})
                self.assertIn("must be confirmed_via 'interactive'", outcome.errors[0])

    def test_a_draft_may_have_pending_findings_and_no_finalised_at(self) -> None:
        report = draft()
        finding = finding_of(report, "F-001")
        finding["disposition"] = "pending"
        del finding["confirmed_via"]
        self.assertEqual(vr.validate_document(report).errors, [])

    def test_a_draft_may_be_an_eval_run(self) -> None:
        report = draft()
        report["run_context"].update({"eval_mode": True, "confirmation_policy": "defer-all"})
        self.assertEqual(vr.validate_document(report).errors, [])


class Rule9Tests(unittest.TestCase):
    def test_accept_all_is_for_eval_runs_only(self) -> None:
        report = draft()
        report["run_context"]["confirmation_policy"] = "accept-all"
        outcome = vr.validate_document(report)
        self.assertEqual(
            outcome.errors, ["rule 9: /run_context/confirmation_policy: 'accept-all' is allowed only in eval mode"]
        )

    def test_an_eval_run_is_never_interactive(self) -> None:
        report = draft()
        report["run_context"]["eval_mode"] = True
        outcome = vr.validate_document(report)
        self.assertEqual(
            outcome.errors, ["rule 9: /run_context/confirmation_policy: an eval-mode run cannot be 'interactive'"]
        )

    def test_policy_confirmation_needs_a_policy_that_confirms(self) -> None:
        report = base()
        finding_of(report, "F-006")["confirmed_via"] = "policy"
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {9})
        self.assertIn("/findings/5/confirmed_via", outcome.errors[0])

    def test_an_eval_run_that_accepts_everything_is_accepted(self) -> None:
        report = draft()
        report["run_context"].update({"eval_mode": True, "confirmation_policy": "accept-all"})
        for finding in report["findings"]:
            finding["confirmed_via"] = "policy"
        self.assertEqual(vr.validate_document(report).errors, [])


class Rule10Tests(unittest.TestCase):
    def only_rule_10(self, report: dict[str, Any]) -> list[str]:
        errors = vr.validate_document(report).errors
        self.assertTrue(all(e.startswith("rule 10:") for e in errors), errors)
        return errors

    def test_a_summary_that_matches_its_checks_passes(self) -> None:
        self.assertEqual(vr.validate_document(base()).errors, [])
        self.assertEqual(_summary.compute_summary(base()), base()["summary"])

    def test_each_number_that_differs_is_named_with_the_value_each_side_holds(self) -> None:
        changes: dict[str, tuple[str, Callable[[dict[str, Any]], object]]] = {
            "phase1_score": ("/summary/phase1_score", lambda s: s.update(phase1_score=0.9)),
            "scored_checks": ("/summary/scored_checks", lambda s: s.update(scored_checks=11)),
            "total": ("/summary/blockers_remaining/total", lambda s: s["blockers_remaining"].update(total=3)),
            "fail": ("/summary/blockers_remaining/fail", lambda s: s["blockers_remaining"].update(fail=3)),
            "partial": ("/summary/blockers_remaining/partial", lambda s: s["blockers_remaining"].update(partial=1)),
            "unknown": ("/summary/blockers_remaining/unknown", lambda s: s["blockers_remaining"].update(unknown=1)),
            "unknown_scored_checks": ("/summary/unknown_scored_checks", lambda s: s.update(unknown_scored_checks=0)),
            "unconfirmed": ("/summary/unconfirmed_agent_findings", lambda s: s.update(unconfirmed_agent_findings=2)),
        }
        for name, (pointer, change) in changes.items():
            with self.subTest(field=name):
                report = base()
                change(report["summary"])
                errors = self.only_rule_10(report)
                self.assertEqual(len(errors), 1, errors)
                self.assertTrue(errors[0].startswith(f"rule 10: {pointer}: the report says "), errors[0])
        report = base()
        report["summary"]["phase1_score"] = 0.9
        self.assertEqual(
            vr.validate_document(report).errors,
            ["rule 10: /summary/phase1_score: the report says 0.9 and its checks and findings give 0.3333"],
        )

    def test_a_verdict_changed_without_the_summary_is_found(self) -> None:
        report = base()
        check_of(report, "CMD-01")["verdict"] = "PASS"
        finding_of(report, "F-001")["disposition"] = "rejected"
        errors = vr.validate_document(report).errors
        self.assertTrue(any(e.startswith("rule 10: /summary/blockers_remaining/fail") for e in errors), errors)

    def test_a_summary_recomputed_after_the_change_passes(self) -> None:
        report = base()
        check_of(report, "CMD-01")["verdict"] = "PASS"
        finding_of(report, "F-001")["disposition"] = "rejected"
        report["summary"] = _summary.compute_summary(report)
        self.assertFalse([e for e in vr.validate_document(report).errors if e.startswith("rule 10:")])
        self.assertEqual(report["summary"]["blockers_remaining"]["fail"], 3)

    def test_the_summary_errors_come_after_rule_9_and_before_rule_11(self) -> None:
        report = base()
        report["summary"]["scored_checks"] = 1
        report["run_context"].update({"eval_mode": True, "confirmation_policy": "defer-all"})
        check_of(report, "AGT-11")["evidence"][0]["quote"] = "pass" + "word" + " = " + "hunter" + "2"
        report["status"] = "draft"
        del report["provenance"]["finalised_at"]
        report["run_context"]["confirmation_policy"] = "interactive"  # rule 9
        numbers = [rule_number(error) for error in vr.validate_document(report).errors]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(set(numbers), {9, 10, 11})


class Rule11Tests(unittest.TestCase):
    """One string for each of the engine's six credential patterns, built here so no scan finds it in the file."""

    def credentials(self) -> list[str]:
        return [
            "pass" + "word" + " = " + "hunter" + "2",
            "sk" + "-" + "a1B2c3D4" * 3,
            "gh" + "p_" + "A1b2C3d4E5f6G7h8I9",
            "AK" + "IA" + "ABCDEFGHIJKLMNOP",
            "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
            "Bear" + "er " + "abcdefghij.klmnopqrst",
        ]

    def test_each_of_the_engines_patterns_is_applied(self) -> None:
        patterns = vr.redaction_patterns()
        self.assertEqual(len(patterns), 6)
        for number, text in enumerate(self.credentials(), start=1):
            with self.subTest(pattern=number):
                self.assertIsNotNone(patterns[number - 1].search(text))

    def test_a_credential_in_a_quote_is_an_error_and_is_never_repeated(self) -> None:
        for number, text in enumerate(self.credentials(), start=1):
            with self.subTest(pattern=number):
                report = base()
                check_of(report, "AGT-11")["evidence"][0]["quote"] = f"the value is {text} here"
                outcome = vr.validate_document(report)
                self.assertEqual(rules_in(outcome), {11})
                self.assertEqual(len(outcome.errors), 1)
                self.assertIn(
                    f"/checks/3/evidence/0/quote: it looks like a credential (the engine's redaction pattern {number})",
                    outcome.errors[0],
                )
                self.assertNotIn(text.split()[-1], " ".join(outcome.errors))

    def test_a_credential_in_the_tail_of_a_command_is_an_error(self) -> None:
        report = base()
        report["checks"][0]["evidence"].append(
            {
                "kind": "command",
                "captured_by": "tool",
                "tool": "engine",
                "tool_version": "0.1.0",
                "command": "make test",
                "exit_code": 1,
                "output_tail": "ok\n" + self.credentials()[1] + "\n",
            }
        )
        outcome = vr.validate_document(report)
        self.assertEqual(rules_in(outcome), {11})
        self.assertIn("/checks/0/evidence/0/output_tail", outcome.errors[0])

    def test_ordinary_text_and_an_already_redacted_tail_pass(self) -> None:
        report = base()
        check_of(report, "AGT-11")["evidence"][0]["quote"] = "Rotate the token every 90 days and never log it."
        report["checks"][0]["evidence"].append(
            {
                "kind": "command",
                "captured_by": "tool",
                "tool": "engine",
                "tool_version": "0.1.0",
                "command": "make test",
                "exit_code": 0,
                "output_tail": "connecting with [REDACTED] and [REDACTED]\n",
                "redactions": 2,
            }
        )
        self.assertEqual(vr.validate_document(report).errors, [])


def git_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    return environment


def run_git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, env=git_environment())
    return done.stdout.strip()


def write_files(root: Path, paths: Sequence[str]) -> None:
    for path in paths:
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text("x\n", encoding="utf-8")


class Rule12Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / "target"
        self.target.mkdir()

    def commit(self, paths: Sequence[str]) -> str:
        write_files(self.target, paths)
        run_git(self.target, "init", "-q")
        run_git(self.target, "add", "-A")
        run_git(self.target, "commit", "-q", "-m", "x")
        return run_git(self.target, "rev-parse", "HEAD")

    def report_for(self, sha: str | None) -> dict[str, Any]:
        report = base()
        report["provenance"]["target"]["git_sha"] = sha
        return report

    def cited(self) -> list[str]:
        return list(vr.cited_paths(base()))

    def test_every_cited_file_in_the_commit_gives_no_warning(self) -> None:
        sha = self.commit(self.cited())
        outcome = vr.validate_document(self.report_for(sha), target=self.target)
        self.assertEqual((outcome.errors, outcome.warnings), ([], []))

    def test_a_cited_file_that_is_not_in_the_commit_is_a_warning_at_its_place(self) -> None:
        paths = self.cited()
        sha = self.commit(paths[1:])
        outcome = vr.validate_document(self.report_for(sha), target=self.target)
        self.assertEqual(outcome.errors, [])
        self.assertEqual(len(outcome.warnings), 1)
        self.assertRegex(
            outcome.warnings[0],
            rf"^/(checks|findings)/\d+/evidence/\d+: the file {re.escape(paths[0])} is not in the target at {sha[:12]}$",
        )

    def test_a_file_that_exists_only_in_the_working_tree_is_not_in_the_commit(self) -> None:
        paths = self.cited()
        sha = self.commit(paths[1:])
        write_files(self.target, [paths[0]])
        outcome = vr.validate_document(self.report_for(sha), target=self.target)
        self.assertEqual(len(outcome.warnings), 1)

    def test_a_target_without_the_commit_gives_one_warning_and_no_more(self) -> None:
        self.commit(self.cited())
        outcome = vr.validate_document(self.report_for(FAKE_SHA), target=self.target)
        self.assertEqual(outcome.errors, [])
        self.assertEqual(
            outcome.warnings, [f"the cited files were not checked: the target does not hold the commit {FAKE_SHA[:12]}"]
        )

    def test_a_target_that_is_not_a_repository_gives_the_same_warning(self) -> None:
        write_files(self.target, self.cited())
        outcome = vr.validate_document(self.report_for(FAKE_SHA), target=self.target)
        self.assertEqual(len(outcome.warnings), 1)
        self.assertIn("were not checked", outcome.warnings[0])

    def test_without_git_the_tool_says_so_and_checks_nothing(self) -> None:
        write_files(self.target, self.cited())
        with mock.patch.object(shutil, "which", return_value=None):
            outcome = vr.validate_document(self.report_for(FAKE_SHA), target=self.target)
        self.assertEqual(outcome.warnings, ["the cited files were not checked: git is not installed"])

    def test_with_no_commit_recorded_the_working_tree_is_looked_at(self) -> None:
        paths = self.cited()
        write_files(self.target, paths[1:])
        outcome = vr.validate_document(self.report_for(None), target=self.target)
        self.assertEqual(len(outcome.warnings), 1)
        self.assertIn(f"the file {paths[0]} is not in the target", outcome.warnings[0])
        write_files(self.target, [paths[0]])
        self.assertEqual(vr.validate_document(self.report_for(None), target=self.target).warnings, [])

    def test_a_link_that_leads_out_of_the_target_does_not_count_as_a_file(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("x\n", encoding="utf-8")
        (self.target / "link").symlink_to(outside)
        report = self.report_for(None)
        check_of(report, "IDX-01")["evidence"].append(tool_evidence("link/secret.txt"))
        outcome = vr.validate_document(report, target=self.target)
        self.assertTrue(any("link/secret.txt is not in the target" in w for w in outcome.warnings))

    def test_nothing_is_checked_without_a_target(self) -> None:
        self.assertEqual(vr.validate_document(self.report_for(FAKE_SHA)).warnings, [])

    def test_a_report_with_errors_gets_no_warnings(self) -> None:
        report = self.report_for(FAKE_SHA)
        report["checks"][0]["id"] = "ZZZ-99"
        outcome = vr.validate_document(report, target=self.target)
        self.assertTrue(outcome.errors)
        self.assertEqual(outcome.warnings, [])

    def test_a_path_with_a_newline_is_a_warning_and_cannot_break_the_lookup(self) -> None:
        sha = self.commit(self.cited())
        report = self.report_for(sha)
        check_of(report, "IDX-01")["evidence"].append(tool_evidence("a\nb"))
        outcome = vr.validate_document(report, target=self.target)
        self.assertEqual(len(outcome.warnings), 1)


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(vr.INFO, vr.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


class ToolContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def write(self, name: str, content: str | bytes) -> Path:
        path = self.root / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def test_a_valid_report_is_exit_0_with_a_short_summary(self) -> None:
        code, envelope, stderr = call([str(WORKED)])
        self.assertEqual(code, 0)
        self.assertEqual(
            (envelope["tool"], envelope["ok"], envelope["warnings"], envelope["truncated"]),
            ("validate_report", True, [], False),
        )
        self.assertEqual(
            envelope["data"],
            {
                "valid": True,
                "report": str(WORKED),
                "schema_version": "0.1",
                "status": "final",
                "checks": 12,
                "findings": 10,
                "target_checked": False,
            },
        )
        self.assertEqual(stderr, "validate_report: valid (12 checks, 10 findings, 0 warnings)\n")

    def test_an_invalid_report_is_exit_2_with_every_error_in_data(self) -> None:
        report = base()
        check_of(report, "CI-04")["id"] = "ZZZ-99"
        finding_of(report, "F-001")["remediation"]["depends_on"] = ["F-099"]
        path = self.write("bad.json", json.dumps(report))
        code, envelope, stderr = call([str(path)])
        self.assertEqual(code, 2)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["data"]["error"], "the report is not valid: 3 errors in the rules stage")
        self.assertEqual(len(envelope["data"]["errors"]), 3)
        self.assertTrue(envelope["data"]["errors"][0].startswith("rule 1:"))
        self.assertIn("validate_report: the report is not valid", stderr)

    def test_one_error_is_not_pluralised(self) -> None:
        report = base()
        report["provenance"]["catalogue_version"] = "x"
        code, envelope, _ = call([str(self.write("bad.json", json.dumps(report)))])
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["error"], "the report is not valid: 1 error in the schema stage")

    def test_warnings_ride_in_the_envelope_and_are_bounded(self) -> None:
        report = base()
        report["provenance"]["target"].update({"git_sha": None, "branch": None, "dirty": None})
        long_name = "x" * 200
        for index, check in enumerate(report["checks"]):
            check["evidence"] += [tool_evidence(f"missing/{index:02d}/{n:03d}/{long_name}") for n in range(40)]
        target = self.root / "empty"
        target.mkdir()
        code, envelope, _ = call([str(self.write("many.json", json.dumps(report))), "--target", str(target)])
        self.assertEqual(code, 0)
        self.assertTrue(envelope["truncated"])
        self.assertGreater(envelope["data"]["warnings_omitted"], 0)
        self.assertGreater(len(envelope["warnings"]), 100)
        self.assertLessEqual(len(json.dumps(envelope).encode()), _common.MAX_OUTPUT_BYTES)

    def test_a_missing_file_or_a_directory_is_exit_1(self) -> None:
        for argument in (str(self.root / "nope.json"), str(self.root)):
            with self.subTest(argument=argument):
                code, envelope, _ = call([argument])
                self.assertEqual(code, 1)
                self.assertFalse(envelope["ok"])

    def test_a_report_over_the_size_limit_is_exit_1(self) -> None:
        with mock.patch.object(vr, "MAX_REPORT_BYTES", 10):
            code, envelope, _ = call([str(WORKED)])
        self.assertEqual(code, 1)
        self.assertIn("the limit is 10", envelope["data"]["error"])

    def test_a_file_that_is_not_a_report_is_exit_2(self) -> None:
        cases = {
            "text.json": b"not json at all",
            "empty.json": b"",
            "repeated.json": b'{"a": 1, "a": 2}',
            "nan.json": b'{"a": NaN}',
            "infinity.json": b'{"a": Infinity}',
            "latin1.json": b'{"a": "\xe9"}',
        }
        for name, content in cases.items():
            with self.subTest(file=name):
                code, envelope, _ = call([str(self.write(name, content))])
                self.assertEqual(code, 2)
                self.assertIn("the file is not a report", envelope["data"]["error"])

    def test_a_json_document_nested_too_deeply_is_exit_2(self) -> None:
        # Whether a real document this deep actually overflows the C stack, and at what depth, depends
        # on the platform's stack size and the Python build (observed: reliable on some CI legs, never
        # triggered on others at 100_000 levels) — CPython 3.14 also changed the json decoder's guard from
        # a frame-count check to a raw stack-memory one, unaffected by sys.setrecursionlimit. Mocking
        # json.loads to raise RecursionError tests parse_report's own handling of it deterministically,
        # independent of any platform's actual stack headroom. The mock only intercepts the one call
        # parse_report makes on this file's own marker content, so `call()`'s own json.loads (parsing the
        # tool's JSON envelope back out) still runs for real.
        marker = "__test_a_json_document_nested_too_deeply_is_exit_2__"
        path = self.write("deep.json", marker)
        real_loads = json.loads

        def fake_loads(text: str, **kwargs: Any) -> Any:
            if text == marker:
                raise RecursionError("too deep")
            return real_loads(text, **kwargs)

        with mock.patch.object(vr.json, "loads", side_effect=fake_loads):
            code, envelope, _ = call([str(path)])
        self.assertEqual(code, 2)
        self.assertIn("the file is not a report", envelope["data"]["error"])

    def test_a_target_that_does_not_exist_is_exit_1(self) -> None:
        code, envelope, _ = call([str(WORKED), "--target", str(self.root / "nope")])
        self.assertEqual(code, 1)
        self.assertIn("target not found", envelope["data"]["error"])

    def test_a_bad_argument_is_exit_1_and_an_abbreviation_is_refused(self) -> None:
        for argv in ([], [str(WORKED), "--nope"], [str(WORKED), "--targ", str(self.root)]):
            with self.subTest(argv=argv):
                code, envelope, _ = call(argv)
                self.assertEqual(code, 1)
                self.assertFalse(envelope["ok"])

    def test_describe_prints_the_manifest(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["name"], "validate_report")
        self.assertEqual(envelope["data"]["synopsis"], ["validate_report.py <report> [--target <repo>]"])
        self.assertEqual(envelope["data"]["writes"], "nothing")

    def test_the_tool_writes_nothing_to_the_report_or_the_target(self) -> None:
        target = self.root / "target"
        write_files(target, ["a.txt", "dir/b.txt"])
        path = self.write("report.json", WORKED.read_text(encoding="utf-8"))
        before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in [path, *sorted(target.rglob("*")), self.root]}
        call([str(path), "--target", str(target)])
        after = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in before}
        self.assertEqual(before, after)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["report.json", "target"])

    def test_it_runs_as_a_script_from_any_directory(self) -> None:
        done = subprocess.run(
            [sys.executable, str(TOOLS / "validate_report.py"), str(WORKED)],
            cwd="/",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads(done.stdout)["data"]["valid"])


class HelperTests(unittest.TestCase):
    def test_leaves_target_gives_a_reason_only_for_a_path_that_leaves(self) -> None:
        table: list[tuple[str, Callable[[str | None], bool]]] = [
            ("src/a.py", lambda r: r is None),
            ("/abs", lambda r: r == "is absolute"),
            ("../x", lambda r: r == "climbs out of the target"),
            ("a\x00b", lambda r: r == "contains a NUL character"),
        ]
        for path, expected in table:
            with self.subTest(path=path):
                self.assertTrue(expected(vr.leaves_target(path)))

    def test_a_parsed_report_keeps_the_order_of_its_keys(self) -> None:
        self.assertEqual(list(vr.parse_report('{"b": 1, "a": 2}')), ["b", "a"])

    def test_the_reader_names_what_it_reads_and_says_report_by_default(self) -> None:
        with self.assertRaises(_common.ValidationFailed) as default:
            vr.parse_report("{")
        with self.assertRaises(_common.ValidationFailed) as named:
            vr.parse_report("{", "intake")
        self.assertIn("the file is not a report: it is not valid JSON", str(default.exception))
        self.assertIn("the file is not an intake: it is not valid JSON", str(named.exception))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(_common.UsageError) as missing:
                vr.read_report(Path(tmp) / "none.json", "fragment")
            with self.assertRaises(_common.UsageError) as folder:
                vr.read_report(Path(tmp), "fragment")
        self.assertIn("fragment not found:", str(missing.exception))
        self.assertIn("the fragment is not a file:", str(folder.exception))


if __name__ == "__main__":
    unittest.main()
