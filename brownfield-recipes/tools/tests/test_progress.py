# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`progress.py init`, `show` and `render`: the state they write, what they refuse, and how they fail.

`init` runs on the framework's own synthetic example report, which holds confirmed, edited, rejected and deferred
findings, copied into a temporary target. Its output must equal the checked-in example state and its Markdown byte for
byte. `render` must give the same bytes for the same state in any key order, and an interrupted write must leave the
old file whole. Standard library only.
"""

from __future__ import annotations

import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence
from unittest import mock

import _paths
import _common
import progress

RECIPES = _paths.TOOLS.parent
EXAMPLES = RECIPES / "schema" / "examples"
REPORT = EXAMPLES / "example-service.audit-report.20261010T094207Z.json"
DRAFT = EXAMPLES / "realistic" / "digital-assistant-server.audit-draft.20261010T065739Z.json"
EXAMPLE_STATE = EXAMPLES / "readiness-state.example-service.json"
EXAMPLE_MD = EXAMPLES / "readiness-state.example-service.md"
LATER_STATE = EXAMPLES / "readiness-state.example-service.in-progress.json"
LATER_MD = EXAMPLES / "readiness-state.example-service.in-progress.md"
REPORT_DIR = "docs/agentic-readiness-report"
JSON_NAME = "example-service-agentic-readiness-state.json"
MD_NAME = "example-service-agentic-readiness-STATE.md"
# The values the checked-in example was made with.
EXAMPLE_ARGS = ("--date", "2026-10-29", "--framework-rev", "cafecafecafecafecafecafecafecafecafecafe")


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    """Run the tool in process. Returns the exit code, the parsed envelope and stderr."""
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(progress.INFO, progress.handler, list(argv), stdout=out, stderr=err)
    envelope: dict[str, Any] = json.loads(out.getvalue())
    return code, envelope, err.getvalue()


def reversed_keys(value: Any) -> Any:
    """`value` with every object's keys in reverse order."""
    if isinstance(value, dict):
        return {key: reversed_keys(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [reversed_keys(entry) for entry in value]
    return value


class TargetCase(unittest.TestCase):
    """A temporary target that holds the example report where an audit leaves it."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="progress-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.target = self.tmp / "example-service"
        (self.target / REPORT_DIR).mkdir(parents=True)
        self.report = self.target / REPORT_DIR / REPORT.name
        shutil.copyfile(REPORT, self.report)
        self.state_dir = self.target / "docs" / "agentic-readiness"
        self.json_path = self.state_dir / JSON_NAME
        self.md_path = self.state_dir / MD_NAME

    def init(self, *extra: str, report: Path | None = None) -> tuple[int, dict[str, Any], str]:
        return call(["init", "--report", str(report or self.report), "--target", str(self.target), *extra])

    def init_ok(self) -> dict[str, Any]:
        code, envelope, err = self.init(*EXAMPLE_ARGS)
        self.assertEqual(code, 0, (envelope, err))
        return envelope

    def place_state(self, source: Path) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, self.json_path)

    def temporaries(self) -> list[str]:
        return sorted(path.name for path in self.state_dir.iterdir() if path.name.endswith(".tmp"))


class ThemeMapTests(unittest.TestCase):
    def test_every_catalogue_check_has_exactly_one_theme(self) -> None:
        catalogue = json.loads((RECIPES / "catalogue.json").read_text(encoding="utf-8"))
        checks = sorted(check["id"] for check in catalogue["checks"])
        mapped = [check for _, _, owned in progress.THEMES for check in owned]
        self.assertEqual(len(mapped), len(set(mapped)), "a check is in two themes")
        self.assertEqual(sorted(mapped), checks)

    def test_the_themes_are_t1_to_t8_in_order(self) -> None:
        self.assertEqual(progress.THEME_IDS, tuple(f"T{number}" for number in range(1, 9)))


class ContractTests(unittest.TestCase):
    def test_describe_names_the_one_write_inside_the_target(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        manifest = envelope["data"]
        self.assertEqual(manifest, progress.INFO.manifest())
        self.assertEqual(manifest["name"], "progress")
        self.assertIs(manifest["writes_inside_target"], True)
        self.assertIs(manifest["network"], False)
        self.assertIn("docs/agentic-readiness/<label>-agentic-readiness-state.json", manifest["writes"])

    def test_no_subcommand_is_a_usage_error(self) -> None:
        code, envelope, _ = call([])
        self.assertEqual((code, envelope["ok"]), (1, False))


class InitTests(TargetCase):
    def test_init_writes_the_example_state_and_its_markdown(self) -> None:
        envelope = self.init_ok()
        self.assertEqual(self.json_path.read_bytes(), EXAMPLE_STATE.read_bytes())
        self.assertEqual(self.md_path.read_bytes(), EXAMPLE_MD.read_bytes())
        data = envelope["data"]
        self.assertEqual((data["label"], data["items"], data["not_queued"]), ("example-service", 8, 2))
        self.assertEqual(data["statuses"]["queued"], 7)
        self.assertEqual(data["statuses"]["deferred"], 1)
        self.assertEqual(self.temporaries(), [])

    def test_init_maps_each_disposition(self) -> None:
        self.init_ok()
        state = json.loads(self.json_path.read_text(encoding="utf-8"))
        items = {item["finding"]: item for item in state["items"]}
        self.assertEqual(sorted(items), ["F-001", "F-002", "F-003", "F-004", "F-006", "F-007", "F-008", "F-010"])
        self.assertEqual([entry["finding"] for entry in state["not_queued"]], ["F-005", "F-009"])
        self.assertEqual(state["not_queued"][0]["note"], "Placeholder values in a unit test, not credentials.")
        edited = items["F-003"]
        self.assertEqual((edited["status"], edited["theme"]), ("queued", "T2"))
        self.assertTrue(edited["notes"].startswith("Edited during the audit: The owner pins Node 22"))
        deferred = items["F-010"]
        self.assertEqual((deferred["status"], deferred["by"], deferred["theme"]), ("deferred", "owner", "T7"))
        self.assertTrue(deferred["reason"].startswith("The team uses two of the harnesses"))
        self.assertEqual(items["F-004"]["theme"], "T3")
        self.assertEqual(state["source_reports"][0]["path"], f"{REPORT_DIR}/{REPORT.name}")
        self.assertEqual(state["source_reports"][0]["git_sha"], "deadbeef" * 5)
        self.assertEqual(state["repo"], {"label": "example-service", "default_branch": "main"})

    def test_init_takes_the_default_branch_and_phase_given(self) -> None:
        code, _, _ = self.init(*EXAMPLE_ARGS, "--default-branch", "dev", "--phase", "IR03.1")
        self.assertEqual(code, 0)
        state = json.loads(self.json_path.read_text(encoding="utf-8"))
        self.assertEqual(state["repo"]["default_branch"], "dev")
        self.assertEqual(state["log"][0]["phase"], "IR03.1")

    def test_init_records_this_checkout_by_default(self) -> None:
        with mock.patch.object(progress, "framework_revision", return_value="ab" * 20):
            code, _, _ = self.init("--date", "2026-10-29")
        self.assertEqual(code, 0)
        state = json.loads(self.json_path.read_text(encoding="utf-8"))
        self.assertEqual(state["recipe"]["framework_rev"], "ab" * 20)

    def test_init_refuses_an_existing_state(self) -> None:
        self.init_ok()
        before = self.json_path.read_bytes()
        code, envelope, _ = self.init(*EXAMPLE_ARGS)
        self.assertEqual(code, 1)
        self.assertIn("a state already exists", envelope["data"]["error"])
        self.assertEqual(self.json_path.read_bytes(), before)

    def test_init_refuses_a_draft(self) -> None:
        draft = self.target / REPORT_DIR / DRAFT.name
        shutil.copyfile(DRAFT, draft)
        code, envelope, _ = self.init(*EXAMPLE_ARGS, report=draft)
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["error"], "the report is a draft, not final")
        self.assertFalse(self.state_dir.exists())

    def test_init_refuses_an_invalid_report(self) -> None:
        report = json.loads(self.report.read_text(encoding="utf-8"))
        report["findings"][0]["severity"] = "CRITICAL"
        self.report.write_text(json.dumps(report), encoding="utf-8")
        code, envelope, _ = self.init(*EXAMPLE_ARGS)
        self.assertEqual(code, 2)
        self.assertIn("the report is not valid", envelope["data"]["error"])
        self.assertFalse(self.state_dir.exists())

    def test_init_refuses_a_report_outside_the_target(self) -> None:
        code, envelope, _ = self.init(*EXAMPLE_ARGS, report=REPORT)
        self.assertEqual(code, 1)
        self.assertIn("the report must be inside the target", envelope["data"]["error"])

    def test_init_refuses_a_missing_report(self) -> None:
        code, envelope, _ = self.init(report=self.target / "nothing.json")
        self.assertEqual(code, 1)
        self.assertIn("report not found", envelope["data"]["error"])

    def test_init_refuses_a_state_folder_that_leaves_the_target(self) -> None:
        outside = self.tmp / "elsewhere"
        outside.mkdir()
        (self.target / "docs" / "agentic-readiness").symlink_to(outside, target_is_directory=True)
        code, envelope, _ = self.init(*EXAMPLE_ARGS)
        self.assertEqual(code, 1)
        self.assertIn("the path leaves the target", envelope["data"]["error"])
        self.assertEqual(list(outside.iterdir()), [])

    def test_init_refuses_a_state_file_that_is_a_symlink(self) -> None:
        self.state_dir.mkdir(parents=True)
        decoy = self.tmp / "decoy.md"
        decoy.write_text("keep\n", encoding="utf-8")
        self.md_path.symlink_to(decoy)
        code, envelope, _ = self.init(*EXAMPLE_ARGS)
        self.assertEqual(code, 1)
        self.assertIn("is a symlink", envelope["data"]["error"])
        self.assertEqual(decoy.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse(self.json_path.exists())

    def test_init_refuses_a_check_with_no_theme(self) -> None:
        reduced = {check: theme for check, theme in progress.CHECK_THEME.items() if check != "CMD-01"}
        with mock.patch.object(progress, "CHECK_THEME", reduced):
            code, envelope, _ = self.init(*EXAMPLE_ARGS)
        self.assertEqual(code, 2)
        self.assertIn("checks with no theme: CMD-01", envelope["data"]["error"])
        self.assertFalse(self.json_path.exists())

    def test_init_refuses_a_bad_date_and_sha(self) -> None:
        for extra, message in ((("--date", "29-10-2026"), "--date must be"), (("--framework-rev", "XYZ"), "7 to 40")):
            with self.subTest(extra):
                code, envelope, _ = self.init(*extra)
                self.assertEqual(code, 1)
                self.assertIn(message, envelope["data"]["error"])

    def test_a_killed_init_leaves_no_state_and_no_temporary_file(self) -> None:
        with mock.patch("os.replace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                progress.handler(["init", "--report", str(self.report), "--target", str(self.target), *EXAMPLE_ARGS])
        self.assertFalse(self.json_path.exists())
        self.assertEqual(self.temporaries(), [])


class ShowTests(TargetCase):
    def test_show_summarises_the_state(self) -> None:
        self.place_state(LATER_STATE)
        code, envelope, err = call(["show", "--target", str(self.target)])
        self.assertEqual(code, 0)
        data = envelope["data"]
        self.assertEqual(data["label"], "example-service")
        self.assertEqual(data["statuses"]["partial"], 1)
        self.assertEqual(data["skipped"], ["F-004"])
        self.assertEqual((data["debt"], data["preferences"], data["not_queued"]), (1, 2, 2))
        self.assertEqual(data["themes"][0], {"id": "T1", "status": "merged", "items": 2, "open": 1})
        self.assertIn("8 items (3 queued, 1 in_progress, 1 done, 1 partial, 1 deferred, 1 skipped)", err)

    def test_show_json_prints_the_state(self) -> None:
        self.place_state(LATER_STATE)
        code, envelope, _ = call(["show", "--target", str(self.target), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["state"], json.loads(LATER_STATE.read_text(encoding="utf-8")))
        self.assertIs(envelope["truncated"], False)

    def test_show_json_bounds_a_long_log_and_keeps_the_newest(self) -> None:
        state = json.loads(LATER_STATE.read_text(encoding="utf-8"))
        state["log"] = [
            {"date": "2026-11-01", "phase": "IR04.2", "event": f"event {n} " + "x" * 400} for n in range(60)
        ]
        self.state_dir.mkdir(parents=True)
        self.json_path.write_text(json.dumps(state), encoding="utf-8")
        code, envelope, _ = call(["show", "--target", str(self.target), "--json"])
        self.assertEqual(code, 0)
        self.assertIs(envelope["truncated"], True)
        shown = envelope["data"]["state"]["log"]
        self.assertTrue(shown[-1]["event"].startswith("event 59 "))
        self.assertEqual(len(shown) + envelope["data"]["omitted"]["log"], 60)

    def test_show_needs_a_state(self) -> None:
        code, envelope, err = call(["show", "--target", str(self.target)])
        self.assertEqual(code, 1)
        self.assertIn("no state in", envelope["data"]["error"])
        self.assertIn("progress.py init", err)

    def test_two_states_need_a_label(self) -> None:
        self.place_state(LATER_STATE)
        other = json.loads(LATER_STATE.read_text(encoding="utf-8"))
        other["repo"]["label"] = "other"
        (self.state_dir / "other-agentic-readiness-state.json").write_text(json.dumps(other), encoding="utf-8")
        code, envelope, _ = call(["show", "--target", str(self.target)])
        self.assertEqual(code, 1)
        self.assertIn("pick one with --label: example-service, other", envelope["data"]["error"])
        code, envelope, _ = call(["show", "--target", str(self.target), "--label", "other"])
        self.assertEqual((code, envelope["data"]["label"]), (0, "other"))

    def test_show_refuses_an_invalid_state(self) -> None:
        state = json.loads(LATER_STATE.read_text(encoding="utf-8"))
        state["items"][0]["status"] = "skipped"
        self.state_dir.mkdir(parents=True)
        self.json_path.write_text(json.dumps(state), encoding="utf-8")
        code, envelope, _ = call(["show", "--target", str(self.target)])
        self.assertEqual(code, 2)
        self.assertTrue(any("needs a reason" in error for error in envelope["data"]["errors"]))

    def test_show_refuses_a_repeated_key(self) -> None:
        self.state_dir.mkdir(parents=True)
        self.json_path.write_text('{"schema_version": "0.1", "schema_version": "0.1"}', encoding="utf-8")
        code, envelope, _ = call(["show", "--target", str(self.target)])
        self.assertEqual(code, 2)
        self.assertIn("repeats the key", envelope["data"]["error"])


class RenderTests(TargetCase):
    def test_render_writes_the_golden_markdown(self) -> None:
        self.place_state(LATER_STATE)
        code, envelope, _ = call(["render", "--target", str(self.target)])
        self.assertEqual(code, 0)
        self.assertEqual(self.md_path.read_bytes(), LATER_MD.read_bytes())
        self.assertEqual(envelope["data"]["bytes"], len(LATER_MD.read_bytes()))

    def test_render_is_byte_stable_across_runs_key_order_and_list_order(self) -> None:
        state = json.loads(LATER_STATE.read_text(encoding="utf-8"))
        expected = progress.render(state)
        self.assertEqual(progress.render(copy.deepcopy(state)), expected)
        self.assertEqual(progress.render(reversed_keys(state)), expected)
        shuffled = copy.deepcopy(state)
        for key in ("items", "not_queued", "preferences", "themes", "source_reports"):
            shuffled[key].reverse()
        self.assertEqual(progress.render(shuffled), expected)
        self.assertTrue(expected.endswith("|\n") and not expected.endswith("\n\n"))

    def test_render_escapes_table_cells(self) -> None:
        state = json.loads(LATER_STATE.read_text(encoding="utf-8"))
        state["log"].append({"date": "2026-11-01", "phase": "IR04.2", "event": "a | b\nc"})
        self.assertIn("| 2026-11-01 | IR04.2 | a \\| b c |", progress.render(state))

    def test_render_starts_with_the_heading_and_the_generated_note(self) -> None:
        lines = EXAMPLE_MD.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "# Agentic readiness state: example-service")
        self.assertEqual(lines[2], f"> Generated by `progress.py render` from `{JSON_NAME}`.")
        self.assertIn("Do not edit this file", lines[3])

    def test_a_killed_render_leaves_the_old_file_whole(self) -> None:
        self.place_state(LATER_STATE)
        self.md_path.write_text("old view\n", encoding="utf-8")
        with mock.patch("os.replace", side_effect=OSError("killed")):
            code, envelope, _ = call(["render", "--target", str(self.target)])
        self.assertEqual(code, 3)
        self.assertIn("killed", envelope["data"]["error"])
        self.assertEqual(self.md_path.read_text(encoding="utf-8"), "old view\n")
        self.assertEqual(self.temporaries(), [])

    def test_render_sweeps_a_temporary_file_a_killed_write_left(self) -> None:
        self.place_state(LATER_STATE)
        stale = self.state_dir / f".{MD_NAME}.abc123.tmp"
        stale.write_text("half", encoding="utf-8")
        unrelated = self.state_dir / ".other.tmp"
        unrelated.write_text("keep", encoding="utf-8")
        code, envelope, _ = call(["render", "--target", str(self.target)])
        self.assertEqual(code, 0)
        self.assertFalse(stale.exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(len(envelope["warnings"]), 1)

    def test_render_refuses_a_state_whose_label_differs_from_its_name(self) -> None:
        state = json.loads(LATER_STATE.read_text(encoding="utf-8"))
        state["repo"]["label"] = "other"
        self.state_dir.mkdir(parents=True)
        self.json_path.write_text(json.dumps(state), encoding="utf-8")
        code, envelope, _ = call(["render", "--target", str(self.target)])
        self.assertEqual(code, 2)
        self.assertIn("is for 'other'", envelope["data"]["error"])
        self.assertFalse(self.md_path.exists())

    def test_render_refuses_a_markdown_file_that_is_a_symlink(self) -> None:
        self.place_state(LATER_STATE)
        decoy = self.tmp / "decoy.md"
        decoy.write_text("keep\n", encoding="utf-8")
        self.md_path.symlink_to(decoy)
        code, _, _ = call(["render", "--target", str(self.target)])
        self.assertEqual(code, 1)
        self.assertEqual(decoy.read_text(encoding="utf-8"), "keep\n")
        self.assertTrue(os.path.islink(self.md_path))


if __name__ == "__main__":
    unittest.main()
