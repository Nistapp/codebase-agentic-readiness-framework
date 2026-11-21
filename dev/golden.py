# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Prove that a structural change altered no output: record a digest of every shipped output, then compare.

    golden.py record --out DIR
    golden.py compare DIR

``record`` writes ``DIR/golden.json``: one JSON object with sorted keys, holding a SHA-256 for each of

* ``engine_reports``: the engine's JSON report of every folder under ``audit/engine/tests/fixtures/``;
* ``list_checks``: the output of ``--list-checks``, as text and as JSON;
* ``tools_describe``: the ``--describe`` output of each tool in ``audit/tools/`` and ``implement/tools/``;
* ``catalogue``: ``audit/catalogue.json``;
* ``skill_zips``: the two skill archives that ``dev/build_skills.py --archive DIR --tag golden`` writes;

and the ruleset hash, the ruleset revision and the engine version as plain values (``ruleset``).

``compare`` records again, in memory, and prints each entry that differs from ``DIR/golden.json``: changed, missing
now or new now. It exits 2 on a difference and 1 on a usage error (a missing or unreadable digest, a bad argument).

What makes the digest the same on every run and every machine:

* A report's ``provenance`` loses ``scanned_at`` (the clock), ``git_sha``, ``git_branch``, ``git_dirty`` and
  ``framework_revision`` (they name the checkout, so they change with every commit), and its ``target`` is fixed to
  ``.`` with ``--target-label``. The rest of the report is hashed as it is, with sorted keys.
* Each fixture runs with ``--no-user-config`` and with an empty ``HOME`` and an absent index store, so the
  machine-local checks (the IDX pack) read no state of the host.
* Every fixture is copied into a temporary git repository by the engine's own ``test_fixture_matrix.prepare``,
  which is reused, not copied. So the digest does not depend on whether the checkout is a git work tree. Git's
  global ignore file of the host still applies to the copy.
* The skill archives are byte-reproducible (``build_skills.write_archive``) and are built with the fixed tag
  ``golden``.

Not covered: the Markdown renderings of a report, the tools' outputs other than ``--describe`` (their own tests
cover them) and any file outside the list above. The tool is dev-only: nothing in ``audit/`` or ``implement/`` imports
it. Standard library only.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import os
import runpy
import shutil
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
AUDIT_TOOLS = REPO / "audit" / "tools"
ENGINE_TESTS = REPO / "audit" / "engine" / "tests"
FIXTURES = ENGINE_TESTS / "fixtures"
CATALOGUE = REPO / "audit" / "catalogue.json"
TOOL_FOLDERS = ("audit/tools", "implement/tools")
DIGEST_NAME = "golden.json"
DIGEST_VERSION = 1
ARCHIVE_TAG = "golden"
#: A fixed path that does not exist. A report names it, so it must not change from run to run.
ABSENT_STORE = "/golden-absent-index-store"
#: The provenance keys that name the checkout or the clock. A report loses them before it is hashed.
STRIPPED_PROVENANCE = ("framework_revision", "git_branch", "git_dirty", "git_sha", "scanned_at")

for _path in (AUDIT_TOOLS, REPO / "dev"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import _common  # noqa: E402
import build_skills  # noqa: E402
import engine as launcher  # noqa: E402

INFO = _common.ToolInfo(
    name="golden",
    summary="Record a digest of every shipped output, then compare a later run against it to prove byte identity.",
    synopsis=("golden.py record --out DIR", "golden.py compare DIR"),
    writes="record writes DIR/golden.json and refuses to replace it; compare writes nothing.",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    """The bytes that are hashed for a JSON value: sorted keys, fixed separators, UTF-8."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def strip_report(report: dict[str, Any]) -> dict[str, Any]:
    """The report without the keys that name the clock or the checkout."""
    provenance = {k: v for k, v in report["provenance"].items() if k not in STRIPPED_PROVENANCE}
    return {**report, "provenance": provenance}


@contextlib.contextmanager
def isolated_env(home: Path) -> Iterator[None]:
    """An empty ``HOME`` and an absent index store, so a machine-local check reads nothing of the host."""
    changes = {"HOME": str(home), "AUDIT_INDEX_STORE": ABSENT_STORE}
    saved = {key: os.environ.get(key) for key in changes}
    os.environ.update(changes)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_script(path: Path, argv: Sequence[str]) -> tuple[int, str]:
    """Run a tool script in this process as ``__main__``. Returns its exit code and its stdout."""
    saved_argv, saved_path = sys.argv, list(sys.path)
    out = io.StringIO()
    code: object = 0
    sys.argv = [str(path), *argv]
    sys.path.insert(0, str(path.parent))  # as `python3 path` does
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                runpy.run_path(str(path), run_name="__main__")
            except SystemExit as exc:
                code = 0 if exc.code is None else exc.code
    finally:
        sys.argv, sys.path[:] = saved_argv, saved_path
    return (code if isinstance(code, int) else 1), out.getvalue()


def engine_matrix() -> Any:
    """The engine's ``test_fixture_matrix`` module, whose ``prepare`` builds a fixture's temporary git repository."""
    launcher.load_engine()
    if str(ENGINE_TESTS) not in sys.path:
        sys.path.insert(0, str(ENGINE_TESTS))
    return importlib.import_module("test_fixture_matrix")


def fixture_names(fixtures: Path = FIXTURES) -> list[str]:
    return sorted(p.name for p in fixtures.iterdir() if p.is_dir())


def prepare_in_git(matrix: Any, name: str) -> Path:
    """A copy of the fixture in a temporary git repository, through the matrix's own ``prepare``.

    Every fixture goes through it, not only the ones the matrix lists in ``NEEDS_GIT``. Otherwise the engine would
    find the git repository that holds the checkout, and a copy of the tree without ``.git`` would give other
    reports than the checkout.
    """
    listed = matrix.NEEDS_GIT
    matrix.NEEDS_GIT = listed | {name}
    try:
        target: Path = matrix.prepare(name)
    finally:
        matrix.NEEDS_GIT = listed
    return target


def fixture_report(matrix: Any, name: str, scratch: Path) -> dict[str, Any]:
    """The stripped engine report of one fixture."""
    out = scratch / f"{name}.json"
    target = prepare_in_git(matrix, name)
    try:
        argv = [str(target), "--format", "json", "--out", str(out), "--no-user-config", "--target-label", "."]
        code, _stdout, stderr = launcher.run_engine(argv)
        if code != 0:
            raise _common.ToolError(f"the engine failed on fixture {name} (exit {code}): {stderr.strip()}")
        report: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(target.parent, ignore_errors=True)
    return strip_report(report)


def engine_reports(scratch: Path) -> dict[str, str]:
    matrix = engine_matrix()
    home = scratch / "home"
    home.mkdir()
    reports = scratch / "reports"
    reports.mkdir()
    with isolated_env(home):
        return {name: sha256(canonical(fixture_report(matrix, name, reports))) for name in fixture_names()}


def list_checks() -> tuple[dict[str, str], dict[str, str]]:
    """The hashes of ``--list-checks`` in both formats, and the ruleset the JSON form names."""
    hashes: dict[str, str] = {}
    ruleset: dict[str, str] = {}
    for label, argv in (("text", ["--list-checks"]), ("json", ["--list-checks", "--format", "json"])):
        code, stdout, stderr = launcher.run_engine(argv)
        if code != 0:
            raise _common.ToolError(f"the engine's --list-checks failed (exit {code}): {stderr.strip()}")
        hashes[label] = sha256(stdout.encode("utf-8"))
        if label == "json":
            engine = json.loads(stdout)["engine"]
            ruleset = {
                "engine_version": engine["version"],
                "hash": engine["ruleset_hash"],
                "revision": engine["ruleset_revision"],
            }
    return hashes, ruleset


def tool_scripts(repo: Path = REPO) -> list[Path]:
    found: list[Path] = []
    for folder in TOOL_FOLDERS:
        found += [p for p in sorted((repo / folder).glob("*.py")) if not p.name.startswith("_")]
    return found


def tools_describe(repo: Path = REPO) -> dict[str, str]:
    result: dict[str, str] = {}
    for script in tool_scripts(repo):
        code, stdout = run_script(script, ["--describe"])
        result[script.relative_to(repo).as_posix()] = sha256(f"{code}\n{stdout}".encode())
    return result


def skill_zips(scratch: Path) -> dict[str, str]:
    archives = scratch / "archives"
    build_skills.handler(["--out-dir", str(scratch / "skills"), "--archive", str(archives), "--tag", ARCHIVE_TAG])
    return {path.name: sha256(path.read_bytes()) for path in sorted(archives.glob("*.zip"))}


def record_digest() -> dict[str, Any]:
    """The whole digest of the checkout this process runs in."""
    with tempfile.TemporaryDirectory(prefix="golden-") as raw:
        scratch = Path(raw)
        reports = engine_reports(scratch)
        checks, ruleset = list_checks()
        return {
            "catalogue": sha256(CATALOGUE.read_bytes()),
            "digest_version": DIGEST_VERSION,
            "engine_reports": reports,
            "list_checks": checks,
            "ruleset": ruleset,
            "skill_zips": skill_zips(scratch),
            "tools_describe": tools_describe(),
        }


def flatten(value: object, prefix: str = "") -> dict[str, object]:
    """``{"a": {"b": 1}}`` as ``{"a/b": 1}``, so a difference is named by one path."""
    if not isinstance(value, Mapping):
        return {prefix: value}
    flat: dict[str, object] = {}
    for key, inner in value.items():
        flat.update(flatten(inner, f"{prefix}/{key}" if prefix else str(key)))
    return flat


def differences(recorded: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """One line for each entry that changed, is gone or is new. Empty when the two digests are the same."""
    old, new = flatten(recorded), flatten(current)
    lines: list[str] = []
    for key in sorted(old.keys() | new.keys()):
        if key not in new:
            lines.append(f"missing now: {key}")
        elif key not in old:
            lines.append(f"new now: {key}")
        elif old[key] != new[key]:
            lines.append(f"changed: {key}: {_short(old[key])} -> {_short(new[key])}")
    return lines


def _short(value: object) -> str:
    text = str(value)
    return text[:12] if len(text) == 64 else text


def read_digest(directory: Path) -> dict[str, Any]:
    path = directory / DIGEST_NAME
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _common.UsageError(f"cannot read the digest {path}: {exc}") from exc
    if not isinstance(loaded, dict) or loaded.get("digest_version") != DIGEST_VERSION:
        raise _common.UsageError(f"{path} is not a digest of version {DIGEST_VERSION}")
    return loaded


def write_digest(directory: Path, digest: Mapping[str, Any]) -> Path:
    path = directory / DIGEST_NAME
    if path.exists():
        raise _common.UsageError(f"{path} exists; golden never replaces a file")
    directory.mkdir(parents=True, exist_ok=True)
    return _common.create_file(path, json.dumps(digest, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="golden.py", description=INFO.summary)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_common.ToolParser)
    record = commands.add_parser("record", help="write DIR/golden.json")
    record.add_argument("--out", required=True, metavar="DIR", help="the folder that receives golden.json")
    compare = commands.add_parser("compare", help="compare this checkout with DIR/golden.json")
    compare.add_argument("directory", metavar="DIR", help="the folder that holds golden.json")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    if args.command == "record":
        digest = record_digest()
        path = write_digest(Path(args.out).expanduser().resolve(), digest)
        entries = len(flatten(digest))
        return _common.Result(
            data={"digest": str(path), "entries": entries}, summary=f"golden: recorded {entries} entries"
        )
    recorded = read_digest(Path(args.directory).expanduser().resolve())
    found = differences(recorded, record_digest())
    if found:
        raise _common.ValidationFailed(f"{len(found)} entries differ from the recording", errors=found)
    entries = len(flatten(recorded))
    return _common.Result(data={"entries": entries, "differences": []}, summary=f"golden: all {entries} entries match")


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
