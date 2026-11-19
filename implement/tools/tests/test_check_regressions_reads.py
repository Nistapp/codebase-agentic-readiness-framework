# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`check_regressions.py --changed-from`: the glob matcher and the scopes of the consistency map schema, the
engine's read declarations, and the attribution of each listed check to the paths a real git worktree changed
(committed, deleted and untracked), with ``unattributed`` as a report-only flag. Standard library only, in process.
"""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence
from unittest import mock

import _implement_paths  # noqa: F401  (puts the tools folders on sys.path)
import _common
import _git
import check_regressions
import validate_report
from check_regressions import Declaration, Place

BASE = Path(__file__).resolve().parent / "fixtures" / "check-regressions-base.engine-report.json"
LATER = "2026-11-19T11:00:00+00:00"
FILES = ("README.md", ".mcp.json", "docs/a.md", "src/app.py")


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(check_regressions.INFO, check_regressions.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


class GlobTests(unittest.TestCase):
    def test_a_double_star_folder_matches_any_number_of_folders_none_included(self) -> None:
        cases = [
            ("docs/**/*.md", "docs/a.md", True),
            ("docs/**/*.md", "docs/x/y/a.md", True),
            ("docs/**/*.md", "docsx/a.md", False),
            ("docs/**/*.md", "a.md", False),
            ("**/AGENTS.md", "AGENTS.md", True),
            ("**/AGENTS.md", "a/b/AGENTS.md", True),
            ("**/AGENTS.md", "a/b/AGENTS.md.bak", False),
            ("**", "README.md", True),
            ("**", "a/b/c.txt", True),
            ("**/*.sh", "run.sh", True),
            ("a/**", "a/b/c", True),
            ("a/**/b/**/c.txt", "a/b/c.txt", True),
            ("a/**/b/**/c.txt", "a/x/c.txt", False),
        ]
        for pattern, path, expected in cases:
            with self.subTest(pattern=pattern, path=path):
                self.assertEqual(check_regressions.glob_matches(pattern, path), expected)

    def test_a_star_stays_inside_one_folder(self) -> None:
        cases = [
            (".github/workflows/*.yml", ".github/workflows/ci.yml", True),
            (".github/workflows/*.yml", ".github/workflows/sub/ci.yml", False),
            ("eslint.config.*", "eslint.config.js", True),
            ("eslint.config.*", "web/eslint.config.js", False),
            (".githooks/*", ".githooks/pre-commit", True),
            ("[ab].md", "a.md", True),
            ("[ab].md", "c.md", False),
            ("?.md", "a.md", True),
        ]
        for pattern, path, expected in cases:
            with self.subTest(pattern=pattern, path=path):
                self.assertEqual(check_regressions.glob_matches(pattern, path), expected)

    def test_each_scope_matches_as_the_map_schema_states(self) -> None:
        cases = [
            (Place("Makefile", "root"), "Makefile", True),
            (Place("Makefile", "root"), "sub/Makefile", False),
            (Place(".prettierrc*", "any-depth"), "web/.prettierrc.json", True),
            (Place(".mcp.json", "any-depth"), "a/b/.mcp.json", True),
            (Place(".mcp.json", "any-depth"), "a/b/mcp.json", False),
            (Place("CODEOWNERS", "repository-level"), "CODEOWNERS", True),
            (Place("CODEOWNERS", "repository-level"), ".github/CODEOWNERS", True),
            (Place("CODEOWNERS", "repository-level"), ".gitlab/CODEOWNERS", True),
            (Place("CODEOWNERS", "repository-level"), "docs/CODEOWNERS", True),
            (Place("CODEOWNERS", "repository-level"), "docs/sub/CODEOWNERS", False),
            (Place("CODEOWNERS", "repository-level"), "src/CODEOWNERS", False),
            (Place("docs/**/*.md", "glob"), "docs/a.md", True),
            (Place("**/*communicat*.md", "glob", case="fold"), "docs/COMMUNICATION_RULES.md", True),
            (Place("**/*communicat*.md", "glob"), "docs/COMMUNICATION_RULES.md", False),
            (Place("readme.md", "root", case="fold"), "README.md", True),
        ]
        for place, path, expected in cases:
            with self.subTest(place=place, path=path):
                self.assertEqual(check_regressions.place_matches(place, path), expected)

    def test_hits_mark_via_cap_the_paths_and_list_a_place_once(self) -> None:
        declaration = Declaration(
            places=(
                Place("**", "glob"),
                Place("**", "glob"),
                Place("tests", "any-depth", via="scan-kind"),
                Place("nothing.txt", "root"),
            )
        )
        changed = [f"f{index}.txt" for index in range(7)] + ["src/tests"]
        found = check_regressions.hits(declaration, changed)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0]["paths"], changed[:5])
        self.assertEqual(found[0]["paths_omitted"], 3)
        self.assertNotIn("via", found[0])
        self.assertEqual(found[1], {"place": "tests", "scope": "any-depth", "via": "scan-kind", "paths": ["src/tests"]})

    def test_attribute_flags_a_check_without_a_declaration_or_a_hit(self) -> None:
        row = check_regressions.Row("DOC-01", "evidence", "PASS", "PASS", ("summary",))
        undeclared = check_regressions.attribute(row, {}, ["docs/a.md"])
        self.assertEqual(
            (undeclared["declared"], undeclared["unattributed"], undeclared["reads_hit"]), (False, True, [])
        )
        declared = {"DOC-01": Declaration(places=(Place("README.md", "root"),), named_by_text=True)}
        missed = check_regressions.attribute(row, declared, ["docs/a.md"])
        self.assertEqual((missed["declared"], missed["named_by_text"], missed["unattributed"]), (True, True, True))
        self.assertEqual(missed["class"], "evidence")


class DeclarationTests(unittest.TestCase):
    def test_the_engine_declarations_load_as_plain_data(self) -> None:
        declarations, ruleset_hash = check_regressions.load_declarations()
        self.assertIn(Place(".mcp.json", "any-depth"), declarations["IDX-01"].places)
        self.assertIn(Place("docs/**/*.md", "glob"), declarations["DOC-05"].places)
        self.assertTrue(any(place.via for entry in declarations.values() for place in entry.places))
        self.assertTrue(any(entry.named_by_text for entry in declarations.values()))
        self.assertRegex(ruleset_hash, r"^[0-9a-f]{16}$")

    def test_a_mcp_json_change_is_laid_on_idx_01(self) -> None:
        declarations, _ = check_regressions.load_declarations()
        row = check_regressions.Row("IDX-01", "lost_pass", "PASS", "FAIL", ("summary",))
        attributed = check_regressions.attribute(row, declarations, [".mcp.json", "README.md"])
        self.assertFalse(attributed["unattributed"])
        self.assertIn({"place": ".mcp.json", "scope": "any-depth", "paths": [".mcp.json"]}, attributed["reads_hit"])


class ChangedFromTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name).resolve()
        self.repo = self.folder / "theme"
        _git.make_repo(self.repo, FILES)
        self.start = _git.run_git(self.repo, "rev-parse", "HEAD")
        self.base: dict[str, Any] = json.loads(BASE.read_text(encoding="utf-8"))
        self.base["provenance"].update(target=str(self.repo), git_sha=self.start)
        self.engine_hash = check_regressions.load_declarations()[1]

    def close_report(self) -> dict[str, Any]:
        close: dict[str, Any] = copy.deepcopy(self.base)
        close["provenance"].update(scanned_at=LATER, git_sha=_git.run_git(self.repo, "rev-parse", "HEAD"))
        return close

    def write(self, name: str, document: Any) -> str:
        path = self.folder / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return str(path)

    def run_pair(self, close: Any, *extra: str, base: Any = None) -> tuple[int, dict[str, Any], str]:
        argv = [self.write("base.json", self.base if base is None else base), self.write("close.json", close)]
        return call([*argv, *extra])

    def commit(self, message: str) -> None:
        _git.run_git(self.repo, "add", "-A")
        _git.run_git(self.repo, "commit", "-q", "-m", message)

    def rows(self, envelope: dict[str, Any]) -> dict[str, dict[str, Any]]:
        data = envelope["data"]
        return {row["check"]: row for row in [*data["stops"], *data["moves"], *data["evidence_changes"]]}

    def test_a_deleted_mcp_json_explains_the_lost_idx_01_pass(self) -> None:
        (self.repo / ".mcp.json").unlink()
        (self.repo / "docs" / "b.md").write_text("new\n", encoding="utf-8")
        self.commit("break")
        (self.repo / "notes.txt").write_text("untracked\n", encoding="utf-8")
        close = self.close_report()
        idx = next(check for check in close["checks"] if check["id"] == "IDX-01")
        idx.update(verdict="FAIL", summary="no project-level MCP configuration found")
        doc = next(check for check in close["checks"] if check["id"] == "DOC-01")
        doc["summary"] = "docs/ holds 4 pages"
        before = _git.run_git(self.repo, "status", "--porcelain", "--ignored")
        code, envelope, err = self.run_pair(close, "--changed-from", str(self.repo))
        self.assertEqual(_git.run_git(self.repo, "status", "--porcelain", "--ignored"), before)
        self.assertEqual(code, 0)
        data = envelope["data"]
        self.assertEqual(data["status"], "lost")
        self.assertEqual(
            data["changes"],
            {
                "base_sha": self.start,
                "changed_count": 3,
                "changed_paths": [".mcp.json", "docs/b.md", "notes.txt"],
                "unattributed": 0,
            },
        )
        rows = self.rows(envelope)
        self.assertIn({"place": ".mcp.json", "scope": "any-depth", "paths": [".mcp.json"]}, rows["IDX-01"]["reads_hit"])
        self.assertEqual(rows["IDX-01"]["class"], "lost_pass")
        self.assertIn({"place": "docs/**/*.md", "scope": "glob", "paths": ["docs/b.md"]}, rows["DOC-01"]["reads_hit"])
        self.assertFalse(rows["DOC-01"]["unattributed"])
        self.assertIn("0 unattributed", err)

    def test_a_move_no_changed_path_explains_is_unattributed_and_only_reported(self) -> None:
        (self.repo / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")  # uncommitted change
        close = self.close_report()
        doc = next(check for check in close["checks"] if check["id"] == "DOC-01")
        doc["summary"] = "docs/ holds 4 pages"
        code, envelope, err = self.run_pair(close, "--changed-from", str(self.repo))
        self.assertEqual(code, 0)
        data = envelope["data"]
        self.assertEqual(data["status"], "clean")
        self.assertEqual(data["changes"]["changed_paths"], ["src/app.py"])
        self.assertEqual(data["changes"]["unattributed"], 1)
        row = self.rows(envelope)["DOC-01"]
        self.assertEqual((row["class"], row["unattributed"], row["reads_hit"]), ("evidence", True, []))
        self.assertTrue(any("possible gap in the read declarations" in warning for warning in envelope["warnings"]))
        self.assertIn("1 unattributed", err)

    def test_base_overrides_the_base_reports_commit(self) -> None:
        (self.repo / "README.md").write_text("changed\n", encoding="utf-8")
        self.commit("one")
        middle = _git.run_git(self.repo, "rev-parse", "HEAD")
        (self.repo / "docs" / "a.md").write_text("changed\n", encoding="utf-8")
        self.commit("two")
        code, envelope, _ = self.run_pair(self.close_report(), "--changed-from", str(self.repo), "--base", middle[:12])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["changes"]["base_sha"], middle)
        self.assertEqual(envelope["data"]["changes"]["changed_paths"], ["docs/a.md"])

    def test_another_engine_ruleset_is_a_warning_and_the_same_one_is_not(self) -> None:
        code, envelope, _ = self.run_pair(self.close_report(), "--changed-from", str(self.repo))
        self.assertEqual(code, 0)
        self.assertTrue(any("the read declarations may not be" in warning for warning in envelope["warnings"]))
        base = copy.deepcopy(self.base)
        base["provenance"]["ruleset_hash"] = self.engine_hash
        close = copy.deepcopy(base)
        close["provenance"]["scanned_at"] = LATER
        code, envelope, _ = self.run_pair(close, "--changed-from", str(self.repo), base=base)
        self.assertEqual(code, 0)
        self.assertEqual(envelope["warnings"], [])

    def test_a_long_list_of_changed_paths_is_bounded_and_counted(self) -> None:
        for index in range(600):
            (self.repo / f"generated-file-number-{index:04d}.txt").write_text("x\n", encoding="utf-8")
        code, envelope, _ = self.run_pair(self.close_report(), "--changed-from", str(self.repo))
        self.assertEqual(code, 0)
        self.assertTrue(envelope["truncated"])
        changes = envelope["data"]["changes"]
        self.assertEqual(changes["changed_count"], 600)
        self.assertEqual(len(changes["changed_paths"]) + envelope["data"]["omitted"]["changed_paths"], 600)

    # --- usage errors -------------------------------------------------------------------------------------

    def assert_usage(self, close: Any, text: str, *extra: str, base: Any = None) -> None:
        code, envelope, _ = self.run_pair(close, *extra, base=base)
        self.assertEqual(code, _common.EXIT_USAGE, envelope)
        self.assertIn(text, envelope["data"]["error"])

    def test_a_worktree_that_is_not_the_target_is_refused(self) -> None:
        other = self.folder / "other"
        _git.make_repo(other)
        self.assert_usage(self.close_report(), "is not the reports' target", "--changed-from", str(other))

    def test_a_base_commit_outside_the_history_is_refused(self) -> None:
        self.assert_usage(
            self.close_report(), "is not in the history", "--changed-from", str(self.repo), "--base", "f" * 40
        )

    def test_a_base_report_without_a_commit_needs_base(self) -> None:
        base = copy.deepcopy(self.base)
        base["provenance"]["git_sha"] = None
        close = copy.deepcopy(base)
        close["provenance"]["scanned_at"] = LATER
        self.assert_usage(close, "give the base commit with --base", "--changed-from", str(self.repo), base=base)

    def test_base_without_changed_from_is_a_usage_error(self) -> None:
        self.assert_usage(self.close_report(), "--base needs --changed-from", "--base", self.start)

    def test_git_that_cannot_list_the_changes_is_a_usage_error(self) -> None:
        real = validate_report.git_output

        def failing(target: Path, args: Sequence[str], stdin: str | None = None) -> Any:
            return None if args[0] == "diff" else real(target, args, stdin)

        with mock.patch.object(validate_report, "git_output", failing):
            self.assert_usage(self.close_report(), "git could not list the paths", "--changed-from", str(self.repo))

    def test_a_folder_that_is_no_git_repository_is_refused(self) -> None:
        plain = self.folder / "plain"
        plain.mkdir()
        base = copy.deepcopy(self.base)
        base["provenance"]["target"] = str(plain)
        close = copy.deepcopy(base)
        close["provenance"]["scanned_at"] = LATER
        self.assert_usage(close, "is not in the history", "--changed-from", str(plain), base=base)


if __name__ == "__main__":
    unittest.main()
