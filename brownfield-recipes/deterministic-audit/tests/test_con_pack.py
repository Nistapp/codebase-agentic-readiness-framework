# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CON checks and the CON-04 emitter.

`CON-01` stays blocked by design and is asserted to remain so. `CON-02` is exercised against its
one-defect fixture and against inline repositories that add a real constraint file, an indirect
ignore-rule mechanism, and nothing at all. `CON-03`'s tracked half needs git, so those fixtures are
copied into a temporary git repository — never the audit repo. `CON-04` is an emitter, asserted end
to end: the draft is written outside the target, is deterministic, and is absent unless requested.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks.con import _TEST_DIR_NAMES, _names_directory, build_constraint_draft  # noqa: E402
from audit.scan import build_inventory  # noqa: E402

CON_CHECKS = ("CON-01", "CON-02", "CON-03", "CON-04")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class ConFixtureTests(unittest.TestCase):
    def test_con02_fixture_fails_exactly_its_check(self):
        report = support.run_audit(support.fixture("con-02-unprotected-tests"))
        verdicts = support.verdicts(report)
        self.assertEqual(verdicts["CON-02"], "FAIL")
        failing = sorted(cid for cid in CON_CHECKS if verdicts[cid] == "FAIL")
        self.assertEqual(failing, ["CON-02"], f"unexpected CON FAILs {failing}")

    def test_con03_fixture_fails_exactly_its_check(self):
        report = support.run_audit(support.fixture("con-03-artefacts-not-ignored"))
        verdicts = support.verdicts(report)
        self.assertEqual(verdicts["CON-03"], "FAIL")
        failing = sorted(cid for cid in CON_CHECKS if verdicts[cid] == "FAIL")
        self.assertEqual(failing, ["CON-03"], f"unexpected CON FAILs {failing}")

    def test_con01_stays_blocked(self):
        report = support.run_audit(support.fixture("con-02-unprotected-tests"))
        check = next(c for c in report["checks"] if c["id"] == "CON-01")
        self.assertEqual(check["status"], "blocked")
        self.assertEqual(check["verdict"], "UNKNOWN")


def deny_list(*entries: str, heading: str = "## Do Not Do") -> str:
    """An instruction file whose prohibitions section holds ``entries``, one list item each."""
    body = "\n".join(f"- {entry}" for entry in entries)
    return (
        "# AGENTS.md\n\nThis file tells an agent how to work in this repository. Read it before you change anything.\n"
        "Run the tests before you propose a change. The application is small: one module and its tests, and a\n"
        "folder of documentation that follows the style guide.\n\n## Boundaries\n\n"
        "The application code is in `app.py`.\n\n" + heading + "\n\n" + body + "\n"
    )


class Con02Tests(unittest.TestCase):
    """CON-02 reads the prohibitions section of the instruction file: every verdict of decision 0001's table."""

    def scan(self, files: dict[str, str], test_dirs: tuple[str, ...] = ("tests",)) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "app.py", "print(1)\n")
            for directory in test_dirs:
                support.write(root, f"{directory}/test_app.py", "def test_x():\n    assert True\n")
            for rel, text in files.items():
                support.write(root, rel, text)
            report = support.run_audit(root)
        return next(c for c in report["checks"] if c["id"] == "CON-02"), report

    def con02(self, files: dict[str, str], test_dirs: tuple[str, ...] = ("tests",)):
        check, report = self.scan(files, test_dirs)
        return check, [f for f in report["findings"] if f["check"] == "CON-02"]

    def test_pass_when_the_section_names_every_test_directory(self):
        check, findings = self.con02({"AGENTS.md": deny_list("Never edit `tests/`.")})
        self.assertEqual(
            (check["verdict"], check["summary"], findings),
            ("PASS", "the prohibitions section of AGENTS.md names the test directories (tests/)", []),
        )
        self.assertEqual(check["data"]["paths"], ["tests"])

    def test_pass_names_every_directory_when_there_are_several(self):
        files = {"AGENTS.md": deny_list("Never edit `tests/`.", "Never edit `e2e/test/`.")}
        check, _ = self.con02(files, test_dirs=("tests", "e2e/test"))
        self.assertEqual(
            (check["verdict"], check["summary"]),
            ("PASS", "the prohibitions section of AGENTS.md names the test directories (e2e/test/, tests/)"),
        )

    def test_partial_when_the_section_names_some_test_directories(self):
        check, findings = self.con02({"AGENTS.md": deny_list("Never edit `tests/`.")}, test_dirs=("tests", "e2e/test"))
        self.assertEqual(
            (check["verdict"], check["summary"]),
            ("PARTIAL", "the prohibitions section covers tests/ but not e2e/test/"),
        )
        self.assertEqual(
            findings,
            [
                {
                    "id": "CON-02",
                    "check": "CON-02",
                    "phase": 1,
                    "severity": "BLOCKER",
                    "verdict": "PARTIAL",
                    "statement": "An agent cannot rely on the deny list to keep test directories out of an agent's "
                    "reach because the prohibitions section of AGENTS.md does not name e2e/test/.",
                    "evidence": [{"path": "AGENTS.md", "line": 11, "note": "Do Not Do"}],
                    "remediation": "Name e2e/test/ in a code span in the prohibitions section of AGENTS.md.",
                }
            ],
        )

    def test_fail_when_the_section_names_none_of_them(self):
        check, findings = self.con02({"AGENTS.md": deny_list("Never edit `docs/`.")})
        self.assertEqual(
            (check["verdict"], check["summary"]),
            ("FAIL", "the prohibitions section names none of the test directories (tests/)"),
        )
        self.assertEqual(
            findings,
            [
                {
                    "id": "CON-02",
                    "check": "CON-02",
                    "phase": 1,
                    "severity": "BLOCKER",
                    "verdict": "FAIL",
                    "statement": "An agent cannot trust that a failing test is not rewritten to pass because the "
                    "prohibitions section of AGENTS.md does not name any test directory.",
                    "evidence": [{"path": "AGENTS.md", "line": 11, "note": "Do Not Do"}],
                    "remediation": "Name tests/ in a code span in the prohibitions section of AGENTS.md, so test "
                    "edits are bounded and reviewed.",
                }
            ],
        )

    def test_unknown_with_no_instruction_file_and_agt_01_owns_it(self):
        check, findings = self.con02({})
        self.assertEqual(
            (check["verdict"], check["summary"], findings),
            ("UNKNOWN", "no instruction file to read; AGT-01 owns that finding", []),
        )

    def test_unknown_with_no_prohibitions_section_and_agt_07_owns_it(self):
        check, findings = self.con02({"AGENTS.md": deny_list("Never edit `tests/`.", heading="## Commands")})
        self.assertEqual(
            (check["verdict"], check["summary"], findings),
            ("UNKNOWN", "AGENTS.md has no prohibitions section to read; AGT-07 owns that finding", []),
        )

    def test_unknown_when_the_repository_has_no_test_directory(self):
        check, findings = self.con02({"AGENTS.md": deny_list("Never edit `docs/`.")}, test_dirs=())
        self.assertEqual(
            (check["verdict"], check["summary"], findings),
            ("UNKNOWN", "no test directories detected, so there is nothing for a deny list to protect", []),
        )

    def test_claude_md_is_read_when_there_is_no_agents_md(self):
        check, _ = self.con02({"CLAUDE.md": deny_list("Never edit `tests/`.")})
        self.assertEqual(
            (check["verdict"], check["summary"]),
            ("PASS", "the prohibitions section of CLAUDE.md names the test directories (tests/)"),
        )

    def test_only_a_code_span_names_a_path(self):
        check, _ = self.con02({"AGENTS.md": deny_list("Never edit tests/ or tests.")})
        self.assertEqual(check["verdict"], "FAIL")

    def test_only_the_prohibitions_section_names_a_path(self):
        text = deny_list("Never edit `docs/`.").replace("`app.py`.", "`app.py`, and `tests/` holds the tests.")
        check, _ = self.con02({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "FAIL")

    def test_a_subsection_is_part_of_the_section(self):
        text = deny_list("Never edit `docs/`.") + "\n### Tests\n\n- Do not touch `tests/`.\n"
        check, _ = self.con02({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "PASS")

    def test_a_code_span_in_a_second_prohibitions_section_counts(self):
        text = deny_list("Never edit `docs/`.") + "\n## Forbidden\n\n- `tests/`\n"
        check, _ = self.con02({"AGENTS.md": text})
        self.assertEqual(check["verdict"], "PASS")

    def test_the_old_artifacts_no_longer_protect_anything(self):
        for name, content in (
            (".cursorignore", "tests/\n"),
            (".aiderignore", "tests/\n"),
            ("denylist.txt", "tests/\n"),
            ("constraints.yaml", "deny:\n  - tests/\n"),
            (".gitignore", "tests/\n"),
            (".github/workflows/ci.yml", "jobs:\n  guard:\n    steps:\n      - run: protect tests read-only\n"),
        ):
            with self.subTest(file=name):
                files = {name: content, "AGENTS.md": deny_list("Never edit `docs/`.")}
                check, _ = self.con02(files)
                self.assertEqual(check["verdict"], "FAIL")
                files = {name: content, "AGENTS.md": deny_list("Never edit `tests/`.", heading="## Commands")}
                check, _ = self.con02(files)
                self.assertEqual(check["verdict"], "UNKNOWN")


class NamesDirectoryTests(unittest.TestCase):
    """How a path or pattern in a code span covers a test directory."""

    def test_the_forms_that_cover_a_directory(self):
        for pattern, directory in (
            ("tests/", "tests"),
            ("tests", "tests"),
            ("/tests", "tests"),
            ("tests/", "pkg/tests"),
            ("tests/*", "tests"),
            ("tests/**", "tests"),
            ("**/tests/**", "tests"),
            ("**/tests/**", "pkg/tests"),
            ("**/tests", "a/b/tests"),
            ("pkg/tests/", "pkg/tests"),
            ("pkg/", "pkg/tests"),
            ("test*", "tests"),
            ("**/e2e/test", "e2e/test"),
            ("**/e2e/test", "x/e2e/test"),
            ("  tests/  ", "tests"),
            ("*", "tests"),
            ("xtests/", "xtests"),
            ("//tests//", "tests"),
            ("tests/**/", "tests"),
            ("tests/*/", "tests"),
            ("**/tests/**/", "pkg/tests"),
        ):
            with self.subTest(pattern=pattern, directory=directory):
                self.assertTrue(_names_directory(directory, pattern))

    def test_the_forms_that_do_not(self):
        for pattern, directory in (
            ("/tests", "pkg/tests"),
            ("pkg/tests/", "tests"),
            ("tests/test_app.py", "tests"),
            ("", "tests"),
            ("   ", "tests"),
            ("/", "tests"),
            ("**/", "tests"),
            ("src/", "tests"),
            ("tests/", "tests-old"),
            ("tests/", "mytests"),
            ("e2e/test", "x/e2e/test"),
            ("/e2e/test", "x/e2e/test"),
        ):
            with self.subTest(pattern=pattern, directory=directory):
                self.assertFalse(_names_directory(directory, pattern))


class SpecsAreNotTestsTests(unittest.TestCase):
    """The framework's `specs/` holds feature specifications, so neither `spec` nor `specs` is a test directory."""

    def test_the_names_that_make_a_directory_a_test_directory(self):
        self.assertEqual(_TEST_DIR_NAMES, frozenset({"test", "tests", "__tests__"}))

    def test_a_repository_whose_only_such_directories_hold_specifications_has_no_test_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "app.py", "print(1)\n")
            support.write(root, "specs/greeting.md", "# Greeting\n")
            support.write(root, "spec/other.md", "# Other\n")
            support.write(root, "AGENTS.md", deny_list("Never edit `specs/`.", "Never edit `spec/`."))
            report = support.run_audit(root)
        check = next(c for c in report["checks"] if c["id"] == "CON-02")
        self.assertEqual(
            (check["verdict"], check["summary"]),
            ("UNKNOWN", "no test directories detected, so there is nothing for a deny list to protect"),
        )

    def test_denying_the_test_directory_alone_is_enough_beside_a_specs_directory(self):
        report = support.run_audit(support.fixture("con-02-specs-are-not-tests"))
        check = next(c for c in report["checks"] if c["id"] == "CON-02")
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["data"]["paths"], ["tests"])

    def test_the_draft_does_not_list_specifications_as_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "specs/greeting.md", "# Greeting\n")
            support.write(root, "spec/other.md", "# Other\n")
            support.write(root, "tests/test_app.py", "x\n")
            text = build_constraint_draft(build_inventory(root))
        section = text.split("  tests:\n", 1)[1].split("  iac:\n", 1)[0]
        self.assertEqual(section, '    - "__tests__/"\n    - "test/"\n    - "tests/"\n    - "tests/test_app.py"\n')


class Con03Tests(unittest.TestCase):
    def _repo(self, *, tracked_scratch: bool, ignore: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "repo"
        shutil.copytree(support.fixture("con-03-artefacts-not-ignored"), target)
        (target / ".gitignore").write_text(ignore, encoding="utf-8")
        self.assertEqual(_git(target, "init").returncode, 0)
        self.assertEqual(_git(target, "add", "-A").returncode, 0)
        if tracked_scratch:
            self.assertEqual(_git(target, "add", "-f", "artefacts/notes.md").returncode, 0)
        return target

    IGNORE = "artefacts/\nartifacts/\n.codebase-memory/\n.opencode/\n.agentic-tdd/\n"

    def test_covered_and_untracked_passes(self):
        report = support.run_audit(self._repo(tracked_scratch=False, ignore=self.IGNORE))
        self.assertEqual(support.verdicts(report)["CON-03"], "PASS")

    def test_force_added_scratch_file_fails(self):
        report = support.run_audit(self._repo(tracked_scratch=True, ignore=self.IGNORE))
        self.assertEqual(support.verdicts(report)["CON-03"], "FAIL")

    def test_covered_but_git_unavailable_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, ".gitignore", self.IGNORE)
            support.write(root, "artefacts/notes.md", "# scratch\n")
            report = support.run_audit(root)
        self.assertEqual(support.verdicts(report)["CON-03"], "UNKNOWN")


class Con04EmitterTests(unittest.TestCase):
    def _target(self, root: Path) -> Path:
        target = root / "target"
        support.write(target, "src/app.py", "print(1)\n")
        support.write(target, "tests/test_app.py", "def test_x():\n    assert True\n")
        support.write(target, "migrations/001_init.sql", "CREATE TABLE t;\n")
        support.write(target, "dist/app.min.js", "min\n")
        support.write(target, "infra/main.tf", 'resource "x" "y" {}\n')
        support.write(target, "env/prod/config.yaml", "x: 1\n")
        support.write(target, ".env", "SECRET=value\n")
        return target

    def test_draft_is_written_beside_the_report_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self._target(root)
            out = root / "out" / "report.json"
            proc, _ = support.run_audit_process(target, out=out, extra_args=("--emit-baseline",))
            self.assertEqual(proc.returncode, 0, proc.stderr)

            draft = out.parent / "constraints.draft.yaml"
            self.assertTrue(draft.is_file(), "the emitter produced no draft")
            self.assertFalse(draft.resolve().is_relative_to(target.resolve()), "the emitter wrote inside the target")

            text = draft.read_text(encoding="utf-8")
            for section in (
                "deny:",
                "secrets:",
                "migrations:",
                "generated:",
                "tests:",
                "iac:",
                "production:",
                "allow:",
            ):
                self.assertIn(section, text)

            report = json.loads(out.read_text(encoding="utf-8"))
            check = next(c for c in report["checks"] if c["id"] == "CON-04")
            self.assertEqual(check["verdict"], "PASS")
            self.assertIn(str(draft), check["summary"])

    def test_emitter_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self._target(root)
            drafts = []
            for index in range(2):
                out = root / f"out-{index}" / "report.json"
                support.run_audit_process(target, out=out, extra_args=("--emit-baseline",))
                drafts.append((out.parent / "constraints.draft.yaml").read_text(encoding="utf-8"))
            self.assertEqual(drafts[0], drafts[1])

    def test_no_draft_without_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self._target(root)
            out = root / "out" / "report.json"
            proc, _ = support.run_audit_process(target, out=out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((out.parent / "constraints.draft.yaml").exists())
            report = json.loads(out.read_text(encoding="utf-8"))
            check = next(c for c in report["checks"] if c["id"] == "CON-04")
            self.assertEqual(check["verdict"], "UNKNOWN")

    def test_refuses_to_emit_inside_the_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self._target(root)
            out = target / "audit-out" / "report.json"
            proc, _ = support.run_audit_process(target, out=out, extra_args=("--emit-baseline",))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((target / "audit-out" / "constraints.draft.yaml").exists())
            report = json.loads(out.read_text(encoding="utf-8"))
            check = next(c for c in report["checks"] if c["id"] == "CON-04")
            self.assertEqual(check["verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
