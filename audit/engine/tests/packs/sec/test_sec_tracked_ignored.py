# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Tracked files an ignore rule also matches: `SEC-01` reads env-like names, `SEC-03` key material (issue #12).

The list comes from one helper, ``audit.rules.checks._common.tracked_and_ignored``: git's tracked set less the
excluded and set-aside paths, matched by the engine's scoped ignore matcher. It never asks git which files are
ignored, so the host's global excludes file does not change the answer. The checks run in-process here so that
coverage traces them; the two fixtures also run end to end.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks._common import tracked_and_ignored  # noqa: E402
from audit.rules.checks.sec import (  # noqa: E402
    _KEY_MATERIAL_RULES,
    _SECRET_SHAPES,
    _is_env_like_name,
    _key_material,
    check_sec01,
    check_sec03,
)
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from audit.target import resolve_target  # noqa: E402

#: Every secret shape SEC-03 probes, one rule each, so only a forced file is a defect.
FULL_IGNORE = ".env\n.env.*\nid_rsa*\n*.pem\n*.key\n*.p12\n*.pfx\n*.keystore\n*.crt\n*.cer\n.aws/*\n"
SEC_CHECKS = ("SEC-01", "SEC-02", "SEC-03")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class NameRuleTests(unittest.TestCase):
    def test_an_env_like_name_starts_with_dot_env_ends_with_env_or_starts_with_env_dot(self):
        for rel in (".env", ".env.prod", ".envrc", "config/prod.env", "deploy/env.prod", "a/b/.env.local"):
            with self.subTest(rel=rel):
                self.assertTrue(_is_env_like_name(rel))

    def test_a_template_or_an_unrelated_name_is_not_env_like(self):
        for rel in (".env.example", "env.example", "prod.env.sample", "x/.env.template", "envoy.yaml", "dotenv.py"):
            with self.subTest(rel=rel):
                self.assertFalse(_is_env_like_name(rel))

    def test_key_material_is_every_non_dotenv_shape_at_any_depth(self):
        cases = {
            "server.key": "key",
            "certs/server.pem": "PEM",
            "a/b/id_rsa_old": "ssh private key",
            "x/.aws/credentials": "AWS credentials",
            "app.keystore": "keystore",
            "site.cer": "certificate (.cer)",
        }
        for rel, label in cases.items():
            with self.subTest(rel=rel):
                self.assertEqual(_key_material(rel), label)
        for rel in (".env", "config/prod.env", "README.md", "keys.md"):
            with self.subTest(rel=rel):
                self.assertIsNone(_key_material(rel))

    def test_the_key_shapes_are_the_probed_shapes_without_dotenv(self):
        probed = {label for label, _sample in _SECRET_SHAPES} - {"dotenv", "dotenv variant"}
        self.assertEqual({label for label, _rule in _KEY_MATERIAL_RULES}, probed)


class TrackedAndIgnoredTests(unittest.TestCase):
    def repo(self, files: dict[str, str], *, forced: tuple[str, ...] = (), git: bool = True) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        support.write(root, "README.md", "x\n")
        for rel, text in files.items():
            support.write(root, rel, text)
        if git:
            self.assertEqual(_git(root, "init").returncode, 0)
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
            for rel in forced:
                self.assertEqual(_git(root, "add", "-f", rel).returncode, 0)
        return root

    def run_check(self, root: Path, check, check_id: str, excludes: tuple[str, ...] = ()):
        inventory = build_inventory(root, extra_excludes=excludes)
        return check(
            spec=REGISTRY_BY_ID[check_id],
            target=resolve_target(root),
            inventory=inventory,
            stack=detect_stack(inventory),
            components=None,
            session=None,
        )

    def listed(self, root: Path, excludes: tuple[str, ...] = ()) -> list[str] | None:
        return tracked_and_ignored(resolve_target(root), build_inventory(root, extra_excludes=excludes))

    def test_a_force_added_file_and_a_file_under_an_ignored_directory_are_listed(self):
        root = self.repo(
            {".gitignore": "*.key\nsecrets/\n", "server.key": "x\n", "secrets/a.pem": "x\n", "src/app.py": "x\n"},
            forced=("server.key", "secrets/a.pem"),
        )
        self.assertEqual(self.listed(root), ["secrets/a.pem", "server.key"])

    def test_git_unable_to_answer_is_none(self):
        root = self.repo({".gitignore": "*.key\n", "server.key": "x\n"}, git=False)
        self.assertIsNone(self.listed(root))

    def test_an_excluded_path_is_not_listed(self):
        root = self.repo({".gitignore": "*.key\n", "keys/server.key": "x\n"}, forced=("keys/server.key",))
        self.assertEqual(self.listed(root, ("keys/*",)), [])

    def test_the_hosts_global_excludes_do_not_change_the_list(self):
        root = self.repo({".gitignore": "*.pem\n", "server.key": "x\n"})
        # An excludes file git reads and the scoped matcher does not; it sits inside `.git/`, out of the walk.
        excludes = support.write(root, ".git/host-excludes", "*.key\n")
        self.assertEqual(_git(root, "config", "core.excludesFile", str(excludes)).returncode, 0)
        self.assertEqual(_git(root, "check-ignore", "-q", "--no-index", "server.key").returncode, 0)
        self.assertEqual(self.listed(root), [])
        sec03 = self.run_check(root, check_sec03, "SEC-03")
        self.assertNotIn("server.key", [finding.path for finding in sec03.findings])

    def test_sec01_fails_on_a_force_added_env_like_file(self):
        root = self.repo(
            {".gitignore": FULL_IGNORE + "*.env\n", "config/prod.env": "A=1\n"}, forced=("config/prod.env",)
        )
        outcome = self.run_check(root, check_sec01, "SEC-01")
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual(outcome.findings[0].path, "config/prod.env")

    def test_sec01_reads_the_wider_name_only_past_an_ignore_rule(self):
        # `prod.env` that no rule ignores is tracked on purpose; only `.env` and `.env.*` count by name alone.
        root = self.repo({".gitignore": FULL_IGNORE, "config/prod.env": "A=1\n"})
        self.assertEqual(self.run_check(root, check_sec01, "SEC-01").verdict.value, "PASS")

    def test_sec03_fails_with_its_own_finding_on_force_added_key_material(self):
        root = self.repo({".gitignore": FULL_IGNORE, "server.key": "x\n"}, forced=("server.key",))
        outcome = self.run_check(root, check_sec03, "SEC-03")
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].path, "server.key")
        self.assertEqual([(e.path, e.note) for e in outcome.findings[0].evidence], [("server.key", "key")])
        self.assertIn("tracked although ignored: server.key", outcome.summary)

    def test_sec03_keeps_the_coverage_finding_beside_the_tracked_one(self):
        root = self.repo({".gitignore": "*.key\n", "server.key": "x\n"}, forced=("server.key",))
        outcome = self.run_check(root, check_sec03, "SEC-03")
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual([finding.path for finding in outcome.findings], [None, "server.key"])

    def test_sec03_leaves_a_force_added_dotenv_to_sec01(self):
        root = self.repo({".gitignore": FULL_IGNORE, ".env.prod": "A=1\n"}, forced=(".env.prod",))
        self.assertEqual(self.run_check(root, check_sec03, "SEC-03").verdict.value, "PASS")
        self.assertEqual(self.run_check(root, check_sec01, "SEC-01").verdict.value, "FAIL")

    def test_sec03_without_git_reads_coverage_alone(self):
        root = self.repo({".gitignore": FULL_IGNORE, "server.key": "x\n"}, git=False)
        self.assertEqual(self.run_check(root, check_sec03, "SEC-03").verdict.value, "PASS")


class FixtureTests(unittest.TestCase):
    def prepare(self, name: str, forced: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / name
        shutil.copytree(support.fixture(name), target)
        self.assertEqual(_git(target, "init").returncode, 0)
        self.assertEqual(_git(target, "add", "-A").returncode, 0)
        self.assertEqual(_git(target, "add", "-f", forced).returncode, 0)
        return target

    def test_each_fixture_fails_exactly_its_check(self):
        cases = {
            "sec-01-tracked-ignored-env": ("config/prod.env", "SEC-01"),
            "sec-03-tracked-ignored-key": ("server.key", "SEC-03"),
        }
        for name, (forced, check) in cases.items():
            with self.subTest(fixture=name):
                report = support.run_audit(self.prepare(name, forced))
                verdicts = support.verdicts(report)
                self.assertEqual([c for c in SEC_CHECKS if verdicts[c] == "FAIL"], [check])
                cited = [e["path"] for f in report["findings"] if f["check"] == check for e in f["evidence"]]
                self.assertIn(forced, cited)


if __name__ == "__main__":
    unittest.main()
