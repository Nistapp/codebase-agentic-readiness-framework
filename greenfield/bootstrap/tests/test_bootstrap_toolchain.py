# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The scaffolder's git and npm steps: `init_git`, `--install`, the toolchain verification and `run`.

npm never runs: the `--install` tests replace `bootstrap.run` with a recorder and check the commands it is given.
The git tests run real git in a temporary directory, with a fixed identity, and are skipped when git is not
installed. Standard library only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from _bootstrap_support import IDENTITY, bootstrap, run_main

GIT = shutil.which("git")
#: A fixed identity and no user or system config, so `git commit` works on a CI runner with an empty HOME.
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


class Recorder:
    """Stands in for `bootstrap.run`: records each command and answers as npm would."""

    def __init__(self, view_returncode: int = 1) -> None:
        self.commands: list[list[str]] = []
        self.view_returncode = view_returncode

    def __call__(
        self, cmd: list[str], cwd: Path, *, check: bool = True, quiet: bool = False
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(cmd)
        stdout = ""
        if cmd[:2] == ["npm", "pack"]:
            files = ["package.json", "README.md", "dist/core/index.js", "dist/core/index.d.ts"]
            entries = ", ".join(f'{{"path": "{path}", "size": 1}}' for path in files)
            stdout = f'[{{"filename": "pkg-0.1.0.tgz", "size": 1024, "files": [{entries}]}}]'
        if cmd[:2] == ["npm", "view"]:
            return subprocess.CompletedProcess(cmd, self.view_returncode, "1.2.3\n", "")
        return subprocess.CompletedProcess(cmd, 0, stdout, "")


@contextmanager
def recorded(recorder: Recorder) -> Iterator[Recorder]:
    with mock.patch.object(bootstrap, "run", recorder):
        yield recorder


class InstallTests(unittest.TestCase):
    def scaffold(self, recorder: Recorder, *flags: str) -> str:
        with tempfile.TemporaryDirectory() as tmp, recorded(recorder):
            code, out, err = run_main([str(Path(tmp) / "pkg"), "--name", "pkg", "--no-git", *IDENTITY, *flags])
        self.assertEqual(code, 0, err)
        return out

    def test_without_install_npm_never_runs(self) -> None:
        recorder = Recorder()
        self.scaffold(recorder)
        self.assertEqual(recorder.commands, [])

    def test_install_without_git_skips_the_lifecycle_scripts(self) -> None:
        # husky's prepare script needs a git repository.
        recorder = Recorder()
        out = self.scaffold(recorder, "--install", "--no-verify")
        self.assertEqual(recorder.commands, [["npm", "install", "--ignore-scripts"]])
        self.assertIn("installing with --ignore-scripts", out)

    def test_install_then_verify_runs_the_gate_build_pack_and_name_probe(self) -> None:
        recorder = Recorder()
        out = self.scaffold(recorder, "--install")
        self.assertEqual(
            recorder.commands,
            [
                ["npm", "install", "--ignore-scripts"],
                ["npm", "run", "check"],
                ["npm", "run", "build"],
                ["npm", "pack", "--dry-run", "--json"],
                ["npm", "view", "pkg", "version"],
            ],
        )
        self.assertIn("'pkg' is unclaimed on npm", out)

    def test_a_taken_name_is_reported_not_fatal(self) -> None:
        out = self.scaffold(Recorder(view_returncode=0), "--install")
        self.assertIn("'pkg' already exists on npm (v1.2.3)", out)


@unittest.skipUnless(GIT, "git is not installed; init_git runs git and has nothing to test without it")
class GitTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ, GIT_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "pkg"

    def git(self, *args: str) -> str:
        assert GIT is not None
        return subprocess.run([GIT, *args], cwd=self.target, text=True, capture_output=True, check=True).stdout

    def test_the_scaffold_is_committed_on_dev(self) -> None:
        code, out, err = run_main([str(self.target), "--name", "pkg", *IDENTITY])
        self.assertEqual(code, 0, err)
        self.assertIn("git initialised on branch 'dev'", out)
        self.assertEqual(self.git("branch", "--show-current").strip(), "dev")
        self.assertEqual(self.git("log", "--format=%s").strip(), "chore: scaffold project with world-class standards")
        self.assertEqual(self.git("status", "--porcelain"), "")
        tracked = self.git("ls-files").split()
        self.assertIn("package.json", tracked)
        self.assertIn(".husky/pre-commit", tracked)

    def test_an_existing_repository_is_left_alone(self) -> None:
        self.target.mkdir()
        assert GIT is not None
        subprocess.run([GIT, "init", "-q", "-b", "main"], cwd=self.target, check=True)
        code, out, err = run_main([str(self.target), "--name", "pkg", "--force", *IDENTITY])
        self.assertEqual(code, 0, err)
        self.assertIn("existing git repository detected", out)
        self.assertEqual(self.git("branch", "--show-current").strip(), "main")
        self.assertEqual(subprocess.run([GIT, "log"], cwd=self.target, capture_output=True).returncode, 128)

    def test_install_with_git_runs_the_lifecycle_scripts(self) -> None:
        recorder = Recorder()
        with recorded(recorder):
            # init_git goes through run too; the recorder stands in for it, so only the commands are checked.
            code, _, err = run_main([str(self.target), "--name", "pkg", "--install", "--no-verify", *IDENTITY])
        self.assertEqual(code, 0, err)
        self.assertIn(["npm", "install"], recorder.commands)
        self.assertEqual(recorder.commands[0], ["git", "init", "-b", "dev"])


class RunTests(unittest.TestCase):
    """`run` itself, on the running Python, so no other tool is needed."""

    def test_a_passing_command_returns_its_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = bootstrap.run([sys.executable, "-c", "print('hi')"], Path(tmp), quiet=True)
        self.assertEqual(result.stdout.strip(), "hi")

    def test_a_failing_command_exits_1_with_the_tail_of_its_output(self) -> None:
        script = "import sys; print('\\n'.join(f'line {i}' for i in range(30))); sys.exit(3)"
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit) as raised:
            with mock.patch("sys.stderr") as stderr, mock.patch("sys.stdout"):
                bootstrap.run([sys.executable, "-c", script], Path(tmp))
        self.assertEqual(raised.exception.code, 1)
        message = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertIn("command failed (3)", message)
        self.assertIn("line 29", message)
        self.assertNotIn("line 14\n", message)

    def test_check_false_returns_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = bootstrap.run([sys.executable, "-c", "raise SystemExit(4)"], Path(tmp), check=False, quiet=True)
        self.assertEqual(result.returncode, 4)


if __name__ == "__main__":
    unittest.main()
