# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The fixture matrix — one explicit expectation per fixture, checked end to end.

This is the Phase-14 consolidation of the per-pack fixture tests. It walks ``tests/fixtures/`` and
asserts, for every fixture directory, the verdict its README entry promises. The matrix is an
**explicit table**, not a wildcard guess: a new fixture with no row here fails
``test_every_fixture_is_accounted_for``.

Two rules the matrix makes mechanical:

* **One defect per fixture.** A fixture that fails three checks cannot tell you which rule broke.
  The per-pack tests already assert "exactly this check" within a pack; this test asserts the
  documented verdict for the row.
* **A positive fixture per pack.** ``test_governed_fixtures_pass_every_scoreable_check`` runs the
  positive fixtures and asserts that, between them, every scoreable check passes at least once.
  Two families are excluded by construction and named below, because their verdicts cannot be
  produced without executed probes or machine-local state (AGENTS.md §10.4: never fake a pass).

Fixtures whose target check reads git's tracked set are copied into a temporary git repository
created inside the test's temp directory — never the audit repo — and a tracked defect that an
ignore rule would hide is force-added, exactly as the owning pack tests do.
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

from audit.rules.registry import REGISTRY, scoreable  # noqa: E402
from packs.agt.matrix import ROWS as AGT_ROWS  # noqa: E402
from packs.base.matrix import ROWS as BASE_ROWS  # noqa: E402
from packs.ci.matrix import ROWS as CI_ROWS  # noqa: E402
from packs.cmd.matrix import ROWS as CMD_ROWS  # noqa: E402
from packs.con.matrix import ROWS as CON_ROWS  # noqa: E402
from packs.cross_family.matrix import ROWS as CROSS_FAMILY_ROWS  # noqa: E402
from packs.doc_nav.matrix import ROWS as DOC_NAV_ROWS  # noqa: E402
from packs.exec.matrix import ROWS as EXEC_ROWS  # noqa: E402
from packs.hyg.matrix import ROWS as HYG_ROWS  # noqa: E402
from packs.idx.matrix import ROWS as IDX_ROWS  # noqa: E402
from packs.sec.matrix import ROWS as SEC_ROWS  # noqa: E402
from packs.tool.matrix import ROWS as TOOL_ROWS  # noqa: E402
from packs.tst.matrix import ROWS as TST_ROWS  # noqa: E402

FIXTURES_DIR = support.FIXTURES_DIR

#: The family tables, in the order the rows are listed in ``MATRIX``.
FAMILY_TABLES = (
    AGT_ROWS,
    DOC_NAV_ROWS,
    CMD_ROWS,
    TOOL_ROWS,
    CI_ROWS,
    BASE_ROWS,
    CON_ROWS,
    EXEC_ROWS,
    TST_ROWS,
    SEC_ROWS,
    IDX_ROWS,
    HYG_ROWS,
    CROSS_FAMILY_ROWS,
)

#: fixture directory -> {check id: expected verdict}. Every directory under tests/fixtures/ must
#: appear here (``test_every_fixture_is_accounted_for``). The rows live in one table per family,
#: ``tests/packs/<family>/matrix.py``; ``packs/cross_family/matrix.py`` holds the fixtures that belong to no single
#: family (carried data, layout and stack fixtures, ``governed-minimal``). A fixture's row goes in one table only.
MATRIX: dict[str, dict[str, str]] = {}
for _table in FAMILY_TABLES:
    MATRIX.update(_table)

#: Fixtures whose target reads git's tracked set; they are copied into a fresh git repository.
NEEDS_GIT = frozenset(
    {
        "doc-03-tracked-artefacts",
        "ignore-ok-nested-gitignore",
        "exec-02-no-lockfile",
        "exec-02-nested-lockfile",
        "exec-02-lockfile-no-manifest",
        # The fixture's own ignore file hides the stray file from this repository too, so the stray file is
        # committed here with `git add -f`; the fresh copy's `add -A` leaves it untracked, as the fixture needs.
        "exec-04-anchored-ignored-dir",
        "exec-04-nested-ignored-dir",
        "layout-app-per-folder",
        "exec-05-generated",
        "exec-05-committed-dist",
        "exec-05-build-script",
        "exec-ok",
        "sec-01-ok",
        "sec-01-tracked-env",
        "sec-01-excluded-env",
        "sec-01-tracked-ignored-env",
        "sec-03-tracked-ignored-key",
        "sec-02-key-shaped",
        "con-03-artefacts-not-ignored",
        "stack-dotnet",
        "stack-dotnet-locked",
        "stack-gradle-wrapper-readme",
        "stack-just-inline-version",
        "stack-maven-wrapper-readme",
        "stack-php-composer",
        "stack-python-uv-inline-version",
        "stack-ruby-bundler",
        "stack-rust-cargo",
    }
)

#: Fixtures where an ignore rule hides the tracked defect; the defect is force-added after `add -A`.
FORCE_ADD: dict[str, str] = {
    "doc-03-tracked-artefacts": "artefacts/notes.md",
    "sec-01-tracked-env": ".env",
    "sec-01-excluded-env": "vendor-samples/.env",
    "sec-01-tracked-ignored-env": "config/prod.env",
    "sec-03-tracked-ignored-key": "server.key",
    "con-03-artefacts-not-ignored": "artefacts/notes.md",
    "exec-05-committed-dist": "build/x.class",
}

#: Fixtures whose verdict depends on machine-local state; run with an isolated HOME and store.
NEEDS_ISOLATED_ENV = frozenset({"idx-01-no-mcp-config", "idx-02-no-index"})

#: Fixtures that are not part of the check matrix and are exercised by their own structural test.
#: Currently empty: git cannot store an empty directory, so the empty-repository case is built at
#: runtime by ``test_empty_directory_reports_nothing_and_does_not_crash``. Add a name here only
#: alongside a dedicated test.
NOT_IN_MATRIX: dict[str, str] = {}

#: Positive fixtures whose union must cover every scoreable check. ``tst-03``/``tst-05`` are not
#: "ok" fixtures but are the only checked-in fixtures where TST-03/TST-04 pass, so they complete
#: the census rather than pretend the check is verified elsewhere.
GOVERNED_FIXTURES = (
    "cmd-ok-npm",
    "cmd-ok-make",
    "cmd-ok-make-prereqs",
    "cmd-ok-make-alias",
    "tool-ok-node",
    "ci-ok-gh",
    "base-ok",
    "doc-nav-ok",
    "sec-01-ok",
    "exec-ok",
    "governed-minimal",
    "agt-05-ok",
    "con-02-protected",
    "tst-03-skip-markers",
    "tst-05-no-coverage",
)

#: Scoreable checks that cannot PASS without executed Tier-C probes or machine-local state.
#: IDX-* assert the operator's harness and index store; TST-02 runs the suite to learn its status.
#: They are covered by their own tests (packs/idx/test_idx_pack.py, the positive fixture) and are never
#: faked as passes here.
PROBE_OR_ENVIRONMENT_SCOPED = frozenset(
    {
        "IDX-01",
        "IDX-02",
        "IDX-03",
        "TST-02",
    }
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def prepare(name: str) -> Path:
    """Copy a fixture into a temp dir and apply its declared git/env preparation."""
    fixture = support.fixture(name)
    if name not in NEEDS_GIT:
        return fixture
    tmp = tempfile.mkdtemp()
    target = Path(tmp) / name
    shutil.copytree(fixture, target)
    assert _git(target, "init").returncode == 0
    assert _git(target, "add", "-A").returncode == 0
    forced = FORCE_ADD.get(name)
    if forced:
        assert _git(target, "add", "-f", forced).returncode == 0
    return target


def run(name: str) -> dict:
    target = prepare(name)
    env = None
    if name in NEEDS_ISOLATED_ENV:
        home = tempfile.mkdtemp()
        env = {"HOME": home, "AUDIT_INDEX_STORE": str(Path(home) / "absent-store")}
    return support.run_audit(target, env=env)


class FixtureMatrixTests(unittest.TestCase):
    def test_every_fixture_is_accounted_for(self):
        actual = {p.name for p in FIXTURES_DIR.iterdir() if p.is_dir()}
        declared = set(MATRIX) | set(NOT_IN_MATRIX)
        self.assertEqual(actual - declared, set(), "fixture directories with no explicit matrix row")
        self.assertEqual(declared - actual, set(), "matrix rows naming a fixture that does not exist")

    def test_no_fixture_has_a_row_in_two_family_tables(self):
        names = [name for table in FAMILY_TABLES for name in table]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        self.assertEqual(duplicated, [], "fixture rows in more than one family table")
        self.assertEqual(len(names), len(MATRIX))

    def test_each_fixture_reports_its_documented_verdict_and_names_every_finding_once(self):
        for name in sorted(MATRIX):
            if not MATRIX[name]:
                continue
            with self.subTest(fixture=name):
                report = run(name)
                verdicts = support.verdicts(report)
                for check, expected in MATRIX[name].items():
                    self.assertEqual(verdicts.get(check), expected, f"{name}: {check} expected {expected}")
                # A finding's id is its check and its path; the baseline ratchet compares ids, so two findings
                # with one id would be merged into one.
                ids = [finding["id"] for finding in report["findings"]]
                duplicated = sorted({i for i in ids if ids.count(i) > 1})
                self.assertEqual(duplicated, [], f"{name}: finding ids that more than one finding has")

    def test_empty_directory_reports_nothing_and_does_not_crash(self):
        # A completed scan of an empty directory exits 0 (it reports, it does not gate) and emits a
        # verdict for every catalogued check without crashing. The blocker checks that a repository
        # must satisfy by *presence* fail; the checks that could only be satisfied by a repository
        # that does not exist (single-root coverage, no competitors) pass vacuously — that is the
        # documented behaviour, not a pass by omission (Scan Engine §9; AGENTS.md §10.4).
        # Built at runtime: git cannot store an empty directory, so a checked-in fixture would not
        # survive a clean clone.
        with tempfile.TemporaryDirectory() as tmp:
            report = support.run_audit(Path(tmp))
        verdicts = support.verdicts(report)
        self.assertEqual(set(verdicts), {spec.id for spec in REGISTRY}, "the empty scan dropped or added checks")
        self.assertTrue(
            all(v in {"PASS", "PARTIAL", "FAIL", "UNKNOWN"} for v in verdicts.values()),
            "the empty scan produced a non-verdict",
        )
        self.assertEqual(verdicts["AGT-01"], "FAIL", "an empty repository has no instruction file")
        blocker_fails = {c["id"] for c in report["checks"] if c["verdict"] == "FAIL" and c["severity"] == "BLOCKER"}
        self.assertTrue(blocker_fails, "an empty repository satisfies no blocker")

    def test_governed_fixtures_pass_every_scoreable_check(self):
        passed: set[str] = set()
        for name in GOVERNED_FIXTURES:
            with self.subTest(fixture=name):
                report = run(name)
                passed |= {
                    cid
                    for cid, verdict in support.verdicts(report).items()
                    if verdict == "PASS" and cid not in PROBE_OR_ENVIRONMENT_SCOPED
                }

        required = {spec.id for spec in scoreable()} - PROBE_OR_ENVIRONMENT_SCOPED
        missing = sorted(required - passed)
        self.assertEqual(missing, [], f"no governed fixture passes these scoreable checks: {missing}")


class DeterminismOverFixtureTests(unittest.TestCase):
    def test_a_multi_finding_fixture_is_byte_stable_across_runs(self):
        name = "hyg-minimal"
        first = run(name)
        second = run(name)
        self.assertGreaterEqual(len(first["findings"]), 2, "pick a fixture with more than one finding")
        for report in (first, second):
            report["provenance"].pop("scanned_at", None)
        self.assertEqual(first, second, f"{name}: the report is not deterministic")


if __name__ == "__main__":
    unittest.main()
