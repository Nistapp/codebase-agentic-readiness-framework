# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Six golden `facts.json` files, one headlining each section besides `facts_version`, `label` and `caps`.

Each golden is a copy of one engine fixture, scanned outside any git repository so the tool sees no real git state
(``git.sha`` null, ``git.dirty`` false) unless the golden is the one that headlines ``git``, which is instead given a
real, fixed-date commit plus one untracked file, so its ``sha`` is reproducible and its ``dirty`` is true. The six:

* ``git`` — ``tool-ok-node``, a committed, then dirtied, copy.
* ``inventory`` — ``nav-03-red-flags``, five kinds in one small tree.
* ``stack`` — ``cmd-ok-maven``, the jvm ecosystem and the maven package manager.
* ``instruction-files`` — ``agt-01-shadowed``, a canonical file and the one that shadows it.
* ``components`` — ``agt-02-uncovered``, a root manifest and two declared sub-components.
* ``size`` — ``nav-03-red-flags`` again, capped at two files so the walk is cut short and the class is ``huge``.

The golden files sit beside the schema's examples (`schema/examples/facts.golden.<name>.json`), covered by that
folder's licence note. To change one on purpose: delete it, run this module with `python -m test_facts_golden
--write <name>` from `tools/tests` (or `--write all`), and read the diff before committing it. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

import _paths  # noqa: F401
import _git
import engine as launcher
import facts
from test_facts import call, working_directory

FIXTURES = launcher.ENGINE_DIR / "tests" / "fixtures"
EXAMPLES = facts.RECIPES / "schema" / "examples"
FIXED_DATE = "2026-01-01T00:00:00+00:00"


def plain_copy(fixture: str, root: Path) -> Path:
    """A copy of `fixture` outside any git repository, so the tool sees no git at all."""
    target = root / "repo"
    shutil.copytree(FIXTURES / fixture, target)
    return target


def dirtied_commit(fixture: str, root: Path) -> Path:
    """A copy of `fixture`, committed with a fixed date so its sha is reproducible, then given one untracked file."""
    target = plain_copy(fixture, root)
    env = {**_git.git_environment(), "GIT_AUTHOR_DATE": FIXED_DATE, "GIT_COMMITTER_DATE": FIXED_DATE}
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "golden"]):
        subprocess.run(["git", *args], cwd=target, check=True, capture_output=True, text=True, env=env)
    (target / "untracked.txt").write_text("golden\n", encoding="utf-8")
    return target


GOLDENS: dict[str, dict[str, Any]] = {
    "git": {"fixture": "tool-ok-node", "build": dirtied_commit, "max_files": None},
    "inventory": {"fixture": "nav-03-red-flags", "build": plain_copy, "max_files": None},
    "stack": {"fixture": "cmd-ok-maven", "build": plain_copy, "max_files": None},
    "instruction-files": {"fixture": "agt-01-shadowed", "build": plain_copy, "max_files": None},
    "components": {"fixture": "agt-02-uncovered", "build": plain_copy, "max_files": None},
    "size": {"fixture": "nav-03-red-flags", "build": plain_copy, "max_files": 2},
}


def golden_path(name: str) -> Path:
    return EXAMPLES / f"facts.golden.{name}.json"


def facts_bytes(name: str) -> bytes:
    """A fresh run of the tool for the golden `name`, as the bytes it writes."""
    spec = GOLDENS[name]
    build: Callable[[str, Path], Path] = spec["build"]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        repo = build(spec["fixture"], root)
        out = root / "out.json"
        argv = [str(repo), "--out", str(out), "--repo-label", f"{name}-example"]
        if spec["max_files"] is not None:
            argv += ["--max-files", str(spec["max_files"])]
        code, envelope, err = call(argv)
        if code != 0:
            raise AssertionError(f"{name}: facts.py refused: {envelope} {err}")
        return out.read_bytes()


def walk_strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in walk_strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in walk_strings(value)]
    return []


class GoldenTests(unittest.TestCase):
    def test_each_golden_matches_byte_for_byte(self) -> None:
        for name in GOLDENS:
            with self.subTest(golden=name):
                golden = golden_path(name)
                self.assertTrue(golden.is_file(), f"the golden file {golden} is missing")
                self.assertEqual(
                    facts_bytes(name),
                    golden.read_bytes(),
                    f"{golden.name} differs from a fresh run. If the change is deliberate, delete {golden.name} "
                    f"and run `python -m test_facts_golden --write {name}` from tools/tests.",
                )

    def test_two_runs_on_one_target_give_the_same_bytes(self) -> None:
        for name in GOLDENS:
            with self.subTest(golden=name):
                self.assertEqual(facts_bytes(name), facts_bytes(name))

    def test_a_run_from_another_working_directory_gives_the_same_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as elsewhere:
            with working_directory(Path(elsewhere)):
                for name in GOLDENS:
                    with self.subTest(golden=name):
                        self.assertEqual(facts_bytes(name), golden_path(name).read_bytes())

    def test_every_golden_holds_no_timestamp_and_no_absolute_path(self) -> None:
        for name in GOLDENS:
            with self.subTest(golden=name):
                document = json.loads(golden_path(name).read_bytes())
                for text in walk_strings(document):
                    self.assertIsNone(re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}", text), text)
                    self.assertFalse(text.startswith("/"), text)

    def test_every_list_in_each_golden_is_sorted(self) -> None:
        for name in GOLDENS:
            with self.subTest(golden=name):
                document = json.loads(golden_path(name).read_bytes())
                stack = document["stack"]
                for key in (
                    "ecosystems",
                    "source_only",
                    "package_managers",
                    "ci_providers",
                    "test_frameworks",
                    "hook_managers",
                    "notes",
                ):
                    self.assertEqual(stack[key], sorted(stack[key]), key)
                self.assertEqual(
                    [entry["path"] for entry in document["instruction_files"]],
                    sorted(entry["path"] for entry in document["instruction_files"]),
                )
                self.assertEqual(
                    [entry["path"] for entry in document["components"]["declared"]],
                    sorted(entry["path"] for entry in document["components"]["declared"]),
                )
                self.assertEqual(document["components"]["candidates"], sorted(document["components"]["candidates"]))
                self.assertEqual(document["components"]["notes"], sorted(document["components"]["notes"]))
                self.assertEqual(
                    [entry["reason"] for entry in document["inventory"]["skipped"]],
                    sorted(entry["reason"] for entry in document["inventory"]["skipped"]),
                )


def write_goldens(names: list[str]) -> None:
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    for name in names:
        golden_path(name).write_bytes(facts_bytes(name))
        print(f"wrote {golden_path(name)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", choices=[*GOLDENS, "all"])
    args = parser.parse_args()
    if args.write:
        write_goldens(list(GOLDENS) if args.write == "all" else [args.write])
        sys.exit(0)
    unittest.main()
