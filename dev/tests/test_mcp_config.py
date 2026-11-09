# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The project MCP file, ``.mcp.json``, registers ``codebase-memory-mcp`` and nothing that runs without consent.

The file is the one source for agent tools in this repository. Claude Code and VS Code read it directly; other
harnesses copy its entry. It names a bare command, so each person's own install runs and no version is written
here (the one-place pin rule of ``test_tool_pins.py``). Approval stays with each person: the committed Claude Code
settings never pre-approve a project server.
"""

from __future__ import annotations

import json
import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from _dev_paths import REPO

MCP_FILE = REPO / ".mcp.json"
CLAUDE_SETTINGS = REPO / ".claude" / "settings.json"
SERVER = "codebase-memory-mcp"
PRE_APPROVAL_KEYS = ("enableAllProjectMcpServers", "enabledMcpjsonServers")


def servers() -> dict[str, dict[str, object]]:
    data = json.loads(MCP_FILE.read_text(encoding="utf-8"))
    result: dict[str, dict[str, object]] = data["mcpServers"]
    return result


class McpFileRegistersTheIndex(unittest.TestCase):
    def test_only_the_index_server_is_listed(self) -> None:
        self.assertEqual(set(servers()), {SERVER})

    def test_the_command_is_a_bare_name(self) -> None:
        entry = servers()[SERVER]
        command = entry["command"]
        self.assertEqual(command, SERVER, "use the bare command: no path, no version, no package runner")
        self.assertNotIn("args", entry)

    def test_no_server_carries_environment_values(self) -> None:
        for name, entry in servers().items():
            with self.subTest(server=name):
                self.assertNotIn("env", entry)
                self.assertNotIn("envFile", entry)


class ApprovalStaysWithEachPerson(unittest.TestCase):
    def test_committed_settings_do_not_pre_approve_project_servers(self) -> None:
        settings = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
        for key in PRE_APPROVAL_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, settings)


if __name__ == "__main__":
    unittest.main()
