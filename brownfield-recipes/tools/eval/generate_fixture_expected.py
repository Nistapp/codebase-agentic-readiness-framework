# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Generate one eval-expected file per engine fixture (S4.2.1, DP §11, review R-07).

    generate_fixture_expected.py [--check]

For every fixture named in the engine's own ``tests/test_fixture_matrix.py`` (``MATRIX``), this:

1. copies the fixture into a throwaway directory and turns it into a one-commit git repository, with a
   fixed author/committer identity and date so the commit (and therefore ``repo_sha``) is reproducible;
2. runs the real engine on it (``tools/engine.py``'s launcher) and imports the result into a draft
   (``tools/report.py init`` + ``import-engine``), exactly as a headless recipe run would;
3. asserts the draft's verdict for every check the matrix names for that fixture agrees with the matrix
   (the "engine baseline") — a disagreement is a defect in this generator or in git-ifying a fixture that was
   not built to be one, and stops the run rather than writing a wrong ground truth;
4. writes ``schema/examples/eval-expected/fixtures/<fixture>.json``, matching
   ``schema/eval-expected.schema.json``.

A fixture that needs an isolated ``HOME`` (``NEEDS_ISOLATED_ENV``) or a forced-tracked path despite an ignore
rule (``FORCE_ADD``) is prepared the same way ``test_fixture_matrix.py`` prepares it for its own run.

``--check`` compares the already-written files against a fresh generation without rewriting them, and exits
1 on any difference. It is not run by ``make check`` or ``make test`` — regenerating means running the
engine 69 times — so ``tools/tests/test_eval_expected_fixtures.py`` instead loads the committed files and
checks them against the matrix directly, with no engine run. Standard library only.
"""

from __future__ import annotations

import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common
import engine as launcher
import report as rb

RECIPES = Path(__file__).resolve().parent.parent.parent
OUT_DIR = RECIPES / "schema" / "examples" / "eval-expected" / "fixtures"

#: Fixed so the commit — and therefore repo_sha — is the same on every run of this generator.
GIT_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "agentic-readiness-eval",
    "GIT_AUTHOR_EMAIL": "eval@agentic-readiness.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_NAME": "agentic-readiness-eval",
    "GIT_COMMITTER_EMAIL": "eval@agentic-readiness.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}
COMMIT_MESSAGE = "fixture snapshot for eval ground truth"


def engine_matrix() -> ModuleType:
    """The engine's own `test_fixture_matrix` module (`MATRIX`, `FORCE_ADD`, `NEEDS_ISOLATED_ENV`)."""
    launcher.load_engine()
    tests_dir = str(launcher.ENGINE_DIR / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    return importlib.import_module("test_fixture_matrix")


def _git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args], text=True, capture_output=True, env={**os.environ, **(env or {})}
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr}")
    return proc


def materialise(fixture_dir: Path, name: str, dest_root: Path, force_add: str | None) -> Path:
    """Copy `fixture_dir` to `dest_root/name` and commit it, with a fixed identity and date."""
    target = dest_root / name
    shutil.copytree(fixture_dir, target)
    _git("init", "--quiet", cwd=target)
    _git("add", "-A", cwd=target)
    if force_add:
        _git("add", "-f", force_add, cwd=target)
    _git("commit", "--quiet", "--no-gpg-sign", "-m", COMMIT_MESSAGE, cwd=target, env=GIT_COMMIT_ENV)
    return target


def head_sha(target: Path) -> str:
    sha: str = _git("rev-parse", "HEAD", cwd=target).stdout.strip()
    return sha


def run_engine(target: Path, name: str, out_dir: Path, env: dict[str, str] | None = None) -> Path:
    out, err = io.StringIO(), io.StringIO()
    previous = {key: os.environ.get(key) for key in (env or {})}
    os.environ.update(env or {})
    try:
        code = _common.run_tool(
            launcher.INFO,
            launcher.handler,
            [str(target), "--out-dir", str(out_dir), "--repo-label", name],
            stdout=out,
            stderr=err,
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if code != 0:
        raise RuntimeError(f"the engine failed on {name}: {err.getvalue()}")
    return Path(json.loads(out.getvalue())["data"]["report"])


def make_draft(target: Path, name: str, engine_report: Path, out_dir: Path) -> dict[str, Any]:
    intake = out_dir / f"audit-intake.{name}.json"
    intake.write_text(
        json.dumps(
            {
                "intake_version": "0.1",
                "target_path": str(target),
                "repo_label": name,
                "harness": "none",
                "model": "none",
                "provider_exposure_acknowledged": True,
                "index": {"kind": "none"},
                "confirmation_policy": "interactive",
                "output_dir": str(out_dir),
            }
        ),
        encoding="utf-8",
    )
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(rb.INFO, rb.handler, ["init", str(intake)], stdout=out, stderr=err)
    if code != 0:
        raise RuntimeError(f"report init failed on {name}: {err.getvalue()}")
    draft_path = Path(json.loads(out.getvalue())["data"]["draft"])
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(
        rb.INFO, rb.handler, ["import-engine", str(draft_path), str(engine_report)], stdout=out, stderr=err
    )
    if code != 0:
        raise RuntimeError(f"import-engine failed on {name}: {err.getvalue()}")
    draft: dict[str, Any] = json.loads(draft_path.read_text(encoding="utf-8"))
    return draft


def build_expected(name: str, row: dict[str, str], draft: dict[str, Any], sha: str) -> dict[str, Any]:
    verdicts = {c["id"]: c["verdict"] for c in draft["checks"]}
    mismatches = {cid: (expected, verdicts.get(cid)) for cid, expected in row.items() if verdicts.get(cid) != expected}
    if mismatches:
        raise RuntimeError(f"{name}: engine verdict disagrees with the matrix: {mismatches}")
    return {
        "expected_version": "0.1",
        "repo_label": name,
        "repo_sha": sha,
        "notes": (
            f"Generated by tools/eval/generate_fixture_expected.py from test_fixture_matrix.py's MATRIX row "
            f"for '{name}' (brownfield-recipes/deterministic-audit/tests/fixtures/{name}), a one-defect "
            "engine fixture committed into a throwaway git repository with a fixed commit so repo_sha is "
            "reproducible."
        ),
        "checks": [{"id": cid, "acceptable_verdicts": [row[cid]]} for cid in sorted(row)],
    }


def generate_one(matrix: ModuleType, name: str, row: dict[str, str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        dest_root = Path(tmp)
        target = materialise(matrix.support.fixture(name), name, dest_root, matrix.FORCE_ADD.get(name))
        sha = head_sha(target)
        env = {}
        if name in matrix.NEEDS_ISOLATED_ENV:
            home = dest_root / "home"
            home.mkdir()
            env = {"HOME": str(home), "AUDIT_INDEX_STORE": str(home / "absent-store")}
        out_dir = dest_root / "out"
        out_dir.mkdir()
        engine_report = run_engine(target, name, out_dir, env)
        draft = make_draft(target, name, engine_report, out_dir)
        return build_expected(name, row, draft, sha)


def main(argv: list[str] | None = None) -> int:
    check_only = (argv if argv is not None else sys.argv[1:]) == ["--check"]
    matrix = engine_matrix()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatched: list[str] = []
    for name in sorted(matrix.MATRIX):
        row = matrix.MATRIX[name]
        if not row:
            continue
        expected = generate_one(matrix, name, row)
        path = OUT_DIR / f"{name}.json"
        text = json.dumps(expected, indent=2, ensure_ascii=False) + "\n"
        if check_only:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                mismatched.append(name)
            continue
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    if check_only and mismatched:
        print(f"out of date: {', '.join(mismatched)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
