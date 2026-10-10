# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The report builder: each subcommand does what it says, writes only through the contract, and leaves the draft valid.

Every test starts from an intake and a target made in a temporary folder, runs the tool in process through
`run_tool` (so the envelope and the exit code are what a recipe sees), and reads the draft back from disk. A test that
needs a repository makes a real one with git. Credential-shaped strings are built at run time, so that the secrets
scan finds nothing in this file. Standard library only.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from unittest import mock

import _paths
import _common
import _git
import _summary
import report as rb
import validate_report as vr

TOOLS = _paths.TOOLS
REALISTIC = TOOLS.parent / "schema" / "examples" / "realistic"
DRAFT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*\.audit-draft\.[0-9]{8}T[0-9]{6}Z(-[0-9]+)?\.json$")
MOMENT = datetime(2026, 10, 10, 9, 30, 0, tzinfo=timezone.utc)
FINAL_MOMENT = datetime(2026, 10, 10, 11, 45, 30, tzinfo=timezone.utc)


def call(argv: Sequence[str], stdin: str = "") -> tuple[int, dict[str, Any], str]:
    """Run the builder in process. Returns the exit code, the envelope and what went to stderr."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "stdin", io.StringIO(stdin)):
        code = _common.run_tool(rb.INFO, rb.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


def read_json(path: str | Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return document


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    """Every path under `root` with its size and modification time, so that a change of any kind shows."""
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(root.rglob("*"))}


class BuilderCase(unittest.TestCase):
    """A temporary folder with a target repository, an output folder that does not exist yet, and an intake."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / "My_Service"
        self.target.mkdir()
        self.out = self.root / "out"

    def intake(self, **changes: Any) -> dict[str, Any]:
        document: dict[str, Any] = {
            "intake_version": "0.1",
            "target_path": str(self.target),
            "harness": "claude-code",
            "model": "claude-sonnet-5-5",
            "provider_exposure_acknowledged": True,
            "index": {"kind": "none"},
            "confirmation_policy": "interactive",
            "output_dir": str(self.out),
        }
        document.update(changes)
        return document

    def write_intake(self, **changes: Any) -> Path:
        path = self.root / "audit-intake.my-service.json"
        path.write_text(json.dumps(self.intake(**changes)), encoding="utf-8")
        return path

    def init(self, **changes: Any) -> tuple[int, dict[str, Any], str]:
        with mock.patch.object(rb, "utc_now", return_value=MOMENT):
            return call(["init", str(self.write_intake(**changes))])

    def start(self, **changes: Any) -> Path:
        """Run `init`, insist it worked, and return the draft's path."""
        code, envelope, stderr = self.init(**changes)
        self.assertEqual(code, 0, stderr)
        return Path(envelope["data"]["draft"])

    def drafts(self) -> list[str]:
        return sorted(p.name for p in self.out.iterdir()) if self.out.is_dir() else []

    def engine_draft(self) -> Path:
        """A copy of the engine's real report on agentic-tdd, converted: 69 engine checks, 24 pending findings.

        The copy points at the temporary target, with no commit, so that nothing depends on this machine.
        """
        source = next(REALISTIC.glob("agentic-tdd.audit-draft.*.json"))
        document = read_json(source)
        document["provenance"]["target"].update(path=str(self.target), git_sha=None, branch=None, dirty=None)
        self.out.mkdir(exist_ok=True)
        path = self.out / source.name
        path.write_text(rb.dumps(document), encoding="utf-8")
        return path

    def add_check(self, draft: Path, fragment: Any) -> tuple[int, dict[str, Any], str]:
        return call(["add-check", str(draft), "--from", "-"], json.dumps(fragment))

    def add_finding(self, draft: Path, fragment: Any) -> tuple[int, dict[str, Any], str]:
        return call(["add-finding", str(draft), "--from", "-"], json.dumps(fragment))

    def decide(self, draft: Path, *args: str, stdin: str = "") -> tuple[int, dict[str, Any], str]:
        return call(["set-disposition", str(draft), *args], stdin)

    def draft_with_findings(self, scopes: Sequence[str] = ("a", "b", "c"), **changes: Any) -> Path:
        """A draft in which AGT-11 failed and has one pending finding for each scope."""
        draft = self.failing_draft(**changes)
        for scope in scopes:
            code, envelope, _ = self.add_finding(draft, agent_finding(scope=scope))
            self.assertEqual(code, 0, envelope)
        return draft

    def complete_engine_draft(self) -> Path:
        """The engine draft with both agent-only checks recorded and every finding decided by a person."""
        draft = self.engine_draft()
        evidence = [{"kind": "file", "path": "AGENTS.md", "quote": "x"}]
        for check_id in ("AGT-11", "CI-04"):
            code, envelope, _ = self.add_check(draft, agent_check(id=check_id, evidence=evidence))
            self.assertEqual(code, 0, envelope)
        findings = read_json(draft)["findings"]
        blockers = [f["id"] for f in findings if f["severity"] == "BLOCKER"]
        others = [{"finding": f["id"], "disposition": "confirmed"} for f in findings if f["severity"] != "BLOCKER"]
        for finding_id in blockers:
            code, envelope, _ = self.decide(
                draft, "--via", "interactive", "--finding", finding_id, "--disposition", "confirmed"
            )
            self.assertEqual(code, 0, envelope)
        code, envelope, _ = self.decide(draft, "--via", "batch", "--from", "-", stdin=json.dumps(others))
        self.assertEqual(code, 0, envelope)
        return draft

    def finalise(self, draft: Path) -> tuple[int, dict[str, Any], str]:
        with mock.patch.object(rb, "utc_now", return_value=FINAL_MOMENT):
            return call(["finalise", str(draft)])

    def files(self) -> dict[str, bytes]:
        """Every file in the output folder with its bytes, to show that nothing changed or was replaced."""
        return {p.name: p.read_bytes() for p in sorted(self.out.iterdir())}

    def stdout_lines(self, *argv: str) -> int:
        """Run the tool as a script and count the lines it prints on stdout, which is what a recipe reads."""
        done = subprocess.run(
            [sys.executable, str(TOOLS / "report.py"), *argv], capture_output=True, text=True, check=False
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return len(done.stdout.splitlines())

    def failing_draft(self, **changes: Any) -> Path:
        """A new draft in which AGT-11 has failed, so that it can have findings."""
        draft = self.start(**changes)
        code, envelope, _ = self.add_check(draft, agent_check(verdict="FAIL", summary="Restates the README."))
        self.assertEqual(code, 0, envelope)
        return draft

    def unchanged_by(self, draft: Path, run: Any) -> tuple[int, dict[str, Any], str]:
        """Run `run()`, which must change nothing: the draft's bytes and the folder's files stay as they were."""
        before, names = draft.read_bytes(), sorted(p.name for p in draft.parent.iterdir())
        outcome: tuple[int, dict[str, Any], str] = run()
        self.assertEqual(draft.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in draft.parent.iterdir()), names)
        return outcome


def agent_check(**changes: Any) -> dict[str, Any]:
    """A fragment for AGT-11, a check only an agent can evaluate, with one file as evidence."""
    fragment: dict[str, Any] = {
        "id": "AGT-11",
        "verdict": "PASS",
        "confidence": "high",
        "summary": "AGENTS.md states a release rule that the code does not reveal.",
        "evidence": [
            {"kind": "file", "path": "AGENTS.md", "lines": "14-15", "quote": "Never run npm publish by hand."}
        ],
    }
    fragment.update(changes)
    return fragment


def agent_finding(**changes: Any) -> dict[str, Any]:
    """A fragment for a finding on AGT-11, which must have failed first."""
    fragment: dict[str, Any] = {
        "check": "AGT-11",
        "statement": "An agent cannot tell which rules are the team's because AGENTS.md only restates the README.",
        "evidence": [{"kind": "file", "path": "AGENTS.md", "lines": "1-3"}],
        "remediation": {"summary": "Replace the overview with the rules the code does not show.", "effort": "S"},
    }
    fragment.update(changes)
    return fragment


def credentials() -> list[str]:
    """Strings the engine's redaction patterns match, built here so that no scan finds one in this file."""
    return [
        "pass" + "word" + " = " + "hunter" + "2",
        "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "gh" + "p_" + "A1b2C3d4E5f6G7h8I9",
    ]


class InitTests(BuilderCase):
    def test_it_creates_a_named_draft_that_validates(self) -> None:
        code, envelope, stderr = self.init()
        self.assertEqual(code, 0, stderr)
        path = Path(envelope["data"]["draft"])
        self.assertEqual(path.parent, self.out)
        self.assertEqual(path.name, "my-service.audit-draft.20261010T093000Z.json")
        self.assertRegex(path.name, DRAFT_NAME)
        self.assertEqual(self.drafts(), [path.name])
        document = read_json(path)
        self.assertEqual(vr.validate_document(document).errors, [])
        self.assertEqual((document["schema_version"], document["status"]), ("0.1", "draft"))
        self.assertEqual((document["checks"], document["findings"], document["components"]), ([], [], []))
        self.assertEqual(document["summary"], _summary.compute_summary(document))
        self.assertEqual(stderr, f"report: started {path.name} for my-service\n")
        self.assertEqual(envelope["data"]["label"], "my-service")
        self.assertEqual(envelope["data"]["status"], "draft")

    def test_the_draft_is_written_in_the_shape_of_the_examples(self) -> None:
        path = self.start()
        text = path.read_text(encoding="utf-8")
        document = read_json(path)
        self.assertEqual(text, rb.dumps(document))
        self.assertTrue(text.endswith("}\n"))
        self.assertEqual(
            list(document),
            [
                "schema_version",
                "status",
                "provenance",
                "run_context",
                "stack",
                "components",
                "checks",
                "findings",
                "summary",
                "unattested",
                "coverage",
            ],
        )

    def test_non_ascii_text_is_kept_as_it_was_typed(self) -> None:
        path = self.start(model="modèle-é")
        self.assertIn('"model": "modèle-é"', path.read_text(encoding="utf-8"))

    def test_a_draft_that_would_not_be_valid_is_never_written(self) -> None:
        failing = vr.Outcome(errors=["rule 1: /: made up"])
        with mock.patch.object(vr, "validate_document", return_value=failing):
            code, envelope, _ = self.init()
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["error"], "the new draft would not be valid")
        self.assertEqual(envelope["data"]["errors"], ["rule 1: /: made up"])
        self.assertEqual(self.drafts(), [])

    def test_an_explicit_label_is_used_for_the_file_and_the_report(self) -> None:
        path = self.start(repo_label="svc.one")
        self.assertEqual(path.name, "svc.one.audit-draft.20261010T093000Z.json")
        self.assertEqual(read_json(path)["provenance"]["target"]["label"], "svc.one")

    def test_a_label_that_is_not_allowed_is_an_intake_error_and_writes_nothing(self) -> None:
        code, envelope, _ = self.init(repo_label="My Service")
        self.assertEqual(code, 2)
        self.assertIn("repo_label", "\n".join(envelope["data"]["errors"]))
        self.assertEqual(self.drafts(), [])
        self.assertFalse(self.out.exists())

    def test_the_provenance_is_what_the_intake_and_the_catalogue_say(self) -> None:
        document = read_json(self.start())
        provenance = document["provenance"]
        self.assertEqual(provenance["recipe"], {"name": "brownfield-audit", "version": "0.1.0"})
        self.assertEqual(provenance["agent"], {"harness": "claude-code", "model": "claude-sonnet-5-5"})
        self.assertEqual(provenance["catalogue_version"], vr.load_catalogue()["catalogue_version"])
        self.assertEqual(provenance["started_at"], "2026-10-10T09:30:00+00:00")
        self.assertNotIn("engine", provenance)
        self.assertNotIn("finalised_at", provenance)
        self.assertEqual(provenance["target"]["path"], str(self.target))
        self.assertEqual(provenance["target"]["label"], "my-service")

    def test_the_run_context_copies_the_answers_and_leaves_the_instructions_behind(self) -> None:
        document = read_json(
            self.start(
                eval_mode=True,
                confirmation_policy="defer-all",
                index={"kind": "mcp", "name": "codebase-memory-mcp", "allow_install": True, "notes": "indexed"},
                probes={"allowed": ["test", "lint"], "timeout_s": 30},
                excluded=["vendor"],
                known_components=["packages/api"],
            )
        )
        self.assertEqual(
            document["run_context"],
            {
                "eval_mode": True,
                "confirmation_policy": "defer-all",
                "provider_exposure_acknowledged": True,
                "index": {"kind": "mcp", "name": "codebase-memory-mcp", "notes": "indexed"},
                "probes": {"allowed": ["test", "lint"], "timeout_s": 30},
                "excluded": ["vendor"],
                "known_components": ["packages/api"],
            },
        )
        self.assertNotIn("output_dir", json.dumps(document))
        self.assertNotIn("allow_install", json.dumps(document))

    def test_an_intake_without_the_optional_answers_gets_the_defaults(self) -> None:
        context = read_json(self.start())["run_context"]
        self.assertIs(context["eval_mode"], False)
        self.assertEqual(context["probes"], {"allowed": [], "timeout_s": 120})
        self.assertEqual((context["excluded"], context["known_components"]), ([], []))

    def test_the_framework_revision_is_this_checkout_or_nothing(self) -> None:
        document = read_json(self.start())
        recorded = document["provenance"]["framework_revision"]
        root = vr.RECIPES.parent
        if rb.git_toplevel(root) == root.resolve():
            self.assertEqual(recorded, _git.run_git(root, "rev-parse", "HEAD"))
        else:
            self.assertIsNone(recorded)
        with mock.patch.object(rb, "git_toplevel", return_value=self.root):
            self.assertIsNone(rb.framework_revision())


class TargetFactsTests(BuilderCase):
    def facts(self) -> dict[str, Any]:
        return dict(read_json(self.start())["provenance"]["target"])

    def test_a_folder_that_is_not_a_repository_records_nothing_and_does_not_complain(self) -> None:
        code, envelope, _ = self.init()
        self.assertEqual((code, envelope["warnings"]), (0, []))
        target = read_json(envelope["data"]["draft"])["provenance"]["target"]
        self.assertEqual((target["git_sha"], target["branch"], target["dirty"]), (None, None, None))

    def test_a_clean_repository_gives_its_commit_and_branch(self) -> None:
        _git.make_repo(self.target, branch="trunk")
        facts = self.facts()
        self.assertEqual(facts["git_sha"], _git.run_git(self.target, "rev-parse", "HEAD"))
        self.assertEqual((facts["branch"], facts["dirty"]), ("trunk", False))

    def test_a_change_in_the_working_tree_makes_it_dirty(self) -> None:
        _git.make_repo(self.target)
        (self.target / "new.txt").write_text("y\n", encoding="utf-8")
        self.assertIs(self.facts()["dirty"], True)

    def test_a_detached_head_has_a_commit_and_no_branch(self) -> None:
        _git.make_repo(self.target)
        _git.run_git(self.target, "checkout", "-q", "--detach")
        facts = self.facts()
        self.assertEqual(facts["git_sha"], _git.run_git(self.target, "rev-parse", "HEAD"))
        self.assertIsNone(facts["branch"])

    def test_a_repository_without_a_commit_has_a_branch_and_no_commit(self) -> None:
        _git.make_repo(self.target, commit=False, branch="main")
        facts = self.facts()
        self.assertEqual((facts["git_sha"], facts["branch"]), (None, "main"))

    def test_a_folder_inside_a_repository_records_nothing_and_says_why(self) -> None:
        _git.make_repo(self.root, ["a.txt"])
        code, envelope, _ = self.init()
        self.assertEqual(code, 0)
        target = read_json(envelope["data"]["draft"])["provenance"]["target"]
        self.assertEqual((target["git_sha"], target["branch"], target["dirty"]), (None, None, None))
        self.assertEqual(len(envelope["warnings"]), 1)
        self.assertIn("not at its root", envelope["warnings"][0])

    def test_without_git_it_records_nothing_and_says_why(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            code, envelope, _ = self.init()
        self.assertEqual(code, 0)
        self.assertEqual(len(envelope["warnings"]), 1)
        self.assertIn("git is not installed", envelope["warnings"][0])
        self.assertIsNone(read_json(envelope["data"]["draft"])["provenance"]["target"]["git_sha"])

    def test_a_commit_id_of_another_length_is_not_recorded(self) -> None:
        _git.make_repo(self.target)
        real = vr.git_output

        def sha256_like(target: Path, args: Sequence[str], stdin: str | None = None) -> Any:
            done = real(target, args, stdin)
            if list(args) == ["rev-parse", "HEAD"] and done is not None:
                done.stdout = "a" * 64 + "\n"
            return done

        with mock.patch.object(vr, "git_output", sha256_like):
            code, envelope, _ = self.init()
        self.assertEqual(code, 0)
        self.assertIsNone(read_json(envelope["data"]["draft"])["provenance"]["target"]["git_sha"])
        self.assertTrue(any("not 40 hexadecimal digits" in w for w in envelope["warnings"]))

    def test_reading_the_target_changes_nothing_in_it(self) -> None:
        _git.make_repo(self.target, ["src/a.py", "b.txt"])
        (self.target / "dirty.txt").write_text("z\n", encoding="utf-8")
        index = (self.target / ".git" / "index").read_bytes()
        before = tree_state(self.target)
        self.start()
        self.assertEqual(tree_state(self.target), before)
        self.assertEqual((self.target / ".git" / "index").read_bytes(), index)


class IntakeRuleTests(BuilderCase):
    def rejected(self, expected: str, **changes: Any) -> None:
        code, envelope, _ = self.init(**changes)
        self.assertEqual(code, 2, envelope)
        self.assertEqual(len(envelope["data"]["errors"]), 1, envelope["data"]["errors"])
        self.assertIn(expected, envelope["data"]["errors"][0])
        self.assertFalse(self.out.exists(), "nothing is created for an intake that is refused")

    def test_accept_all_needs_eval_mode(self) -> None:
        self.rejected("'accept-all' is allowed only with eval_mode", confirmation_policy="accept-all")

    def test_an_eval_run_cannot_be_interactive(self) -> None:
        self.rejected("an eval-mode run cannot be 'interactive'", eval_mode=True)

    def test_an_index_that_is_used_needs_a_name(self) -> None:
        self.rejected("the index kind is 'cli', so the index needs a name", index={"kind": "cli"})

    def test_an_eval_run_with_accept_all_is_allowed(self) -> None:
        code, _, stderr = self.init(eval_mode=True, confirmation_policy="accept-all")
        self.assertEqual(code, 0, stderr)

    def test_the_provider_must_be_acknowledged(self) -> None:
        code, envelope, _ = self.init(provider_exposure_acknowledged=False)
        self.assertEqual(code, 2)
        self.assertTrue(envelope["data"]["errors"][0].startswith("schema: /provider_exposure_acknowledged"))
        self.assertFalse(self.out.exists())

    def test_the_schema_errors_are_all_listed(self) -> None:
        path = self.root / "bad.json"
        path.write_text(json.dumps({"intake_version": "0.1"}), encoding="utf-8")
        code, envelope, stderr = call(["init", str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["error"], "the intake is not valid: 7 errors in the schema stage")
        self.assertEqual(len(envelope["data"]["errors"]), 7)
        self.assertIn("report: the intake is not valid", stderr)

    def test_a_file_that_is_not_json_is_exit_2_and_says_intake(self) -> None:
        path = self.root / "bad.json"
        path.write_text("{", encoding="utf-8")
        code, envelope, _ = call(["init", str(path)])
        self.assertEqual(code, 2)
        self.assertIn("the file is not an intake", envelope["data"]["error"])

    def test_a_missing_intake_is_exit_1(self) -> None:
        code, envelope, _ = call(["init", str(self.root / "none.json")])
        self.assertEqual(code, 1)
        self.assertIn("intake not found", envelope["data"]["error"])


class InitPathTests(BuilderCase):
    def test_a_target_that_is_missing_is_exit_1_and_nothing_is_created(self) -> None:
        code, envelope, _ = self.init(target_path=str(self.root / "nowhere"))
        self.assertEqual(code, 1)
        self.assertIn("target not found", envelope["data"]["error"])
        self.assertFalse(self.out.exists())

    def test_a_target_that_is_a_file_is_exit_1(self) -> None:
        (self.root / "file.txt").write_text("x", encoding="utf-8")
        code, envelope, _ = self.init(target_path=str(self.root / "file.txt"))
        self.assertEqual(code, 1)
        self.assertIn("not a directory", envelope["data"]["error"])

    def test_an_output_folder_inside_the_target_is_refused_and_nothing_is_written(self) -> None:
        before = tree_state(self.root)
        code, envelope, _ = self.init(output_dir=str(self.target / "reports"))
        self.assertEqual(code, 1)
        self.assertIn("refusing to write inside the target", envelope["data"]["error"])
        self.assertEqual(tree_state(self.root), {**before, "audit-intake.my-service.json": mock.ANY})

    def test_an_output_folder_that_reaches_the_target_through_a_link_is_refused(self) -> None:
        link = self.root / "link"
        link.symlink_to(self.target, target_is_directory=True)
        code, envelope, _ = self.init(output_dir=str(link / "reports"))
        self.assertEqual(code, 1)
        self.assertIn("refusing to write inside the target", envelope["data"]["error"])
        self.assertEqual(list(self.target.iterdir()), [])

    def test_a_target_that_is_a_link_is_resolved_and_recorded_resolved(self) -> None:
        link = self.root / "alias"
        link.symlink_to(self.target, target_is_directory=True)
        document = read_json(self.start(target_path=str(link)))
        self.assertEqual(document["provenance"]["target"]["path"], str(self.target))
        self.assertEqual(document["provenance"]["target"]["label"], "my-service")

    def test_the_output_folder_is_created_when_it_is_missing(self) -> None:
        deep = self.root / "a" / "b" / "c"
        path = self.start(output_dir=str(deep))
        self.assertEqual(path.parent, deep)


class NeverReplaceTests(BuilderCase):
    def test_two_drafts_in_the_same_second_are_two_files_and_the_first_is_untouched(self) -> None:
        first = self.start()
        first_bytes = first.read_bytes()
        second = self.start()
        self.assertNotEqual(first, second)
        self.assertEqual(second.name, "my-service.audit-draft.20261010T093000Z-2.json")
        self.assertEqual(first.read_bytes(), first_bytes)
        self.assertEqual(self.drafts(), sorted([first.name, second.name]))
        self.assertEqual(vr.validate_document(read_json(second)).errors, [])

    def test_a_second_run_on_the_same_repository_later_leaves_the_earlier_draft_as_it_was(self) -> None:
        first = self.start()
        first_bytes = first.read_bytes()
        later = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(rb, "utc_now", return_value=later):
            code, envelope, _ = call(["init", str(self.write_intake())])
        self.assertEqual(code, 0)
        self.assertEqual(Path(envelope["data"]["draft"]).name, "my-service.audit-draft.20261010T100000Z.json")
        self.assertEqual(first.read_bytes(), first_bytes)
        self.assertEqual(len(self.drafts()), 2)

    def test_the_other_runs_file_is_never_overwritten_even_when_it_is_a_dangling_link(self) -> None:
        self.out.mkdir()
        name = self.out / "my-service.audit-draft.20261010T093000Z.json"
        name.symlink_to(self.root / "gone.json")
        path = self.start()
        self.assertEqual(path.name, "my-service.audit-draft.20261010T093000Z-2.json")
        self.assertFalse((self.root / "gone.json").exists())


class AddCheckTests(BuilderCase):
    def setUp(self) -> None:
        super().setUp()
        self.draft = self.start()

    def test_it_records_an_agent_check_and_fills_in_what_the_catalogue_knows(self) -> None:
        code, envelope, stderr = self.add_check(self.draft, agent_check())
        self.assertEqual(code, 0, envelope)
        self.assertEqual(
            envelope["data"],
            {
                "draft": str(self.draft),
                "check": "AGT-11",
                "action": "added",
                "verdict": "PASS",
                "checks_recorded": 1,
                "checks_expected": 71,
            },
        )
        self.assertEqual(stderr, "report: AGT-11 added as PASS\n")
        document = read_json(self.draft)
        (check,) = document["checks"]
        entry = next(c for c in vr.load_catalogue()["checks"] if c["id"] == "AGT-11")
        for name in ("title", "phase", "severity", "scored", "method"):
            self.assertEqual(check[name], entry[name])
        self.assertEqual(
            list(check),
            [
                "id",
                "title",
                "phase",
                "severity",
                "scored",
                "method",
                "verdict",
                "confidence",
                "summary",
                "evidence",
                "searches",
            ],
        )
        self.assertEqual(check["evidence"][0]["captured_by"], "agent")
        self.assertEqual(list(check["evidence"][0])[:2], ["kind", "captured_by"])
        self.assertEqual(check["searches"], [])
        self.assertEqual(vr.validate_document(document).errors, [])

    def test_the_summary_is_computed_by_the_tool(self) -> None:
        self.add_check(self.draft, agent_check())
        summary = read_json(self.draft)["summary"]
        self.assertEqual(summary["phase1_score"], 1.0)
        self.assertEqual(summary["scored_checks"], 1)
        self.add_check(self.draft, agent_check(id="CI-04", verdict="FAIL", evidence=[]))
        document = read_json(self.draft)
        self.assertEqual(document["summary"], _summary.compute_summary(document))
        self.assertEqual(document["summary"]["scored_checks"], 2)
        self.assertLess(document["summary"]["phase1_score"], 1.0)

    def test_the_fragment_can_come_from_a_file(self) -> None:
        source = self.root / "fragment.json"
        source.write_text(json.dumps(agent_check()), encoding="utf-8")
        code, _, _ = call(["add-check", str(self.draft), "--from", str(source)])
        self.assertEqual(code, 0)
        self.assertEqual(len(read_json(self.draft)["checks"]), 1)

    def test_the_agent_cannot_write_what_the_catalogue_or_the_tool_decides(self) -> None:
        for name, value in [
            ("title", "mine"),
            ("severity", "COSMETIC"),
            ("scored", False),
            ("method", "automated"),
            ("phase", 2),
            ("engine_verdict", "PASS"),
            ("data", {}),
        ]:
            with self.subTest(field=name):
                code, envelope, _ = self.unchanged_by(
                    self.draft, lambda: self.add_check(self.draft, agent_check(**{name: value}))
                )
                self.assertEqual(code, 2)
                self.assertIn(f"unexpected property: '{name}'", "\n".join(envelope["data"]["errors"]))

    def test_the_agent_cannot_pass_off_its_own_evidence_as_a_tools(self) -> None:
        claims = [
            {"captured_by": "tool"},
            {"tool": "engine"},
            {"tool_version": "1"},
            {"captured_by": "tool", "tool": "engine", "tool_version": "1"},
        ]
        for claim in claims:
            with self.subTest(claim=claim):
                evidence = [{"kind": "file", "path": "AGENTS.md", **claim}]
                code, envelope, _ = self.unchanged_by(
                    self.draft, lambda: self.add_check(self.draft, agent_check(evidence=evidence))
                )
                self.assertEqual(code, 2)
                self.assertIn("the agent cannot record tool-captured evidence", "\n".join(envelope["data"]["errors"]))

    def test_an_automated_check_cannot_be_added_by_the_agent(self) -> None:
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.add_check(self.draft, agent_check(id="CMD-01")))
        self.assertEqual(code, 2)
        self.assertIn("an automated check", envelope["data"]["error"])
        self.assertIn("importing the engine's report", envelope["data"]["errors"][0])

    def test_a_check_that_is_not_in_the_catalogue_is_refused(self) -> None:
        for check_id, expected in [("ZZZ-99", "is not a check in the catalogue"), ("abc", "does not match")]:
            with self.subTest(check_id=check_id):
                code, envelope, _ = self.unchanged_by(
                    self.draft, lambda: self.add_check(self.draft, agent_check(id=check_id))
                )
                self.assertEqual(code, 2)
                self.assertIn(expected, envelope["data"]["error"] + "\n".join(envelope["data"]["errors"]))

    def test_recording_a_check_again_replaces_it_in_place(self) -> None:
        self.add_check(self.draft, agent_check())
        self.add_check(self.draft, agent_check(id="CI-04", verdict="FAIL", summary="No CI.", evidence=[]))
        searches = [{"tool": "glob", "pattern": "AGENTS.md", "scope": ".", "hits": 0}]
        again = agent_check(verdict="FAIL", summary="No release rule found.", evidence=[], searches=searches)
        del again["confidence"]
        code, envelope, _ = self.add_check(self.draft, again)
        self.assertEqual((code, envelope["data"]["action"]), (0, "replaced"))
        document = read_json(self.draft)
        self.assertEqual([c["id"] for c in document["checks"]], ["AGT-11", "CI-04"])
        first = document["checks"][0]
        self.assertEqual((first["verdict"], first["evidence"], first["searches"]), ("FAIL", [], searches))
        self.assertNotIn("confidence", first)
        self.assertEqual(envelope["data"]["checks_recorded"], 2)

    def test_an_agent_pass_without_evidence_is_refused_by_the_rules(self) -> None:
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.add_check(self.draft, agent_check(evidence=[])))
        self.assertEqual(code, 2)
        self.assertTrue(
            envelope["data"]["error"].startswith("the change would leave the draft invalid, so nothing was written")
        )
        self.assertTrue(envelope["data"]["errors"][0].startswith("rule 5: /checks/0/evidence:"))

    def test_an_agent_fail_needs_neither_evidence_nor_a_search(self) -> None:
        code, _, _ = self.add_check(self.draft, agent_check(verdict="FAIL", evidence=[]))
        self.assertEqual(code, 0)

    def test_a_credential_in_a_quote_is_refused_and_never_repeated(self) -> None:
        for text in credentials():
            with self.subTest(text=text[:6]):
                evidence = [{"kind": "file", "path": "AGENTS.md", "quote": f"see {text}"}]
                code, envelope, stderr = self.unchanged_by(
                    self.draft, lambda: self.add_check(self.draft, agent_check(evidence=evidence))
                )
                self.assertEqual(code, 2)
                self.assertTrue(envelope["data"]["errors"][0].startswith("rule 11:"))
                self.assertNotIn(text, json.dumps(envelope) + stderr)

    def test_an_evidence_path_that_leaves_the_target_is_refused(self) -> None:
        for path in ["../outside.txt", "/etc/hostname"]:
            with self.subTest(path=path):
                evidence = [{"kind": "file", "path": path}]
                code, envelope, _ = self.unchanged_by(
                    self.draft, lambda: self.add_check(self.draft, agent_check(evidence=evidence))
                )
                self.assertEqual(code, 2)
                self.assertTrue(envelope["data"]["errors"][0].startswith("rule 3:"))

    def test_a_bad_fragment_lists_every_problem_with_its_place(self) -> None:
        fragment = agent_check(
            verdict="MAYBE", evidence=[{"kind": "file", "lines": "x"}, {"kind": "tape", "captured_by": "agent"}]
        )
        del fragment["summary"]
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.add_check(self.draft, fragment))
        self.assertEqual(code, 2)
        errors = "\n".join(envelope["data"]["errors"])
        for place in (
            "/: missing the required property 'summary'",
            "/verdict",
            "/evidence/0/lines",
            "/evidence/1/kind",
        ):
            self.assertIn(place, errors)
        self.assertTrue(all(e.startswith("fragment: ") for e in envelope["data"]["errors"]))

    def test_a_fragment_that_is_not_an_object_or_not_json_is_refused(self) -> None:
        for text, expected in [("[]", "expected object"), ("{", "not valid JSON"), ("", "not valid JSON")]:
            with self.subTest(text=text):
                code, envelope, _ = self.unchanged_by(
                    self.draft, lambda: call(["add-check", str(self.draft), "--from", "-"], text)
                )
                self.assertEqual(code, 2)
                self.assertIn(expected, envelope["data"]["error"] + "\n".join(envelope["data"].get("errors", [])))

    def test_a_missing_fragment_file_or_draft_is_exit_1(self) -> None:
        code, envelope, _ = call(["add-check", str(self.draft), "--from", str(self.root / "none.json")])
        self.assertEqual((code, "check fragment not found" in envelope["data"]["error"]), (1, True))
        code, envelope, _ = call(
            ["add-check", str(self.root / "nowhere" / "d.json"), "--from", "-"], json.dumps(agent_check())
        )
        self.assertEqual((code, "draft not found" in envelope["data"]["error"]), (1, True))
        code, envelope, _ = call(["add-check", str(self.out / "none.json"), "--from", "-"], json.dumps(agent_check()))
        self.assertEqual((code, "draft not found" in envelope["data"]["error"]), (1, True))

    def test_a_draft_that_is_not_valid_is_refused_and_left_alone(self) -> None:
        document = read_json(self.draft)
        document["provenance"]["catalogue_version"] = "one"
        self.draft.write_text(rb.dumps(document), encoding="utf-8")
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.add_check(self.draft, agent_check()))
        self.assertEqual(code, 2)
        self.assertIn("the draft is not valid before the change", envelope["data"]["error"])

    def test_a_final_report_is_never_changed(self) -> None:
        worked = next((TOOLS.parent / "schema" / "examples").glob("example-service.audit-report.*.json"))
        copy = self.out / worked.name
        shutil.copyfile(worked, copy)
        code, envelope, _ = self.unchanged_by(copy, lambda: self.add_check(copy, agent_check()))
        self.assertEqual(code, 1)
        self.assertIn("is a final report", envelope["data"]["error"])

    def test_a_draft_inside_the_target_is_refused(self) -> None:
        document = read_json(self.draft)
        document["provenance"]["target"]["path"] = str(self.root)
        self.draft.write_text(rb.dumps(document), encoding="utf-8")
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.add_check(self.draft, agent_check()))
        self.assertEqual(code, 1)
        self.assertIn("refusing to write inside the target", envelope["data"]["error"])

    def test_a_link_to_the_draft_changes_the_draft_and_stays_a_link(self) -> None:
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        link = elsewhere / "latest.json"
        link.symlink_to(self.draft)
        code, envelope, _ = self.add_check(link, agent_check())
        self.assertEqual(code, 0, envelope)
        self.assertTrue(link.is_symlink())
        self.assertEqual(envelope["data"]["draft"], str(self.draft))
        self.assertEqual(len(read_json(self.draft)["checks"]), 1)
        self.assertEqual(sorted(p.name for p in elsewhere.iterdir()), ["latest.json"])

    def test_a_failed_write_leaves_the_previous_draft_and_no_stray_file(self) -> None:
        self.add_check(self.draft, agent_check())
        for name in ("os.replace", "os.fsync"):
            with self.subTest(failing=name):
                with mock.patch(name, side_effect=OSError(28, "No space left on device")):
                    code, envelope, _ = self.unchanged_by(
                        self.draft, lambda: self.add_check(self.draft, agent_check(verdict="FAIL"))
                    )
                self.assertEqual(code, 1)
                self.assertIn("cannot write the draft", envelope["data"]["error"])
        self.assertEqual(read_json(self.draft)["checks"][0]["verdict"], "PASS")

    def test_a_cited_file_that_is_not_in_the_target_is_a_warning_about_this_check_only(self) -> None:
        _git.make_repo(self.target, ["AGENTS.md"])
        draft = self.start()
        evidence = [{"kind": "file", "path": "AGENTS.md"}, {"kind": "file", "path": "docs/missing.md"}]
        code, envelope, _ = self.add_check(draft, agent_check(evidence=evidence))
        self.assertEqual(code, 0)
        self.assertEqual(len(envelope["warnings"]), 1)
        self.assertTrue(envelope["warnings"][0].startswith("/checks/0/evidence/1: the file docs/missing.md is not in"))
        code, envelope, _ = self.add_check(draft, agent_check(id="CI-04", verdict="FAIL", evidence=[]))
        self.assertEqual((code, envelope["warnings"]), (0, []))


class OverrideTests(BuilderCase):
    """The agent disputes a verdict that the engine gave. The checks come from a real engine report."""

    def setUp(self) -> None:
        super().setUp()
        self.draft = self.engine_draft()
        self.agent_evidence = [{"kind": "file", "path": "Makefile", "lines": "3", "quote": "check: format-check test"}]

    def dispute(
        self, check_id: str = "EXEC-02", verdict: str = "PASS", **changes: Any
    ) -> tuple[int, dict[str, Any], str]:
        fragment = {
            "id": check_id,
            "verdict": verdict,
            "summary": "The Makefile composes the verbs.",
            "override_reason": "The engine missed the composition through a prerequisite.",
            "evidence": self.agent_evidence,
        }
        fragment.update(changes)
        return self.add_check(self.draft, fragment)

    def check(self, check_id: str = "EXEC-02") -> dict[str, Any]:
        return next(c for c in read_json(self.draft)["checks"] if c["id"] == check_id)

    def test_a_disputed_verdict_keeps_the_engines_and_adds_the_reason_and_evidence(self) -> None:
        before = self.check()
        self.assertEqual((before["verdict"], before["engine_verdict"]), ("PARTIAL", "PARTIAL"))
        code, envelope, _ = self.dispute()
        self.assertEqual(code, 0, envelope)
        self.assertEqual(
            {k: envelope["data"][k] for k in ("check", "action", "verdict", "engine_verdict")},
            {"check": "EXEC-02", "action": "overridden", "verdict": "PASS", "engine_verdict": "PARTIAL"},
        )
        after = self.check()
        self.assertEqual((after["verdict"], after["engine_verdict"]), ("PASS", "PARTIAL"))
        self.assertEqual(after["override_reason"], "The engine missed the composition through a prerequisite.")
        self.assertEqual(after["evidence"][-1]["captured_by"], "agent")
        self.assertEqual(after["method"], "automated")
        self.assertEqual(after.get("data"), before.get("data"))
        self.assertEqual(vr.validate_document(read_json(self.draft)).errors, [])

    def test_the_engines_evidence_stays_and_the_agents_replaces_an_earlier_dispute(self) -> None:
        document = read_json(self.draft)
        engine_items = [e for e in next(c for c in document["checks"] if c["id"] == "BASE-01")["evidence"]]
        self.assertTrue(engine_items and all(e["captured_by"] == "tool" for e in engine_items))
        for number in (1, 2):
            code, _, _ = self.dispute(
                "BASE-01", "FAIL", summary=f"Round {number}.", evidence=[{"kind": "file", "path": f"r{number}.txt"}]
            )
            self.assertEqual(code, 0)
        evidence = self.check("BASE-01")["evidence"]
        self.assertEqual(evidence[: len(engine_items)], engine_items)
        self.assertEqual([e["path"] for e in evidence[len(engine_items) :]], ["r2.txt"])
        self.assertEqual(self.check("BASE-01")["summary"], "Round 2.")

    def test_a_dispute_needs_a_reason_and_evidence_from_the_agent(self) -> None:
        fragment_without_reason = {"id": "EXEC-02", "verdict": "PASS", "summary": "x", "evidence": self.agent_evidence}
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.add_check(self.draft, fragment_without_reason))
        self.assertEqual(code, 2)
        self.assertTrue(envelope["data"]["errors"][0].startswith("rule 6: /checks/"))
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.dispute(evidence=[]))
        self.assertEqual(code, 2)
        self.assertIn("no evidence that the agent captured", envelope["data"]["errors"][0])

    def test_a_check_with_a_pending_finding_cannot_be_overridden_to_pass(self) -> None:
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.dispute("SEC-01", "PASS"))
        self.assertEqual(code, 2)
        self.assertIn("its finding must be rejected", "\n".join(envelope["data"]["errors"]))

    def test_the_same_verdict_as_the_engines_clears_the_dispute(self) -> None:
        self.dispute()
        fragment = {
            "id": "EXEC-02",
            "verdict": "PARTIAL",
            "summary": "The engine was right.",
            "evidence": self.agent_evidence,
        }
        code, envelope, _ = self.add_check(self.draft, fragment)
        self.assertEqual((code, envelope["data"]["action"]), (0, "agreed"))
        check = self.check()
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertNotIn("override_reason", check)

    def test_an_agreeing_verdict_with_a_reason_is_refused(self) -> None:
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.dispute(verdict="PARTIAL"))
        self.assertEqual(code, 2)
        self.assertIn("its verdict matches the engine's", envelope["data"]["errors"][0])

    def test_a_dispute_moves_the_summary(self) -> None:
        before = read_json(self.draft)["summary"]
        self.dispute()
        after = read_json(self.draft)["summary"]
        self.assertGreater(after["phase1_score"], before["phase1_score"])
        self.assertEqual(after["blockers_remaining"]["partial"], before["blockers_remaining"]["partial"] - 1)

    def test_an_automated_check_that_has_no_engine_verdict_is_not_the_agents_to_change(self) -> None:
        document = read_json(self.draft)
        del next(c for c in document["checks"] if c["id"] == "EXEC-02")["engine_verdict"]
        self.draft.write_text(rb.dumps(document), encoding="utf-8")
        code, envelope, _ = self.unchanged_by(self.draft, lambda: self.dispute())
        self.assertEqual(code, 2)
        self.assertIn("automated check with no engine verdict", envelope["data"]["error"])

    def test_only_phase_1_checks_count_toward_what_a_draft_is_expected_to_hold(self) -> None:
        catalogue = {"checks": [{"id": "AGT-11", "phase": 1}, {"id": "CI-04", "phase": 2}]}
        document = {"checks": [{"id": "AGT-11"}, {"id": "CI-04"}]}
        with mock.patch.object(vr, "load_catalogue", return_value=catalogue):
            self.assertEqual(rb.check_counts(document), {"checks_recorded": 1, "checks_expected": 1})

    def test_an_agent_only_check_is_added_beside_the_engines(self) -> None:
        code, envelope, _ = self.add_check(self.draft, agent_check())
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["checks_recorded"], 70)
        self.assertEqual(self.check("AGT-11")["method"], "agent")


class AddFindingTests(BuilderCase):
    def setUp(self) -> None:
        super().setUp()
        self.draft = self.failing_draft()

    def findings(self) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = read_json(self.draft)["findings"]
        return found

    def test_it_records_a_finding_and_computes_its_id_key_and_disposition(self) -> None:
        code, envelope, stderr = self.add_finding(self.draft, agent_finding())
        self.assertEqual(code, 0, envelope)
        self.assertEqual(
            envelope["data"],
            {
                "draft": str(self.draft),
                "finding": "F-001",
                "key": "AGT-11",
                "action": "added",
                "check": "AGT-11",
                "severity": "DEGRADER",
                "disposition": "pending",
                "findings": 1,
                "findings_pending": 1,
            },
        )
        self.assertEqual(stderr, "report: F-001 added for AGT-11\n")
        (finding,) = self.findings()
        self.assertEqual(
            list(finding),
            ["id", "key", "check", "severity", "statement", "evidence", "searches", "remediation", "disposition"],
        )
        self.assertEqual(finding["evidence"][0]["captured_by"], "agent")
        self.assertEqual(vr.validate_document(read_json(self.draft)).errors, [])

    def test_the_summary_counts_the_pending_agent_finding(self) -> None:
        self.assertEqual(read_json(self.draft)["summary"]["unconfirmed_agent_findings"], 0)
        self.add_finding(self.draft, agent_finding())
        document = read_json(self.draft)
        self.assertEqual(document["summary"]["unconfirmed_agent_findings"], 1)
        self.assertEqual(document["summary"], _summary.compute_summary(document))

    def test_the_key_is_the_check_and_the_scope_in_one_spelling(self) -> None:
        spellings = [
            ("src/a.ts", "AGT-11:src/a.ts"),
            ("./src//a.ts", "AGT-11:src/a.ts"),
            ("src\\a.ts", "AGT-11:src/a.ts"),
            ("  src/a.ts/  ", "AGT-11:src/a.ts"),
            ("packages/../src/a.ts", "AGT-11:src/a.ts"),
            ("api-gateway", "AGT-11:api-gateway"),
            (".", "AGT-11"),
            ("./", "AGT-11"),
        ]
        for scope, key in spellings:
            with self.subTest(scope=scope):
                draft = self.failing_draft()
                code, envelope, _ = self.add_finding(draft, agent_finding(scope=scope))
                self.assertEqual(code, 0, envelope)
                self.assertEqual(envelope["data"]["key"], key)
                self.assertEqual(read_json(draft)["findings"][0]["key"], key)

    def test_a_scope_that_is_not_a_place_in_the_target_is_refused(self) -> None:
        for scope, expected in [
            ("/etc/passwd", "is absolute"),
            ("../x", "climbs out"),
            ("a/../../x", "climbs out"),
            ("two words", "whitespace"),
            ("   ", "is empty"),
            ("C:\\x", "is absolute"),
        ]:
            with self.subTest(scope=scope):
                code, envelope, _ = self.unchanged_by(
                    self.draft, lambda: self.add_finding(self.draft, agent_finding(scope=scope))
                )
                self.assertEqual(code, 2)
                self.assertIn(expected, "\n".join(envelope["data"]["errors"]))

    def test_ids_count_up_and_are_never_reused(self) -> None:
        for number, scope in enumerate(["a", "b", "c"], start=1):
            _, envelope, _ = self.add_finding(self.draft, agent_finding(scope=scope))
            self.assertEqual(envelope["data"]["finding"], f"F-{number:03d}")
        document = read_json(self.draft)
        self.assertEqual([f["id"] for f in document["findings"]], ["F-001", "F-002", "F-003"])
        self.assertEqual(rb.next_finding_id([]), "F-001")
        self.assertEqual(rb.next_finding_id([{"id": "F-009"}, {"id": "F-002"}]), "F-010")
        self.assertEqual(rb.next_finding_id([{"id": "F-999"}]), "F-1000")

    def test_the_agent_cannot_write_what_the_tool_computes(self) -> None:
        fields = [
            ("id", "F-009"),
            ("key", "AGT-11"),
            ("disposition", "confirmed"),
            ("confirmed_via", "interactive"),
            ("disposition_note", "x"),
        ]
        for name, value in fields:
            with self.subTest(field=name):
                code, envelope, _ = self.unchanged_by(
                    self.draft, lambda: self.add_finding(self.draft, agent_finding(**{name: value}))
                )
                self.assertEqual(code, 2)
                self.assertIn(f"unexpected property: '{name}'", "\n".join(envelope["data"]["errors"]))

    def test_the_statement_has_the_required_form(self) -> None:
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.add_finding(self.draft, agent_finding(statement="The docs are thin."))
        )
        self.assertEqual(code, 2)
        self.assertIn("/statement", envelope["data"]["errors"][0])

    def test_a_finding_needs_a_check_that_is_in_the_draft(self) -> None:
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.add_finding(self.draft, agent_finding(check="CI-04"))
        )
        self.assertEqual(code, 2)
        self.assertIn("CI-04 is not a check in this draft", envelope["data"]["error"])
        self.assertIn("record CI-04 first", envelope["data"]["errors"][0])

    def test_a_passing_check_cannot_have_an_undecided_finding(self) -> None:
        self.add_check(
            self.draft,
            agent_check(id="CI-04", verdict="PASS", evidence=[{"kind": "file", "path": ".github/workflows/ci.yml"}]),
        )
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.add_finding(self.draft, agent_finding(check="CI-04"))
        )
        self.assertEqual(code, 2)
        self.assertIn("its finding must be rejected", envelope["data"]["errors"][0])

    def test_severity_defaults_to_the_checks_and_may_be_lower_but_not_higher(self) -> None:
        _, envelope, _ = self.add_finding(self.draft, agent_finding(scope="a"))
        self.assertEqual(envelope["data"]["severity"], "DEGRADER")
        _, envelope, _ = self.add_finding(self.draft, agent_finding(scope="b", severity="COSMETIC"))
        self.assertEqual(envelope["data"]["severity"], "COSMETIC")
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.add_finding(self.draft, agent_finding(scope="c", severity="BLOCKER"))
        )
        self.assertEqual(code, 2)
        self.assertIn("BLOCKER is higher than AGT-11's DEGRADER", envelope["data"]["errors"][0])

    def test_dependencies_must_be_findings_in_the_draft(self) -> None:
        self.add_finding(self.draft, agent_finding(scope="a"))
        remediation = {"summary": "Do it after F-001.", "depends_on": ["F-001"], "touches": ["AGENTS.md"]}
        code, envelope, _ = self.add_finding(self.draft, agent_finding(scope="b", remediation=remediation))
        self.assertEqual(code, 0, envelope)
        remediation["depends_on"] = ["F-009"]
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.add_finding(self.draft, agent_finding(scope="c", remediation=remediation))
        )
        self.assertEqual(code, 2)
        self.assertIn("F-009 is not a finding in this report", envelope["data"]["errors"][0])

    def test_a_playbook_must_be_one_the_catalogue_names(self) -> None:
        named = next(c["playbooks"][0] for c in vr.load_catalogue()["checks"] if c["playbooks"])
        code, _, _ = self.add_finding(
            self.draft, agent_finding(scope="a", remediation={"summary": "x", "playbook": named})
        )
        self.assertEqual(code, 0)
        code, envelope, _ = self.unchanged_by(
            self.draft,
            lambda: self.add_finding(
                self.draft, agent_finding(scope="b", remediation={"summary": "x", "playbook": "make-it-nice"})
            ),
        )
        self.assertEqual(code, 2)
        self.assertIn("the catalogue names no playbook make-it-nice", envelope["data"]["errors"][0])

    def test_a_finding_the_agent_wrote_is_replaced_in_place_while_it_is_pending(self) -> None:
        self.add_finding(self.draft, agent_finding(scope="a"))
        self.add_finding(self.draft, agent_finding(scope="b"))
        code, envelope, _ = self.add_finding(
            self.draft,
            agent_finding(scope="a", statement="An agent cannot trust the rules because they are stale.", evidence=[]),
        )
        self.assertEqual((code, envelope["data"]["action"], envelope["data"]["finding"]), (0, "replaced", "F-001"))
        findings = self.findings()
        self.assertEqual([f["id"] for f in findings], ["F-001", "F-002"])
        self.assertEqual(findings[0]["statement"], "An agent cannot trust the rules because they are stale.")
        self.assertEqual(findings[0]["evidence"], [])
        self.assertEqual(envelope["data"]["findings"], 2)

    def test_a_finding_that_has_a_decision_is_not_the_agents_to_rewrite(self) -> None:
        self.add_finding(self.draft, agent_finding())
        document = read_json(self.draft)
        document["findings"][0].update(disposition="confirmed", confirmed_via="interactive")
        document["summary"] = _summary.compute_summary(document)
        self.draft.write_text(rb.dumps(document), encoding="utf-8")
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.add_finding(self.draft, agent_finding(statement="An agent cannot x because y."))
        )
        self.assertEqual(code, 2)
        self.assertIn("F-001 (AGT-11) already has a decision", envelope["data"]["error"])
        self.assertIn("is confirmed", envelope["data"]["errors"][0])

    def test_the_run_policy_decides_the_disposition(self) -> None:
        for policy, eval_mode, expected in [
            ("accept-all", True, ("confirmed", "policy")),
            ("defer-all", True, ("pending", None)),
            ("defer-all", False, ("pending", None)),
            ("interactive", False, ("pending", None)),
        ]:
            with self.subTest(policy=policy, eval_mode=eval_mode):
                draft = self.failing_draft(confirmation_policy=policy, eval_mode=eval_mode)
                code, envelope, _ = self.add_finding(draft, agent_finding())
                self.assertEqual(code, 0, envelope)
                finding = read_json(draft)["findings"][0]
                self.assertEqual((finding["disposition"], finding.get("confirmed_via")), expected)
                self.assertEqual(vr.validate_document(read_json(draft)).errors, [])

    def test_evidence_follows_the_same_rules_as_a_checks(self) -> None:
        evidence = [{"kind": "file", "path": "AGENTS.md", "captured_by": "tool", "tool": "engine", "tool_version": "1"}]
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.add_finding(self.draft, agent_finding(evidence=evidence))
        )
        self.assertEqual(code, 2)
        self.assertIn("the agent cannot record tool-captured evidence", "\n".join(envelope["data"]["errors"]))
        quote = [{"kind": "file", "path": "AGENTS.md", "quote": credentials()[1]}]
        code, envelope, stderr = self.unchanged_by(
            self.draft, lambda: self.add_finding(self.draft, agent_finding(evidence=quote))
        )
        self.assertEqual(code, 2)
        self.assertTrue(envelope["data"]["errors"][0].startswith("rule 11:"))
        self.assertNotIn(credentials()[1], json.dumps(envelope) + stderr)

    def test_a_cited_file_that_is_missing_is_a_warning_about_this_finding_only(self) -> None:
        _git.make_repo(self.target, ["AGENTS.md"])
        draft = self.failing_draft()
        code, envelope, _ = self.add_finding(draft, agent_finding(evidence=[{"kind": "file", "path": "gone.md"}]))
        self.assertEqual(code, 0)
        self.assertEqual(len(envelope["warnings"]), 1)
        self.assertTrue(envelope["warnings"][0].startswith("/findings/0/evidence/0: the file gone.md"))

    def test_a_finding_on_an_engine_check_gets_the_next_id_after_the_engines(self) -> None:
        draft = self.engine_draft()
        before = read_json(draft)["findings"]
        fragment = agent_finding(
            check="TOOL-05", scope="packages/api", evidence=[], remediation={"summary": "Add the command."}
        )
        fragment["statement"] = "An agent cannot run the type check in packages/api because no script defines it."
        code, envelope, _ = self.add_finding(draft, fragment)
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["finding"], f"F-{len(before) + 1:03d}")
        self.assertEqual(envelope["data"]["key"], "TOOL-05:packages/api")
        self.assertEqual(vr.validate_document(read_json(draft)).errors, [])


class SetDispositionTests(BuilderCase):
    def setUp(self) -> None:
        super().setUp()
        self.draft = self.draft_with_findings()

    def finding(self, finding_id: str, draft: Path | None = None) -> dict[str, Any]:
        found: dict[str, Any] = next(f for f in read_json(draft or self.draft)["findings"] if f["id"] == finding_id)
        return found

    def test_it_records_one_decision_and_who_made_it(self) -> None:
        code, envelope, stderr = self.decide(
            self.draft, "--via", "interactive", "--finding", "F-001", "--disposition", "confirmed"
        )
        self.assertEqual(code, 0, envelope)
        self.assertEqual(
            envelope["data"],
            {
                "draft": str(self.draft),
                "updated": 1,
                "by_disposition": {"confirmed": 1},
                "findings": 3,
                "findings_pending": 2,
                "blockers_pending": 0,
            },
        )
        self.assertEqual(stderr, "report: 1 decision recorded, 2 findings pending\n")
        finding = self.finding("F-001")
        self.assertEqual((finding["disposition"], finding["confirmed_via"]), ("confirmed", "interactive"))
        self.assertNotIn("disposition_note", finding)
        self.assertEqual(list(finding)[-2:], ["disposition", "confirmed_via"])
        document = read_json(self.draft)
        self.assertEqual(document["summary"]["unconfirmed_agent_findings"], 2)
        self.assertEqual(vr.validate_document(document).errors, [])

    def test_a_note_is_kept_and_a_later_decision_without_one_drops_it(self) -> None:
        self.decide(
            self.draft,
            "--via",
            "interactive",
            "--finding",
            "F-001",
            "--disposition",
            "rejected",
            "--note",
            "Placeholders in a test.",
        )
        finding = self.finding("F-001")
        self.assertEqual((finding["disposition"], finding["disposition_note"]), ("rejected", "Placeholders in a test."))
        self.assertEqual(list(finding)[-3:], ["disposition", "disposition_note", "confirmed_via"])
        self.decide(self.draft, "--via", "interactive", "--finding", "F-001", "--disposition", "confirmed")
        self.assertNotIn("disposition_note", self.finding("F-001"))

    def test_taking_a_decision_back_clears_who_made_it_and_the_note(self) -> None:
        self.decide(
            self.draft, "--via", "interactive", "--finding", "F-002", "--disposition", "deferred", "--note", "Later."
        )
        code, envelope, _ = self.decide(self.draft, "--finding", "F-002", "--disposition", "pending")
        self.assertEqual(code, 0, envelope)
        finding = self.finding("F-002")
        self.assertEqual(finding["disposition"], "pending")
        self.assertNotIn("confirmed_via", finding)
        self.assertNotIn("disposition_note", finding)
        self.assertEqual(read_json(self.draft)["summary"]["unconfirmed_agent_findings"], 3)

    def test_a_batch_sets_every_decision_in_one_write(self) -> None:
        batch = [
            {"finding": "F-001", "disposition": "confirmed"},
            {"finding": "F-002", "disposition": "rejected", "note": "Not an issue."},
            {"finding": "F-003", "disposition": "confirmed"},
        ]
        code, envelope, _ = self.decide(self.draft, "--via", "batch", "--from", "-", stdin=json.dumps(batch))
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["updated"], 3)
        self.assertEqual(envelope["data"]["by_disposition"], {"confirmed": 2, "rejected": 1})
        self.assertEqual(envelope["data"]["findings_pending"], 0)
        self.assertEqual([f["confirmed_via"] for f in read_json(self.draft)["findings"]], ["batch"] * 3)

    def test_a_batch_can_come_from_a_file(self) -> None:
        source = self.root / "decisions.json"
        source.write_text(json.dumps([{"finding": "F-001", "disposition": "confirmed"}]), encoding="utf-8")
        code, _, _ = self.decide(self.draft, "--via", "batch", "--from", str(source))
        self.assertEqual(code, 0)
        self.assertEqual(self.finding("F-001")["confirmed_via"], "batch")

    def test_a_batch_with_one_bad_decision_changes_nothing(self) -> None:
        batch = [{"finding": "F-001", "disposition": "confirmed"}, {"finding": "F-009", "disposition": "confirmed"}]
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.decide(self.draft, "--via", "batch", "--from", "-", stdin=json.dumps(batch))
        )
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["errors"], ["fragment: /1/finding: F-009 is not a finding in this draft"])

    def test_a_finding_twice_in_one_list_is_refused(self) -> None:
        batch = [{"finding": "F-001", "disposition": "confirmed"}, {"finding": "F-001", "disposition": "rejected"}]
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.decide(self.draft, "--via", "batch", "--from", "-", stdin=json.dumps(batch))
        )
        self.assertEqual(code, 2)
        self.assertIn("F-001 appears twice", envelope["data"]["errors"][0])

    def test_a_bad_list_names_each_problem_by_place(self) -> None:
        batch = [
            {"finding": "F-1", "disposition": "maybe"},
            {"disposition": "confirmed", "note": "n" * 501},
            {"finding": "F-001", "disposition": "confirmed", "extra": 1},
            {"finding": "F-002"},
        ]
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.decide(self.draft, "--via", "batch", "--from", "-", stdin=json.dumps(batch))
        )
        self.assertEqual(code, 2)
        errors = "\n".join(envelope["data"]["errors"])
        for place in (
            "/0/finding",
            "/0/disposition",
            "/1: missing the required property 'finding'",
            "/1/note",
            "/2: unexpected property: 'extra'",
            "/3: missing the required property 'disposition'",
        ):
            self.assertIn(place, errors)
        for text in ("[]", "{}", "{"):
            with self.subTest(text=text):
                code, _, _ = self.unchanged_by(
                    self.draft, lambda: self.decide(self.draft, "--via", "batch", "--from", "-", stdin=text)
                )
                self.assertEqual(code, 2)

    def test_a_decision_needs_to_say_how_it_was_made(self) -> None:
        code, envelope, _ = self.unchanged_by(
            self.draft, lambda: self.decide(self.draft, "--finding", "F-001", "--disposition", "confirmed")
        )
        self.assertEqual(code, 1)
        self.assertIn("--via is required", envelope["data"]["error"])

    def test_the_arguments_must_name_one_way_to_give_the_decisions(self) -> None:
        cases = [
            (["--via", "batch"], "give --finding and --disposition"),
            (["--via", "batch", "--finding", "F-001"], "give --finding and --disposition"),
            (["--via", "batch", "--disposition", "confirmed"], "give --finding and --disposition"),
            (["--via", "batch", "--from", "-", "--finding", "F-001"], "--from cannot be combined"),
            (["--via", "batch", "--from", "-", "--note", "x"], "--from cannot be combined"),
            (["--via", "somehow", "--finding", "F-001", "--disposition", "confirmed"], "invalid choice"),
            (["--via", "batch", "--finding", "F-001", "--disposition", "agreed"], "invalid choice"),
        ]
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                code, envelope, _ = self.unchanged_by(
                    self.draft, lambda: self.decide(self.draft, *arguments, stdin="[]")
                )
                self.assertEqual(code, 1)
                self.assertIn(expected, envelope["data"]["error"])

    def test_a_finding_that_is_not_in_the_draft_is_refused(self) -> None:
        code, envelope, _ = self.unchanged_by(
            self.draft,
            lambda: self.decide(self.draft, "--via", "interactive", "--finding", "F-077", "--disposition", "confirmed"),
        )
        self.assertEqual(code, 2)
        self.assertIn("F-077 is not a finding in this draft", envelope["data"]["errors"][0])

    def test_a_decision_on_a_finding_of_a_passing_check_must_be_a_rejection(self) -> None:
        engine = self.engine_draft()
        sec = next(f for f in read_json(engine)["findings"] if f["check"] == "SEC-01")
        code, _, _ = self.add_check(
            engine,
            {
                "id": "SEC-01",
                "verdict": "PASS",
                "summary": "Fixed.",
                "override_reason": "r",
                "evidence": [{"kind": "file", "path": "a"}],
            },
        )
        self.assertEqual(code, 2, "the pending finding holds the check back")
        code, envelope, _ = self.decide(
            engine,
            "--via",
            "interactive",
            "--finding",
            sec["id"],
            "--disposition",
            "rejected",
            "--note",
            "Fixed since.",
        )
        self.assertEqual(code, 0, envelope)
        code, envelope, _ = self.add_check(
            engine,
            {
                "id": "SEC-01",
                "verdict": "PASS",
                "summary": "Fixed.",
                "override_reason": "r",
                "evidence": [{"kind": "file", "path": "a"}],
            },
        )
        self.assertEqual(code, 0, envelope)
        code, envelope, _ = self.unchanged_by(
            engine,
            lambda: self.decide(engine, "--via", "interactive", "--finding", sec["id"], "--disposition", "confirmed"),
        )
        self.assertEqual(code, 2)
        self.assertIn("its finding must be rejected", envelope["data"]["errors"][0])

    def test_a_blocker_is_decided_by_a_person_alone_and_never_in_a_batch(self) -> None:
        engine = self.engine_draft()
        document = read_json(engine)
        blocker = next(f["id"] for f in document["findings"] if f["severity"] == "BLOCKER")
        other = next(f["id"] for f in document["findings"] if f["severity"] != "BLOCKER")
        batch = [{"finding": other, "disposition": "confirmed"}, {"finding": blocker, "disposition": "confirmed"}]
        code, envelope, _ = self.unchanged_by(
            engine, lambda: self.decide(engine, "--via", "batch", "--from", "-", stdin=json.dumps(batch))
        )
        self.assertEqual(code, 2)
        self.assertIn(f"{blocker} is a BLOCKER, so a person decides on it alone", envelope["data"]["errors"][0])
        code, _, _ = self.decide(engine, "--via", "batch", "--from", "-", stdin=json.dumps(batch[:1]))
        self.assertEqual(code, 0)
        code, _, _ = self.decide(engine, "--via", "interactive", "--finding", blocker, "--disposition", "confirmed")
        self.assertEqual(code, 0)
        self.assertEqual(self.finding(blocker, engine)["confirmed_via"], "interactive")

    def test_pending_blockers_are_counted(self) -> None:
        engine = self.engine_draft()
        document = read_json(engine)
        blockers = [f["id"] for f in document["findings"] if f["severity"] == "BLOCKER"]
        _, envelope, _ = self.decide(
            engine, "--via", "interactive", "--finding", blockers[0], "--disposition", "confirmed"
        )
        self.assertEqual(envelope["data"]["blockers_pending"], len(blockers) - 1)

    def test_an_eval_run_has_no_person_so_only_the_policy_decides(self) -> None:
        draft = self.draft_with_findings(["a"], confirmation_policy="defer-all", eval_mode=True)
        for via in ("interactive", "batch"):
            with self.subTest(via=via):
                code, envelope, _ = self.unchanged_by(
                    draft, lambda: self.decide(draft, "--via", via, "--finding", "F-001", "--disposition", "confirmed")
                )
                self.assertEqual(code, 2)
                self.assertIn("eval-mode run, which has no person", envelope["data"]["errors"][0])
        code, envelope, _ = self.unchanged_by(
            draft, lambda: self.decide(draft, "--via", "policy", "--finding", "F-001", "--disposition", "confirmed")
        )
        self.assertEqual(code, 2)
        self.assertIn("needs the 'accept-all' confirmation policy", envelope["data"]["errors"][0])

    def test_taking_a_decision_back_needs_no_person_even_in_an_eval_run(self) -> None:
        draft = self.draft_with_findings(["a"], confirmation_policy="accept-all", eval_mode=True)
        code, envelope, _ = self.decide(draft, "--finding", "F-001", "--disposition", "pending")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(self.finding("F-001", draft)["disposition"], "pending")

    def test_under_accept_all_the_policy_decides_and_nothing_else_does(self) -> None:
        draft = self.draft_with_findings(["a"], confirmation_policy="accept-all", eval_mode=True)
        self.assertEqual(self.finding("F-001", draft)["confirmed_via"], "policy")
        code, _, _ = self.decide(draft, "--via", "policy", "--finding", "F-001", "--disposition", "deferred")
        self.assertEqual(code, 0)
        code, _, _ = self.unchanged_by(
            draft,
            lambda: self.decide(draft, "--via", "interactive", "--finding", "F-001", "--disposition", "confirmed"),
        )
        self.assertEqual(code, 2)

    def test_the_policy_cannot_decide_when_a_person_is_to(self) -> None:
        code, envelope, _ = self.unchanged_by(
            self.draft,
            lambda: self.decide(self.draft, "--via", "policy", "--finding", "F-001", "--disposition", "confirmed"),
        )
        self.assertEqual(code, 2)
        self.assertIn(
            "needs the 'accept-all' confirmation policy, and this run's is 'interactive'", envelope["data"]["errors"][0]
        )

    def test_a_person_can_decide_on_a_deferred_run_afterwards(self) -> None:
        draft = self.draft_with_findings(["a"], confirmation_policy="defer-all")
        self.assertEqual(self.finding("F-001", draft)["disposition"], "pending")
        code, envelope, _ = self.decide(
            draft, "--via", "interactive", "--finding", "F-001", "--disposition", "confirmed"
        )
        self.assertEqual(code, 0, envelope)
        self.assertEqual(vr.validate_document(read_json(draft)).errors, [])

    def test_it_writes_nothing_but_the_draft_and_does_not_touch_the_target(self) -> None:
        before = tree_state(self.target)
        self.decide(self.draft, "--via", "interactive", "--finding", "F-001", "--disposition", "confirmed")
        self.assertEqual(tree_state(self.target), before)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [self.draft.name])

    def test_a_failed_write_leaves_the_previous_draft(self) -> None:
        with mock.patch("os.replace", side_effect=OSError(5, "Input/output error")):
            code, envelope, _ = self.unchanged_by(
                self.draft,
                lambda: self.decide(
                    self.draft, "--via", "interactive", "--finding", "F-001", "--disposition", "confirmed"
                ),
            )
        self.assertEqual(code, 1)
        self.assertIn("cannot write the draft", envelope["data"]["error"])

    def test_the_agent_can_record_a_finding_again_after_the_decision_is_taken_back(self) -> None:
        self.decide(
            self.draft, "--via", "interactive", "--finding", "F-001", "--disposition", "edited", "--note", "Reworded."
        )
        code, _, _ = self.unchanged_by(self.draft, lambda: self.add_finding(self.draft, agent_finding(scope="a")))
        self.assertEqual(code, 2)
        self.decide(self.draft, "--finding", "F-001", "--disposition", "pending")
        code, envelope, _ = self.add_finding(
            self.draft, agent_finding(scope="a", statement="An agent cannot x because y.")
        )
        self.assertEqual((code, envelope["data"]["action"], envelope["data"]["finding"]), (0, "replaced", "F-001"))


class StatusTests(BuilderCase):
    def status(self, draft: Path) -> tuple[int, dict[str, Any], str]:
        return call(["status", str(draft)])

    def data(self, draft: Path) -> dict[str, Any]:
        code, envelope, stderr = self.status(draft)
        self.assertEqual(code, 0, stderr)
        data: dict[str, Any] = envelope["data"]
        return data

    def test_a_new_draft_has_every_family_remaining(self) -> None:
        draft = self.start()
        code, envelope, stderr = self.status(draft)
        self.assertEqual(code, 0)
        data = envelope["data"]
        self.assertEqual(data["draft"], str(draft))
        self.assertEqual(
            (data["status"], data["eval_mode"], data["confirmation_policy"]), ("draft", False, "interactive")
        )
        self.assertEqual((data["checks_recorded"], data["checks_expected"]), (0, 71))
        self.assertEqual(data["families_done"], "")
        self.assertEqual(
            list(data["families_remaining"]),
            ["IDX", "AGT", "DOC", "CMD", "TOOL", "CI", "BASE", "CON", "EXEC", "TST", "NAV", "SEC", "HYG"],
        )
        self.assertEqual(data["families_remaining"]["CI"], "CI-01 CI-02 CI-03 CI-04")
        self.assertEqual((data["findings"], data["findings_pending"], data["blockers_pending"]), (0, 0, 0))
        self.assertEqual((data["ready_to_finalise"], data["blocking"]), (False, "71 of 71 checks are not recorded"))
        self.assertEqual(data["pending"], [])
        self.assertNotIn("pending_omitted", data)
        self.assertFalse(envelope["truncated"])
        self.assertEqual(
            stderr, "report: 0 of 71 checks recorded; not ready to finalise: 71 of 71 checks are not recorded\n"
        )

    def test_recording_a_check_takes_it_off_the_remaining_list(self) -> None:
        draft = self.start()
        self.add_check(draft, agent_check(id="CI-04", verdict="FAIL", evidence=[]))
        data = self.data(draft)
        self.assertEqual(data["checks_recorded"], 1)
        self.assertEqual(data["families_remaining"]["CI"], "CI-01 CI-02 CI-03")
        self.assertNotIn("CI-04", " ".join(data["families_remaining"].values()))

    def test_an_engine_draft_lists_what_is_left_and_the_pending_findings_blockers_first(self) -> None:
        draft = self.engine_draft()
        data = self.data(draft)
        self.assertEqual((data["checks_recorded"], data["checks_expected"]), (69, 71))
        self.assertEqual(data["families_remaining"], {"AGT": "AGT-11", "CI": "CI-04"})
        self.assertEqual(data["families_done"], "IDX DOC CMD TOOL BASE CON EXEC TST NAV SEC HYG")
        self.assertEqual((data["findings"], data["findings_pending"], data["blockers_pending"]), (24, 24, 4))
        self.assertEqual(data["blocking"], "2 of 71 checks are not recorded; 24 findings are pending")
        findings = read_json(draft)["findings"]
        blockers = [f for f in findings if f["severity"] == "BLOCKER"]
        self.assertEqual(data["pending"][: len(blockers)], [f"{f['id']} BLOCKER {f['key']}" for f in blockers])
        self.assertEqual(len(data["pending"]), 8)
        self.assertEqual(data["pending_omitted"], 16)
        self.assertTrue(all(line.split()[1] in ("BLOCKER", "DEGRADER", "COSMETIC") for line in data["pending"]))
        order = [line.split()[1] for line in data["pending"]]
        self.assertEqual(order, sorted(order, key=["BLOCKER", "DEGRADER", "COSMETIC"].index))

    def test_blockers_come_first_whatever_the_order_the_findings_were_recorded_in(self) -> None:
        draft = self.engine_draft()
        document = read_json(draft)
        document["findings"].reverse()
        draft.write_text(rb.dumps(document), encoding="utf-8")
        pending = self.data(draft)["pending"]
        self.assertEqual([line.split()[1] for line in pending[:4]], ["BLOCKER"] * 4)
        self.assertNotEqual(pending[4].split()[1], "BLOCKER")

    def test_what_was_left_out_of_the_list_is_said_in_the_envelope(self) -> None:
        code, envelope, _ = self.status(self.engine_draft())
        self.assertEqual(code, 0)
        self.assertIs(envelope["truncated"], True)

    def test_a_report_of_70_checks_prints_40_lines_or_fewer(self) -> None:
        draft = self.engine_draft()
        self.add_check(draft, agent_check())
        self.assertEqual(len(read_json(draft)["checks"]), 70)
        self.assertLessEqual(self.stdout_lines("status", str(draft)), 40)

    def test_no_draft_can_make_it_print_more_than_40_lines(self) -> None:
        fresh = self.start()
        self.assertLessEqual(self.stdout_lines("status", str(fresh)), 40)
        busy = self.failing_draft()
        for number in range(30):
            code, envelope, _ = self.add_finding(busy, agent_finding(scope=f"module-{number}"))
            self.assertEqual(code, 0, envelope)
        lines = self.stdout_lines("status", str(busy))
        self.assertLessEqual(lines, 40)
        data = self.data(busy)
        self.assertEqual(len(data["pending"]) + data["pending_omitted"], 30)
        self.assertGreater(data["pending_omitted"], 0)
        self.assertEqual(len(data["families_remaining"]), 13)

    def test_it_is_ready_when_every_check_is_recorded_and_every_finding_decided(self) -> None:
        draft = self.complete_engine_draft()
        data = self.data(draft)
        self.assertEqual((data["checks_recorded"], data["checks_expected"]), (71, 71))
        self.assertEqual((data["families_remaining"], data["findings_pending"], data["blockers_pending"]), ({}, 0, 0))
        self.assertEqual((data["ready_to_finalise"], data["blocking"]), (True, ""))
        self.assertEqual(data["pending"], [])
        self.assertEqual(self.status(draft)[2], "report: 71 of 71 checks recorded; ready to finalise\n")

    def test_one_pending_finding_is_enough_to_hold_it_back(self) -> None:
        draft = self.complete_engine_draft()
        self.decide(draft, "--finding", "F-001", "--disposition", "pending")
        data = self.data(draft)
        self.assertEqual((data["ready_to_finalise"], data["blocking"]), (False, "1 finding is pending"))
        self.assertEqual(len(data["pending"]), 1)

    def test_an_eval_run_is_never_ready(self) -> None:
        draft = self.draft_with_findings(["a"], confirmation_policy="accept-all", eval_mode=True)
        data = self.data(draft)
        self.assertTrue(data["blocking"].startswith("this is an eval-mode run, and its report is never final"))
        self.assertIs(data["ready_to_finalise"], False)

    def test_a_blocker_decided_by_anything_but_a_person_holds_it_back(self) -> None:
        draft = self.complete_engine_draft()
        document = read_json(draft)
        blocker = next(f for f in document["findings"] if f["severity"] == "BLOCKER")
        blocker["confirmed_via"] = "batch"
        draft.write_text(rb.dumps(document), encoding="utf-8")
        data = self.data(draft)
        self.assertEqual(
            (data["ready_to_finalise"], data["blocking"]), (False, "1 BLOCKER finding not decided interactively")
        )

    def test_a_final_report_can_be_described_and_is_not_changeable(self) -> None:
        worked = next((TOOLS.parent / "schema" / "examples").glob("example-service.audit-report.*.json"))
        copy = self.out / worked.name
        self.out.mkdir()
        shutil.copyfile(worked, copy)
        data = self.data(copy)
        self.assertEqual(
            (data["status"], data["ready_to_finalise"], data["blocking"]),
            ("final", False, "the report is already final"),
        )

    def test_an_invalid_draft_is_exit_2_and_a_missing_one_is_exit_1(self) -> None:
        draft = self.start()
        document = read_json(draft)
        document["summary"]["scored_checks"] = 9
        draft.write_text(rb.dumps(document), encoding="utf-8")
        code, envelope, _ = self.status(draft)
        self.assertEqual(code, 2)
        self.assertIn("the draft is not valid to report on", envelope["data"]["error"])
        self.assertTrue(envelope["data"]["errors"][0].startswith("rule 10:"))
        code, envelope, _ = self.status(self.out / "none.json")
        self.assertEqual(code, 1)
        self.assertIn("draft not found", envelope["data"]["error"])

    def test_it_writes_nothing_and_does_not_wait_for_the_lock(self) -> None:
        draft = self.engine_draft()
        before = tree_state(self.out)
        with rb.write_lock(self.out):
            code, _, _ = self.status(draft)
        self.assertEqual(code, 0)
        self.assertEqual(tree_state(self.out), before)

    def test_a_draft_inside_the_target_can_still_be_described(self) -> None:
        draft = self.start()
        document = read_json(draft)
        document["provenance"]["target"]["path"] = str(self.root)
        draft.write_text(rb.dumps(document), encoding="utf-8")
        self.assertEqual(self.status(draft)[0], 0)


class FinaliseTests(BuilderCase):
    def setUp(self) -> None:
        super().setUp()
        self.draft = self.complete_engine_draft()

    def test_it_writes_the_final_report_as_a_new_file_and_leaves_the_draft_as_it_was(self) -> None:
        before = self.files()
        code, envelope, stderr = self.finalise(self.draft)
        self.assertEqual(code, 0, envelope)
        final = Path(envelope["data"]["report"])
        self.assertEqual(final.name, "agentic-tdd.audit-report.20261010T114530Z.json")
        self.assertEqual(final.parent, self.out)
        after = self.files()
        self.assertEqual({name: data for name, data in after.items() if name != final.name}, before)
        self.assertEqual(set(after) - set(before), {final.name})
        self.assertEqual(envelope["data"]["status"], "final")
        self.assertEqual(envelope["data"]["finalised_at"], "2026-10-10T11:45:30+00:00")
        self.assertEqual((envelope["data"]["checks"], envelope["data"]["findings"]), (71, 24))
        self.assertEqual(envelope["data"]["summary"], read_json(final)["summary"])
        self.assertRegex(
            stderr,
            r"^report: wrote agentic-tdd\.audit-report\.20261010T114530Z\.json \(phase-1 score [0-9.]+, 24 findings\)\n$",
        )

    def test_the_final_report_validates_and_is_the_draft_made_final(self) -> None:
        _, envelope, _ = self.finalise(self.draft)
        final = read_json(envelope["data"]["report"])
        self.assertEqual(vr.validate_document(final).errors, [])
        self.assertEqual((final["status"], final["provenance"]["finalised_at"]), ("final", "2026-10-10T11:45:30+00:00"))
        self.assertEqual(final["summary"], _summary.compute_summary(final))
        self.assertEqual(list(final["provenance"])[-2:], ["started_at", "finalised_at"])
        reopened = json.loads(json.dumps(final))
        reopened["status"] = "draft"
        del reopened["provenance"]["finalised_at"]
        self.assertEqual(reopened, read_json(self.draft))
        done = subprocess.run(
            [sys.executable, str(TOOLS / "validate_report.py"), envelope["data"]["report"]],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_second_finalise_leaves_every_earlier_file_byte_identical(self) -> None:
        self.finalise(self.draft)
        first = self.files()
        code, envelope, _ = self.finalise(self.draft)
        self.assertEqual(code, 0)
        self.assertEqual(Path(envelope["data"]["report"]).name, "agentic-tdd.audit-report.20261010T114530Z-2.json")
        after = self.files()
        self.assertEqual({name: data for name, data in after.items() if name in first}, first)
        self.assertEqual(len(after), len(first) + 1)
        later = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(rb, "utc_now", return_value=later):
            code, envelope, _ = call(["finalise", str(self.draft)])
        self.assertEqual(Path(envelope["data"]["report"]).name, "agentic-tdd.audit-report.20261010T120000Z.json")
        self.assertEqual({name: data for name, data in self.files().items() if name in first}, first)

    def test_a_second_run_on_the_same_repository_leaves_a_finished_report_alone(self) -> None:
        _, envelope, _ = self.finalise(self.draft)
        final = Path(envelope["data"]["report"])
        final_bytes = final.read_bytes()
        intake = self.write_intake()
        later = datetime(2026, 10, 11, 8, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(rb, "utc_now", return_value=later):
            code, _, _ = call(["init", str(intake)])
        self.assertEqual(code, 0)
        self.assertEqual(final.read_bytes(), final_bytes)

    def test_a_draft_with_a_finding_still_pending_is_refused_and_nothing_is_written(self) -> None:
        self.decide(self.draft, "--finding", "F-001", "--disposition", "pending")
        code, envelope, _ = self.unchanged_dir(lambda: self.finalise(self.draft))
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["error"], "the draft cannot be finalised: 1 problem")
        self.assertEqual(envelope["data"]["errors"], ["1 finding still pending: F-001"])

    def unchanged_dir(self, run: Any) -> tuple[int, dict[str, Any], str]:
        before = self.files()
        outcome: tuple[int, dict[str, Any], str] = run()
        self.assertEqual(self.files(), before)
        return outcome

    def test_every_problem_is_listed_and_long_lists_are_cut(self) -> None:
        draft = self.engine_draft()
        code, envelope, _ = self.unchanged_dir(lambda: self.finalise(draft))
        self.assertEqual(code, 2)
        self.assertEqual(
            envelope["data"]["errors"][:2], ["checks not recorded in AGT: AGT-11", "checks not recorded in CI: CI-04"]
        )
        self.assertEqual(envelope["data"]["errors"][2].split(":")[0], "24 findings still pending")
        self.assertTrue(envelope["data"]["errors"][2].endswith(" and 4 more"))
        shown = envelope["data"]["errors"][2].split(": ", 1)[1].split(" and ")[0].split()
        self.assertEqual((len(shown), shown[0]), (20, "F-001"))
        self.assertEqual(rb.listed(["F-1", "F-2"]), "F-1 F-2")

    def test_an_eval_run_is_never_finalised(self) -> None:
        draft = self.draft_with_findings(["a"], confirmation_policy="accept-all", eval_mode=True)
        code, envelope, _ = self.unchanged_dir(lambda: self.finalise(draft))
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["errors"][0], "this is an eval-mode run, and its report is never final")

    def test_a_blocker_that_no_person_decided_alone_is_refused(self) -> None:
        document = read_json(self.draft)
        blocker = next(f for f in document["findings"] if f["severity"] == "BLOCKER")
        blocker["confirmed_via"] = "batch"
        self.draft.write_text(rb.dumps(document), encoding="utf-8")
        code, envelope, _ = self.unchanged_dir(lambda: self.finalise(self.draft))
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["errors"], [f"BLOCKER findings not decided interactively: {blocker['id']}"])

    def test_a_final_report_that_would_not_be_valid_is_never_written(self) -> None:
        real = vr.validate_document

        def failing_for_final(document: Any, **kwargs: Any) -> Any:
            if isinstance(document, dict) and document.get("status") == "final":
                return vr.Outcome(errors=["rule 8: /: made up"])
            return real(document, **kwargs)

        with mock.patch.object(vr, "validate_document", failing_for_final):
            code, envelope, _ = self.unchanged_dir(lambda: self.finalise(self.draft))
        self.assertEqual(code, 2)
        self.assertEqual(envelope["data"]["errors"], ["rule 8: /: made up"])
        self.assertTrue(
            envelope["data"]["error"].startswith("the final report would not be valid, so nothing was written")
        )

    def test_a_failed_write_leaves_no_partial_file_and_the_draft_intact(self) -> None:
        with mock.patch("os.fsync", side_effect=OSError(28, "No space left on device")):
            code, envelope, _ = self.unchanged_dir(lambda: self.finalise(self.draft))
        self.assertEqual(code, 1)
        self.assertIn("cannot write the final report", envelope["data"]["error"])

    def test_a_final_report_is_never_changed_afterwards(self) -> None:
        _, envelope, _ = self.finalise(self.draft)
        final = Path(envelope["data"]["report"])
        code, envelope, _ = self.unchanged_by(final, lambda: self.add_check(final, agent_check()))
        self.assertEqual(code, 1)
        self.assertIn("is a final report", envelope["data"]["error"])
        code, envelope, _ = self.unchanged_dir(lambda: self.finalise(final))
        self.assertEqual(code, 1)
        self.assertIn("is a final report", envelope["data"]["error"])

    def test_a_draft_inside_the_target_is_refused(self) -> None:
        document = read_json(self.draft)
        document["provenance"]["target"]["path"] = str(self.root)
        self.draft.write_text(rb.dumps(document), encoding="utf-8")
        code, envelope, _ = self.unchanged_dir(lambda: self.finalise(self.draft))
        self.assertEqual(code, 1)
        self.assertIn("refusing to write inside the target", envelope["data"]["error"])

    def test_a_draft_that_is_missing_or_invalid_is_refused(self) -> None:
        code, envelope, _ = self.finalise(self.out / "none.json")
        self.assertEqual((code, "draft not found" in envelope["data"]["error"]), (1, True))
        code, envelope, _ = self.finalise(self.root / "nowhere" / "d.json")
        self.assertEqual((code, "draft not found" in envelope["data"]["error"]), (1, True))
        document = read_json(self.draft)
        document["summary"]["phase1_score"] = 0.5
        self.draft.write_text(rb.dumps(document), encoding="utf-8")
        code, envelope, _ = self.unchanged_dir(lambda: self.finalise(self.draft))
        self.assertEqual(code, 2)
        self.assertIn("the draft is not valid before the change", envelope["data"]["error"])

    def test_cited_files_that_are_not_in_the_target_are_warnings_and_bounded(self) -> None:
        code, envelope, _ = self.finalise(self.draft)
        self.assertEqual(code, 0)
        self.assertGreater(len(envelope["warnings"]), 0)
        self.assertTrue(all(w.startswith("/") and "is not in the target" in w for w in envelope["warnings"]))

    def test_it_waits_for_the_lock_and_writes_nothing_inside_the_target(self) -> None:
        before = tree_state(self.target)
        self.finalise(self.draft)
        self.assertEqual(tree_state(self.target), before)
        with mock.patch.object(rb, "LOCK_WAIT_S", 0.2), rb.write_lock(self.out):
            code, envelope, _ = self.unchanged_dir(lambda: self.finalise(self.draft))
        self.assertEqual(code, 1)
        self.assertIn("another report command has held the lock", envelope["data"]["error"])

    def test_status_says_ready_exactly_when_finalise_succeeds(self) -> None:
        def one_pending() -> Path:
            draft = self.complete_engine_draft()
            self.decide(draft, "--finding", "F-003", "--disposition", "pending")
            return draft

        scenarios: dict[str, Callable[[], Path]] = {
            "new": self.start,
            "engine": self.engine_draft,
            "complete": self.complete_engine_draft,
            "one pending": one_pending,
            "eval": lambda: self.draft_with_findings(["a"], confirmation_policy="accept-all", eval_mode=True),
        }
        outcomes: dict[str, tuple[Any, bool]] = {}
        for name, make in scenarios.items():
            self.out = self.root / f"out-{name.replace(' ', '-')}"
            draft = make()
            ready = self.data_of(draft)["ready_to_finalise"]
            code, _, _ = self.finalise(draft)
            outcomes[name] = (ready, code == 0)
        self.assertEqual(
            outcomes,
            {
                "new": (False, False),
                "engine": (False, False),
                "complete": (True, True),
                "one pending": (False, False),
                "eval": (False, False),
            },
        )

    def data_of(self, draft: Path) -> dict[str, Any]:
        _, envelope, _ = call(["status", str(draft)])
        data: dict[str, Any] = envelope["data"]
        return data

    def test_a_scripted_sequence_builds_a_draft_that_validates_at_every_step(self) -> None:
        draft = self.start()
        steps: list[Callable[[], tuple[int, dict[str, Any], str]]] = [
            lambda: self.add_check(draft, agent_check(verdict="FAIL", summary="Restates the README.")),
            lambda: self.add_check(draft, agent_check(id="CI-04", verdict="FAIL", summary="No CI.", evidence=[])),
            lambda: self.add_finding(draft, agent_finding()),
            lambda: self.add_finding(draft, agent_finding(scope="docs")),
            lambda: self.decide(draft, "--via", "interactive", "--finding", "F-001", "--disposition", "confirmed"),
            lambda: self.decide(
                draft, "--via", "batch", "--finding", "F-002", "--disposition", "deferred", "--note", "Later."
            ),
        ]
        for number, step in enumerate(steps, start=1):
            code, envelope, _ = step()
            self.assertEqual(code, 0, (number, envelope))
            document = read_json(draft)
            self.assertEqual(vr.validate_document(document).errors, [], number)
            self.assertEqual(document["summary"], _summary.compute_summary(document), number)
        data = self.data_of(draft)
        self.assertEqual((data["checks_recorded"], data["findings"], data["findings_pending"]), (2, 2, 0))
        code, envelope, _ = self.unchanged_dir(lambda: self.finalise(draft))
        self.assertEqual(code, 2, "the 69 checks of the engine arrive with import-engine (S2.5)")
        self.assertEqual(len(envelope["data"]["errors"]), 13, "one line for each of the 13 families")


class ConcurrencyTests(BuilderCase):
    def test_commands_that_run_at_the_same_time_lose_nothing(self) -> None:
        draft = self.failing_draft()
        scopes = [f"module-{number}" for number in range(8)]
        script = str(TOOLS / "report.py")
        with contextlib.ExitStack() as stack:
            procs = [
                stack.enter_context(
                    subprocess.Popen(
                        [sys.executable, script, "add-finding", str(draft), "--from", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                )
                for _ in scopes
            ]
            for proc, scope in zip(procs, scopes):
                assert proc.stdin is not None
                proc.stdin.write(json.dumps(agent_finding(scope=scope)))
                proc.stdin.close()
            results = [(proc.wait(60), proc.stdout.read() if proc.stdout else "") for proc in procs]
        self.assertEqual([code for code, _ in results], [0] * len(scopes), [out for _, out in results])
        document = read_json(draft)
        self.assertEqual(sorted(f["key"] for f in document["findings"]), sorted(f"AGT-11:{scope}" for scope in scopes))
        self.assertEqual(sorted(f["id"] for f in document["findings"]), [f"F-{n:03d}" for n in range(1, 9)])
        self.assertEqual(vr.validate_document(document).errors, [])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [draft.name])


class LockTests(BuilderCase):
    def test_a_second_holder_waits_until_the_first_lets_go(self) -> None:
        events: list[str] = []
        entered = threading.Event()
        release = threading.Event()

        def first() -> None:
            with rb.write_lock(self.root):
                events.append("first in")
                entered.set()
                release.wait(5)
                events.append("first out")

        def second() -> None:
            entered.wait(5)
            with rb.write_lock(self.root):
                events.append("second in")

        threads = [threading.Thread(target=first), threading.Thread(target=second)]
        for thread in threads:
            thread.start()
        entered.wait(5)
        threads[1].join(0.3)
        self.assertEqual(events, ["first in"], "the second holder must wait")
        release.set()
        for thread in threads:
            thread.join(5)
        self.assertEqual(events, ["first in", "first out", "second in"])

    def test_a_holder_that_never_lets_go_is_a_clear_error_and_not_a_hang(self) -> None:
        with rb.write_lock(self.root):
            with mock.patch.object(rb, "LOCK_WAIT_S", 0.2):
                with self.assertRaises(_common.UsageError) as caught:
                    with rb.write_lock(self.root):
                        self.fail("the lock was taken twice")
        self.assertIn("another report command has held the lock", str(caught.exception))

    def test_the_lock_is_free_again_after_an_error(self) -> None:
        with self.assertRaises(RuntimeError):
            with rb.write_lock(self.root):
                raise RuntimeError("x")
        with mock.patch.object(rb, "LOCK_WAIT_S", 0.2):
            with rb.write_lock(self.root):
                pass


class ToolContractTests(BuilderCase):
    def test_describe_lists_the_subcommands_and_says_it_writes_outside_the_target(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        manifest = envelope["data"]
        self.assertEqual(manifest["name"], "report")
        self.assertIs(manifest["writes_inside_target"], False)
        self.assertIs(manifest["network"], False)
        self.assertTrue(any(line.startswith("report.py init") for line in manifest["synopsis"]))
        self.assertTrue(any(line.startswith("report.py add-check") for line in manifest["synopsis"]))
        self.assertTrue(any(line.startswith("report.py add-finding") for line in manifest["synopsis"]))
        self.assertTrue(any(line.startswith("report.py set-disposition") for line in manifest["synopsis"]))
        self.assertTrue(any(line.startswith("report.py status") for line in manifest["synopsis"]))
        self.assertTrue(any(line.startswith("report.py finalise") for line in manifest["synopsis"]))

    def test_a_missing_or_unknown_subcommand_is_exit_1(self) -> None:
        for argv in ([], ["nothing"]):
            with self.subTest(argv=argv):
                code, envelope, _ = call(argv)
                self.assertEqual(code, 1)
                self.assertFalse(envelope["ok"])

    def test_an_abbreviation_is_refused(self) -> None:
        code, _, _ = call(["in", str(self.root / "x.json")])
        self.assertEqual(code, 1)

    def test_it_runs_as_a_script_from_any_directory(self) -> None:
        intake = self.write_intake()
        done = subprocess.run(
            [sys.executable, str(TOOLS / "report.py"), "init", str(intake)],
            cwd="/",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        envelope = json.loads(done.stdout)
        self.assertTrue(envelope["ok"])
        check = subprocess.run(
            [sys.executable, str(TOOLS / "validate_report.py"), envelope["data"]["draft"]],
            cwd="/",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_the_envelope_and_the_files_do_not_depend_on_the_working_directory(self) -> None:
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.root)
        code, envelope, _ = call(["init", str(self.write_intake(output_dir="out", target_path="My_Service"))])
        self.assertEqual(code, 0)
        self.assertEqual(Path(envelope["data"]["draft"]).parent, self.out)


if __name__ == "__main__":
    unittest.main()
