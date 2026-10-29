# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The shared helpers keep the tool contract: one envelope, four exit codes, bounded output, safe paths.

Standard library only. The helpers are imported directly, and `run_tool` is given string streams, so no
process is started.
"""

from __future__ import annotations

import ast
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence
from unittest import mock

import _paths
import _common

TOOLS = _paths.TOOLS

INFO = _common.ToolInfo(
    name="demo",
    summary="A tool for the tests.",
    synopsis=("demo.py <target>",),
    writes="nothing",
)


def run(handler: _common.Handler, argv: Sequence[str] = (), **kwargs: Any) -> tuple[int, dict[str, Any], str]:
    """Run a handler under the contract. Returns the exit code, the parsed envelope and stderr."""
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(INFO, handler, list(argv), stdout=out, stderr=err, **kwargs)
    envelope: dict[str, Any] = json.loads(out.getvalue())
    return code, envelope, err.getvalue()


def never_called(argv: Sequence[str]) -> _common.Result:
    raise AssertionError("the handler must not run")


class EnvelopeTests(unittest.TestCase):
    def test_success_has_the_six_keys_in_order(self) -> None:
        code, envelope, err = run(lambda argv: _common.Result(data={"n": 1}, summary="did it", warnings=["w"]))
        self.assertEqual(code, 0)
        self.assertEqual(list(envelope), ["tool", "version", "ok", "data", "warnings", "truncated"])
        self.assertEqual(envelope["tool"], "demo")
        self.assertEqual(envelope["version"], _common.TOOLS_VERSION)
        self.assertIs(envelope["ok"], True)
        self.assertEqual(envelope["data"], {"n": 1})
        self.assertEqual(envelope["warnings"], ["w"])
        self.assertIs(envelope["truncated"], False)
        self.assertEqual(err, "did it\n")

    def test_stdout_is_one_json_object_and_nothing_else(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        _common.run_tool(INFO, lambda argv: _common.Result(data={}), [], stdout=out, stderr=err)
        text = out.getvalue()
        self.assertTrue(text.endswith("}\n"))
        self.assertEqual(json.loads(text)["ok"], True)

    def test_same_input_gives_the_same_bytes(self) -> None:
        def handler(argv: Sequence[str]) -> _common.Result:
            return _common.Result(data={"b": 2, "a": [1, 2, 3]})

        first, second = io.StringIO(), io.StringIO()
        for stream in (first, second):
            _common.run_tool(INFO, handler, [], stdout=stream, stderr=io.StringIO())
        self.assertEqual(first.getvalue(), second.getvalue())

    def test_non_ascii_text_is_kept_as_it_is(self) -> None:
        out = io.StringIO()
        _common.run_tool(
            INFO, lambda argv: _common.Result(data={"t": "Diátaxis"}), [], stdout=out, stderr=io.StringIO()
        )
        self.assertIn("Diátaxis", out.getvalue())

    def test_truncated_flag_is_carried(self) -> None:
        _, envelope, _ = run(lambda argv: _common.Result(data={}, truncated=True))
        self.assertIs(envelope["truncated"], True)


class ExitCodeTests(unittest.TestCase):
    def test_usage_error_is_1(self) -> None:
        def handler(argv: Sequence[str]) -> _common.Result:
            raise _common.UsageError("no such thing")

        code, envelope, err = run(handler)
        self.assertEqual(code, 1)
        self.assertIs(envelope["ok"], False)
        self.assertEqual(envelope["data"], {"error": "no such thing"})
        self.assertEqual(err, "demo: no such thing\n")

    def test_validation_failure_is_2_and_lists_the_errors(self) -> None:
        def handler(argv: Sequence[str]) -> _common.Result:
            raise _common.ValidationFailed("2 problems", errors=["a is wrong", "b is wrong"])

        code, envelope, err = run(handler)
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["errors"], ["a is wrong", "b is wrong"])
        self.assertIn("a is wrong", err)

    def test_a_long_error_list_is_bounded_and_says_so(self) -> None:
        errors = [f"error {n}: " + "x" * 200 for n in range(1000)]

        def handler(argv: Sequence[str]) -> _common.Result:
            raise _common.ValidationFailed("many problems", errors=errors)

        code, envelope, _ = run(handler)
        self.assertEqual(code, 2)
        self.assertIs(envelope["truncated"], True)
        self.assertEqual(len(envelope["data"]["errors"]) + envelope["data"]["errors_omitted"], 1000)
        self.assertEqual(envelope["data"]["errors"][0], errors[0])

    def test_an_unexpected_exception_is_3_with_a_traceback_and_still_an_envelope(self) -> None:
        def handler(argv: Sequence[str]) -> _common.Result:
            raise KeyError("boom")

        code, envelope, err = run(handler)
        self.assertEqual(code, 3)
        self.assertIs(envelope["ok"], False)
        self.assertIn("KeyError", envelope["data"]["error"])
        self.assertIn("Traceback", err)

    def test_a_huge_message_is_clipped(self) -> None:
        def handler(argv: Sequence[str]) -> _common.Result:
            raise _common.UsageError("m" * 100_000)

        code, envelope, _ = run(handler)
        self.assertEqual(code, 1)
        self.assertLess(len(envelope["data"]["error"]), _common.MAX_MESSAGE_CHARS + 10)

    def test_output_over_the_limit_is_3_and_nothing_partial_is_printed(self) -> None:
        code, envelope, _ = run(lambda argv: _common.Result(data={"big": "x" * (_common.MAX_OUTPUT_BYTES + 1)}))
        self.assertEqual(code, 3)
        self.assertIs(envelope["ok"], False)
        self.assertIn("limit", envelope["data"]["error"])

    def test_the_exit_codes_are_the_documented_four(self) -> None:
        self.assertEqual(
            (_common.EXIT_OK, _common.EXIT_USAGE, _common.EXIT_INVALID, _common.EXIT_INTERNAL), (0, 1, 2, 3)
        )
        self.assertEqual(sorted(_common.EXIT_CODES), ["0", "1", "2", "3"])


class DescribeTests(unittest.TestCase):
    def test_describe_prints_the_manifest_without_running_the_handler(self) -> None:
        code, envelope, _ = run(never_called, ["--describe"])
        self.assertEqual(code, 0)
        manifest = envelope["data"]
        self.assertEqual(
            sorted(manifest),
            ["exit_codes", "name", "network", "summary", "synopsis", "version", "writes", "writes_inside_target"],
        )
        self.assertEqual(manifest["name"], "demo")
        self.assertIs(manifest["network"], False)
        self.assertIs(manifest["writes_inside_target"], False)
        self.assertEqual(manifest["synopsis"], ["demo.py <target>"])

    def test_describe_needs_no_other_argument(self) -> None:
        parser = _common.ToolParser(prog="demo")
        parser.add_argument("target")

        def handler(argv: Sequence[str]) -> _common.Result:
            parser.parse_args(argv)
            return _common.Result(data={})

        self.assertEqual(run(handler, ["--describe"])[0], 0)
        self.assertEqual(run(handler, [])[0], 1)


class ParserTests(unittest.TestCase):
    def test_an_abbreviation_is_refused(self) -> None:
        parser = _common.ToolParser(prog="demo")
        parser.add_argument("--out-dir")
        with self.assertRaises(_common.UsageError):
            parser.parse_args(["--out", "x"])
        self.assertEqual(parser.parse_args(["--out-dir", "x"]).out_dir, "x")

    def test_a_bad_argument_is_a_usage_error_with_an_envelope(self) -> None:
        parser = _common.ToolParser(prog="demo")
        parser.add_argument("--known")

        def handler(argv: Sequence[str]) -> _common.Result:
            parser.parse_args(argv)
            return _common.Result(data={})

        code, envelope, err = run(handler, ["--unknown"])
        self.assertEqual(code, 1)
        self.assertIs(envelope["ok"], False)
        self.assertIn("unrecognized arguments", envelope["data"]["error"])
        self.assertIn("demo:", err)


class PreflightTests(unittest.TestCase):
    def test_an_old_python_is_refused_with_a_uv_hint_and_the_handler_does_not_run(self) -> None:
        code, envelope, err = run(never_called, python_version=(3, 9, 6))
        self.assertEqual(code, 1)
        self.assertIs(envelope["ok"], False)
        self.assertEqual(envelope["data"]["error"], "needs Python 3.11 or newer, found 3.9.6")
        self.assertIn("uv run --python 3.12 python3", err)
        self.assertIn("found 3.9.6", err)

    def test_the_minimum_is_accepted(self) -> None:
        code, _, _ = run(lambda argv: _common.Result(data={}), python_version=(3, 11, 0))
        self.assertEqual(code, 0)

    def test_a_newer_python_is_accepted(self) -> None:
        code, _, _ = run(lambda argv: _common.Result(data={}), python_version=(3, 14, 1))
        self.assertEqual(code, 0)

    def test_the_preflight_runs_before_describe(self) -> None:
        code, _, _ = run(never_called, ["--describe"], python_version=(3, 10, 0))
        self.assertEqual(code, 1)

    def test_the_running_interpreter_passes(self) -> None:
        _common.check_python()

    def test_the_minimum_is_3_11(self) -> None:
        self.assertEqual(_common.MINIMUM_PYTHON, (3, 11))

    def test_tool_files_parse_as_python_3_9_so_the_preflight_can_run(self) -> None:
        tool_files = sorted(p for p in TOOLS.glob("*.py"))
        self.assertIn(TOOLS / "_common.py", tool_files)
        for path in tool_files:
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))


class BoundedOutputTests(unittest.TestCase):
    def test_everything_is_kept_when_it_fits(self) -> None:
        kept, omitted = _common.bound_items(["a", "b", "c"], limit_bytes=1000)
        self.assertEqual((kept, omitted), (["a", "b", "c"], 0))

    def test_leading_items_are_kept_and_the_rest_counted(self) -> None:
        items = [{"n": n, "pad": "x" * 100} for n in range(100)]
        kept, omitted = _common.bound_items(items, limit_bytes=2000)
        self.assertGreater(len(kept), 0)
        self.assertEqual(kept, items[: len(kept)])
        self.assertEqual(len(kept) + omitted, 100)
        self.assertGreater(omitted, 0)

    def test_the_same_input_drops_the_same_items(self) -> None:
        items = [{"n": n} for n in range(500)]
        self.assertEqual(_common.bound_items(items, limit_bytes=500), _common.bound_items(items, limit_bytes=500))

    def test_an_item_that_does_not_fit_stops_the_list(self) -> None:
        kept, omitted = _common.bound_items(["x" * 100, "y"], limit_bytes=50)
        self.assertEqual((kept, omitted), ([], 2))

    def test_the_item_budget_sits_below_the_hard_limit(self) -> None:
        self.assertLess(_common.ITEM_BUDGET_BYTES, _common.MAX_OUTPUT_BYTES)

    def test_bounded_items_fit_the_envelope(self) -> None:
        items = [{"n": n, "pad": "x" * 50} for n in range(5000)]
        kept, omitted = _common.bound_items(items)
        envelope = _common.make_envelope(INFO, ok=True, data={"items": kept}, truncated=bool(omitted))
        self.assertLessEqual(len(_common.encode_envelope(envelope).encode("utf-8")), _common.MAX_OUTPUT_BYTES)


class PathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name).resolve()
        self.target = base / "target"
        (self.target / "src").mkdir(parents=True)
        (self.target / "src" / "a.txt").write_text("a", encoding="utf-8")
        self.outside = base / "outside"
        self.outside.mkdir()
        (self.outside / "secret.txt").write_text("s", encoding="utf-8")

    def symlink(self, link: Path, destination: Path) -> None:
        try:
            link.symlink_to(destination)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")

    def test_resolve_target_returns_the_resolved_directory(self) -> None:
        self.assertEqual(_common.resolve_target(self.target / "src" / ".."), self.target)

    def test_resolve_target_refuses_a_missing_path(self) -> None:
        with self.assertRaises(_common.UsageError):
            _common.resolve_target(self.target / "nope")

    def test_resolve_target_refuses_a_file(self) -> None:
        with self.assertRaises(_common.UsageError):
            _common.resolve_target(self.target / "src" / "a.txt")

    def test_a_relative_path_inside_the_target_is_resolved(self) -> None:
        self.assertEqual(_common.resolve_within(self.target, "src/a.txt"), self.target / "src" / "a.txt")

    def test_a_path_that_does_not_exist_yet_is_allowed_when_it_would_be_inside(self) -> None:
        self.assertEqual(_common.resolve_within(self.target, "src/new.txt"), self.target / "src" / "new.txt")

    def test_the_target_itself_is_inside(self) -> None:
        self.assertEqual(_common.resolve_within(self.target, "."), self.target)

    def test_climbing_out_with_dotdot_is_refused(self) -> None:
        with self.assertRaises(_common.PathNotAllowed):
            _common.resolve_within(self.target, "../outside/secret.txt")

    def test_an_absolute_path_outside_is_refused(self) -> None:
        with self.assertRaises(_common.PathNotAllowed):
            _common.resolve_within(self.target, self.outside / "secret.txt")

    def test_a_sibling_whose_name_starts_with_the_target_name_is_refused(self) -> None:
        sibling = self.target.parent / "target-other"
        sibling.mkdir()
        with self.assertRaises(_common.PathNotAllowed):
            _common.resolve_within(self.target, sibling)

    def test_a_symlink_that_leads_out_is_refused(self) -> None:
        self.symlink(self.target / "src" / "link", self.outside)
        with self.assertRaises(_common.PathNotAllowed):
            _common.resolve_within(self.target, "src/link/secret.txt")

    def test_a_symlink_that_stays_inside_is_followed(self) -> None:
        self.symlink(self.target / "alias", self.target / "src")
        self.assertEqual(_common.resolve_within(self.target, "alias/a.txt"), self.target / "src" / "a.txt")

    def test_a_symlink_loop_is_not_a_crash(self) -> None:
        # Python before 3.13 raises on a loop and later versions leave it unresolved. Either way the
        # tool must refuse the path or hand back one that is still inside the target.
        self.symlink(self.target / "loop", self.target / "loop")
        try:
            resolved = _common.resolve_within(self.target, "loop/x")
        except _common.PathNotAllowed:
            return
        self.assertTrue(_common.is_within(self.target, resolved))

    def test_an_output_directory_outside_the_target_is_created(self) -> None:
        wanted = self.outside / "reports" / "deep"
        self.assertEqual(_common.output_directory(wanted, target=self.target), wanted)
        self.assertTrue(wanted.is_dir())

    def test_an_output_directory_inside_the_target_is_refused_and_not_created(self) -> None:
        wanted = self.target / "reports"
        with self.assertRaises(_common.PathNotAllowed):
            _common.output_directory(wanted, target=self.target)
        self.assertFalse(wanted.exists())

    def test_the_target_itself_is_refused_as_an_output_directory(self) -> None:
        with self.assertRaises(_common.PathNotAllowed):
            _common.output_directory(self.target, target=self.target)

    def test_an_output_directory_that_reaches_the_target_through_a_symlink_is_refused(self) -> None:
        self.symlink(self.outside / "into-target", self.target)
        with self.assertRaises(_common.PathNotAllowed):
            _common.output_directory(self.outside / "into-target" / "reports", target=self.target)
        self.assertFalse((self.target / "reports").exists())

    def test_an_output_directory_that_is_a_file_is_a_usage_error(self) -> None:
        with self.assertRaises(_common.UsageError):
            _common.output_directory(self.outside / "secret.txt", target=self.target)

    def test_a_directory_that_contains_the_target_is_a_fine_output_directory(self) -> None:
        self.assertEqual(_common.output_directory(self.target.parent, target=self.target), self.target.parent)


class AtomicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_a_new_file_is_written_with_the_text(self) -> None:
        path = self.dir / "draft.json"
        _common.atomic_write_text(path, "one\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "one\n")

    def test_an_existing_file_is_replaced_whole(self) -> None:
        path = self.dir / "draft.json"
        path.write_text("old old old\n", encoding="utf-8")
        _common.atomic_write_text(path, "new\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "new\n")

    def test_no_temporary_file_is_left_behind(self) -> None:
        _common.atomic_write_text(self.dir / "draft.json", "x")
        self.assertEqual([p.name for p in self.dir.iterdir()], ["draft.json"])

    def test_a_failure_keeps_the_old_file_and_removes_the_temporary_one(self) -> None:
        path = self.dir / "draft.json"
        path.write_text("old\n", encoding="utf-8")
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                _common.atomic_write_text(path, "new\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "old\n")
        self.assertEqual([p.name for p in self.dir.iterdir()], ["draft.json"])

    def test_the_mode_of_an_existing_file_is_kept(self) -> None:
        path = self.dir / "draft.json"
        path.write_text("old", encoding="utf-8")
        os.chmod(path, 0o640)
        _common.atomic_write_text(path, "new")
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_a_new_file_gets_the_usual_mode_not_the_private_one_of_the_temporary_file(self) -> None:
        path = self.dir / "draft.json"
        _common.atomic_write_text(path, "x")
        self.assertEqual(path.stat().st_mode & 0o644, 0o644)


if __name__ == "__main__":
    unittest.main()
