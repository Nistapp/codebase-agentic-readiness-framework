# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine replaces an output file only when told to (``--force``), and refuses before it writes anything.

The outputs are the JSON report, the Markdown beside it for ``--format both`` and the ``CON-04`` draft. A refusal is a
message and exit 1, never a traceback, and it leaves every file as it was: no partial report, no new draft.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit import cli  # noqa: E402
from audit.evaluate import evaluate  # noqa: E402
from audit.report import ReportWriteError, emit, planned_files, refuse_to_replace  # noqa: E402
from audit.rules.checks import con  # noqa: E402
from audit.rules.registry import REGISTRY  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from audit.target import Target, resolve_target  # noqa: E402

OLD = "old content\n"


def scan(*argv: str) -> tuple[int, str, str]:
    """Run the CLI in this process; return ``(exit code, stdout, stderr)``."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.run(list(argv))
    return code, out.getvalue(), err.getvalue()


class OutputFileTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(con.set_emit_target, None)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.target = self.root / "target"
        support.write(self.target, "src/app.py", "print(1)\n")
        support.write(self.target, "tests/test_app.py", "def test_x():\n    assert True\n")
        self.out = self.root / "out"
        self.json = self.out / "report.json"
        self.md = self.out / "report.md"
        self.draft = self.out / "do-not-do.draft.md"

    def old(self, *paths: Path) -> None:
        for path in paths:
            support.write(self.out, path.name, OLD)

    def assert_untouched(self, *paths: Path) -> None:
        for path in paths:
            self.assertEqual(path.read_text(encoding="utf-8"), OLD, f"{path} was changed")

    def assert_absent(self, *paths: Path) -> None:
        for path in paths:
            self.assertFalse(path.exists(), f"{path} was written")

    # --- the JSON report ---------------------------------------------------------------------------------------

    def test_an_existing_report_is_refused_with_a_message_and_left_alone(self):
        self.old(self.json)
        code, stdout, stderr = scan(str(self.target), "--format", "json", "--out", str(self.json))
        self.assertEqual((code, stdout), (1, ""))
        self.assertEqual(stderr, f"audit: {self.json} exists — pass --force to overwrite\n")
        self.assert_untouched(self.json)

    def test_force_replaces_an_existing_report(self):
        self.old(self.json)
        code, _, stderr = scan(str(self.target), "--format", "json", "--out", str(self.json), "--force")
        self.assertEqual(code, 0, stderr)
        self.assertNotEqual(self.json.read_text(encoding="utf-8"), OLD)
        self.assertEqual(stderr, f"\nreport written: {self.json}\n")

    # --- the Markdown beside it --------------------------------------------------------------------------------

    def test_an_existing_markdown_file_is_refused_and_no_report_is_written_beside_it(self):
        self.old(self.md)
        code, stdout, stderr = scan(str(self.target), "--format", "both", "--out", str(self.json))
        self.assertEqual((code, stdout), (1, ""))
        self.assertEqual(stderr, f"audit: {self.md} exists — pass --force to overwrite\n")
        self.assert_untouched(self.md)
        self.assert_absent(self.json)

    def test_both_existing_files_are_named_in_one_message_and_neither_is_changed(self):
        self.old(self.json, self.md)
        code, _, stderr = scan(str(self.target), "--format", "both", "--out", str(self.json))
        self.assertEqual(code, 1)
        self.assertEqual(
            stderr,
            f"audit: {self.json} exists — pass --force to overwrite; {self.md} exists — pass --force to overwrite\n",
        )
        self.assert_untouched(self.json, self.md)

    def test_force_replaces_the_markdown_too(self):
        self.old(self.json, self.md)
        code, _, stderr = scan(str(self.target), "--format", "both", "--out", str(self.json), "--force")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, f"\nreport written: {self.json}\nreport written: {self.md}\n")
        self.assertTrue(self.md.read_text(encoding="utf-8").startswith("# "))
        self.assertTrue(self.json.read_text(encoding="utf-8").startswith("{"))

    def test_markdown_only_writes_and_replaces_nothing(self):
        self.old(self.json, self.md)
        code, stdout, stderr = scan(str(self.target), "--format", "md", "--out", str(self.json))
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue(stdout.startswith("# "))
        self.assert_untouched(self.json, self.md)

    def test_the_default_format_writes_the_markdown_too_so_it_is_guarded_by_default(self):
        self.old(self.md)
        code, _, stderr = scan(str(self.target), "--out", str(self.json))
        self.assertEqual(code, 1)
        self.assertEqual(stderr, f"audit: {self.md} exists — pass --force to overwrite\n")
        self.assert_untouched(self.md)
        self.assert_absent(self.json)

    def test_an_out_directory_names_the_report_audit_report_and_the_markdown_beside_it(self):
        support.write(self.out, "audit-report.md", OLD)
        code, _, stderr = scan(str(self.target), "--out", str(self.out))
        self.assertEqual(code, 1)
        self.assertEqual(stderr, f"audit: {self.out / 'audit-report.md'} exists — pass --force to overwrite\n")
        self.assert_absent(self.out / "audit-report.json")

    def test_an_out_directory_names_a_json_report_audit_report_json(self):
        support.write(self.out, "audit-report.json", OLD)
        code, _, stderr = scan(str(self.target), "--format", "json", "--out", str(self.out))
        self.assertEqual(code, 1)
        self.assertEqual(stderr, f"audit: {self.out / 'audit-report.json'} exists — pass --force to overwrite\n")

    def test_with_no_out_the_report_goes_to_audit_report_json_in_the_current_directory(self):
        before = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, before)
        support.write(self.root, "audit-report.json", OLD)
        code, _, stderr = scan(str(self.target), "--format", "json")
        self.assertEqual(code, 1)
        self.assertEqual(
            stderr, f"audit: {Path.cwd().resolve() / 'audit-report.json'} exists — pass --force to overwrite\n"
        )

    def test_a_run_from_inside_the_target_without_an_out_is_refused_before_the_scan(self):
        before = os.getcwd()
        os.chdir(self.target)
        self.addCleanup(os.chdir, before)
        for extra in ((), ("--emit-baseline",)):
            with self.subTest(extra=extra):
                code, stdout, stderr = scan(str(self.target), *extra)
                self.assertEqual((code, stdout), (1, ""))
                self.assertEqual(
                    stderr,
                    "audit: refusing to write the report inside the target — run from elsewhere or pass --out\n",
                )
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ["src", "tests"])

    def test_a_json_only_run_does_not_mind_a_markdown_file_that_is_there(self):
        self.old(self.md)
        code, _, stderr = scan(str(self.target), "--format", "json", "--out", str(self.json))
        self.assertEqual(code, 0, stderr)
        self.assert_untouched(self.md)
        self.assertTrue(self.json.is_file())

    # --- the CON-04 draft --------------------------------------------------------------------------------------

    def test_an_existing_draft_is_refused_before_anything_is_written(self):
        self.old(self.draft)
        code, stdout, stderr = scan(str(self.target), "--format", "json", "--out", str(self.json), "--emit-baseline")
        self.assertEqual((code, stdout), (1, ""))
        self.assertEqual(stderr, f"audit: {self.draft} exists — pass --force to overwrite\n")
        self.assert_untouched(self.draft)
        self.assert_absent(self.json)

    def test_a_refused_report_leaves_no_new_draft(self):
        self.old(self.json)
        code, _, stderr = scan(str(self.target), "--format", "json", "--out", str(self.json), "--emit-baseline")
        self.assertEqual(code, 1)
        self.assertEqual(stderr, f"audit: {self.json} exists — pass --force to overwrite\n")
        self.assert_untouched(self.json)
        self.assert_absent(self.draft)

    def test_every_existing_output_is_named_in_the_order_report_markdown_draft(self):
        self.old(self.draft, self.md, self.json)
        code, _, stderr = scan(str(self.target), "--format", "both", "--out", str(self.json), "--emit-baseline")
        self.assertEqual(code, 1)
        self.assertEqual(
            stderr,
            f"audit: {self.json} exists — pass --force to overwrite; {self.md} exists — pass --force to overwrite; "
            f"{self.draft} exists — pass --force to overwrite\n",
        )
        self.assert_untouched(self.json, self.md, self.draft)

    def test_force_replaces_the_draft(self):
        self.old(self.draft)
        code, _, stderr = scan(
            str(self.target), "--format", "json", "--out", str(self.json), "--emit-baseline", "--force"
        )
        self.assertEqual(code, 0, stderr)
        self.assertTrue(self.draft.read_text(encoding="utf-8").startswith("<!-- Generated by python-agentic-audit"))

    def test_an_existing_draft_is_no_concern_without_the_flag(self):
        self.old(self.draft)
        code, _, stderr = scan(str(self.target), "--format", "json", "--out", str(self.json))
        self.assertEqual(code, 0, stderr)
        self.assert_untouched(self.draft)

    def test_a_stale_draft_inside_the_target_is_not_in_the_way_because_none_is_written_there(self):
        inside = self.target / "audit-out"
        support.write(inside, "do-not-do.draft.md", OLD)
        code, _, stderr = scan(
            str(self.target), "--format", "json", "--out", str(inside / "report.json"), "--emit-baseline"
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual((inside / "do-not-do.draft.md").read_text(encoding="utf-8"), OLD)

    # --- the same refusal one level down, for a caller that did not go through the CLI -------------------------

    def test_the_writer_refuses_on_its_own_and_so_does_the_emitter(self):
        args = cli.build_parser().parse_args([str(self.target), "--format", "both", "--out", str(self.json)])
        resolved = resolve_target(self.target)
        inventory = build_inventory(resolved.path)
        result = evaluate(target=resolved, inventory=inventory, stack=detect_stack(inventory), args=args)
        self.old(self.md)
        with self.assertRaises(ReportWriteError) as caught:
            emit(result, args=args)
        self.assertEqual(str(caught.exception), f"{self.md} exists — pass --force to overwrite")
        self.assert_untouched(self.md)
        self.assert_absent(self.json)

    def test_the_emitter_refuses_to_replace_a_draft_and_the_check_says_so(self):
        resolved = resolve_target(self.target)
        inventory = build_inventory(resolved.path)
        spec = next(s for s in REGISTRY if s.id == "CON-04")
        self.old(self.draft)
        con.set_emit_target(self.json)
        with self.assertRaises(FileExistsError) as caught:
            con._write_draft(resolved, self.json, "new\n")
        self.assertEqual(str(caught.exception), str(self.draft))
        outcome = con.check_con04(
            spec=spec, target=resolved, inventory=inventory, stack=None, components=None, session=None
        )
        self.assertEqual(outcome.verdict.value, "UNKNOWN")
        self.assertEqual(outcome.summary, f"refusing to replace {self.draft}; pass --force to overwrite")
        self.assert_untouched(self.draft)

        con.set_emit_target(self.json, force=True)
        outcome = con.check_con04(
            spec=spec, target=resolved, inventory=inventory, stack=None, components=None, session=None
        )
        self.assertEqual(outcome.verdict.value, "PASS")
        self.assertEqual(outcome.summary, f"draft deny list written: {self.draft}")
        self.assertNotEqual(self.draft.read_text(encoding="utf-8"), OLD)


class PlannedFilesTests(unittest.TestCase):
    OUT = Path("/x/report.json")

    def planned(self, fmt: str, out: str | None) -> list[Path]:
        return planned_files(Namespace(format=fmt, out=out), self.OUT)

    def test_json_is_the_report_alone(self):
        self.assertEqual(self.planned("json", "/x/report.json"), [self.OUT])
        self.assertEqual(self.planned("json", None), [self.OUT])

    def test_both_adds_the_markdown_beside_it_when_there_is_an_out(self):
        self.assertEqual(self.planned("both", "/x/report.json"), [self.OUT, Path("/x/report.md")])

    def test_both_without_an_out_prints_the_markdown_and_writes_none(self):
        self.assertEqual(self.planned("both", None), [self.OUT])

    def test_md_writes_nothing(self):
        self.assertEqual(self.planned("md", "/x/report.json"), [])
        self.assertEqual(self.planned("md", None), [])


class RefuseToReplaceTests(unittest.TestCase):
    def test_nothing_is_refused_when_nothing_exists_or_when_forced(self):
        with tempfile.TemporaryDirectory() as tmp:
            free, taken = Path(tmp) / "free", Path(tmp) / "taken"
            taken.write_text("x", encoding="utf-8")
            refuse_to_replace([], force=False)
            refuse_to_replace([free], force=False)
            refuse_to_replace([free, taken], force=True)
            with self.assertRaises(ReportWriteError) as caught:
                refuse_to_replace([free, taken], force=False)
            self.assertEqual(str(caught.exception), f"{taken} exists — pass --force to overwrite")


class DraftPathTests(unittest.TestCase):
    def test_the_draft_goes_beside_the_report_and_never_inside_the_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "target").mkdir()
            target = Target(root / "target", False, None, None, False, "")
            self.assertEqual(con.draft_path(target, root / "out" / "r.json"), root / "out" / "do-not-do.draft.md")
            self.assertIsNone(con.draft_path(target, root / "target" / "out" / "r.json"))
            self.assertIsNone(con.draft_path(target, root / "target" / "r.json"))


if __name__ == "__main__":
    unittest.main()
