# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""IDX checks, exercised against constructed stores.

Index and registration state is machine-local, so these tests never depend on the host's real
environment: user-level MCP configuration is isolated by redirecting ``HOME``, and the index store is
redirected with the documented ``AUDIT_INDEX_STORE`` override. Every store used here is constructed
in a temporary directory. ``IDX-03`` is asserted only on its ``UNKNOWN`` path without probes.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

IDX_CHECKS = ("IDX-01", "IDX-02", "IDX-03")


def write_store(store: Path, roots: list[str]) -> Path:
    """Build a SQLite store with a ``projects`` table holding one row per root."""
    store.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(store / "fake-project.db")
    try:
        connection.execute("CREATE TABLE projects (name TEXT PRIMARY KEY, indexed_at TEXT, root_path TEXT)")
        connection.executemany(
            "INSERT INTO projects (name, indexed_at, root_path) VALUES (?, ?, ?)",
            [(f"project-{index}", "2026-01-01T00:00:00Z", root) for index, root in enumerate(roots)],
        )
        connection.commit()
    finally:
        connection.close()
    return store


class IdxFixtureTests(unittest.TestCase):
    def test_idx01_fails_when_no_mcp_config_exists(self):
        with tempfile.TemporaryDirectory() as home:
            report = support.run_audit(support.fixture("idx-01-no-mcp-config"), env={"HOME": home})
        self.assertEqual(support.verdicts(report)["IDX-01"], "FAIL")

    def test_idx02_unknown_when_store_cannot_be_located(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"HOME": tmp, "AUDIT_INDEX_STORE": str(Path(tmp) / "absent-store")}
            report = support.run_audit(support.fixture("idx-02-no-index"), env=env)
        self.assertEqual(support.verdicts(report)["IDX-02"], "UNKNOWN")

    def test_idx03_unknown_without_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"HOME": tmp, "AUDIT_INDEX_STORE": str(Path(tmp) / "absent-store")}
            report = support.run_audit(support.fixture("idx-02-no-index"), env=env)
        self.assertEqual(support.verdicts(report)["IDX-03"], "UNKNOWN")


class IdxStoreTests(unittest.TestCase):
    def test_idx02_passes_when_store_has_a_matching_project(self):
        fixture = support.fixture("idx-02-no-index")
        with tempfile.TemporaryDirectory() as tmp:
            store = write_store(Path(tmp) / "store", [str(fixture.resolve())])
            env = {"HOME": tmp, "AUDIT_INDEX_STORE": str(store)}
            report = support.run_audit(fixture, env=env)
        self.assertEqual(support.verdicts(report)["IDX-02"], "PASS")

    def test_idx02_fails_when_store_has_no_matching_project(self):
        fixture = support.fixture("idx-02-no-index")
        with tempfile.TemporaryDirectory() as tmp:
            store = write_store(Path(tmp) / "store", ["/somewhere/else"])
            env = {"HOME": tmp, "AUDIT_INDEX_STORE": str(store)}
            report = support.run_audit(fixture, env=env)
        self.assertEqual(support.verdicts(report)["IDX-02"], "FAIL")

    def test_idx02_unknown_for_unreadable_zst_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            support.write(root, "package.json", '{"name": "x"}')
            artifact = root / ".codebase-memory" / "graph.db.zst"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b"\x28\xb5\x2f\xfd not really zstd")
            report = support.run_audit(root, env={"HOME": tmp})
        self.assertEqual(support.verdicts(report)["IDX-02"], "UNKNOWN")


class IdxRegistrationTests(unittest.TestCase):
    def _scan(self, files: dict[str, str], env: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.run_audit(root, env=env)

    def test_project_config_naming_the_server_passes(self):
        with tempfile.TemporaryDirectory() as home:
            report = self._scan({"opencode.json": '{"mcp": {"codebase-memory-mcp": {}}}'}, {"HOME": home})
        self.assertEqual(support.verdicts(report)["IDX-01"], "PASS")

    def test_user_config_naming_the_server_passes(self):
        with tempfile.TemporaryDirectory() as home:
            support.write(Path(home), ".config/opencode/opencode.jsonc", '{"mcp": {"codebase-memory-mcp": {}}}')
            report = self._scan({"README.md": "# repo\n"}, {"HOME": home})
        self.assertEqual(support.verdicts(report)["IDX-01"], "PASS")

    def test_config_without_the_server_is_partial(self):
        with tempfile.TemporaryDirectory() as home:
            report = self._scan({".mcp.json": '{"mcpServers": {"another-tool": {}}}'}, {"HOME": home})
        self.assertEqual(support.verdicts(report)["IDX-01"], "PARTIAL")


class NoUserConfigTests(unittest.TestCase):
    """`--no-user-config`: nothing under ``$HOME`` is read, and the report says so."""

    def _scan(self, home: Path, *extra: str) -> dict:
        support.write(home, ".config/opencode/opencode.jsonc", '{"mcp": {"codebase-memory-mcp": {}}}')
        root = home / "repo"
        support.write(root, "README.md", "# repo\n")
        return support.run_audit(root, env={"HOME": str(home)}, extra_args=extra)

    def test_by_default_the_user_config_is_read_and_its_path_is_in_the_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._scan(Path(tmp))
            expected = str(Path(tmp) / ".config" / "opencode" / "opencode.jsonc")
        self.assertEqual(support.verdicts(report)["IDX-01"], "PASS")
        self.assertEqual(report["provenance"]["user_config"], {"read_allowed": True, "paths_read": [expected]})

    def test_with_the_flag_nothing_under_home_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._scan(Path(tmp), "--no-user-config")
        self.assertEqual(support.verdicts(report)["IDX-01"], "FAIL")
        self.assertEqual(report["provenance"]["user_config"], {"read_allowed": False, "paths_read": []})
        summary = next(c for c in report["checks"] if c["id"] == "IDX-01")["summary"]
        self.assertIn("--no-user-config", summary)

    def test_with_the_flag_the_default_store_locations_are_not_searched(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_store(home / ".codebase-memory", [str((home / "repo").resolve())])
            report = self._scan(home, "--no-user-config")
        self.assertEqual(support.verdicts(report)["IDX-02"], "UNKNOWN")
        self.assertEqual(report["provenance"]["user_config"]["paths_read"], [])

    def test_an_explicit_store_override_still_applies_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            store = write_store(home / "store", [str((home / "repo").resolve())])
            support.write(home, "repo/README.md", "# repo\n")
            report = support.run_audit(
                home / "repo",
                env={"HOME": str(home), "AUDIT_INDEX_STORE": str(store)},
                extra_args=("--no-user-config",),
            )
        self.assertEqual(support.verdicts(report)["IDX-02"], "PASS")
        self.assertEqual(report["provenance"]["user_config"]["paths_read"], [str(store)])


if __name__ == "__main__":
    unittest.main()
