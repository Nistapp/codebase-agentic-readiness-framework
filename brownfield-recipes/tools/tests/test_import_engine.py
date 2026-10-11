# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`report.py import-engine`: the engine's report becomes the draft's automated checks, once, and only for its own target.

A test builds a small engine report (schema v2) as a dictionary, or reads one of the engine's real reports, writes it
to a folder of its own, and runs the tool in process through `run_tool`, so that the envelope and the exit code are what
a recipe sees. Every refusal must leave the draft's bytes and the folder's files as they were. Standard library only.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import _paths
import _engine_reports as er
import _summary
import render_report
import report as rb
import validate_report as vr
from test_report import BuilderCase, agent_check, agent_finding, call, read_json, tree_state

TOOLS = _paths.TOOLS
REALISTIC = TOOLS.parent / "schema" / "examples" / "realistic"
SHA_A = "a" * 40
SHA_B = "b" * 40


class ImportCase(BuilderCase):
    """A draft, and a folder of its own for engine reports, outside the target and outside the output folder."""

    def setUp(self) -> None:
        super().setUp()
        self.engine_dir = self.root / "engine"
        self.engine_dir.mkdir()

    def engine_file(self, report: Any, name: str = "my-service.engine-report.20261010T065738Z.json") -> Path:
        path = self.engine_dir / name
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def import_engine(self, draft: Path, source: Path | str) -> tuple[int, dict[str, Any], str]:
        return call(["import-engine", str(draft), str(source)])

    def imported(self, report: Any = None, **intake: Any) -> tuple[Path, dict[str, Any]]:
        """A new draft with `report` (by default, a bare provenance for the draft's own target) imported into it."""
        draft = self.start(**intake)
        code, envelope, stderr = self.import_engine(
            draft, self.engine_file(er.report(self.target) if report is None else report)
        )
        self.assertEqual(code, 0, (envelope, stderr))
        return draft, envelope

    def refused(self, draft: Path, source: Path | str, code: int = 2) -> dict[str, Any]:
        """Import `source`, which must be refused with `code` and leave the draft and its folder as they were."""
        exit_code, envelope, _ = self.unchanged_by(draft, lambda: self.import_engine(draft, source))
        self.assertEqual(exit_code, code, envelope)
        self.assertFalse(envelope["ok"])
        return envelope


class EngineRecordTests(ImportCase):
    def test_the_draft_records_the_engine_in_the_order_of_the_schema(self) -> None:
        draft, _ = self.imported()
        provenance = read_json(draft)["provenance"]
        self.assertEqual(
            provenance["engine"],
            {
                "name": "python-agentic-audit",
                "version": "0.1.0",
                "ruleset_revision": "2026-09-28.13",
                "ruleset_hash": "0123456789abcdef",
                "scanned_at": "2026-10-10T06:57:38+00:00",
            },
        )
        self.assertEqual(
            list(provenance["engine"]), ["name", "version", "ruleset_revision", "ruleset_hash", "scanned_at"]
        )
        self.assertEqual(
            list(provenance),
            ["recipe", "framework_revision", "catalogue_version", "engine", "agent", "target", "started_at"],
        )

    def test_the_draft_stays_valid_and_keeps_the_target_it_was_given(self) -> None:
        draft = self.start()
        before = read_json(draft)
        self.assertEqual(self.import_engine(draft, self.engine_file(er.report(self.target)))[0], 0)
        after = read_json(draft)
        self.assertEqual(vr.validate_document(after).errors, [])
        self.assertEqual(after["provenance"]["target"], before["provenance"]["target"])
        self.assertEqual(after["run_context"], before["run_context"])
        self.assertEqual(after["status"], "draft")

    def test_a_revision_and_a_scan_time_the_engine_did_not_give_are_left_out(self) -> None:
        provenance = er.provenance(self.target)
        del provenance["ruleset_revision"], provenance["scanned_at"]
        draft, _ = self.imported(er.report(self.target, provenance=provenance))
        self.assertEqual(
            read_json(draft)["provenance"]["engine"],
            {"name": "python-agentic-audit", "version": "0.1.0", "ruleset_hash": "0123456789abcdef"},
        )

    def test_the_envelope_names_the_draft_the_engine_report_and_the_engine(self) -> None:
        draft, envelope = self.imported()
        self.assertEqual(envelope["data"]["draft"], str(draft))
        self.assertEqual(
            envelope["data"]["engine_report"],
            str((self.engine_dir / "my-service.engine-report.20261010T065738Z.json").resolve()),
        )
        self.assertEqual(envelope["data"]["engine"]["ruleset_hash"], "0123456789abcdef")
        self.assertEqual(envelope["warnings"], [])

    def test_fields_the_adapter_does_not_read_are_ignored(self) -> None:
        report = er.report(self.target, future_field={"anything": [1, 2, 3]})
        report["provenance"]["another"] = "ignored"
        draft, _ = self.imported(report)
        self.assertNotIn("another", json.dumps(read_json(draft)))

    def test_the_engine_report_is_read_and_never_written(self) -> None:
        draft = self.start()
        source = self.engine_file(er.report(self.target))
        before, folder = source.read_bytes(), tree_state(self.engine_dir)
        self.assertEqual(self.import_engine(draft, source)[0], 0)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(tree_state(self.engine_dir), folder)

    def test_it_writes_nothing_but_the_draft_and_does_not_touch_the_target(self) -> None:
        draft = self.start()
        target = tree_state(self.target)
        self.import_engine(draft, self.engine_file(er.report(self.target)))
        self.assertEqual(tree_state(self.target), target)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [draft.name])

    def test_the_script_runs_from_another_directory_and_prints_one_envelope(self) -> None:
        draft = self.start()
        source = self.engine_file(er.report(self.target))
        done = subprocess.run(
            [sys.executable, str(TOOLS / "report.py"), "import-engine", str(draft), str(source)],
            capture_output=True,
            text=True,
            check=False,
            cwd=self.root,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        envelope = json.loads(done.stdout)
        self.assertEqual((envelope["tool"], envelope["ok"]), ("report", True))
        self.assertIn("imported 0 checks and 0 findings from python-agentic-audit 0.1.0", done.stderr)

    def test_the_describe_manifest_lists_the_subcommand(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertIn("report.py import-engine <draft> <engine report>", envelope["data"]["synopsis"])


class OnceTests(ImportCase):
    def test_a_second_import_is_refused_and_leaves_the_draft_as_it_was(self) -> None:
        draft, _ = self.imported()
        again = self.engine_file(
            er.report(self.target, provenance=er.provenance(self.target, ruleset_hash="fedcba9876543210")),
            "second.json",
        )
        envelope = self.refused(draft, again)
        self.assertIn("already holds an engine report", envelope["data"]["error"])
        self.assertIn("0123456789abcdef", envelope["data"]["error"])
        self.assertEqual(read_json(draft)["provenance"]["engine"]["ruleset_hash"], "0123456789abcdef")

    def test_the_same_report_twice_is_refused_too(self) -> None:
        draft, _ = self.imported()
        self.refused(draft, self.engine_dir / "my-service.engine-report.20261010T065738Z.json")

    def test_a_final_report_cannot_take_an_import(self) -> None:
        draft = self.complete_engine_draft()
        code, envelope, _ = self.finalise(draft)
        self.assertEqual(code, 0, envelope)
        final = Path(envelope["data"]["report"])
        source = self.engine_file(er.report(self.target))
        before = final.read_bytes()
        code, envelope, _ = self.import_engine(final, source)
        self.assertEqual(code, 1, envelope)
        self.assertEqual(final.read_bytes(), before)


class NotAnEngineReportTests(ImportCase):
    def setUp(self) -> None:
        super().setUp()
        self.draft = self.start()

    def test_a_schema_version_other_than_2_is_refused(self) -> None:
        for version in ("1", "3", 2, None, "2.0"):
            with self.subTest(version=version):
                report = er.report(self.target)
                report["schema_version"] = version
                envelope = self.refused(self.draft, self.engine_file(report))
                self.assertIn(f"schema_version {version!r}", envelope["data"]["error"])
                self.assertIn("reads only '2'", envelope["data"]["error"])

    def test_a_missing_schema_version_is_refused(self) -> None:
        report = er.report(self.target)
        del report["schema_version"]
        envelope = self.refused(self.draft, self.engine_file(report))
        self.assertIn("schema_version None", envelope["data"]["error"])

    def test_a_report_for_another_phase_is_refused(self) -> None:
        for phase in (0, 2, 7):
            with self.subTest(phase=phase):
                report = er.report(self.target, provenance=er.provenance(self.target, phase=phase))
                envelope = self.refused(self.draft, self.engine_file(report))
                self.assertIn(f"for phase {phase}", envelope["data"]["error"])
                self.assertIn("covers phase 1", envelope["data"]["error"])
                self.assertEqual(
                    envelope["data"]["errors"], [f"engine report: /provenance/phase: expected 1, found {phase}"]
                )

    def test_a_report_that_is_not_an_object_is_refused(self) -> None:
        reports: list[Any] = [[], "text", 7, None]
        for report in reports:
            with self.subTest(report=report):
                envelope = self.refused(self.draft, self.engine_file(report))
                self.assertIn("not a JSON object", envelope["data"]["error"])

    def test_a_missing_or_mistyped_provenance_field_is_named(self) -> None:
        for name, bad in (
            ("tool", None),
            ("version", 1),
            ("ruleset_hash", None),
            ("target", ["x"]),
            ("phase", "1"),
            ("scanned_at", 5),
            ("git_sha", 5),
        ):
            with self.subTest(field=name):
                report = er.report(self.target)
                report["provenance"][name] = bad
                envelope = self.refused(self.draft, self.engine_file(report))
                self.assertIn("wrong shape", envelope["data"]["error"])
                self.assertTrue(
                    any(
                        error.startswith(f"engine report: /provenance/{name}:") for error in envelope["data"]["errors"]
                    ),
                    envelope["data"]["errors"],
                )
        for name in ("tool", "version", "ruleset_hash", "target", "phase"):
            with self.subTest(missing=name):
                report = er.report(self.target)
                del report["provenance"][name]
                envelope = self.refused(self.draft, self.engine_file(report))
                self.assertIn(f"'{name}'", " ".join(envelope["data"]["errors"]))

    def test_a_report_with_no_provenance_is_refused(self) -> None:
        envelope = self.refused(self.draft, self.engine_file({"schema_version": "2"}))
        self.assertIn("'provenance'", " ".join(envelope["data"]["errors"]))

    def test_the_errors_are_counted_and_every_one_is_listed(self) -> None:
        report = er.report(self.target)
        report["provenance"].update(tool=1, version=2)
        envelope = self.refused(self.draft, self.engine_file(report))
        self.assertIn("2 errors", envelope["data"]["error"])
        self.assertEqual(len(envelope["data"]["errors"]), 2)

    def test_a_value_the_report_schema_limits_is_refused_by_the_draft_validation(self) -> None:
        report = er.report(self.target, provenance=er.provenance(self.target, ruleset_hash="not-a-hash"))
        envelope = self.refused(self.draft, self.engine_file(report))
        self.assertIn("would leave the draft invalid, so nothing was written", envelope["data"]["error"])
        self.assertTrue(any("/provenance/engine/ruleset_hash" in error for error in envelope["data"]["errors"]))

    def test_a_file_that_is_not_json_is_refused(self) -> None:
        source = self.engine_dir / "broken.json"
        source.write_text("{not json", encoding="utf-8")
        self.refused(self.draft, source)

    def test_a_file_that_repeats_a_key_is_refused(self) -> None:
        source = self.engine_dir / "repeated.json"
        source.write_text('{"schema_version": "2", "schema_version": "2", "provenance": {}}', encoding="utf-8")
        self.refused(self.draft, source)

    def test_a_missing_file_and_a_folder_are_a_usage_error(self) -> None:
        self.refused(self.draft, self.engine_dir / "nothing.json", code=1)
        self.refused(self.draft, self.engine_dir, code=1)

    def test_a_missing_draft_is_a_usage_error(self) -> None:
        source = self.engine_file(er.report(self.target))
        code, envelope, _ = self.import_engine(self.out / "nothing.audit-draft.20261010T093000Z.json", source)
        self.assertEqual(code, 1, envelope)

    def test_an_argument_missing_is_a_usage_error(self) -> None:
        self.assertEqual(call(["import-engine", str(self.draft)])[0], 1)
        self.assertEqual(call(["import-engine"])[0], 1)


class SameTargetTests(ImportCase):
    def set_commit(self, draft: Path, sha: str | None) -> None:
        document = read_json(draft)
        document["provenance"]["target"]["git_sha"] = sha
        draft.write_text(rb.dumps(document), encoding="utf-8")

    def test_a_report_of_another_repository_is_refused(self) -> None:
        draft = self.start()
        other = self.root / "Other_Service"
        other.mkdir()
        envelope = self.refused(draft, self.engine_file(er.report(other)))
        self.assertIn("not of this draft's target", envelope["data"]["error"])
        self.assertEqual(len(envelope["data"]["errors"]), 1)
        self.assertIn(str(other), envelope["data"]["errors"][0])
        self.assertIn(str(self.target), envelope["data"]["errors"][0])

    def test_the_same_directory_by_another_spelling_is_accepted(self) -> None:
        link = self.root / "link-to-target"
        link.symlink_to(self.target, target_is_directory=True)
        for spelling in (link, f"{self.target}/", f"{self.root}/./My_Service", f"{self.root}/out/../My_Service"):
            with self.subTest(spelling=str(spelling)):
                code, envelope, _ = self.import_engine(self.start(), self.engine_file(er.report(spelling)))
                self.assertEqual(code, 0, envelope)

    def test_another_commit_is_refused_and_both_are_named(self) -> None:
        draft = self.start()
        self.set_commit(draft, SHA_A)
        report = er.report(self.target, provenance=er.provenance(self.target, git_sha=SHA_B))
        envelope = self.refused(draft, self.engine_file(report))
        self.assertIn(SHA_A, envelope["data"]["errors"][0])
        self.assertIn(SHA_B, envelope["data"]["errors"][0])
        self.assertIn("scan again", envelope["data"]["errors"][0])

    def test_the_same_commit_is_accepted_without_a_warning(self) -> None:
        draft = self.start()
        self.set_commit(draft, SHA_A)
        report = er.report(self.target, provenance=er.provenance(self.target, git_sha=SHA_A))
        code, envelope, _ = self.import_engine(draft, self.engine_file(report))
        self.assertEqual((code, envelope["warnings"]), (0, []))

    def test_a_commit_known_to_one_side_only_is_accepted_with_a_warning(self) -> None:
        draft = self.start()
        report = er.report(self.target, provenance=er.provenance(self.target, git_sha=SHA_B))
        code, envelope, _ = self.import_engine(draft, self.engine_file(report))
        self.assertEqual(code, 0, envelope)
        self.assertEqual(
            envelope["warnings"], ["only the engine knows the target's commit, so the draft's cannot be compared"]
        )
        other = self.start()
        self.set_commit(other, SHA_A)
        code, envelope, _ = self.import_engine(other, self.engine_file(er.report(self.target), "third.json"))
        self.assertEqual(code, 0, envelope)
        self.assertEqual(
            envelope["warnings"], ["only the draft knows the target's commit, so the engine's cannot be compared"]
        )

    def test_both_a_wrong_target_and_a_wrong_commit_are_listed(self) -> None:
        draft = self.start()
        self.set_commit(draft, SHA_A)
        other = self.root / "Other_Service"
        other.mkdir()
        report = er.report(other, provenance=er.provenance(other, git_sha=SHA_B))
        envelope = self.refused(draft, self.engine_file(report))
        self.assertEqual(len(envelope["data"]["errors"]), 2)


def sample_report(target: Path | str, **changes: Any) -> dict[str, Any]:
    """Five checks of the engine, three findings, one check that does not apply, and one path outside the repository."""
    return er.report(
        target,
        [
            er.check("IDX-02", "FAIL"),
            er.check("SEC-02", "FAIL"),
            er.check("AGT-08", "PARTIAL", severity="DEGRADER"),
            er.check("TOOL-01", "PASS"),
            er.check("TOOL-02", "UNKNOWN"),
        ],
        [
            er.finding("IDX-02", evidence=[er.evidence("/home/someone/.cache/index")]),
            er.finding("SEC-02", "src/a.ts", evidence=[er.evidence("src/a.ts", 5, "credential-shaped string")]),
            er.finding("AGT-08", severity="COSMETIC"),
        ],
        not_applicable=["TOOL-03"],
        **changes,
    )


class ImportChecksTests(ImportCase):
    def test_the_checks_and_findings_arrive_and_the_draft_is_valid_and_renders(self) -> None:
        draft, envelope = self.imported(sample_report(self.target))
        document = read_json(draft)
        self.assertEqual(vr.validate_document(document).errors, [])
        self.assertTrue(render_report.render(document))
        self.assertEqual(
            [c["id"] for c in document["checks"]], ["IDX-02", "SEC-02", "AGT-08", "TOOL-01", "TOOL-02", "TOOL-03"]
        )
        self.assertEqual([f["id"] for f in document["findings"]], ["F-001", "F-002", "F-003"])
        self.assertEqual([f["key"] for f in document["findings"]], ["IDX-02", "SEC-02:src/a.ts", "AGT-08"])
        self.assertEqual({f["disposition"] for f in document["findings"]}, {"pending"})
        self.assertEqual(envelope["data"]["findings_imported"], 3)

    def test_the_keys_of_a_check_and_a_finding_are_in_the_order_of_the_schema(self) -> None:
        document = read_json(self.imported(sample_report(self.target))[0])
        schema = rb.report_schema()["$defs"]
        for check in document["checks"]:
            self.assertEqual(list(check), [n for n in schema["check"]["properties"] if n in check])
        for finding in document["findings"]:
            self.assertEqual(list(finding), [n for n in schema["finding"]["properties"] if n in finding])

    def test_the_summary_is_the_tools_and_counts_the_imported_checks(self) -> None:
        document = read_json(self.imported(sample_report(self.target))[0])
        self.assertEqual(document["summary"], _summary.compute_summary(document))
        self.assertEqual(document["summary"]["blockers_remaining"], {"total": 2, "fail": 2, "partial": 0, "unknown": 0})
        self.assertGreater(document["summary"]["scored_checks"], 0)

    def test_the_envelope_counts_what_came_in(self) -> None:
        (self.target / "src").mkdir()
        (self.target / "src" / "a.ts").write_text("x\n", encoding="utf-8")
        _, envelope = self.imported(sample_report(self.target))
        data = envelope["data"]
        self.assertEqual(data["checks_imported"], 6)
        self.assertEqual(data["by_verdict"], {"FAIL": 2, "NOT_APPLICABLE": 1, "PARTIAL": 1, "PASS": 1, "UNKNOWN": 1})
        self.assertEqual(list(data["by_verdict"]), sorted(data["by_verdict"]))
        self.assertEqual((data["findings_imported"], data["findings"], data["findings_pending"]), (3, 3, 3))
        self.assertEqual((data["checks_recorded"], data["checks_expected"]), (6, 71))
        self.assertEqual(data["evidence_not_carried"], 1)
        self.assertEqual(
            envelope["warnings"],
            [
                "IDX-02: the evidence path '/home/someone/.cache/index' is not carried: "
                "the path is absolute, so it is outside the repository"
            ],
        )

    def test_the_summary_line_says_how_many_came_in(self) -> None:
        draft = self.start()
        _, _, stderr = self.import_engine(draft, self.engine_file(sample_report(self.target)))
        self.assertIn("report: imported 6 checks and 3 findings from python-agentic-audit 0.1.0", stderr)

    def test_the_engines_checks_follow_those_the_agent_recorded_and_ids_go_on_from_the_agents_findings(self) -> None:
        draft = self.failing_draft()
        self.assertEqual(self.add_finding(draft, agent_finding(scope="a"))[0], 0)
        code, envelope, _ = self.import_engine(draft, self.engine_file(sample_report(self.target)))
        self.assertEqual(code, 0, envelope)
        document = read_json(draft)
        self.assertEqual([c["id"] for c in document["checks"]][:3], ["AGT-11", "IDX-02", "SEC-02"])
        self.assertEqual([f["id"] for f in document["findings"]], ["F-001", "F-002", "F-003", "F-004"])
        self.assertEqual(document["findings"][0]["check"], "AGT-11")
        self.assertEqual(vr.validate_document(document).errors, [])

    def test_an_interactive_run_leaves_every_finding_pending(self) -> None:
        document = read_json(self.imported(sample_report(self.target))[0])
        self.assertEqual(
            [(f["disposition"], "confirmed_via" in f) for f in document["findings"]], [("pending", False)] * 3
        )

    def test_a_defer_all_run_leaves_every_finding_pending(self) -> None:
        document = read_json(
            self.imported(sample_report(self.target), confirmation_policy="defer-all", eval_mode=True)[0]
        )
        self.assertEqual({f["disposition"] for f in document["findings"]}, {"pending"})

    def test_an_accept_all_run_confirms_every_finding_by_policy(self) -> None:
        document = read_json(
            self.imported(sample_report(self.target), confirmation_policy="accept-all", eval_mode=True)[0]
        )
        self.assertEqual(
            {(f["disposition"], f["confirmed_via"]) for f in document["findings"]}, {("confirmed", "policy")}
        )
        self.assertEqual(vr.validate_document(document).errors, [])

    def test_a_check_can_be_disputed_after_the_import_and_keeps_the_engines_verdict(self) -> None:
        draft, _ = self.imported(sample_report(self.target))
        code, envelope, _ = self.add_check(
            draft,
            {
                "id": "TOOL-02",
                "verdict": "PASS",
                "summary": "A linter is configured in a file the engine does not read.",
                "override_reason": "eslint.config.mjs is present.",
                "evidence": [{"kind": "file", "path": "eslint.config.mjs"}],
            },
        )
        self.assertEqual((code, envelope["data"]["action"]), (0, "overridden"), envelope)
        check = next(c for c in read_json(draft)["checks"] if c["id"] == "TOOL-02")
        self.assertEqual((check["verdict"], check["engine_verdict"]), ("PASS", "UNKNOWN"))

    def test_a_finding_can_be_decided_after_the_import(self) -> None:
        draft, _ = self.imported(sample_report(self.target))
        code, envelope, _ = self.decide(
            draft, "--via", "interactive", "--finding", "F-001", "--disposition", "confirmed"
        )
        self.assertEqual(code, 0, envelope)

    def test_status_counts_the_imported_checks_as_recorded(self) -> None:
        draft, _ = self.imported(sample_report(self.target))
        code, envelope, _ = call(["status", str(draft)])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["checks_recorded"], 6)
        self.assertEqual(envelope["data"]["findings_pending"], 3)

    def test_a_draft_that_already_records_a_check_the_engine_reports_is_refused(self) -> None:
        draft = self.start()
        document = read_json(draft)
        document["checks"].append(
            {
                "id": "TOOL-01",
                "title": next(c["title"] for c in er.CATALOGUE.values() if c["id"] == "TOOL-01"),
                "phase": 1,
                "severity": er.CATALOGUE["TOOL-01"]["severity"],
                "scored": er.CATALOGUE["TOOL-01"]["scored"],
                "method": "automated",
                "verdict": "PASS",
                "summary": "Made by hand.",
                "evidence": [],
                "searches": [],
            }
        )
        document["summary"] = _summary.compute_summary(document)
        draft.write_text(rb.dumps(document), encoding="utf-8")
        envelope = self.refused(draft, self.engine_file(sample_report(self.target)))
        self.assertIn("already records TOOL-01", envelope["data"]["error"])

    def test_an_engine_finding_more_severe_than_its_check_is_refused_by_the_rules(self) -> None:
        report = er.report(self.target, [er.check("AGT-08", "FAIL")], [er.finding("AGT-08", severity="BLOCKER")])
        draft = self.start()
        envelope = self.refused(draft, self.engine_file(report))
        self.assertIn("would leave the draft invalid, so nothing was written", envelope["data"]["error"])
        self.assertTrue(any("/findings/0" in error for error in envelope["data"]["errors"]), envelope["data"]["errors"])

    def test_an_engine_finding_on_a_passing_check_is_refused_by_the_rules(self) -> None:
        report = er.report(self.target, [er.check("AGT-08", "PASS")], [er.finding("AGT-08")])
        envelope = self.refused(self.start(), self.engine_file(report))
        self.assertTrue(any("rejected" in error for error in envelope["data"]["errors"]), envelope["data"]["errors"])

    def test_a_check_that_disagrees_with_the_catalogue_is_refused_by_the_rules(self) -> None:
        report = er.report(self.target, [er.check("TOOL-01", "PASS", title="Another title")])
        envelope = self.refused(self.start(), self.engine_file(report))
        self.assertTrue(any("catalogue" in error for error in envelope["data"]["errors"]), envelope["data"]["errors"])

    def test_a_report_the_adapter_refuses_changes_nothing(self) -> None:
        report = sample_report(self.target)
        report["checks"].append(er.check("AGT-11"))
        envelope = self.refused(self.start(), self.engine_file(report))
        self.assertIn("cannot be imported", envelope["data"]["error"])

    def test_the_adapters_warnings_are_bounded_like_every_other_list(self) -> None:
        findings = [
            er.finding("SEC-02", f"f{n}.ts", evidence=[er.evidence(f"/abs/{n}/{'x' * 80}")]) for n in range(700)
        ]
        report = er.report(self.target, [er.check("SEC-02", "FAIL")], findings)
        _, envelope = self.imported(report)
        self.assertTrue(envelope["truncated"])
        self.assertGreater(envelope["data"]["warnings_omitted"], 0)
        self.assertLess(len(envelope["warnings"]), 700)
        self.assertEqual(len(envelope["warnings"]) + envelope["data"]["warnings_omitted"], 700)
        self.assertEqual(envelope["data"]["evidence_not_carried"], 700)


class ImportUnattestedTests(ImportCase):
    def test_the_engines_five_items_are_listed_in_the_engines_own_words(self) -> None:
        golden = read_json(next(REALISTIC.glob("agentic-tdd.audit-draft.*.json")))
        items = ["index-in-use", "baseline-adequacy", "suite-trustworthiness", "doc-accuracy", "gate-honoured"]
        draft, envelope = self.imported(er.report(self.target, unattested=items))
        document = read_json(draft)
        self.assertEqual(document["unattested"], golden["unattested"])
        self.assertEqual(vr.validate_document(document).errors, [])
        self.assertEqual(envelope["data"]["unattested_listed"], 5)

    def test_a_check_marked_attest_is_not_a_check_but_is_not_missing_either(self) -> None:
        report = er.report(self.target, [er.check("TOOL-01", "ATTEST"), er.check("TOOL-02")])
        draft, envelope = self.imported(report)
        document = read_json(draft)
        self.assertEqual([c["id"] for c in document["checks"]], ["TOOL-02"])
        self.assertEqual(
            [(u["requirement"], u["property"]) for u in document["unattested"]], [("REQ-SH-027", "tool-01")]
        )
        self.assertEqual(vr.validate_document(document).errors, [])
        self.assertEqual(envelope["data"]["unattested_listed"], 1)
        self.assertNotIn("TOOL-01", rb.missing_checks(document).get("TOOL", []))
        self.assertEqual(envelope["data"]["checks_recorded"], 2)
        code, status, _ = call(["status", str(draft)])
        self.assertEqual(code, 0)
        self.assertEqual(status["data"]["checks_recorded"], 2)
        self.assertNotIn("TOOL-01", status["data"]["families_remaining"].get("TOOL", ""))
        self.assertNotIn("TOOL-01", " ".join(rb.finalisation_errors(document)))

    def test_a_check_missing_from_the_engines_report_is_still_missing(self) -> None:
        document = read_json(self.imported(er.report(self.target, [er.check("TOOL-02")]))[0])
        self.assertIn("TOOL-01", rb.missing_checks(document)["TOOL"])


PAIRS = {
    "agentic-tdd": [
        "IDX-02: the evidence path '/home/kc/.cache/codebase-memory-mcp' is not carried: "
        "the path is absolute, so it is outside the repository"
    ],
    "digital-assistant-sdk": [],
    "digital-assistant-server": [],
}


def golden_pair(name: str) -> tuple[Path, Path]:
    """The raw engine report and the draft made from it, which the adapter must reproduce."""
    (draft,) = REALISTIC.glob(f"{name}.audit-draft.*.json")
    (engine,) = REALISTIC.glob(f"{name}.engine-report.*.json")
    return engine, draft


def started(golden: dict[str, Any]) -> dict[str, Any]:
    """What `init` leaves of a draft: the golden draft without what `import-engine` fills in."""
    document = copy.deepcopy(golden)
    del document["provenance"]["engine"]
    document["stack"] = {
        name: [] for name in ("ecosystems", "package_managers", "ci_providers", "test_frameworks", "hook_managers")
    }
    document.update(components=[], checks=[], findings=[], unattested=[])
    del document["coverage"]["inventory"]
    document["summary"] = _summary.compute_summary(document)
    return document


class GoldenPairTests(ImportCase):
    """Each raw engine report in `schema/examples/realistic/` imports to the draft beside it, byte for byte.

    The draft is made from the golden draft's own fields that `init` supplies, so that nothing depends on the machine
    the engine scanned. The pairs are golden for the ruleset they were produced with: when the mapping changes, the
    drafts are regenerated from the raw reports.
    """

    def run_pair(self, name: str) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any], str]:
        engine_path, golden_path = golden_pair(name)
        self.out.mkdir(exist_ok=True)
        draft = self.out / golden_path.name
        golden_text = golden_path.read_text(encoding="utf-8")
        draft.write_text(rb.dumps(started(json.loads(golden_text))), encoding="utf-8")
        code, envelope, stderr = self.import_engine(draft, engine_path)
        self.assertEqual(code, 0, (envelope, stderr))
        return (
            draft,
            envelope,
            json.loads(golden_text),
            json.loads(engine_path.read_text(encoding="utf-8")),
            golden_text,
        )

    def test_the_golden_drafts_are_in_the_tools_own_serialisation(self) -> None:
        for name in PAIRS:
            with self.subTest(pair=name):
                text = golden_pair(name)[1].read_text(encoding="utf-8")
                self.assertEqual(rb.dumps(json.loads(text)), text)

    def test_each_raw_report_imports_to_the_draft_beside_it(self) -> None:
        for name in PAIRS:
            with self.subTest(pair=name):
                draft, _, golden, _, golden_text = self.run_pair(name)
                self.assertEqual(read_json(draft), golden)
                self.assertEqual(draft.read_text(encoding="utf-8"), golden_text)

    def test_the_imported_draft_validates_and_renders(self) -> None:
        for name in PAIRS:
            with self.subTest(pair=name):
                draft = self.run_pair(name)[0]
                document = read_json(draft)
                self.assertEqual(vr.validate_document(document).errors, [])
                self.assertTrue(render_report.render(document))

    def test_the_adapters_own_warnings_are_the_ones_expected(self) -> None:
        for name, expected in PAIRS.items():
            with self.subTest(pair=name):
                envelope = self.run_pair(name)[1]
                adapter_warnings = [w for w in envelope["warnings"] if not w.startswith("/")]
                self.assertEqual(adapter_warnings, expected)

    def test_every_engine_verdict_and_finding_comes_through_and_the_score_is_the_engines(self) -> None:
        for name in PAIRS:
            with self.subTest(pair=name):
                draft, _, _, engine, _ = self.run_pair(name)
                document = read_json(draft)
                self.assertEqual(
                    {c["id"]: (c["verdict"], c["engine_verdict"]) for c in document["checks"]},
                    {c["id"]: (c["verdict"], c["verdict"]) for c in engine["checks"]},
                )
                self.assertEqual([f["check"] for f in document["findings"]], [f["check"] for f in engine["findings"]])
                self.assertEqual(document["summary"]["phase1_score"], engine["summary"]["phase1_score"])
                self.assertEqual({c["method"] for c in document["checks"]}, {"automated"})
                self.assertEqual({f["disposition"] for f in document["findings"]}, {"pending"})

    def test_a_finding_the_engine_raised_twice_keeps_both_with_the_second_numbered(self) -> None:
        draft = self.run_pair("digital-assistant-server")[0]
        keys = [f["key"] for f in read_json(draft)["findings"] if f["check"] == "AGT-08"]
        self.assertEqual(keys, ["AGT-08", "AGT-08:2"])

    def test_no_evidence_item_names_a_place_outside_the_repository_or_a_placeholder(self) -> None:
        for name in PAIRS:
            with self.subTest(pair=name):
                document = read_json(self.run_pair(name)[0])
                paths = [
                    item["path"]
                    for finding in document["findings"]
                    for item in finding["evidence"]
                    if item["kind"] == "file"
                ]
                self.assertTrue(paths)
                self.assertFalse([p for p in paths if p.startswith(("/", "<", "("))], paths)
                self.assertFalse([p for p in paths if ":" in p], paths)

    def test_a_key_in_an_evidence_path_is_a_note_that_does_not_say_what_it_means(self) -> None:
        document = read_json(self.run_pair("agentic-tdd")[0])
        base = next(f for f in document["findings"] if f["check"] == "BASE-01")
        self.assertEqual(
            [(i["path"], i["note"]) for i in base["evidence"]],
            [("package.json", "lint"), ("package.json", "security"), ("package.json", "typecheck")],
        )

    def test_the_whole_audit_goes_on_from_the_imported_draft_to_a_final_report(self) -> None:
        """Import the real report, dispute a check, add the agent's two checks, decide every finding, and finalise."""
        engine_path, _ = golden_pair("digital-assistant-sdk")
        engine = json.loads(engine_path.read_text(encoding="utf-8"))
        engine["provenance"].update(target=str(self.target), git_sha=None)
        draft = self.start()
        code, envelope, _ = self.import_engine(draft, self.engine_file(engine))
        self.assertEqual(code, 0, envelope)
        before = read_json(draft)["summary"]["phase1_score"]
        raised = next(f for f in read_json(draft)["findings"] if f["check"] == "TOOL-03")
        code, envelope, _ = self.decide(
            draft,
            "--via",
            "interactive",
            "--finding",
            raised["id"],
            "--disposition",
            "rejected",
            "--note",
            "Inherited.",
        )
        self.assertEqual(code, 0, envelope)
        code, envelope, _ = self.add_check(
            draft,
            {
                "id": "TOOL-03",
                "verdict": "PASS",
                "summary": "tsconfig.json extends a base that sets strict.",
                "override_reason": "tsconfig.base.json sets strict: true and tsconfig.json extends it.",
                "evidence": [{"kind": "file", "path": "tsconfig.base.json", "quote": "strict: true"}],
            },
        )
        self.assertEqual((code, envelope["data"]["action"]), (0, "overridden"), envelope)
        self.assertGreater(read_json(draft)["summary"]["phase1_score"], before)
        for check_id in ("AGT-11", "CI-04"):
            self.assertEqual(self.add_check(draft, agent_check(id=check_id))[0], 0)
        findings = [f for f in read_json(draft)["findings"] if f["disposition"] == "pending"]
        decisions = [{"finding": f["id"], "disposition": "confirmed"} for f in findings if f["severity"] != "BLOCKER"]
        for finding in [f for f in findings if f["severity"] == "BLOCKER"]:
            code, envelope, _ = self.decide(
                draft, "--via", "interactive", "--finding", finding["id"], "--disposition", "confirmed"
            )
            self.assertEqual(code, 0, envelope)
        self.assertEqual(self.decide(draft, "--via", "batch", "--from", "-", stdin=json.dumps(decisions))[0], 0)
        code, envelope, _ = self.finalise(draft)
        self.assertEqual(code, 0, envelope)
        final = read_json(envelope["data"]["report"])
        self.assertEqual((final["status"], len(final["checks"]), vr.validate_document(final).errors), ("final", 71, []))
        self.assertTrue(Path(envelope["data"]["markdown"]).read_text(encoding="utf-8"))


class ImportScanFactsTests(ImportCase):
    def test_the_stack_the_components_and_the_inventory_arrive(self) -> None:
        report = er.report(
            self.target,
            stack=dict(
                er.report(self.target)["stack"], ecosystems=["node"], package_managers=["npm"], notes=["a note"]
            ),
            components=[
                {
                    "name": "(root)",
                    "path": ".",
                    "declared": True,
                    "declared_by": "implicit",
                    "manifest": "package.json",
                    "agents_md": "present",
                }
            ],
            candidate_components=["tools/x"],
            inventory={"files_inspected": 12, "files_skipped": 1, "truncated": False},
        )
        document = read_json(self.imported(report)[0])
        self.assertEqual(document["stack"]["ecosystems"], ["node"])
        self.assertEqual(document["stack"]["notes"], ["a note"])
        self.assertEqual([c["path"] for c in document["components"]], [".", "tools/x"])
        self.assertEqual(
            document["coverage"]["inventory"], {"files_inspected": 12, "files_skipped": 1, "truncated": False}
        )
        self.assertEqual(document["coverage"]["scopes_examined"], [])
        self.assertEqual(list(document["coverage"]), ["scopes_examined", "scopes_skipped", "inventory"])
        self.assertEqual(vr.validate_document(document).errors, [])

    def test_a_scan_the_engine_cut_short_is_a_warning_of_the_import(self) -> None:
        report = er.report(self.target, inventory={"files_inspected": 5, "files_skipped": 0, "truncated": True})
        _, envelope = self.imported(report)
        self.assertEqual(
            envelope["warnings"], ["the engine's scan was cut short, so what it did not reach is not in the report"]
        )

    def score_of(self, report: dict[str, Any]) -> float:
        score: float = read_json(self.imported(report)[0])["summary"]["phase1_score"]
        return score

    def test_a_score_that_agrees_with_the_reports_needs_no_warning(self) -> None:
        ours = self.score_of(sample_report(self.target))
        for given in (ours, ours + 0.00001, None):
            with self.subTest(given=given):
                _, envelope = self.imported(sample_report(self.target, summary={"phase1_score": given}))
                self.assertFalse([w for w in envelope["warnings"] if "score" in w], envelope["warnings"])

    def test_a_score_that_differs_is_said_and_the_reports_is_kept(self) -> None:
        ours = self.score_of(sample_report(self.target))
        draft, envelope = self.imported(sample_report(self.target, summary={"phase1_score": 0.9999}))
        self.assertIn(
            f"the engine's phase-1 score is 0.9999 and the report's is {ours}; the report's follows "
            "spec/readiness-summary.md and is the one kept",
            envelope["warnings"],
        )
        self.assertEqual(read_json(draft)["summary"]["phase1_score"], ours)


class RealProbeTests(ImportCase):
    """The engine runs on a small repository of its own, through the launcher, and its real report is imported."""

    def scan(self, test_script: str, *extra: str) -> Path:
        (self.target / "package.json").write_text(json.dumps({"scripts": {"test": test_script}}), encoding="utf-8")
        return er.scan(self.target, self.engine_dir, *extra)

    def check(self, draft: Path, check_id: str) -> dict[str, Any]:
        found: dict[str, Any] = next(c for c in read_json(draft)["checks"] if c["id"] == check_id)
        return found

    def test_a_scan_that_ran_no_probe_gives_a_check_with_no_command(self) -> None:
        report = self.scan('python3 -c "pass"')
        draft = self.start()
        code, envelope, _ = self.import_engine(draft, report)
        self.assertEqual(code, 0, envelope)
        check = self.check(draft, "TST-02")
        self.assertEqual((check["verdict"], check["engine_verdict"]), ("UNKNOWN", "UNKNOWN"))
        self.assertEqual([i for i in check["evidence"] if i["kind"] == "command"], [])
        self.assertEqual(envelope["data"]["probes_carried"], 0)
        self.assertEqual(vr.validate_document(read_json(draft)).errors, [])

    def test_a_probe_that_passed_is_command_evidence_on_the_check(self) -> None:
        report = self.scan('python3 -c "pass"', "--run-gates", "--allow-probe", "test")
        draft = self.start()
        code, envelope, _ = self.import_engine(draft, report)
        self.assertEqual(code, 0, envelope)
        check = self.check(draft, "TST-02")
        self.assertEqual((check["verdict"], check["engine_verdict"]), ("PASS", "PASS"))
        (item,) = [i for i in check["evidence"] if i["kind"] == "command"]
        self.assertEqual(
            (item["captured_by"], item["tool"], item["exit_code"], item["timed_out"]),
            ("tool", "python-agentic-audit", 0, False),
        )
        self.assertEqual(item["command"], "python3 -c pass")
        self.assertEqual(envelope["data"]["probes_carried"], 1)
        document = read_json(draft)
        self.assertEqual(vr.validate_document(document).errors, [])
        self.assertTrue(render_report.render(document))

    def test_a_probe_that_failed_is_evidence_beside_the_finding_it_raised(self) -> None:
        report = self.scan('python3 -c "raise SystemExit(3)"', "--run-gates", "--allow-probe", "test")
        draft = self.start()
        code, envelope, _ = self.import_engine(draft, report)
        self.assertEqual(code, 0, envelope)
        document = read_json(draft)
        check = self.check(draft, "TST-02")
        self.assertEqual(check["verdict"], "FAIL")
        (item,) = [i for i in check["evidence"] if i["kind"] == "command"]
        self.assertEqual(item["exit_code"], 3)
        (finding,) = [f for f in document["findings"] if f["check"] == "TST-02"]
        self.assertIn("exited 3", finding["statement"])
        self.assertEqual([i["kind"] for i in finding["evidence"]], ["file"])
        self.assertEqual(vr.validate_document(document).errors, [])


class WriteFailureTests(ImportCase):
    def test_a_failed_write_leaves_the_previous_draft(self) -> None:
        draft = self.start()
        source = self.engine_file(er.report(self.target))
        with mock.patch("os.replace", side_effect=OSError(5, "Input/output error")):
            code, envelope, _ = self.unchanged_by(draft, lambda: self.import_engine(draft, source))
        self.assertEqual(code, 1)
        self.assertIn("cannot write the draft", envelope["data"]["error"])
        self.assertEqual(self.import_engine(draft, source)[0], 0, "the same import works once the disk does")


if __name__ == "__main__":
    unittest.main()
