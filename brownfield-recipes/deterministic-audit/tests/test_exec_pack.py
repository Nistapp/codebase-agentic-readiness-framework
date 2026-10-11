# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC execution-determinism checks against their one-defect fixtures.

Each fixture is a minimal repository that fails exactly one `EXEC` check. The audit runs as a
subprocess through `tests/support.py`, so the fixtures exercise the real end-to-end path.

`EXEC-02` and `EXEC-05` read git's tracked-file set, so their fixture is copied into a temporary
git repository created inside the test's own temp directory — never the audit repo. The same
fixtures are also exercised *without* git to prove the checks degrade to `UNKNOWN`, never `PASS`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks.execution import _lock_consistency, _lockfile_paths  # noqa: E402
from audit.scan import build_inventory  # noqa: E402

#: fixture directory -> (check id under test, expected verdict, needs a git repository)
FIXTURES: dict[str, tuple[str, str, bool]] = {
    "exec-01-unpinned": ("EXEC-01", "FAIL", False),
    "exec-02-no-lockfile": ("EXEC-02", "FAIL", True),
    "exec-03-no-setup": ("EXEC-03", "FAIL", False),
    "exec-04-missing-env": ("EXEC-04", "FAIL", False),
    "exec-05-generated": ("EXEC-05", "FAIL", True),
    "exec-06-broken-command": ("EXEC-06", "FAIL", False),
    "exec-07-dual-lint": ("EXEC-07", "FAIL", False),
}

EXEC_CHECKS = tuple(f"EXEC-0{i}" for i in range(1, 8))


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class ExecFixtureTests(unittest.TestCase):
    def _prepare(self, name: str, *, git: bool) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / name
        shutil.copytree(support.fixture(name), target)
        if git:
            self.assertEqual(_git(target, "init").returncode, 0)
            self.assertEqual(_git(target, "add", "-A").returncode, 0)
        return target

    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected, git) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(self._prepare(name, git=git))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in EXEC_CHECKS if verdicts[cid] == "FAIL")
                self.assertEqual(failing, [check], f"{name}: unexpected EXEC FAILs {failing}")

    def test_tracked_state_unavailable_degrades_to_unknown_not_pass(self):
        for name, _check in (("exec-02-no-lockfile", "EXEC-02"), ("exec-05-generated", "EXEC-05")):
            with self.subTest(fixture=name):
                report = support.run_audit(self._prepare(name, git=False))
                verdicts = support.verdicts(report)
                self.assertEqual(
                    verdicts[_check], "UNKNOWN", f"{name}: without git the check must not infer a tracked set"
                )

    def test_a_broken_command_lists_its_evidence(self):
        report = support.run_audit(self._prepare("exec-06-broken-command", git=False))
        findings = [f for f in report["findings"] if f["check"] == "EXEC-06"]
        self.assertTrue(findings, "EXEC-06 failed without emitting a finding")
        self.assertTrue(
            any("does-not-exist" in (e.get("note") or "") for f in findings for e in f["evidence"]),
            "the unresolvable command is not named in the evidence",
        )


class Exec02LockfilePathTests(unittest.TestCase):
    """A lockfile is found at any depth, and is tracked or not by the path it was found at."""

    NODE = '{"name": "x", "version": "0.1.0"}\n'
    LOCK = '{"name": "x", "version": "0.1.0", "lockfileVersion": 3, "requires": true, "packages": {}}\n'

    OTHER_LOCK = (
        '{"name": "x", "version": "0.1.0", "lockfileVersion": 3, "requires": true, '
        '"packages": {"": {}, "node_modules/right-pad": {"version": "1.0.0"}}}\n'
    )

    def audit(self, files: dict[str, str], *, track: tuple[str, ...] | None = None):
        """Audit ``files`` as a git repository in which ``track`` (default: all of them) is staged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            self.assertEqual(_git(root, "init").returncode, 0)
            self.assertEqual(_git(root, "add", "-A" if track is None else "--", *(track or ())).returncode, 0)
            report = support.run_audit(root)
        check = next(c for c in report["checks"] if c["id"] == "EXEC-02")
        return check, [f for f in report["findings"] if f["check"] == "EXEC-02"]

    def test_a_tracked_lockfile_in_a_subdirectory_is_tracked(self):
        check, findings = self.audit({"app/package.json": self.NODE, "app/package-lock.json": self.LOCK})
        self.assertEqual(
            (check["verdict"], check["summary"]), ("PARTIAL", "consistency unverified: app/package-lock.json")
        )
        self.assertEqual(findings, [])

    def test_a_lockfile_in_a_subdirectory_that_git_does_not_track_is_still_untracked(self):
        check, findings = self.audit(
            {"app/package.json": self.NODE, "app/package-lock.json": self.LOCK}, track=("app/package.json",)
        )
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(
            [(f["statement"], f["evidence"]) for f in findings],
            [
                (
                    "An agent cannot install identical dependencies on every run because app/package-lock.json "
                    "exists but is not tracked, so a fresh checkout does not get it.",
                    [{"path": "app/package-lock.json", "line": None, "note": None}],
                )
            ],
        )

    def test_a_lockfile_that_a_rule_ignores_is_no_lockfile_at_all(self):
        check, findings = self.audit(
            {"app/package.json": self.NODE, "app/package-lock.json": self.LOCK, ".gitignore": "package-lock.json\n"}
        )
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("the node project has no lockfile", findings[0]["statement"])

    def test_the_shallowest_tracked_lockfile_is_the_one_read(self):
        check, _ = self.audit(
            {
                "package.json": self.NODE,
                "package-lock.json": self.LOCK,
                "app/package.json": self.NODE,
                "app/package-lock.json": self.LOCK,
            }
        )
        self.assertEqual((check["verdict"], check["summary"]), ("PASS", "tracked: package-lock.json"))
        check, _ = self.audit(
            {"a/b/package.json": self.NODE, "a/b/package-lock.json": self.LOCK, "z/package-lock.json": self.LOCK}
        )
        self.assertEqual(check["summary"], "consistency unverified: z/package-lock.json")

    def test_a_root_lockfile_is_still_compared_with_the_root_manifest(self):
        manifest = '{"name": "x", "version": "0.1.0", "dependencies": {"left-pad": "1.3.0"}}\n'
        check, findings = self.audit({"package.json": manifest, "package-lock.json": self.OTHER_LOCK})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(
            findings[0]["statement"],
            "An agent cannot install identical dependencies on every run because package-lock.json is tracked "
            "but omits manifest dependencies: left-pad.",
        )

    def test_the_lockfiles_of_an_ecosystem_are_listed_shallowest_first_then_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (
                "z/package-lock.json",
                "a/b/package-lock.json",
                "package-lock.json",
                "a/yarn.lock",
                "notes.txt",
            ):
                support.write(root, rel, "x\n")
            inventory = build_inventory(root)
        self.assertEqual(
            _lockfile_paths(inventory, "node"),
            ["package-lock.json", "a/yarn.lock", "z/package-lock.json", "a/b/package-lock.json"],
        )

    def test_only_a_root_lockfile_is_compared_with_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "package.json", '{"dependencies": {"left-pad": "1"}}\n')
            support.write(root, "package-lock.json", self.OTHER_LOCK)
            support.write(root, "app/package-lock.json", self.OTHER_LOCK)
            inventory = build_inventory(root)
            self.assertEqual(_lock_consistency(inventory, "node", "package-lock.json"), ("mismatch", {"left-pad"}))
            self.assertEqual(_lock_consistency(inventory, "node", "app/package-lock.json"), ("unverified", set()))


class Exec02MessageTests(unittest.TestCase):
    """What a person reads when EXEC-02 has something to say, pinned exactly."""

    NODE = '{"name": "x", "version": "0.1.0"}\n'
    OTHER_LOCK = '{"packages": {"": {}, "node_modules/other": {}}}\n'
    CARGO_LOCK = '[[package]]\nname = "serde"\n'
    ACTION = "An agent cannot install identical dependencies on every run because"

    def audit(self, files: dict[str, str], *, git: bool = True, track: tuple[str, ...] | None = None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            if git:
                self.assertEqual(_git(root, "init").returncode, 0)
                self.assertEqual(_git(root, "add", "-A" if track is None else "--", *(track or ())).returncode, 0)
            report = support.run_audit(root)
        check = next(c for c in report["checks"] if c["id"] == "EXEC-02")
        return check, [f for f in report["findings"] if f["check"] == "EXEC-02"]

    def test_no_recognised_ecosystem_expects_no_lockfile(self):
        check, findings = self.audit({"README.md": "# x\n"})
        self.assertEqual(
            (check["verdict"], check["summary"]), ("UNKNOWN", "no recognised ecosystem, so no lockfile is expected")
        )
        self.assertEqual(findings, [])

    def test_without_git_the_tracked_state_is_unknown(self):
        check, _ = self.audit({"package.json": self.NODE}, git=False)
        self.assertEqual(
            (check["verdict"], check["summary"]),
            ("UNKNOWN", "git could not report tracked files, so the lockfile's tracked state is unknown"),
        )

    def test_a_project_with_no_lockfile_lists_the_names_it_looked_for(self):
        check, findings = self.audit({"package.json": self.NODE})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(
            [(f["statement"], f["evidence"], f["remediation"], f["severity"]) for f in findings],
            [
                (
                    f"{self.ACTION} the node project has no lockfile (package-lock.json, pnpm-lock.yaml, yarn.lock, "
                    "bun.lockb), so a fresh install resolves whatever versions are current.",
                    [],
                    "Generate the lockfile with the project's package manager and commit it.",
                    "BLOCKER",
                )
            ],
        )

    def test_untracked_lockfiles_are_listed_in_path_order_with_their_paths_as_evidence(self):
        locks = {"a/package-lock.json": "{}\n", "z/package-lock.json": "{}\n"}
        _, findings = self.audit({"package.json": self.NODE, **locks}, track=("package.json",))
        self.assertEqual(
            [(f["statement"], f["evidence"], f["remediation"]) for f in findings],
            [
                (
                    f"{self.ACTION} a/package-lock.json, z/package-lock.json exists but is not tracked, so a fresh "
                    "checkout does not get it.",
                    [
                        {"path": "a/package-lock.json", "line": None, "note": None},
                        {"path": "z/package-lock.json", "line": None, "note": None},
                    ],
                    "Commit the lockfile; add it to .gitignore only if the team has deliberately chosen floating "
                    "dependencies.",
                )
            ],
        )

    def test_the_first_twelve_missing_dependencies_are_named(self):
        deps = ", ".join(f'"d{i:02d}": "1"' for i in range(13))
        _, findings = self.audit(
            {"package.json": '{"dependencies": {%s}}\n' % deps, "package-lock.json": self.OTHER_LOCK}
        )
        self.assertEqual(
            [(f["statement"], f["evidence"], f["remediation"]) for f in findings],
            [
                (
                    f"{self.ACTION} package-lock.json is tracked but omits manifest dependencies: d00, d01, d02, "
                    "d03, d04, d05, d06, d07, d08, d09, d10, d11.",
                    [{"path": "package-lock.json", "line": None, "note": "lockfile out of step with the manifest"}],
                    "Re-run the package manager's install/lock step and commit the updated lockfile.",
                )
            ],
        )

    def test_the_detail_says_which_lockfiles_were_tracked_and_which_could_not_be_checked(self):
        files = {"package.json": self.NODE, "package-lock.json": self.OTHER_LOCK, "Cargo.toml": "[dependencies]\n"}
        check, _ = self.audit({**files, "Cargo.lock": self.CARGO_LOCK})
        self.assertEqual((check["verdict"], check["summary"]), ("PASS", "tracked: package-lock.json, Cargo.lock"))
        check, _ = self.audit({**files, "crate/Cargo.lock": self.CARGO_LOCK})
        self.assertEqual(
            (check["verdict"], check["summary"]),
            ("PARTIAL", "tracked: package-lock.json; consistency unverified: crate/Cargo.lock"),
        )
        check, _ = self.audit({**files, "crate/Cargo.lock": self.CARGO_LOCK, "other/Cargo.lock": self.CARGO_LOCK})
        self.assertEqual(check["summary"], "tracked: package-lock.json; consistency unverified: crate/Cargo.lock")
        two = {"package.json": self.NODE, "app/package-lock.json": self.OTHER_LOCK, "Cargo.toml": "[dependencies]\n"}
        check, _ = self.audit({**two, "crate/Cargo.lock": self.CARGO_LOCK})
        self.assertEqual(check["summary"], "consistency unverified: app/package-lock.json, crate/Cargo.lock")


class LockConsistencyTests(unittest.TestCase):
    def state(self, files: dict[str, str], ecosystem: str, lockfile: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return _lock_consistency(build_inventory(root), ecosystem, lockfile)

    LOCK = '{"packages": {"": {}, "node_modules/left-pad": {}, "node_modules/right-pad": {}}}\n'

    def test_a_manifest_that_the_lock_covers_is_ok(self):
        manifest = '{"dependencies": {"left-pad": "1"}, "devDependencies": {"right-pad": "1"}}\n'
        self.assertEqual(
            self.state({"package.json": manifest, "package-lock.json": self.LOCK}, "node", "package-lock.json"),
            ("ok", set()),
        )

    def test_a_manifest_with_no_dependencies_is_ok_whatever_the_lock_holds(self):
        self.assertEqual(
            self.state({"package.json": "{}\n", "package-lock.json": self.LOCK}, "node", "package-lock.json"),
            ("ok", set()),
        )

    def test_a_lock_with_no_packages_cannot_be_compared(self):
        manifest = '{"dependencies": {"left-pad": "1"}}\n'
        lock = '{"packages": {}}\n'
        self.assertEqual(
            self.state({"package.json": manifest, "package-lock.json": lock}, "node", "package-lock.json"),
            ("unverified", set()),
        )

    def test_no_manifest_or_no_readable_lock_cannot_be_compared(self):
        self.assertEqual(
            self.state({"package-lock.json": self.LOCK}, "node", "package-lock.json"), ("unverified", set())
        )
        manifest = '{"dependencies": {"left-pad": "1"}}\n'
        self.assertEqual(
            self.state({"package.json": manifest, "package-lock.json": "not json"}, "node", "package-lock.json"),
            ("unverified", set()),
        )
        self.assertEqual(self.state({"package.json": manifest}, "node", "package-lock.json"), ("unverified", set()))

    def test_a_dependency_the_lock_omits_is_named(self):
        manifest = '{"dependencies": {"left-pad": "1", "up-pad": "1"}}\n'
        self.assertEqual(
            self.state({"package.json": manifest, "package-lock.json": self.LOCK}, "node", "package-lock.json"),
            ("mismatch", {"up-pad"}),
        )

    def test_a_lock_below_the_root_is_not_compared_with_the_root_manifest(self):
        manifest = '[dependencies]\nserde = "1"\n'
        lock = '[[package]]\nname = "other"\n'
        files = {"Cargo.toml": manifest, "Cargo.lock": lock, "crate/Cargo.lock": lock}
        self.assertEqual(self.state(files, "rust", "Cargo.lock"), ("mismatch", {"serde"}))
        self.assertEqual(self.state(files, "rust", "crate/Cargo.lock"), ("unverified", set()))


if __name__ == "__main__":
    unittest.main()
