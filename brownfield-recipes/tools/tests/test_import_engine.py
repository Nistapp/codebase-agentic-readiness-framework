# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`report.py import-engine`: the engine's report becomes the draft's automated checks, once, and only for its own target.

A test builds a small engine report (schema v2) as a dictionary, or reads one of the engine's real reports, writes it
to a folder of its own, and runs the tool in process through `run_tool`, so that the envelope and the exit code are what
a recipe sees. Every refusal must leave the draft's bytes and the folder's files as they were. Standard library only.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import _paths
import report as rb
import validate_report as vr
from test_report import BuilderCase, call, read_json, tree_state

TOOLS = _paths.TOOLS
SHA_A = "a" * 40
SHA_B = "b" * 40


def engine_provenance(target: Path | str, **changes: Any) -> dict[str, Any]:
    """The `provenance` object of an engine report, as the engine writes it."""
    provenance: dict[str, Any] = {
        "tool": "python-agentic-audit",
        "version": "0.1.0",
        "ruleset_revision": "2026-09-28.13",
        "ruleset_hash": "0123456789abcdef",
        "scanned_at": "2026-10-10T06:57:38+00:00",
        "target": str(target),
        "git_sha": None,
        "git_branch": None,
        "git_dirty": None,
        "phase": 1,
        "probes_enabled": False,
        "framework_revision": None,
    }
    provenance.update(changes)
    return provenance


def engine_report(target: Path | str, **changes: Any) -> dict[str, Any]:
    """An engine report with a provenance and nothing else. Later tests add the parts they need."""
    report: dict[str, Any] = {"schema_version": "2", "provenance": engine_provenance(target)}
    report.update(changes)
    return report


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
            draft, self.engine_file(engine_report(self.target) if report is None else report)
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
        self.assertEqual(self.import_engine(draft, self.engine_file(engine_report(self.target)))[0], 0)
        after = read_json(draft)
        self.assertEqual(vr.validate_document(after).errors, [])
        self.assertEqual(after["provenance"]["target"], before["provenance"]["target"])
        self.assertEqual(after["run_context"], before["run_context"])
        self.assertEqual(after["status"], "draft")

    def test_a_revision_and_a_scan_time_the_engine_did_not_give_are_left_out(self) -> None:
        provenance = engine_provenance(self.target)
        del provenance["ruleset_revision"], provenance["scanned_at"]
        draft, _ = self.imported({"schema_version": "2", "provenance": provenance})
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
        report = engine_report(self.target, future_field={"anything": [1, 2, 3]})
        report["provenance"]["another"] = "ignored"
        draft, _ = self.imported(report)
        self.assertNotIn("another", json.dumps(read_json(draft)))

    def test_the_engine_report_is_read_and_never_written(self) -> None:
        draft = self.start()
        source = self.engine_file(engine_report(self.target))
        before, folder = source.read_bytes(), tree_state(self.engine_dir)
        self.assertEqual(self.import_engine(draft, source)[0], 0)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(tree_state(self.engine_dir), folder)

    def test_it_writes_nothing_but_the_draft_and_does_not_touch_the_target(self) -> None:
        draft = self.start()
        target = tree_state(self.target)
        self.import_engine(draft, self.engine_file(engine_report(self.target)))
        self.assertEqual(tree_state(self.target), target)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [draft.name])

    def test_the_script_runs_from_another_directory_and_prints_one_envelope(self) -> None:
        draft = self.start()
        source = self.engine_file(engine_report(self.target))
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
        self.assertIn("imported the engine report", done.stderr)

    def test_the_describe_manifest_lists_the_subcommand(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertIn("report.py import-engine <draft> <engine report>", envelope["data"]["synopsis"])


class OnceTests(ImportCase):
    def test_a_second_import_is_refused_and_leaves_the_draft_as_it_was(self) -> None:
        draft, _ = self.imported()
        again = self.engine_file(
            engine_report(self.target, provenance=engine_provenance(self.target, ruleset_hash="fedcba9876543210")),
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
        source = self.engine_file(engine_report(self.target))
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
                report = engine_report(self.target)
                report["schema_version"] = version
                envelope = self.refused(self.draft, self.engine_file(report))
                self.assertIn(f"schema_version {version!r}", envelope["data"]["error"])
                self.assertIn("reads only '2'", envelope["data"]["error"])

    def test_a_missing_schema_version_is_refused(self) -> None:
        report = engine_report(self.target)
        del report["schema_version"]
        envelope = self.refused(self.draft, self.engine_file(report))
        self.assertIn("schema_version None", envelope["data"]["error"])

    def test_a_report_for_another_phase_is_refused(self) -> None:
        for phase in (0, 2, 7):
            with self.subTest(phase=phase):
                report = engine_report(self.target, provenance=engine_provenance(self.target, phase=phase))
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
                report = engine_report(self.target)
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
                report = engine_report(self.target)
                del report["provenance"][name]
                envelope = self.refused(self.draft, self.engine_file(report))
                self.assertIn(f"'{name}'", " ".join(envelope["data"]["errors"]))

    def test_a_report_with_no_provenance_is_refused(self) -> None:
        envelope = self.refused(self.draft, self.engine_file({"schema_version": "2"}))
        self.assertIn("'provenance'", " ".join(envelope["data"]["errors"]))

    def test_the_errors_are_counted_and_every_one_is_listed(self) -> None:
        report = engine_report(self.target)
        report["provenance"].update(tool=1, version=2)
        envelope = self.refused(self.draft, self.engine_file(report))
        self.assertIn("2 errors", envelope["data"]["error"])
        self.assertEqual(len(envelope["data"]["errors"]), 2)

    def test_a_value_the_report_schema_limits_is_refused_by_the_draft_validation(self) -> None:
        report = engine_report(self.target, provenance=engine_provenance(self.target, ruleset_hash="not-a-hash"))
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
        source = self.engine_file(engine_report(self.target))
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
        envelope = self.refused(draft, self.engine_file(engine_report(other)))
        self.assertIn("not of this draft's target", envelope["data"]["error"])
        self.assertEqual(len(envelope["data"]["errors"]), 1)
        self.assertIn(str(other), envelope["data"]["errors"][0])
        self.assertIn(str(self.target), envelope["data"]["errors"][0])

    def test_the_same_directory_by_another_spelling_is_accepted(self) -> None:
        link = self.root / "link-to-target"
        link.symlink_to(self.target, target_is_directory=True)
        for spelling in (link, f"{self.target}/", f"{self.root}/./My_Service", f"{self.root}/out/../My_Service"):
            with self.subTest(spelling=str(spelling)):
                code, envelope, _ = self.import_engine(self.start(), self.engine_file(engine_report(spelling)))
                self.assertEqual(code, 0, envelope)

    def test_another_commit_is_refused_and_both_are_named(self) -> None:
        draft = self.start()
        self.set_commit(draft, SHA_A)
        report = engine_report(self.target, provenance=engine_provenance(self.target, git_sha=SHA_B))
        envelope = self.refused(draft, self.engine_file(report))
        self.assertIn(SHA_A, envelope["data"]["errors"][0])
        self.assertIn(SHA_B, envelope["data"]["errors"][0])
        self.assertIn("scan again", envelope["data"]["errors"][0])

    def test_the_same_commit_is_accepted_without_a_warning(self) -> None:
        draft = self.start()
        self.set_commit(draft, SHA_A)
        report = engine_report(self.target, provenance=engine_provenance(self.target, git_sha=SHA_A))
        code, envelope, _ = self.import_engine(draft, self.engine_file(report))
        self.assertEqual((code, envelope["warnings"]), (0, []))

    def test_a_commit_known_to_one_side_only_is_accepted_with_a_warning(self) -> None:
        draft = self.start()
        report = engine_report(self.target, provenance=engine_provenance(self.target, git_sha=SHA_B))
        code, envelope, _ = self.import_engine(draft, self.engine_file(report))
        self.assertEqual(code, 0, envelope)
        self.assertEqual(
            envelope["warnings"], ["only the engine knows the target's commit, so the draft's cannot be compared"]
        )
        other = self.start()
        self.set_commit(other, SHA_A)
        code, envelope, _ = self.import_engine(other, self.engine_file(engine_report(self.target), "third.json"))
        self.assertEqual(code, 0, envelope)
        self.assertEqual(
            envelope["warnings"], ["only the draft knows the target's commit, so the engine's cannot be compared"]
        )

    def test_both_a_wrong_target_and_a_wrong_commit_are_listed(self) -> None:
        draft = self.start()
        self.set_commit(draft, SHA_A)
        other = self.root / "Other_Service"
        other.mkdir()
        report = engine_report(other, provenance=engine_provenance(other, git_sha=SHA_B))
        envelope = self.refused(draft, self.engine_file(report))
        self.assertEqual(len(envelope["data"]["errors"]), 2)


class WriteFailureTests(ImportCase):
    def test_a_failed_write_leaves_the_previous_draft(self) -> None:
        draft = self.start()
        source = self.engine_file(engine_report(self.target))
        with mock.patch("os.replace", side_effect=OSError(5, "Input/output error")):
            code, envelope, _ = self.unchanged_by(draft, lambda: self.import_engine(draft, source))
        self.assertEqual(code, 1)
        self.assertIn("cannot write the draft", envelope["data"]["error"])
        self.assertEqual(self.import_engine(draft, source)[0], 0, "the same import works once the disk does")


if __name__ == "__main__":
    unittest.main()
