# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`IDX-01` reads Claude Code's `~/.claude.json`, and `IDX-03` compares times when the store records no revision.

Issue #16. Both run in-process, so coverage traces them. `HOME` is a temporary folder, and the index store is
redirected with `AUDIT_INDEX_STORE`. The git repository of the `IDX-03` tests is built with a fixed committer time,
which git also writes into the reflog entry, so HEAD's time is known.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.probes import ProbeSession  # noqa: E402
from audit.rules.checks.idx import INDEX_STORE_ENV, check_idx01, check_idx03  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.target import resolve_target  # noqa: E402
from packs.idx.test_idx_pack import write_store  # noqa: E402

#: HEAD's committer time in the git repository of the IDX-03 tests: 2026-01-01T00:00:00Z.
HEAD_TIME = "2026-01-01T00:00:00+00:00"


def _idx01(root: Path, home: Path, *, user_config: bool = True):
    session = ProbeSession(cwd=root, enabled=False, user_config=user_config)
    with mock.patch.dict(os.environ, {"HOME": str(home)}):
        outcome = check_idx01(
            spec=REGISTRY_BY_ID["IDX-01"],
            target=resolve_target(root),
            inventory=build_inventory(root),
            stack=None,
            components=None,
            session=session,
        )
    return outcome, session


class ClaudeUserConfigTests(unittest.TestCase):
    def scan(self, claude: object | str, *, user_config: bool = True):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = home / "repo"
            support.write(root, "README.md", "# repo\n")
            text = claude if isinstance(claude, str) else json.dumps(claude)
            support.write(home, ".claude.json", text)
            outcome, session = _idx01(root, home, user_config=user_config)
            return outcome, session, str(home / ".claude.json"), str(root.resolve())

    def test_the_user_scope_registers_every_checkout(self):
        outcome, session, path, _ = self.scan({"mcpServers": {"codebase-memory-mcp": {"command": "x"}}})
        self.assertEqual(outcome.verdict.value, "PASS")
        self.assertEqual(outcome.summary, f"codebase-memory-mcp registered in: {path} (user scope)")
        self.assertIn(path, session.user_reads)

    def test_the_local_scope_registers_only_its_own_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = home / "repo"
            support.write(root, "README.md", "# repo\n")
            for key, verdict, scope in (
                (str(root.resolve()), "PASS", "(local scope)"),
                (str(home / "other"), "PARTIAL", "does not name codebase-memory-mcp"),
            ):
                with self.subTest(key=key):
                    claude = {"projects": {key: {"mcpServers": {"codebase-memory-mcp": {}}}}}
                    support.write(home, ".claude.json", json.dumps(claude))
                    outcome, _ = _idx01(root, home)
                    self.assertEqual(outcome.verdict.value, verdict)
                    self.assertIn(scope, outcome.summary)

    def test_a_server_named_elsewhere_in_the_file_does_not_register(self):
        claude = {"mcpServers": {"other": {}}, "skillUsage": {"codebase-memory-mcp": 3}, "projects": []}
        outcome, _, path, _ = self.scan(claude)
        self.assertEqual(outcome.verdict.value, "PARTIAL")
        self.assertIn(path, outcome.summary)

    def test_a_file_that_is_not_json_is_unknown(self):
        for text in ("{not json", "[]"):
            with self.subTest(text=text):
                outcome, _, path, _ = self.scan(text)
                self.assertEqual(outcome.verdict.value, "UNKNOWN")
                self.assertIn(path, outcome.summary)

    def test_with_no_user_config_the_file_is_not_read(self):
        outcome, session, _, _ = self.scan({"mcpServers": {"codebase-memory-mcp": {}}}, user_config=False)
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual(session.user_reads, [])

    def test_a_file_larger_than_the_bound_is_unreadable(self):
        with mock.patch("audit.rules.checks.idx.idx_01._CLAUDE_READ_LIMIT", 10):
            outcome, _, _, _ = self.scan({"mcpServers": {"codebase-memory-mcp": {}}})
        self.assertEqual(outcome.verdict.value, "UNKNOWN")


def _git_repo(root: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_AUTHOR_DATE": HEAD_TIME,
        "GIT_COMMITTER_DATE": HEAD_TIME,
    }
    support.write(root, "README.md", "# repo\n")
    for args in (("init", "-q"), ("add", "README.md"), ("commit", "-q", "-m", "init")):
        subprocess.run(["git", "-C", str(root), *args], check=True, env=env, capture_output=True)


def _idx03(root: Path, store: Path, *, probes: bool = True):
    session = ProbeSession(cwd=root, enabled=probes, user_config=False)
    with mock.patch.dict(os.environ, {INDEX_STORE_ENV: str(store)}):
        return check_idx03(
            spec=REGISTRY_BY_ID["IDX-03"],
            target=resolve_target(root),
            inventory=None,
            stack=None,
            components=None,
            session=session,
        )


def _store_at(store: Path, root: Path, indexed_at: str) -> Path:
    write_store(store, [str(root.resolve())])
    connection = sqlite3.connect(store / "fake-project.db")
    try:
        connection.execute("UPDATE projects SET indexed_at = ?", (indexed_at,))
        connection.commit()
    finally:
        connection.close()
    return store


class FreshnessByTimeTests(unittest.TestCase):
    def run_at(self, indexed_at: str, *, probes: bool = True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            _git_repo(root)
            store = _store_at(Path(tmp) / "store", root, indexed_at)
            return _idx03(root, store, probes=probes)

    def test_an_index_built_after_head_moved_passes_and_says_it_compared_times(self):
        outcome = self.run_at("2026-01-02T00:00:00Z")
        self.assertEqual(outcome.verdict.value, "PASS")
        self.assertEqual(
            outcome.summary,
            "index built at 2026-01-02T00:00:00Z, at or after HEAD last moved (2026-01-01T00:00:00Z); the store "
            "records no revision, so this is a time comparison and does not cover uncommitted edits made since",
        )

    def test_an_index_built_before_head_moved_is_partial_never_fail(self):
        outcome = self.run_at("2025-12-31T00:00:00Z")
        self.assertEqual(outcome.verdict.value, "PARTIAL")
        (finding,) = outcome.findings
        self.assertEqual(finding.verdict.value, "PARTIAL")
        self.assertIn("before HEAD last moved at 2026-01-01T00:00:00Z", finding.statement)
        self.assertEqual(finding.evidence[0].note, "indexed_at 2025-12-31T00:00:00Z; HEAD moved 2026-01-01T00:00:00Z")

    def test_an_index_time_with_no_zone_is_read_as_utc(self):
        self.assertEqual(self.run_at("2026-01-01T00:00:00").verdict.value, "PASS")

    def test_an_unreadable_index_time_is_unknown(self):
        outcome = self.run_at("yesterday")
        self.assertEqual(outcome.verdict.value, "UNKNOWN")
        self.assertIn("no readable index time", outcome.summary)

    def test_without_probes_nothing_is_compared(self):
        self.assertEqual(self.run_at("2026-01-02T00:00:00Z", probes=False).verdict.value, "UNKNOWN")

    def test_a_checkout_after_the_index_ran_moves_head_by_the_reflog(self):
        from audit.rules.checks.idx import _head_moved_at

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            _git_repo(root)
            env = {**os.environ, "GIT_COMMITTER_DATE": "2026-03-01T00:00:00+00:00"}
            subprocess.run(
                ["git", "-C", str(root), "checkout", "-q", "-b", "other"], check=True, env=env, capture_output=True
            )
            self.assertEqual(_head_moved_at(root), 1772323200)

    def test_git_with_no_head_time_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            _git_repo(root)
            store = _store_at(Path(tmp) / "store", root, "2026-01-02T00:00:00Z")
            with mock.patch("audit.rules.checks.idx.idx_03._git_query", return_value=None):
                outcome = _idx03(root, store)
        self.assertEqual(outcome.verdict.value, "UNKNOWN")
        self.assertIn("git gives no time for HEAD", outcome.summary)


if __name__ == "__main__":
    unittest.main()
