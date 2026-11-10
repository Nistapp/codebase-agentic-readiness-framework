# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``mcp_config.py``: one translation per harness format, safe merges, the record and the check."""

from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import mcp_config

SERVER: dict[str, object] = {"command": "codebase-memory-mcp"}
WITH_ARGS: dict[str, object] = {"command": "tool", "args": ["--stdio"], "env": {"MODE": "fast"}}


class Workspace(unittest.TestCase):
    """A temporary repository root with a ``.mcp.json``, and a temporary home."""

    servers: dict[str, dict[str, object]] = {"codebase-memory-mcp": SERVER}

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.home = Path(tmp.name) / "home"
        self.root.mkdir()
        self.home.mkdir()
        (self.root / ".mcp.json").write_text(json.dumps({"mcpServers": self.servers}), encoding="utf-8")

    def run_tool(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = mcp_config.main(list(argv), root=self.root, home=self.home)
        return code, out.getvalue(), err.getvalue()


class TranslatePerHarness(unittest.TestCase):
    def test_cursor_uses_mcp_servers_with_stdio_type(self) -> None:
        self.assertEqual(
            json.loads(mcp_config.render("cursor", {"x": WITH_ARGS})),
            {"mcpServers": {"x": {"type": "stdio", "command": "tool", "args": ["--stdio"], "env": {"MODE": "fast"}}}},
        )

    def test_gemini_uses_mcp_servers(self) -> None:
        self.assertEqual(
            json.loads(mcp_config.render("gemini", {"x": WITH_ARGS})),
            {"mcpServers": {"x": {"command": "tool", "args": ["--stdio"], "env": {"MODE": "fast"}}}},
        )

    def test_opencode_uses_mcp_servers_local_with_command_array(self) -> None:
        self.assertEqual(
            json.loads(mcp_config.render("opencode", {"x": WITH_ARGS})),
            {
                "mcp": {
                    "servers": {"x": {"type": "local", "command": ["tool", "--stdio"], "environment": {"MODE": "fast"}}}
                }
            },
        )

    def test_codex_writes_a_toml_table_that_parses_back(self) -> None:
        text = mcp_config.render("codex", {"codebase-memory-mcp": SERVER, "x": WITH_ARGS})
        self.assertIn("[mcp_servers.codebase-memory-mcp]\n", text)
        self.assertEqual(
            tomllib.loads(text)["mcp_servers"],
            {"codebase-memory-mcp": SERVER, "x": WITH_ARGS},
        )

    def test_codex_quotes_a_key_that_is_not_bare(self) -> None:
        text = mcp_config.render("codex", {"my server": SERVER})
        self.assertEqual(tomllib.loads(text)["mcp_servers"], {"my server": SERVER})


class Targets(Workspace):
    def test_native_harnesses_have_nothing_to_write(self) -> None:
        for harness in ("claude-code", "vscode", "antigravity", "other"):
            for scope in ("project", "user"):
                with self.subTest(harness=harness, scope=scope):
                    self.assertIsNone(mcp_config.target(harness, scope, self.root, self.home).path)

    def test_paths_per_harness_and_scope(self) -> None:
        expected = {
            ("cursor", "project"): self.root / ".cursor/mcp.json",
            ("cursor", "user"): self.home / ".cursor/mcp.json",
            ("gemini", "project"): self.root / ".gemini/settings.json",
            ("gemini", "user"): self.home / ".gemini/settings.json",
            ("opencode", "project"): self.root / "opencode.json",
            ("opencode", "user"): self.home / ".config/opencode/opencode.json",
            ("codex", "project"): self.root / ".codex/config.toml",
            ("codex", "user"): self.home / ".codex/config.toml",
        }
        for (harness, scope), path in expected.items():
            with self.subTest(harness=harness, scope=scope):
                self.assertEqual(mcp_config.target(harness, scope, self.root, self.home).path, path)

    def test_write_for_a_native_harness_writes_nothing(self) -> None:
        code, out, _ = self.run_tool("write", "--harness", "claude-code")
        self.assertEqual(code, 0)
        self.assertIn("approve", out)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".mcp.json"])

    def test_show_prints_the_path_and_entry_without_writing(self) -> None:
        code, out, _ = self.run_tool("show", "--harness", "gemini")
        self.assertEqual(code, 0)
        self.assertIn(".gemini/settings.json", out)
        self.assertIn('"codebase-memory-mcp"', out)
        self.assertFalse((self.root / ".gemini").exists())


class WriteMerges(Workspace):
    def test_creates_each_file_when_absent(self) -> None:
        for harness in ("cursor", "gemini", "opencode", "codex"):
            with self.subTest(harness=harness):
                code, out, _ = self.run_tool("write", "--harness", harness)
                self.assertEqual(code, 0)
                self.assertIn("added codebase-memory-mcp", out)
        self.assertEqual(
            json.loads((self.root / "opencode.json").read_text())["$schema"], "https://opencode.ai/config.json"
        )
        self.assertIn(
            "codebase-memory-mcp", tomllib.loads((self.root / ".codex/config.toml").read_text())["mcp_servers"]
        )

    def test_keeps_other_settings_and_servers(self) -> None:
        path = self.root / ".gemini" / "settings.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "o"}}}), encoding="utf-8")
        self.assertEqual(self.run_tool("write", "--harness", "gemini")[0], 0)
        data = json.loads(path.read_text())
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(set(data["mcpServers"]), {"other", "codebase-memory-mcp"})

    def test_appends_to_an_existing_toml_file(self) -> None:
        path = self.home / ".codex" / "config.toml"
        path.parent.mkdir()
        path.write_text('model = "x"\n\n[mcp_servers.other]\ncommand = "o"\n', encoding="utf-8")
        self.assertEqual(self.run_tool("write", "--harness", "codex", "--scope", "user")[0], 0)
        data = tomllib.loads(path.read_text())
        self.assertEqual(data["model"], "x")
        self.assertEqual(set(data["mcp_servers"]), {"other", "codebase-memory-mcp"})

    def test_second_write_changes_nothing(self) -> None:
        self.run_tool("write", "--harness", "cursor")
        before = (self.root / ".cursor/mcp.json").read_text()
        code, out, _ = self.run_tool("write", "--harness", "cursor")
        self.assertEqual(code, 0)
        self.assertIn("already set", out)
        self.assertEqual((self.root / ".cursor/mcp.json").read_text(), before)

    def test_refuses_to_replace_a_different_entry(self) -> None:
        for harness, path, text in (
            ("cursor", ".cursor/mcp.json", json.dumps({"mcpServers": {"codebase-memory-mcp": {"command": "/opt/x"}}})),
            ("codex", ".codex/config.toml", '[mcp_servers.codebase-memory-mcp]\ncommand = "/opt/x"\n'),
        ):
            with self.subTest(harness=harness):
                file = self.root / path
                file.parent.mkdir(exist_ok=True)
                file.write_text(text, encoding="utf-8")
                code, _, err = self.run_tool("write", "--harness", harness)
                self.assertEqual(code, 1)
                self.assertIn("already has a different", err)
                self.assertEqual(file.read_text(), text)

    def test_refuses_a_file_that_is_not_plain_json(self) -> None:
        path = self.root / "opencode.json"
        path.write_text("{ // a comment\n}", encoding="utf-8")
        code, _, err = self.run_tool("write", "--harness", "opencode")
        self.assertEqual(code, 2)
        self.assertIn("paste the entry by hand", err)


class FirstRunRecord(Workspace):
    def test_status_is_not_asked_until_recorded(self) -> None:
        self.assertEqual(self.run_tool("status", "--harness", "opencode")[1].strip(), "not asked")

    def test_record_keeps_one_answer_per_harness(self) -> None:
        self.run_tool("record", "--harness", "opencode", "--answer", "accepted")
        self.run_tool("record", "--harness", "claude-code", "--answer", "declined")
        self.assertTrue(self.run_tool("status", "--harness", "opencode")[1].startswith("asked: accepted on "))
        self.assertTrue(self.run_tool("status", "--harness", "claude-code")[1].startswith("asked: declined on "))
        data = json.loads((self.root / ".agentic-readiness/setup.json").read_text())
        self.assertEqual(data["harnesses"]["opencode"]["servers"], ["codebase-memory-mcp"])
        self.assertEqual(data["harnesses"]["opencode"]["scope"], "project")


class CheckCommands(Workspace):
    def test_missing_command_prints_install_routes_without_running_them(self) -> None:
        with (
            mock.patch("mcp_config.shutil.which", return_value=None),
            mock.patch("mcp_config.subprocess.run") as run,
        ):
            code, out, _ = self.run_tool("check")
        self.assertEqual(code, 1)
        self.assertIn("not on PATH", out)
        self.assertIn("--skip-config", out)
        run.assert_not_called()

    def test_present_command_reports_its_version(self) -> None:
        bin_dir = self.root.parent / "bin"
        bin_dir.mkdir()
        script = bin_dir / "codebase-memory-mcp"
        script.write_text("#!/bin/sh\necho 'codebase-memory-mcp 9.9.9'\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}):
            code, out, _ = self.run_tool("check")
        self.assertEqual(code, 0)
        self.assertIn("codebase-memory-mcp 9.9.9", out)


class HarnessesThatKeepTheirOwnConfig(Workspace):
    servers = {"codebase-memory-mcp": SERVER, "x": WITH_ARGS}

    def test_antigravity_prints_agy_mcp_add_and_writes_nothing(self) -> None:
        code, out, _ = self.run_tool("write", "--harness", "antigravity")
        self.assertEqual(code, 0)
        self.assertIn("agy mcp add codebase-memory-mcp -- codebase-memory-mcp\n", out)
        self.assertIn("agy mcp add --env MODE=fast x -- tool --stdio\n", out)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".mcp.json"])

    def test_claude_code_user_scope_prints_claude_mcp_add(self) -> None:
        out = self.run_tool("show", "--harness", "claude-code", "--scope", "user")[1]
        self.assertIn("claude mcp add --scope user codebase-memory-mcp -- codebase-memory-mcp\n", out)

    def test_other_prints_the_plain_entry(self) -> None:
        out = self.run_tool("show", "--harness", "other")[1]
        entry = json.loads(out[out.index("{") :])
        self.assertEqual(entry, {"mcpServers": self.servers})

    def test_other_can_be_recorded(self) -> None:
        self.run_tool("record", "--harness", "other", "--answer", "declined")
        self.assertTrue(self.run_tool("status", "--harness", "other")[1].startswith("asked: declined"))


class Detect(Workspace):
    def detect_with(self, environ: dict[str, str]) -> str:
        with mock.patch.dict(os.environ, environ, clear=True):
            return self.run_tool("detect")[1]

    def test_one_marker_names_the_harness(self) -> None:
        for variable, harness in (
            ("CLAUDECODE", "claude-code"),
            ("ANTIGRAVITY_AGENT", "antigravity"),
            ("OPENCODE", "opencode"),
        ):
            with self.subTest(variable=variable):
                self.assertTrue(self.detect_with({variable: "1"}).startswith(f"{harness} "))

    def test_nested_harnesses_are_ambiguous(self) -> None:
        out = self.detect_with({"CLAUDECODE": "1", "ANTIGRAVITY_AGENT": "1"})
        self.assertTrue(out.startswith("ambiguous: claude-code, antigravity"))
        self.assertIn("Ask the person", out)

    def test_no_marker_is_unknown(self) -> None:
        self.assertTrue(self.detect_with({"AI_AGENT": "something"}).startswith("unknown"))


class SourceErrors(Workspace):
    def test_missing_source_is_a_usage_error(self) -> None:
        (self.root / ".mcp.json").unlink()
        self.assertEqual(self.run_tool("show", "--harness", "cursor")[0], 2)


class RepositorySource(unittest.TestCase):
    def test_this_repository_translates_for_every_harness(self) -> None:
        servers = mcp_config.load_servers(mcp_config.REPO)
        for harness in ("cursor", "gemini", "opencode", "codex"):
            with self.subTest(harness=harness):
                self.assertIn("codebase-memory-mcp", mcp_config.render(harness, servers))


if __name__ == "__main__":
    unittest.main()
