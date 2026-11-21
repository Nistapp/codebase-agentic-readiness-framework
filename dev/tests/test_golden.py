# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``golden.py``: the digest is deterministic, and ``compare`` names what differs.

Everything runs in this process, so coverage traces it. The two real runs use a short list of fixtures: one
that needs no git, one that needs a temporary git repository and one that reads the machine-local index state.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import _dev_paths  # noqa: F401

import _common  # noqa: E402
import engine as launcher  # noqa: E402
import golden  # noqa: E402

SMALL = ["agt-01-missing", "exec-ok", "idx-02-no-index"]


def _run(argv: list[str]) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(golden.INFO, golden.handler, argv, stdout=out, stderr=err)
    return code, json.loads(out.getvalue())


class PureHelperTests(unittest.TestCase):
    def test_canonical_ignores_key_order(self) -> None:
        self.assertEqual(golden.canonical({"b": 1, "a": [2]}), golden.canonical({"a": [2], "b": 1}))

    def test_strip_report_drops_the_clock_and_the_checkout_only(self) -> None:
        provenance = {key: "x" for key in golden.STRIPPED_PROVENANCE}
        provenance.update({"ruleset_hash": "h", "target": "."})
        stripped = golden.strip_report({"provenance": provenance, "checks": [1]})
        self.assertEqual(stripped, {"provenance": {"ruleset_hash": "h", "target": "."}, "checks": [1]})

    def test_flatten_names_a_leaf_by_its_path(self) -> None:
        self.assertEqual(golden.flatten({"a": {"b": "1"}, "c": "2"}), {"a/b": "1", "c": "2"})

    def test_differences_reports_changed_missing_and_new(self) -> None:
        old = {"a": {"x": "1" * 64, "y": "2"}, "same": "s"}
        new = {"a": {"x": "3" * 64, "z": "4"}, "same": "s"}
        self.assertEqual(
            golden.differences(old, new),
            ["changed: a/x: " + "1" * 12 + " -> " + "3" * 12, "missing now: a/y", "new now: a/z"],
        )

    def test_no_difference_is_an_empty_list(self) -> None:
        self.assertEqual(golden.differences({"a": "1"}, {"a": "1"}), [])

    def test_isolated_env_sets_and_restores(self) -> None:
        before = {key: os.environ.get(key) for key in ("HOME", "AUDIT_INDEX_STORE")}
        os.environ.pop("AUDIT_INDEX_STORE", None)
        try:
            with golden.isolated_env(Path("/nowhere")):
                self.assertEqual(os.environ["HOME"], "/nowhere")
                self.assertEqual(os.environ["AUDIT_INDEX_STORE"], golden.ABSENT_STORE)
            self.assertNotIn("AUDIT_INDEX_STORE", os.environ)
            self.assertEqual(os.environ.get("HOME"), before["HOME"])
        finally:
            if before["AUDIT_INDEX_STORE"] is not None:
                os.environ["AUDIT_INDEX_STORE"] = before["AUDIT_INDEX_STORE"]


class RunScriptTests(unittest.TestCase):
    def _script(self, tmp: str, body: str) -> Path:
        path = Path(tmp) / "tool.py"
        path.write_text(body, encoding="utf-8")
        return path

    def test_returns_exit_code_and_stdout_and_restores_argv_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = self._script(tmp, "import sys\nprint(sys.argv[1])\nraise SystemExit(7)\n")
            argv, path = list(sys.argv), list(sys.path)
            self.assertEqual(golden.run_script(script, ["hello"]), (7, "hello\n"))
            self.assertEqual((sys.argv, sys.path), (argv, path))

    def test_a_script_that_just_ends_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(golden.run_script(self._script(tmp, "print('x')\n"), []), (0, "x\n"))

    def test_a_string_exit_code_counts_as_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(golden.run_script(self._script(tmp, "raise SystemExit('boom')\n"), [])[0], 1)

    def test_tools_describe_hashes_each_public_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for folder in golden.TOOL_FOLDERS:
                (repo / folder).mkdir(parents=True)
            (repo / "audit/tools/one.py").write_text("print('1')\n", encoding="utf-8")
            (repo / "audit/tools/_private.py").write_text("print('p')\n", encoding="utf-8")
            (repo / "implement/tools/two.py").write_text("print('2')\n", encoding="utf-8")
            found = golden.tools_describe(repo)
            self.assertEqual(sorted(found), ["audit/tools/one.py", "implement/tools/two.py"])
            self.assertEqual(found["audit/tools/one.py"], golden.sha256(b"0\n1\n"))


class DigestFileTests(unittest.TestCase):
    def test_write_then_read_round_trips_and_never_replaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest = {"digest_version": golden.DIGEST_VERSION, "b": "1", "a": "2"}
            path = golden.write_digest(Path(tmp) / "new", digest)
            self.assertEqual(golden.read_digest(path.parent), digest)
            self.assertLess(path.read_text().index('"a"'), path.read_text().index('"b"'))
            with self.assertRaises(_common.UsageError):
                golden.write_digest(path.parent, digest)

    def test_read_refuses_a_missing_a_broken_and_a_foreign_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with self.assertRaises(_common.UsageError):
                golden.read_digest(directory)
            (directory / golden.DIGEST_NAME).write_text("{not json", encoding="utf-8")
            with self.assertRaises(_common.UsageError):
                golden.read_digest(directory)
            (directory / golden.DIGEST_NAME).write_text('{"digest_version": 99}', encoding="utf-8")
            with self.assertRaises(_common.UsageError):
                golden.read_digest(directory)


class HandlerTests(unittest.TestCase):
    def _record(self, digest: dict[str, Any]) -> Any:
        return mock.patch.object(golden, "record_digest", return_value=digest)

    def test_record_then_compare_match(self) -> None:
        digest = {"digest_version": golden.DIGEST_VERSION, "catalogue": "c"}
        with tempfile.TemporaryDirectory() as tmp, self._record(digest):
            code, envelope = _run(["record", "--out", tmp + "/d"])
            self.assertEqual((code, envelope["data"]["entries"]), (0, 2))
            code, envelope = _run(["compare", tmp + "/d"])
            self.assertEqual((code, envelope["data"]["differences"]), (0, []))

    def test_compare_exits_two_and_lists_each_difference(self) -> None:
        recorded = {"digest_version": golden.DIGEST_VERSION, "catalogue": "c", "gone": "g"}
        now = {"digest_version": golden.DIGEST_VERSION, "catalogue": "d", "fresh": "f"}
        with tempfile.TemporaryDirectory() as tmp:
            golden.write_digest(Path(tmp), recorded)
            with self._record(now):
                code, envelope = _run(["compare", tmp])
        self.assertEqual(code, 2)
        self.assertEqual(
            envelope["data"]["errors"], ["changed: catalogue: c -> d", "new now: fresh", "missing now: gone"]
        )

    def test_usage_errors_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_run(["compare", tmp + "/none"])[0], 1)
            self.assertEqual(_run(["record"])[0], 1)
            self.assertEqual(_run([])[0], 1)
            golden.write_digest(Path(tmp) / "d", {"digest_version": golden.DIGEST_VERSION})
            self.assertEqual(_run(["record", "--out", tmp + "/d"])[0], 1)

    def test_describe_names_both_verbs(self) -> None:
        code, envelope = _run(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["name"], "golden")
        self.assertEqual(len(envelope["data"]["synopsis"]), 2)


class RealRunTests(unittest.TestCase):
    def test_every_fixture_folder_is_listed_sorted(self) -> None:
        names = golden.fixture_names()
        self.assertEqual(names, sorted(names))
        self.assertIn("exec-ok", names)

    def test_tool_scripts_are_the_public_tools_of_both_folders(self) -> None:
        names = {p.relative_to(golden.REPO).as_posix() for p in golden.tool_scripts()}
        self.assertIn("audit/tools/engine.py", names)
        self.assertIn("implement/tools/progress.py", names)
        self.assertFalse([n for n in names if "/_" in n])

    def test_list_checks_names_the_ruleset(self) -> None:
        hashes, ruleset = golden.list_checks()
        self.assertEqual(sorted(hashes), ["json", "text"])
        self.assertEqual(sorted(ruleset), ["engine_version", "hash", "revision"])

    def test_record_twice_gives_the_same_bytes_and_compare_agrees(self) -> None:
        with mock.patch.object(golden, "fixture_names", return_value=SMALL):
            first, second = golden.record_digest(), golden.record_digest()
            self.assertEqual(first, second)
            self.assertEqual(sorted(first["engine_reports"]), SMALL)
            self.assertEqual(
                sorted(first["skill_zips"]),
                [
                    f"agentic-readiness-audit-{golden.ARCHIVE_TAG}.zip",
                    f"agentic-readiness-implement-{golden.ARCHIVE_TAG}.zip",
                ],
            )
            with tempfile.TemporaryDirectory() as tmp:
                golden.write_digest(Path(tmp), first)
                code, envelope = _run(["compare", tmp])
                self.assertEqual((code, envelope["data"]["differences"]), (0, []))

    def test_a_failing_engine_run_is_a_tool_error(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(launcher, "run_engine", return_value=(3, "", "boom")),
        ):
            matrix = golden.engine_matrix()
            with self.assertRaises(_common.ToolError):
                golden.fixture_report(matrix, "agt-01-missing", Path(tmp))

    def test_the_report_of_a_git_fixture_does_not_depend_on_where_it_is_built(self) -> None:
        matrix = golden.engine_matrix()
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            with golden.isolated_env(Path(one)):
                first = golden.fixture_report(matrix, "exec-ok", Path(one))
                second = golden.fixture_report(matrix, "exec-ok", Path(two))
        self.assertEqual(golden.canonical(first), golden.canonical(second))
        self.assertNotIn("scanned_at", first["provenance"])


if __name__ == "__main__":
    unittest.main()
