# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`IDX-02` and `IDX-03` summaries do not depend on where the checkout sits, in-process so coverage traces them.

The same repository is copied into two folders at different depths, and each check runs on both copies with the
same store. Every summary must be equal and must not hold either copy's absolute path: a path inside the target is
written as `<repository>/...`. The store is redirected with `AUDIT_INDEX_STORE`, and `--no-user-config` keeps
`$HOME` out of the run.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.probes import ProbeSession  # noqa: E402
from audit.rules.checks.idx import INDEX_STORE_ENV, check_idx02, check_idx03  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.target import resolve_target  # noqa: E402
from packs.idx.test_idx_pack import write_store  # noqa: E402


def _copies(tmp: Path) -> tuple[Path, Path]:
    """The same small repository in two folders at different depths."""
    roots = (tmp / "a" / "repo", tmp / "b" / "deeper" / "repo")
    for root in roots:
        support.write(root, "README.md", "# repo\n")
    return roots


def _run(check, root: Path, *, store: Path | None, probes: bool = False):
    spec = REGISTRY_BY_ID[check.__name__.replace("check_idx", "IDX-")]
    session = ProbeSession(cwd=root, enabled=probes, user_config=False)
    env = {INDEX_STORE_ENV: str(store)} if store is not None else {}
    with mock.patch.dict(os.environ, env, clear=False):
        if store is None:
            os.environ.pop(INDEX_STORE_ENV, None)
        # IDX-03 needs a HEAD to compare; a fixed revision stands in for a git checkout.
        target = dataclasses.replace(resolve_target(root), git_sha="0" * 40)
        return check(spec=spec, target=target, inventory=None, stack=None, components=None, session=session)


class PathIndependentSummaryTests(unittest.TestCase):
    def assert_same_summary(self, roots: tuple[Path, Path], outcomes: list) -> str:
        first, second = (outcome.summary for outcome in outcomes)
        self.assertEqual(first, second)
        for root in roots:
            self.assertNotIn(str(root), first)
            self.assertNotIn(str(root.resolve()), first)
        return first

    def test_store_not_located_names_the_team_artifact_inside_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = _copies(Path(tmp))
            outcomes = [_run(check_idx02, root, store=None) for root in roots]
        summary = self.assert_same_summary(roots, outcomes)
        self.assertEqual(outcomes[0].verdict.value, "UNKNOWN")
        self.assertIn("<repository>/.codebase-memory/graph.db.zst", summary)

    def test_an_unreadable_team_artifact_is_named_inside_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = _copies(Path(tmp))
            for root in roots:
                artifact = root / ".codebase-memory" / "graph.db.zst"
                artifact.parent.mkdir(parents=True)
                artifact.write_bytes(b"\x28\xb5\x2f\xfd not really zstd")
            idx02 = [_run(check_idx02, root, store=None) for root in roots]
            idx03 = [_run(check_idx03, root, store=None, probes=True) for root in roots]
        self.assertIn("located (<repository>/.codebase-memory/graph.db.zst)", self.assert_same_summary(roots, idx02))
        self.assertIn("at <repository>/.codebase-memory/graph.db.zst", self.assert_same_summary(roots, idx03))

    def test_pass_and_fail_do_not_print_the_target_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = _copies(Path(tmp))
            both = write_store(Path(tmp) / "both", [str(root.resolve()) for root in roots])
            neither = write_store(Path(tmp) / "neither", ["/somewhere/else"])
            passes = [_run(check_idx02, root, store=both) for root in roots]
            fails = [_run(check_idx02, root, store=neither) for root in roots]
        self.assertEqual(passes[0].verdict.value, "PASS")
        self.assertIn("rooted at <repository>", self.assert_same_summary(roots, passes))
        self.assertEqual(fails[0].verdict.value, "FAIL")
        self.assertIn("rooted at <repository>", self.assert_same_summary(roots, fails))
        self.assertEqual(fails[0].findings[0].statement, fails[1].findings[0].statement)

    def test_a_store_override_inside_the_repository_is_named_inside_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = _copies(Path(tmp))
            outcomes = []
            for root in roots:
                store = root / "index"
                store.mkdir()
                outcomes.append(_run(check_idx02, root, store=store))
        summary = self.assert_same_summary(roots, outcomes)
        self.assertIn("located (<repository>/index) but holds no readable database", summary)


if __name__ == "__main__":
    unittest.main()
