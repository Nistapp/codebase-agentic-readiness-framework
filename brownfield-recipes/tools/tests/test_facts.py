# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The facts tool keeps the tool contract: one envelope, exit codes, refusals with exact messages, a new file outside the
target, and a target that is left exactly as it was.

Most tests call the tool in process with string streams, on small repositories made in a temporary directory. One class
starts the tool as a script from the filesystem root, which is how a recipe starts it. Standard library only.
"""

from __future__ import annotations

import hashlib
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any, Sequence
from unittest import mock

import _paths
import _common
import _git
import _jsonschema_subset as subset
import facts

TOOLS = _paths.TOOLS
SHA = "deadbeef" * 5  # 40 hex digits that look like a commit and are not a high-entropy string
STALE = 946684800  # 2000-01-01: a file time that the index does not hold


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    """Run the tool in process. Returns the exit code, the parsed envelope and stderr."""
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(facts.INFO, facts.handler, list(argv), stdout=out, stderr=err)
    envelope: dict[str, Any] = json.loads(out.getvalue())
    return code, envelope, err.getvalue()


def engine_scan() -> Any:
    """The engine's `audit.scan`, loaded through the tool's own launcher."""
    return facts.engine_module("audit.scan")


def engine_default_cap() -> int:
    """The cap the engine's walk uses when it is not given one, read from its signature."""
    return int(inspect.signature(engine_scan().build_inventory).parameters["max_files"].default)


KIND_NAMES = [kind.value for kind in engine_scan().Kind]


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every file and directory under `root`, `.git` included, with size and modification time."""
    state: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        state[str(path.relative_to(root))] = (info.st_size, info.st_mtime_ns)
    return state


def index_hash(repo: Path) -> str:
    return hashlib.sha256((repo / ".git" / "index").read_bytes()).hexdigest()


def make_stale(repo: Path) -> None:
    """Give a tracked file a time that the index does not hold, so that `git status` would refresh the index."""
    os.utime(repo / "README.md", (STALE, STALE))


class working_directory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.previous = ""

    def __enter__(self) -> None:
        self.previous = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, *exc: object) -> None:
        os.chdir(self.previous)


class RepoCase(unittest.TestCase):
    """A committed repository named `My_Repo`, and a folder outside it for the output."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.repo = self.root / "My_Repo"
        _git.make_repo(self.repo)
        self.folder = self.root / "out"
        self.folder.mkdir()
        self.out = self.folder / "facts.json"

    def run_ok(self, *extra: str, target: Path | None = None, out: Path | None = None) -> dict[str, Any]:
        code, envelope, _ = call([str(target or self.repo), "--out", str(out or self.out), *extra])
        self.assertEqual(code, 0, envelope)
        return envelope

    def refused(self, argv: Sequence[str], message: str, *, code: int = 1) -> None:
        got, envelope, err = call(argv)
        self.assertEqual((got, envelope["ok"], envelope["data"]), (code, False, {"error": message}))
        self.assertEqual(err, f"facts: {message}\n")

    def written(self) -> dict[str, Any]:
        document: dict[str, Any] = json.loads(self.out.read_text(encoding="utf-8"))
        return document


class ContractTests(RepoCase):
    def test_describe_prints_the_manifest_and_needs_no_other_argument(self) -> None:
        code, envelope, err = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"], facts.INFO.manifest())
        manifest = envelope["data"]
        self.assertEqual(manifest["name"], "facts")
        self.assertEqual(
            manifest["synopsis"],
            ["facts.py <target> --out FILE [--repo-label LABEL] [--exclude GLOB]... [--max-files N]"],
        )
        self.assertEqual(
            manifest["writes"],
            "One new file, the one --out names, which must be outside the target and must not exist. It is never replaced.",
        )
        self.assertEqual(
            manifest["summary"],
            "Describe a repository with counts and names and no verdicts, as facts.json. "
            "In development: so far it writes facts_version, label, git, inventory and caps.",
        )
        self.assertIs(manifest["writes_inside_target"], False)
        self.assertIs(manifest["network"], False)
        self.assertEqual(err, f"facts {facts.INFO.version}: {manifest['summary']}\n")

    def test_the_envelope_names_the_file_its_size_and_the_version(self) -> None:
        code, envelope, err = call([str(self.repo), "--out", str(self.out)])
        size = self.out.stat().st_size
        self.assertEqual(code, 0)
        self.assertEqual(list(envelope), ["tool", "version", "ok", "data", "warnings", "truncated"])
        self.assertEqual(
            (envelope["tool"], envelope["version"], envelope["ok"]), ("facts", _common.TOOLS_VERSION, True)
        )
        self.assertEqual(envelope["data"], {"file": str(self.out), "bytes": size, "facts_version": "0.1"})
        self.assertEqual(list(envelope["data"]), ["file", "bytes", "facts_version"])
        self.assertEqual((envelope["warnings"], envelope["truncated"]), ([], False))
        self.assertEqual(err, f"facts: wrote facts.json ({size} bytes)\n")

    def test_a_relative_out_is_reported_by_its_full_path(self) -> None:
        with working_directory(self.folder):
            envelope = self.run_ok(out=Path("facts.json"))
        self.assertEqual(envelope["data"]["file"], str(self.out))
        self.assertTrue(self.out.is_file())

    def test_help_says_the_tool_is_in_development(self) -> None:
        with mock.patch.dict(os.environ, {"COLUMNS": "200"}):
            text = facts.build_parser().format_help()
        self.assertTrue(text.startswith("usage: facts.py "), text)
        self.assertIn(facts.INFO.summary, text)
        self.assertRegex(
            text,
            r"(?m)^IN DEVELOPMENT until S2\.7\.5\.3: so far the file holds facts_version, label, git, inventory and caps\.$",
        )
        self.assertRegex(text, r"(?m)^  target {2,}the repository to describe$")
        self.assertRegex(text, r"(?m)^  --out FILE {2,}the file to create; it must not exist$")
        self.assertRegex(
            text,
            r"(?m)^  --repo-label REPO_LABEL\n {2,}the label in the file \(default: derived from the target's name\)$",
        )
        self.assertRegex(
            text,
            r"(?m)^  --exclude GLOB {2,}a path glob to leave out of the inventory, as engine.py's does;"
            r" the file names up to 10$",
        )
        self.assertRegex(
            text,
            r"(?m)^  --max-files MAX_FILES\n {2,}stop the inventory walk after this many files"
            r" \(default: the engine's own cap\); a walk that stops is truncated$",
        )
        self.assertNotIn("no effect", text)


class ScriptTests(RepoCase):
    """The tool started as a script from `/`, as a recipe starts it."""

    def start(self, *args: str) -> tuple[int, dict[str, Any], str]:
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "facts.py"), *args], cwd="/", text=True, capture_output=True, check=False
        )
        return proc.returncode, json.loads(proc.stdout), proc.stderr

    def test_describe_works_from_the_filesystem_root(self) -> None:
        code, envelope, _ = self.start("--describe")
        self.assertEqual((code, envelope["data"]["name"]), (0, "facts"))

    def test_a_run_works_from_the_filesystem_root(self) -> None:
        code, envelope, err = self.start(str(self.repo), "--out", str(self.out))
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["file"], str(self.out))
        self.assertEqual(err, f"facts: wrote facts.json ({self.out.stat().st_size} bytes)\n")

    def test_a_refusal_is_one_envelope_and_exit_one(self) -> None:
        code, envelope, _ = self.start(str(self.root / "missing"), "--out", str(self.out))
        self.assertEqual((code, envelope["ok"]), (1, False))
        self.assertFalse(self.out.exists())


class UsageTests(RepoCase):
    def test_a_missing_argument(self) -> None:
        self.refused([], "the following arguments are required: target, --out")
        self.refused([str(self.repo)], "the following arguments are required: --out")
        self.refused(["--out", str(self.out)], "the following arguments are required: target")

    def test_an_unknown_option_and_an_abbreviation(self) -> None:
        self.refused([str(self.repo), "--out", str(self.out), "--nope"], "unrecognized arguments: --nope")
        self.refused([str(self.repo), "--out", str(self.out), "--max", "5"], "unrecognized arguments: --max 5")
        self.refused([str(self.repo), "--ou", str(self.out)], "the following arguments are required: --out")

    def test_the_cap_must_be_a_whole_number_of_at_least_one(self) -> None:
        base = [str(self.repo), "--out", str(self.out)]
        self.refused([*base, "--max-files", "0"], "--max-files must be at least 1, not 0")
        self.refused([*base, "--max-files", "-5"], "--max-files must be at least 1, not -5")
        self.refused([*base, "--max-files", "many"], "argument --max-files: invalid int value: 'many'")
        self.assertEqual(self.run_ok("--max-files", "1")["ok"], True)

    def test_a_label_that_could_not_name_a_file(self) -> None:
        message = (
            "repo_label {!r} is not allowed: use up to 32 of a-z, 0-9, dot, underscore and hyphen, "
            "starting with a letter or digit"
        )
        for label in ("Bad Label", "-x", "a" * 33):
            with self.subTest(label=label):
                self.refused([str(self.repo), "--out", str(self.out), f"--repo-label={label}"], message.format(label))
        self.assertFalse(self.out.exists())


class TargetTests(RepoCase):
    def test_a_missing_target(self) -> None:
        self.refused([str(self.root / "missing"), "--out", str(self.out)], f"target not found: {self.root / 'missing'}")

    def test_a_file_is_not_a_target(self) -> None:
        path = self.repo / "README.md"
        self.refused([str(path), "--out", str(self.out)], f"target is not a directory: {path}")

    def test_a_filesystem_root_is_refused_before_the_output_is_looked_at(self) -> None:
        self.refused(["/", "--out", str(self.out)], "refusing to scan a filesystem root")
        self.assertFalse(self.out.exists())

    def test_a_refused_target_leaves_no_file(self) -> None:
        call([str(self.root / "missing"), "--out", str(self.out)])
        self.assertEqual(list(self.folder.iterdir()), [])


class OutputTests(RepoCase):
    def test_the_folder_must_exist(self) -> None:
        missing = self.root / "nowhere"
        self.refused(
            [str(self.repo), "--out", str(missing / "facts.json")], f"the folder for --out does not exist: {missing}"
        )
        self.assertFalse(missing.exists())

    def test_the_file_must_not_be_inside_the_target(self) -> None:
        before = snapshot(self.repo)
        self.refused(
            [str(self.repo), "--out", str(self.repo / "facts.json")],
            f"refusing to write inside the target: {self.repo}",
        )
        (self.repo / "docs").mkdir()
        before = snapshot(self.repo)
        self.refused(
            [str(self.repo), "--out", str(self.repo / "docs" / "facts.json")],
            f"refusing to write inside the target: {self.repo / 'docs'}",
        )
        self.assertEqual(snapshot(self.repo), before)

    def test_a_folder_that_leads_into_the_target_through_a_link_is_refused(self) -> None:
        (self.repo / "docs").mkdir()
        link = self.folder / "link"
        link.symlink_to(self.repo / "docs", target_is_directory=True)
        self.refused(
            [str(self.repo), "--out", str(link / "facts.json")],
            f"refusing to write inside the target: {self.repo / 'docs'}",
        )
        self.assertEqual(list((self.repo / "docs").iterdir()), [])

    def test_a_relative_out_from_inside_the_target_is_refused(self) -> None:
        with working_directory(self.repo):
            self.refused([str(self.repo), "--out", "facts.json"], f"refusing to write inside the target: {self.repo}")
        self.assertFalse((self.repo / "facts.json").exists())

    def test_an_existing_file_is_never_replaced(self) -> None:
        self.out.write_text("mine", encoding="utf-8")
        self.refused(
            [str(self.repo), "--out", str(self.out)], f"{self.out} already exists, and a tool never replaces a file"
        )
        self.assertEqual(self.out.read_text(encoding="utf-8"), "mine")

    def test_an_existing_folder_a_dangling_link_and_a_link_to_a_file_are_never_written_through(self) -> None:
        elsewhere = self.root / "elsewhere.txt"
        elsewhere.write_text("kept", encoding="utf-8")
        cases = {
            "folder": self.folder / "dir",
            "dangling": self.folder / "dangling.json",
            "link": self.folder / "link.json",
        }
        cases["folder"].mkdir()
        cases["dangling"].symlink_to(self.root / "gone.json")
        cases["link"].symlink_to(elsewhere)
        for name, path in cases.items():
            with self.subTest(name=name):
                self.refused(
                    [str(self.repo), "--out", str(path)], f"{path} already exists, and a tool never replaces a file"
                )
        self.assertEqual(elsewhere.read_text(encoding="utf-8"), "kept")
        self.assertFalse((self.root / "gone.json").exists())

    def test_a_file_that_appears_after_the_checks_is_not_replaced_either(self) -> None:
        def appear(document: dict[str, Any]) -> None:
            self.out.write_text("raced", encoding="utf-8")

        with mock.patch.object(facts, "check_document", side_effect=appear):
            self.refused(
                [str(self.repo), "--out", str(self.out)], f"{self.out} already exists, and a tool never replaces a file"
            )
        self.assertEqual(self.out.read_text(encoding="utf-8"), "raced")

    def test_a_write_the_system_refuses_is_a_usage_error(self) -> None:
        with mock.patch.object(_common, "create_file", side_effect=PermissionError(13, "Permission denied")):
            self.refused([str(self.repo), "--out", str(self.out)], f"cannot write {self.out}: Permission denied")

    def test_nothing_is_left_when_the_document_is_refused(self) -> None:
        with mock.patch.object(facts, "git_state", return_value={"sha": "xyz", "dirty": False}):
            code, _, _ = call([str(self.repo), "--out", str(self.out)])
        self.assertEqual(code, 3)
        self.assertEqual(list(self.folder.iterdir()), [])


class FileTests(RepoCase):
    def test_the_file_is_exactly_this_text(self) -> None:
        self.run_ok()
        sha = _git.run_git(self.repo, "rev-parse", "HEAD")
        kinds = [f'      "{kind}": {1 if kind == "doc" else 0}' for kind in KIND_NAMES]
        self.assertEqual(
            self.out.read_text(encoding="utf-8"),
            "\n".join(
                [
                    "{",
                    '  "facts_version": "0.1",',
                    '  "label": "my-repo",',
                    '  "git": {',
                    f'    "sha": "{sha}",',
                    '    "dirty": false',
                    "  },",
                    '  "inventory": {',
                    '    "files": 1,',
                    '    "bytes": 2,',
                    '    "by_kind": {',
                    ",\n".join(kinds),
                    "    },",
                    '    "skipped": [],',
                    '    "truncated": false,',
                    f'    "max_files": {engine_default_cap()},',
                    '    "excludes": []',
                    "  },",
                    '  "caps": {',
                    '    "excludes": {',
                    '      "limit": 10,',
                    '      "omitted": 0',
                    "    }",
                    "  }",
                    "}",
                    "",
                ]
            ),
        )

    def test_the_file_fits_its_schema(self) -> None:
        self.run_ok()
        schema = json.loads(facts.FACTS_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual([str(found) for found in subset.SubsetValidator(schema).validate(self.written())], [])
        self.assertEqual(facts.FACTS_SCHEMA, TOOLS.parent / "schema" / "facts.schema.json")

    def test_the_file_holds_no_time_and_no_absolute_path(self) -> None:
        self.run_ok()
        found: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, str):
                found.append(node)
            elif isinstance(node, dict):
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(self.written())
        self.assertEqual(len(found), 3)
        for text in found:
            self.assertIsNone(re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}", text), text)
            self.assertFalse(text.startswith("/"), text)
        self.assertNotIn(str(self.root), self.out.read_text(encoding="utf-8"))

    def test_the_label_follows_the_rule_that_names_output_files(self) -> None:
        long_name = self.root / "Digital_Assistant_microServices"
        _git.make_repo(long_name)
        self.run_ok(target=long_name)
        self.assertEqual(self.written()["label"], "digital-assistant-micros")

    def test_an_explicit_label_wins(self) -> None:
        self.run_ok("--repo-label", "chosen.name_1")
        self.assertEqual(self.written()["label"], "chosen.name_1")

    def test_a_clean_repository(self) -> None:
        self.run_ok()
        self.assertEqual(self.written()["git"], {"sha": _git.run_git(self.repo, "rev-parse", "HEAD"), "dirty": False})

    def test_a_repository_with_changes_is_dirty(self) -> None:
        (self.repo / "new.txt").write_text("x\n", encoding="utf-8")
        self.run_ok()
        self.assertIs(self.written()["git"]["dirty"], True)
        self.out.unlink()
        _git.run_git(self.repo, "add", "-A")
        _git.run_git(self.repo, "commit", "-q", "-m", "y")
        (self.repo / "README.md").write_text("changed\n", encoding="utf-8")
        self.run_ok()
        self.assertEqual(self.written()["git"], {"sha": _git.run_git(self.repo, "rev-parse", "HEAD"), "dirty": True})

    def test_a_directory_that_is_not_a_repository(self) -> None:
        plain = self.root / "plain"
        plain.mkdir()
        (plain / "a.txt").write_text("x\n", encoding="utf-8")
        self.run_ok(target=plain)
        self.assertEqual(self.written()["git"], {"sha": None, "dirty": False})

    def test_a_repository_with_no_commit_has_no_sha(self) -> None:
        fresh = self.root / "fresh"
        _git.make_repo(fresh, commit=False)
        self.run_ok(target=fresh)
        self.assertEqual(self.written()["git"], {"sha": None, "dirty": True})


class ReadOnlyTests(RepoCase):
    """The target is left as it was, down to the index, even when its file times make `git status` want to refresh it.

    The test reads the status with `--no-optional-locks` too: a plain `git status` would refresh the index itself.
    """

    def state(self) -> tuple[str, str, str, dict[str, tuple[int, int]]]:
        return (
            index_hash(self.repo),
            _git.run_git(self.repo, "--no-optional-locks", "status", "--porcelain"),
            _git.run_git(self.repo, "rev-parse", "HEAD"),
            snapshot(self.repo),
        )

    def test_a_run_on_a_repository_with_a_stale_index_changes_nothing(self) -> None:
        make_stale(self.repo)
        before = self.state()
        self.run_ok()
        self.assertEqual(self.state(), before)

    def test_a_run_on_a_dirty_repository_with_a_stale_index_changes_nothing(self) -> None:
        (self.repo / "new.txt").write_text("x\n", encoding="utf-8")
        make_stale(self.repo)
        before = self.state()
        self.run_ok()
        self.assertEqual(self.state(), before)


class EngineReuseTests(RepoCase):
    def test_git_is_what_the_engines_target_module_says(self) -> None:
        target_module = facts.engine_module("audit.target")
        canned = types.SimpleNamespace(git_sha=SHA, git_dirty=True)
        with mock.patch.object(target_module, "resolve_target", return_value=canned) as guard:
            self.run_ok()
        guard.assert_called_once_with(self.repo)
        self.assertEqual(self.written()["git"], {"sha": SHA, "dirty": True})

    def test_the_guards_refusal_is_a_usage_error_with_the_engines_words(self) -> None:
        with self.assertRaises(_common.UsageError) as caught:
            facts.git_state(Path("/"))
        self.assertEqual(str(caught.exception), "refusing to scan a filesystem root")


class DeterminismTests(RepoCase):
    def test_two_runs_write_the_same_bytes(self) -> None:
        other = self.folder / "other.json"
        self.run_ok()
        self.run_ok(out=other)
        self.assertEqual(self.out.read_bytes(), other.read_bytes())

    def test_a_copy_of_the_repository_elsewhere_gives_the_same_bytes(self) -> None:
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        shutil.copytree(self.repo, elsewhere / "My_Repo", symlinks=True)
        other = self.folder / "other.json"
        self.run_ok()
        self.run_ok(target=elsewhere / "My_Repo", out=other)
        self.assertEqual(self.out.read_bytes(), other.read_bytes())

    def test_the_working_directory_does_not_matter(self) -> None:
        other = self.folder / "other.json"
        self.run_ok()
        with working_directory(self.root):
            self.run_ok(out=other)
        self.assertEqual(self.out.read_bytes(), other.read_bytes())


class SchemaGuardTests(RepoCase):
    def test_a_document_that_fits_passes(self) -> None:
        facts.check_document({"facts_version": "0.1", "label": "x", "git": {"sha": SHA, "dirty": False}})

    def test_a_document_that_does_not_fit_is_a_bug_in_the_tool_and_exit_three(self) -> None:
        with mock.patch.object(facts, "git_state", return_value={"sha": "xyz", "dirty": False}):
            code, envelope, err = call([str(self.repo), "--out", str(self.out)])
        self.assertEqual(code, 3)
        self.assertEqual(
            envelope["data"],
            {
                "error": "the facts do not fit facts.schema.json, which is a bug in the tool",
                "errors": ["/git/sha: does not match the pattern ^([0-9a-f]{40}|[0-9a-f]{64})$"],
            },
        )
        self.assertIn("  /git/sha: does not match the pattern", err)

    def test_the_validator_is_built_once_from_the_schema_file(self) -> None:
        self.assertIs(facts.facts_validator(), facts.facts_validator())
        self.assertTrue(facts.FACTS_SCHEMA.is_file())


class BoundTests(RepoCase):
    def test_a_document_that_fits_is_text_in_key_order(self) -> None:
        self.assertEqual(facts.encode_facts({"b": 1, "a": "é"}), '{\n  "b": 1,\n  "a": "é"\n}\n')

    def test_the_limit_is_inclusive_and_counts_bytes(self) -> None:
        document = {"a": "é" * 10}
        text = facts.encode_facts(document, limit=10**9)
        size = len(text.encode("utf-8"))
        self.assertGreater(size, len(text))
        self.assertEqual(facts.encode_facts(document, limit=size), text)
        with self.assertRaises(_common.OutputTooLarge) as caught:
            facts.encode_facts(document, limit=size - 1)
        self.assertEqual(
            str(caught.exception),
            f"the facts are {size} bytes and the limit is {size - 1}; the tool must bound its lists",
        )

    def test_the_limit_is_under_30_kb_whichever_kilobyte_is_meant(self) -> None:
        self.assertEqual(facts.MAX_FACTS_BYTES, 30_000)

    def test_the_handler_refuses_a_document_over_the_limit_and_writes_nothing(self) -> None:
        with mock.patch.object(facts, "encode_facts", side_effect=_common.OutputTooLarge("too big")):
            code, envelope, _ = call([str(self.repo), "--out", str(self.out)])
        self.assertEqual((code, envelope["data"]), (3, {"error": "too big"}))
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
