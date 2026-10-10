# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The report builder: each subcommand does what it says, writes only through the contract, and leaves the draft valid.

Every test starts from an intake and a target made in a temporary folder, runs the tool in process through
`run_tool` (so the envelope and the exit code are what a recipe sees), and reads the draft back from disk. A test that
needs a repository makes a real one with git. Credential-shaped strings are built at run time, so that the secrets
scan finds nothing in this file. Standard library only.
"""

from __future__ import annotations

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
from typing import Any, Sequence
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
