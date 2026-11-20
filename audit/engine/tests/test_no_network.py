# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine makes no network request by default (ADR-0004: determinism; root ``AGENTS.md``: no network).

Each test runs a full audit in this process with the socket entry points and ``urllib.request.urlopen`` replaced
by a guard that records the attempt and raises. The run must complete with exit 0 and the guard must record
nothing. A check that swallowed the raised error would still leave its attempt in the record.

What this covers, and what it does not:

* It tests the default path: no ``--run-gates``, so no probe runs. That is the only path the engine promises is
  offline.
* A probe (``--run-gates`` plus ``--allow-probe <verb>``) runs the target's own command in a subprocess. That
  command may reach the network, and the operator opts in to it (ADR-0002). A socket patch cannot see a
  subprocess, so the opt-in path is out of scope here.
* The engine's own subprocesses are local ``git`` reads (``rev-parse``, ``status``, ``ls-files``), which open no
  connection.
"""

from __future__ import annotations

import contextlib
import io
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit import cli  # noqa: E402
from audit.rules.checks import con  # noqa: E402

SCAFFOLDER = Path(__file__).resolve().parents[3] / "greenfield" / "bootstrap" / "bootstrap.py"
TEMPLATES = SCAFFOLDER.parents[1] / "templates"

#: Fixtures that reach many packs: a passing baseline repository, a GitHub CI repository and an npm repository.
FIXTURES = ("base-ok", "ci-ok-gh", "cmd-ok-npm")


class _NetworkGuard:
    """Replaces the network entry points; each call is recorded, then refused."""

    def __init__(self) -> None:
        self.attempts: list[str] = []

    def _refuse(self, name: str):
        def refuse(*args: object, **kwargs: object) -> object:
            self.attempts.append(f"{name}{args!r}")
            raise OSError(f"network disabled in this test: {name}")

        return refuse

    @contextlib.contextmanager
    def active(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(socket.socket, "connect", self._refuse("socket.connect")))
            stack.enter_context(mock.patch.object(socket.socket, "connect_ex", self._refuse("socket.connect_ex")))
            stack.enter_context(mock.patch.object(socket, "create_connection", self._refuse("create_connection")))
            stack.enter_context(mock.patch.object(socket, "getaddrinfo", self._refuse("getaddrinfo")))
            stack.enter_context(mock.patch.object(urllib.request, "urlopen", self._refuse("urlopen")))
            yield self


def _audit_offline(target: Path) -> tuple[int, str, list[str]]:
    """Audit ``target`` in process behind the guard; return ``(exit code, stderr, attempts)``."""
    guard = _NetworkGuard()
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "report.json"
        err = io.StringIO()
        with guard.active(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = cli.run([str(target), "--format", "both", "--out", str(out)])
        if code == 0:
            assert out.is_file() and out.with_suffix(".md").is_file(), "the audit wrote no report"
    return code, err.getvalue(), guard.attempts


class NoNetworkTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(con.set_emit_target, None)

    def test_guard_refuses_and_records(self):
        guard = _NetworkGuard()
        with guard.active():
            with self.assertRaises(OSError):
                socket.create_connection(("192.0.2.1", 80), timeout=1)
            with self.assertRaises(OSError):
                urllib.request.urlopen("http://192.0.2.1/")
        self.assertEqual(len(guard.attempts), 2)

    def test_fixture_audits_open_no_connection(self):
        for name in FIXTURES:
            with self.subTest(fixture=name):
                code, err, attempts = _audit_offline(support.fixture(name))
                self.assertEqual(code, 0, err)
                self.assertEqual(attempts, [], f"{name}: the default audit tried the network")

    def test_scaffold_audit_opens_no_connection(self):
        self.assertTrue(SCAFFOLDER.is_file(), f"scaffolder not found at {SCAFFOLDER}")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "scaffold"
            target.mkdir()
            proc = subprocess.run(
                [sys.executable, str(SCAFFOLDER), str(target), "--no-git", "--templates", str(TEMPLATES)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            code, err, attempts = _audit_offline(target)
        self.assertEqual(code, 0, err)
        self.assertEqual(attempts, [], "the default audit of a scaffold tried the network")


if __name__ == "__main__":
    unittest.main()
