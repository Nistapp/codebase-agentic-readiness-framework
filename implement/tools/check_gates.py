# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check a theme branch's diff for a weakened gate (boundary B-03) and an unapproved dependency (boundary B-11).

    check_gates.py <worktree> --base <sha> [--theme <ref>] [--state <state.json>]

The tool reads the theme worktree with read-only git: ``git diff --name-status -M <base> <theme>`` and the two sides
of each changed file (``git show``). It never writes, in the worktree or anywhere else. ``--theme`` defaults to
``HEAD``, so uncommitted changes are not checked; a dirty worktree gets a warning.

Findings for B-03, "the run never weakens a gate":

- ``test-deleted``: a test file deleted, or renamed to a path that is not a test file. A test file is one the engine's
  ``TST-03`` census counts: the scan classifies it as a test and its suffix is a test source suffix, or it matches a
  framework test glob (``*_test.go``, ``tests/*.rs``).
- ``skip-added``: a test file holds more skip, ignore or expected-failure markers than at the base. The markers are
  the engine's own ``TST-03`` table (``audit.rules.checks.tst``), loaded through ``engine.py``, never copied here.
- ``suppression-added``: a source file holds more inline suppressions (``# noqa``, ``# type: ignore``,
  ``eslint-disable``, ``@ts-ignore``, ``//nolint``, ``#[allow(``, ``@SuppressWarnings`` and the like) than at the base.
- ``floor-lowered`` and ``floor-removed``: a coverage floor (``fail_under``, ``--cov-fail-under``, a
  ``coverageThreshold`` or ``thresholds`` number) is lower than at the base, or gone from every changed file.
- ``limit-raised``: an ``--max-warnings`` number, or a number in a ``*baseline*.json`` or ``*ratchet*.json`` file,
  is higher than at the base.
- ``gate-removed``: a gate command (``pytest``, ``mypy``, ``eslint``...) that some gate file ran at the base is in no
  gate file at the theme; or a gate target of a Makefile, or a gate script of a ``package.json``, is gone.
- ``gate-loosened``: more lines of a gate file run a gate command and then ``|| true``, ``|| :`` or ``|| exit 0``.

Findings for B-11, "the run installs no dependency the owner did not approve":

- ``dependency-added``: a dependency name declared at the theme and not at the base, in ``package.json``,
  ``pyproject.toml``, ``requirements*.txt``, ``Pipfile``, ``go.mod``, ``Cargo.toml``, ``Gemfile`` or
  ``composer.json``, that the owner's ``dependencies.approved`` preference does not list.
- ``lockfile-changed``: a lockfile changed, and its ecosystem's manifests added no approved dependency.

The owner's choices come from the implement state (``--state``, written by ``progress.py``). Two preference keys are
read. ``dependencies.approved`` lists the dependency names the owner approved. ``gates.accepted`` lists path globs
(``fnmatch``, where ``*`` crosses ``/``) whose B-03 findings the owner chose; such a finding is listed under
``data.accepted`` and does not stop the theme. Names and globs are separated by commas or white space.

With no finding left, ``data.status`` is ``clean`` and the tool exits 0. With one or more, it exits 2 and
``data.errors`` has one line per finding: the theme stops and the agent asks the owner. The tool does not see a
weakened assertion inside a kept test, a rule turned off in a config file, a format it does not parse, a gate
command removed from one file but still run in another, a version bump of a declared dependency, or a global or
one-off install (``npm -g``, ``npx``, ``uvx``) that leaves no trace in the branch.
"""

from __future__ import annotations

import fnmatch
import importlib
import json
import os
import posixpath
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import _audit_tools_path  # noqa: F401  (puts audit/tools on sys.path in a checkout)
import _common
import engine
import progress
import validate_report

INFO = _common.ToolInfo(
    name="check_gates",
    summary="Check a theme branch's diff for a weakened gate (B-03) or a dependency the owner did not approve (B-11).",
    synopsis=("check_gates.py WORKTREE --base SHA [--theme REF] [--state FILE]",),
    writes="nothing",
)

#: The preference that lists the dependency names the owner approved (B-11).
APPROVED_KEY = "dependencies.approved"
#: The preference that lists the path globs whose B-03 findings the owner chose.
ACCEPTED_KEY = "gates.accepted"
#: A file larger than this is not read; a warning names it.
MAX_FILE_BYTES = 2 * 1024 * 1024

GATES = "B-03"
INSTALLS = "B-11"

# --- What the tool looks for ------------------------------------------------------------------------------

#: Inline suppressions in a source file: a rule turned off on one line or one file.
SUPPRESSION = re.compile(
    r"#\s*noqa\b|#\s*type:\s*ignore\b|#\s*pragma:\s*no\s*cover\b|#\s*pylint:\s*disable\b|#\s*nosec\b"
    r"|eslint-disable|@ts-(?:ignore|nocheck|expect-error)\b|\b(?:istanbul|c8)\s+ignore\b|biome-ignore"
    r"|//\s*nolint\b|#!?\[allow\(|@SuppressWarnings\b|rubocop:disable"
)
#: The suffixes of the source files whose suppressions are counted.
SOURCE_SUFFIXES = (
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".go", ".rs", ".java", ".kt",
    ".kts", ".rb", ".php", ".cs", ".swift", ".scala",
)  # fmt: skip

#: A coverage floor with its number; it may only go up.
FLOOR = re.compile(
    r"(?i)\b(fail[_-]under|cov[_-]fail[_-]under|min[_-]?coverage|coverage[_-](?:floor|threshold|minimum))\b"
    r"[\"']?\s*[=:]?\s*[\"']?(\d+(?:\.\d+)?)"
)
#: A coverage threshold of a JavaScript runner (`coverageThreshold`, `coverage.thresholds`, nyc, c8).
THRESHOLD = re.compile(r"\b(branches|functions|lines|statements)[\"']?\s*[:=]\s*(\d+(?:\.\d+)?)")
#: The files a JavaScript coverage threshold is read from.
THRESHOLD_FILES = (
    "package.json", "jest.config.*", "vitest.config.*", "vite.config.*", "karma.conf.*", ".nycrc*", ".c8rc*",
)  # fmt: skip
#: A counted limit with its number; it may only go down.
LIMIT = re.compile(r"(--max-warnings|\bmax[_-]warnings)[\"']?\s*[=:\s]\s*(\d+)\b")
#: A ratchet or baseline file whose numbers may only go down.
COUNT_FILE = re.compile(r"(?i)(?:baseline|ratchet)[^/]*\.json$")

#: The gate commands looked for in gate files, by the name a finding gives them.
GATE_COMMANDS: Mapping[str, re.Pattern[str]] = {
    name: re.compile(pattern)
    for name, pattern in (
        ("pytest", r"\bpytest\b"),
        ("unittest", r"-m\s+unittest\b"),
        ("jest", r"\bjest\b"),
        ("vitest", r"\bvitest\b"),
        ("mocha", r"\bmocha\b"),
        ("go test", r"\bgo\s+test\b"),
        ("go vet", r"\bgo\s+vet\b"),
        ("cargo test", r"\bcargo\s+test\b"),
        ("cargo clippy", r"\bcargo\s+clippy\b"),
        ("ruff", r"\bruff\b"),
        ("mypy", r"\bmypy\b"),
        ("pyright", r"\bpyright\b"),
        ("flake8", r"\bflake8\b"),
        ("pylint", r"\bpylint\b"),
        ("black", r"\bblack\b"),
        ("eslint", r"\beslint\b"),
        ("tsc", r"\btsc\b"),
        ("prettier", r"\bprettier\b"),
        ("biome", r"\bbiome\b"),
        ("golangci-lint", r"\bgolangci-lint\b"),
        ("rubocop", r"\brubocop\b"),
        ("rspec", r"\brspec\b"),
        ("phpunit", r"\bphpunit\b"),
        ("phpstan", r"\bphpstan\b"),
        ("shellcheck", r"\bshellcheck\b"),
        ("markdownlint", r"\bmarkdownlint(?:-cli2)?\b"),
        ("coverage", r"\bcoverage\s+(?:run|report|xml|html|combine)\b|--cov\b"),
        ("detect-secrets", r"\bdetect-secrets\b"),
        ("gitleaks", r"\bgitleaks\b"),
        ("osv-scanner", r"\bosv-scanner\b"),
        ("npm audit", r"\bnpm\s+audit\b"),
    )
}
#: A gate command whose failure is thrown away on the same line.
SWALLOWED = re.compile(r"\|\|\s*(?:true\b|:|exit\s+0\b)")
#: The base names of the files that run gates.
GATE_FILE_NAMES = frozenset(
    {
        "Makefile", "makefile", "GNUmakefile", "justfile", "Justfile", "Taskfile.yml", "Taskfile.yaml",
        "package.json", "tox.ini", "noxfile.py", ".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml",
        ".lefthook.yml", ".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", "bitbucket-pipelines.yml",
    }
)  # fmt: skip
#: The folders whose files run gates (hooks and CI).
GATE_FOLDERS = (".github/workflows/", ".husky/", ".githooks/", ".circleci/")
#: The make targets and package scripts that are gates.
GATE_TARGETS = frozenset(
    {
        "check", "test", "tests", "lint", "typecheck", "type-check", "types", "format-check", "format:check",
        "fmt-check", "coverage", "security", "ci", "verify", "docs-lint", "test:coverage", "test:unit",
    }
)  # fmt: skip
MAKE_TARGET = re.compile(r"(?m)^([A-Za-z0-9_.:/-]+(?:[ \t]+[A-Za-z0-9_.:/-]+)*)[ \t]*:(?![=:])")

#: The lockfiles, by ecosystem.
LOCKFILES: Mapping[str, str] = {
    "package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "yarn.lock": "npm", "pnpm-lock.yaml": "npm",
    "bun.lock": "npm", "bun.lockb": "npm", "uv.lock": "python", "poetry.lock": "python", "pdm.lock": "python",
    "Pipfile.lock": "python", "go.sum": "go", "Cargo.lock": "rust", "Gemfile.lock": "ruby", "composer.lock": "php",
}  # fmt: skip
REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
GEM = re.compile(r"(?m)^\s*gem\s+[\"']([^\"']+)[\"']")
GO_REQUIRE_LINE = re.compile(r"(?m)^\s*require\s+([^\s(]+)\s+\S")
GO_REQUIRE_BLOCK = re.compile(r"(?ms)^\s*require\s*\((.*?)^\s*\)")
NAME_SEPARATOR = re.compile(r"[,\s]+")


@dataclass(frozen=True)
class Finding:
    """One break: its boundary, its kind, the path it is about and what was seen."""

    boundary: str
    kind: str
    path: str
    detail: str

    def line(self) -> str:
        return f"{self.boundary} {self.kind}: {self.path}: {self.detail}"

    def to_json(self) -> dict[str, str]:
        return {"boundary": self.boundary, "kind": self.kind, "path": self.path, "detail": self.detail}


@dataclass(frozen=True)
class Change:
    """One changed path: git's status letter, the path at the base (None when added) and at the theme (None when
    deleted)."""

    status: str
    old: str | None
    new: str | None


# --- Read-only git ----------------------------------------------------------------------------------------


def _git(worktree: Path, args: Sequence[str]) -> bytes | None:
    """A read-only git command's standard output as bytes, or None when it fails or cannot run."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    try:
        done = subprocess.run(
            ["git", "-C", str(worktree), *args],
            capture_output=True,
            timeout=validate_report.GIT_TIMEOUT_S,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def commit(worktree: Path, name: str, flag: str) -> str:
    out = _git(worktree, ["rev-parse", "--verify", "--quiet", name + "^{commit}"])
    if out is None or not out.strip():
        raise _common.UsageError(f"{flag} {name} is not a commit in {worktree}")
    return out.decode().strip()


def changes(worktree: Path, base: str, theme: str) -> list[Change]:
    """The paths the theme changed since the base, with renames found (``-M``)."""
    out = _git(worktree, ["diff", "--name-status", "-z", "-M", base, theme, "--"])
    if out is None:
        raise _common.UsageError(f"git could not list the changes from {base} to {theme} in {worktree}")
    fields = out.decode("utf-8", "surrogateescape").split("\0")
    found: list[Change] = []
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index][0]
        if status in "RC":
            found.append(Change(status, fields[index + 1], fields[index + 2]))
            index += 3
            continue
        path = fields[index + 1]
        found.append(Change(status, None if status == "A" else path, None if status == "D" else path))
        index += 2
    return found


def tree(worktree: Path, rev: str) -> list[str]:
    out = _git(worktree, ["ls-tree", "-r", "-z", "--name-only", rev])
    if out is None:
        raise _common.UsageError(f"git could not list the files of {rev} in {worktree}")
    return [name for name in out.decode("utf-8", "surrogateescape").split("\0") if name]


class Reader:
    """The text of a file at a commit, read once; None for a missing, binary or oversized file."""

    def __init__(self, worktree: Path) -> None:
        self.worktree = worktree
        self.cache: dict[tuple[str, str], str | None] = {}
        self.skipped: list[str] = []

    def text(self, rev: str, path: str | None) -> str | None:
        if path is None:
            return None
        key = (rev, path)
        if key not in self.cache:
            self.cache[key] = self._read(rev, path)
        return self.cache[key]

    def _read(self, rev: str, path: str) -> str | None:
        size = _git(self.worktree, ["cat-file", "-s", f"{rev}:{path}"])
        if size is None:
            return None
        if int(size.decode().strip() or 0) > MAX_FILE_BYTES:
            self.skipped.append(path)
            return None
        data = _git(self.worktree, ["cat-file", "blob", f"{rev}:{path}"])
        if data is None or b"\0" in data:
            return None
        return data.decode("utf-8", "replace")


# --- The engine's TST-03 tables ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CensusTables:
    """What the engine's TST-03 census counts: which files are tests, and their markers by language family."""

    classify: Callable[[str], Any]
    test_kind: Any
    suffixes: tuple[str, ...]
    globs: tuple[str, ...]
    families: Mapping[str, str]
    markers: Mapping[str, tuple[str, ...]]

    def is_test(self, path: str) -> bool:
        base = posixpath.basename(path)
        if any(fnmatch.fnmatch(path, glob) or fnmatch.fnmatch(base, glob) for glob in self.globs):
            return True
        return bool(self.classify(path) is self.test_kind and path.lower().endswith(self.suffixes))

    def count(self, path: str, text: str | None) -> int:
        """The markers in a test file. A JavaScript file is counted with each JavaScript runner's table and the
        largest count wins, since the tool does not detect the runner as the engine's stack detection does."""
        if not text:
            return 0
        base = posixpath.basename(path)
        suffix = "." + base.rsplit(".", 1)[1] if "." in base else ""
        family = self.families.get(suffix, "")
        names = (family, "mocha") if family == "javascript" else (family,)
        tables = [self.markers.get(name, ()) for name in names]
        return max(sum(1 for pattern in table for _ in re.finditer(pattern, text)) for table in tables)


@lru_cache(maxsize=1)
def census_tables() -> CensusTables:
    """The engine's own TST-03 tables, loaded through ``engine.py`` as ``check_regressions`` loads the read
    declarations, so they are never copied here."""
    engine.load_engine()
    tst = importlib.import_module("audit.rules.checks.tst")
    scan = importlib.import_module("audit.scan")
    return CensusTables(
        classify=getattr(scan, "_classify"),
        test_kind=scan.Kind.TEST,
        suffixes=tuple(getattr(tst, "_TEST_SOURCE_SUFFIXES")),
        globs=tuple(getattr(tst, "_FRAMEWORK_TEST_GLOBS")),
        families=dict(getattr(tst, "_FAMILY_BY_SUFFIX")),
        markers={family: tuple(patterns) for family, patterns in getattr(tst, "_MARKER_PATTERNS").items()},
    )


# --- B-03: tests, suppressions, floors and limits ----------------------------------------------------------


def census_findings(found: Sequence[Change], reader: Reader, base: str, theme: str) -> list[Finding]:
    tables = census_tables()
    out: list[Finding] = []
    for change in found:
        was_test = change.old is not None and tables.is_test(change.old)
        is_test = change.new is not None and tables.is_test(change.new)
        if was_test and not is_test:
            old = str(change.old)
            detail = "deleted" if change.new is None else f"renamed to {change.new}, which is not a test file"
            out.append(Finding(GATES, "test-deleted", old, detail))
        if is_test:
            new = str(change.new)
            before = tables.count(change.old, reader.text(base, change.old)) if change.old else 0
            after = tables.count(new, reader.text(theme, new))
            if after > before:
                out.append(Finding(GATES, "skip-added", new, f"skip markers {before} -> {after}"))
    return out


def suppression_findings(found: Sequence[Change], reader: Reader, base: str, theme: str) -> list[Finding]:
    out: list[Finding] = []
    for change in found:
        if change.new is None or not change.new.lower().endswith(SOURCE_SUFFIXES):
            continue
        before = len(SUPPRESSION.findall(reader.text(base, change.old) or ""))
        after_text = reader.text(theme, change.new) or ""
        after = len(SUPPRESSION.findall(after_text))
        if after > before:
            sample = next((line.strip() for line in after_text.splitlines() if SUPPRESSION.search(line)), "")
            out.append(
                Finding(
                    GATES, "suppression-added", change.new, f"inline suppressions {before} -> {after}: {sample[:80]}"
                )
            )
    return out


def _numbers(pattern: re.Pattern[str], text: str | None, prefix: str = "") -> dict[str, list[float]]:
    found: dict[str, list[float]] = {}
    for match in pattern.finditer(text or ""):
        key = prefix + match.group(1).lower().replace("_", "-")
        found.setdefault(key, []).append(float(match.group(2)))
    return found


def _is_threshold_file(path: str) -> bool:
    return any(fnmatch.fnmatch(posixpath.basename(path), name) for name in THRESHOLD_FILES)


def _floors(path: str | None, text: str | None) -> dict[str, list[float]]:
    if path is None or path.lower().endswith((".md", ".rst", ".txt")):
        return {}
    found = _numbers(FLOOR, text)
    if _is_threshold_file(path):
        for key, values in _numbers(THRESHOLD, text, "coverage threshold ").items():
            found.setdefault(key, []).extend(values)
    return found


def _json_counts(text: str | None, prefix: str = "") -> dict[str, float]:
    try:
        document = json.loads(text or "")
    except json.JSONDecodeError:
        return {}
    out: dict[str, float] = {}

    def walk(node: Any, at: str) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            out[at or "/"] = float(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{at}/{key}")
        elif isinstance(node, list):
            for position, value in enumerate(node):
                walk(value, f"{at}/{position}")

    walk(document, prefix)
    return out


def number_findings(found: Sequence[Change], reader: Reader, base: str, theme: str) -> list[Finding]:
    """Floors lowered or removed, and limits raised. Floors are pooled over every changed file, so a floor that
    moves from one file to another (``.coveragerc`` into ``pyproject.toml``) is still compared."""
    out: list[Finding] = []
    floors_before: dict[str, tuple[float, str]] = {}
    floors_after: dict[str, tuple[float, str]] = {}
    for change in found:
        for side, rev, path in ((floors_before, base, change.old), (floors_after, theme, change.new)):
            for key, values in _floors(path, reader.text(rev, path)).items():
                if key not in side or min(values) < side[key][0]:
                    side[key] = (min(values), str(path))
        old_limits = _numbers(LIMIT, reader.text(base, change.old))
        for key, values in _numbers(LIMIT, reader.text(theme, change.new)).items():
            if key in old_limits and max(values) > max(old_limits[key]):
                detail = f"{key} {max(old_limits[key]):g} -> {max(values):g}"
                out.append(Finding(GATES, "limit-raised", str(change.new), detail))
        if change.old and change.new and COUNT_FILE.search(change.new):
            old_counts = _json_counts(reader.text(base, change.old))
            for key, value in _json_counts(reader.text(theme, change.new)).items():
                if key in old_counts and value > old_counts[key]:
                    detail = f"{key} {old_counts[key]:g} -> {value:g}"
                    out.append(Finding(GATES, "limit-raised", change.new, detail))
    for key, (value, path) in sorted(floors_before.items()):
        if key not in floors_after:
            out.append(Finding(GATES, "floor-removed", path, f"{key} {value:g} is gone"))
        elif floors_after[key][0] < value:
            after, where = floors_after[key]
            out.append(Finding(GATES, "floor-lowered", where, f"{key} {value:g} -> {after:g}"))
    return out


# --- B-03: gate commands -----------------------------------------------------------------------------------


def is_gate_file(path: str) -> bool:
    base = posixpath.basename(path)
    if "node_modules/" in path or path.startswith("vendor/"):
        return False
    return base in GATE_FILE_NAMES or path.startswith(GATE_FOLDERS) or base.endswith((".mk", ".sh"))


def _gate_text(path: str, text: str | None) -> str:
    """The text of a gate file that runs commands: a ``package.json`` gives its scripts only, not its dependencies."""
    if text is None or posixpath.basename(path) != "package.json":
        return text or ""
    scripts = _package_scripts(text)
    return "\n".join(scripts.values())


def _package_scripts(text: str | None) -> dict[str, str]:
    try:
        document = json.loads(text or "")
    except json.JSONDecodeError:
        return {}
    scripts = document.get("scripts") if isinstance(document, dict) else None
    if not isinstance(scripts, dict):
        return {}
    return {str(key): str(value) for key, value in scripts.items()}


def _targets(path: str, text: str | None) -> set[str]:
    """The gate targets a Makefile-like file or a ``package.json`` defines."""
    base = posixpath.basename(path)
    if base == "package.json":
        names: Iterable[str] = _package_scripts(text)
    elif base in ("Makefile", "makefile", "GNUmakefile", "justfile", "Justfile") or base.endswith(".mk"):
        names = (name for match in MAKE_TARGET.finditer(text or "") for name in match.group(1).split())
    else:
        return set()
    return {name for name in names if name in GATE_TARGETS}


def _swallowed(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if SWALLOWED.search(line) and any(pattern.search(line) for pattern in GATE_COMMANDS.values())
    )


def gate_findings(
    found: Sequence[Change], reader: Reader, base: str, theme: str, files: tuple[list[str], list[str]]
) -> list[Finding]:
    """Gate commands gone from every gate file, gate targets and scripts gone, and failures swallowed."""
    base_files, theme_files = ([path for path in side if is_gate_file(path)] for side in files)
    out: list[Finding] = []

    def commands(rev: str, paths: Sequence[str]) -> dict[str, str]:
        seen: dict[str, str] = {}
        for path in paths:
            text = _gate_text(path, reader.text(rev, path))
            for name, pattern in GATE_COMMANDS.items():
                if name not in seen and pattern.search(text):
                    seen[name] = path
        return seen

    before, after = commands(base, base_files), commands(theme, theme_files)
    for name in sorted(set(before) - set(after)):
        out.append(
            Finding(GATES, "gate-removed", before[name], f"`{name}` ran at the base and runs in no gate file now")
        )
    for change in found:
        old_gate = change.old is not None and is_gate_file(change.old)
        new_gate = change.new is not None and is_gate_file(change.new)
        if old_gate:
            old = str(change.old)
            kept = _targets(change.new, reader.text(theme, change.new)) if change.new else set()
            for name in sorted(_targets(old, reader.text(base, old)) - kept):
                out.append(Finding(GATES, "gate-removed", old, f"the gate target or script `{name}` is gone"))
        if new_gate:
            new = str(change.new)
            was = _swallowed(_gate_text(change.old, reader.text(base, change.old))) if change.old else 0
            now = _swallowed(_gate_text(new, reader.text(theme, new)))
            if now > was:
                out.append(
                    Finding(GATES, "gate-loosened", new, f"gate commands whose failure is ignored {was} -> {now}")
                )
    return out


# --- B-11: declared dependencies ----------------------------------------------------------------------------


def normalize(name: str) -> str:
    """One spelling of a dependency name: lower case, and each run of ``-``, ``_`` and ``.`` as one ``-`` (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def _requirement(spec: str) -> str | None:
    match = REQUIREMENT_NAME.match(spec)
    return match.group(1) if match else None


def _toml(text: str) -> dict[str, Any]:
    return tomllib.loads(text)


def _keys(node: Any) -> list[str]:
    return [str(key) for key in node] if isinstance(node, dict) else []


def _specs(node: Any) -> list[str]:
    """The names of a list of PEP 508 requirement strings; a table (``{include-group = ...}``) is left out."""
    if not isinstance(node, list):
        return []
    names = (_requirement(spec) for spec in node if isinstance(spec, str))
    return [name for name in names if name]


def _pyproject(text: str) -> list[str]:
    document = _toml(text)
    project = document.get("project", {})
    names = _specs(project.get("dependencies"))
    for group in (project.get("optional-dependencies") or {}).values():
        names += _specs(group)
    for group in (document.get("dependency-groups") or {}).values():
        names += _specs(group)
    tool = document.get("tool", {})
    poetry = tool.get("poetry", {})
    names += [name for name in _keys(poetry.get("dependencies")) if name.lower() != "python"]
    names += _keys(poetry.get("dev-dependencies"))
    for group in (poetry.get("group") or {}).values():
        names += _keys(group.get("dependencies") if isinstance(group, dict) else None)
    names += _specs(tool.get("uv", {}).get("dev-dependencies"))
    for group in (tool.get("pdm", {}).get("dev-dependencies") or {}).values():
        names += _specs(group)
    return names


def _cargo(text: str) -> list[str]:
    document = _toml(text)
    names: list[str] = []
    for table in (document, document.get("workspace", {}), *(document.get("target") or {}).values()):
        if isinstance(table, dict):
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                names += _keys(table.get(section))
    return names


def _package_json(text: str) -> list[str]:
    document = json.loads(text)
    if not isinstance(document, dict):
        return []
    sections = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
    return [name for section in sections for name in _keys(document.get(section))]


def _composer(text: str) -> list[str]:
    document = json.loads(text)
    if not isinstance(document, dict):
        return []
    names = _keys(document.get("require")) + _keys(document.get("require-dev"))
    return [name for name in names if name != "php" and not name.startswith("ext-")]


def _requirements(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            name = _requirement(line)
            if name:
                names.append(name)
    return names


def _go_mod(text: str) -> list[str]:
    names = GO_REQUIRE_LINE.findall(text)
    for block in GO_REQUIRE_BLOCK.findall(text):
        names += [line.split()[0] for line in block.splitlines() if line.split() and not line.strip().startswith("//")]
    return names


def _pipfile(text: str) -> list[str]:
    document = _toml(text)
    return _keys(document.get("packages")) + _keys(document.get("dev-packages"))


def manifest(path: str) -> tuple[str, Callable[[str], list[str]]] | None:
    """The ecosystem and the parser of a manifest, or None when the path is not one."""
    base = posixpath.basename(path)
    if base == "package.json":
        return "npm", _package_json
    if base == "pyproject.toml":
        return "python", _pyproject
    if base == "Pipfile":
        return "python", _pipfile
    if fnmatch.fnmatch(base, "requirements*.txt") or (path.startswith("requirements/") and base.endswith(".txt")):
        return "python", _requirements
    if base == "go.mod":
        return "go", _go_mod
    if base == "Cargo.toml":
        return "rust", _cargo
    if base == "Gemfile":
        return "ruby", GEM.findall
    if base == "composer.json":
        return "php", _composer
    return None


def declared(reader: Reader, rev: str, path: str | None, warnings: list[str]) -> list[tuple[str, list[str], str]]:
    """The ecosystem and the declared dependency names of one manifest at one commit; empty for another file."""
    kind = manifest(path) if path else None
    text = reader.text(rev, path)
    if kind is None or path is None or text is None:
        return []
    ecosystem, parse = kind
    try:
        return [(ecosystem, parse(text), path)]
    except (ValueError, TypeError, AttributeError):
        warnings.append(f"{path} at {rev[:12]} could not be parsed; its dependencies are not checked")
        return []


def dependency_findings(
    found: Sequence[Change], reader: Reader, base: str, theme: str, approved: frozenset[str], warnings: list[str]
) -> tuple[list[Finding], list[str]]:
    """Each declared dependency the theme added that the owner did not approve, and each lockfile that changed with
    no approved addition in its ecosystem. Returns the findings and the approved names the theme added."""
    before: dict[str, set[str]] = {}
    after: dict[str, dict[str, str]] = {}
    for change in found:
        for ecosystem, declared_names, _ in declared(reader, base, change.old, warnings):
            before.setdefault(ecosystem, set()).update(normalize(name) for name in declared_names)
        for ecosystem, declared_names, where in declared(reader, theme, change.new, warnings):
            for name in declared_names:
                after.setdefault(ecosystem, {}).setdefault(normalize(name), where)
    out: list[Finding] = []
    used: list[str] = []
    added_by_ecosystem: dict[str, bool] = {}
    for ecosystem, names in sorted(after.items()):
        for name, path in sorted(names.items()):
            if name in before.get(ecosystem, set()):
                continue
            if name in approved:
                used.append(name)
                added_by_ecosystem[ecosystem] = True
            else:
                out.append(
                    Finding(INSTALLS, "dependency-added", path, f"{name} ({ecosystem}) is not in {APPROVED_KEY}")
                )
    for change in found:
        lockfile = change.new or change.old or ""
        locked = LOCKFILES.get(posixpath.basename(lockfile))
        if locked is not None and not added_by_ecosystem.get(locked):
            out.append(
                Finding(INSTALLS, "lockfile-changed", lockfile, f"changed with no approved {locked} dependency added")
            )
    return out, sorted(set(used))


# --- The owner's preferences ----------------------------------------------------------------------------------


def preference_list(state: Mapping[str, Any] | None, key: str) -> list[str]:
    """The names or globs of one preference, split on commas and white space; empty when it is unset or ``none``."""
    if state is None:
        return []
    value = next((pref["value"] for pref in state["preferences"] if pref["key"] == key), "")
    return [part for part in NAME_SEPARATOR.split(value) if part and part.lower() != "none"]


def accepted_by(finding: Finding, globs: Sequence[str]) -> bool:
    return finding.boundary == GATES and any(fnmatch.fnmatchcase(finding.path, glob) for glob in globs)


# --- The command -------------------------------------------------------------------------------------------


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="check_gates.py", description=INFO.summary)
    parser.add_argument("worktree", help="the theme worktree (read only)")
    parser.add_argument("--base", required=True, metavar="SHA", help="the commit the theme started from")
    parser.add_argument("--theme", default="HEAD", metavar="REF", help="the theme's last commit (default: HEAD)")
    parser.add_argument(
        "--state",
        metavar="FILE",
        help=f"the implement state (<label>-agentic-readiness-state.json): its {APPROVED_KEY} and {ACCEPTED_KEY} "
        "preferences",
    )
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    worktree = _common.resolve_target(args.worktree)
    state = progress.read_state(Path(args.state).expanduser()) if args.state is not None else None
    base = commit(worktree, args.base, "--base")
    theme = commit(worktree, args.theme, "--theme")
    found = changes(worktree, base, theme)
    reader = Reader(worktree)
    warnings: list[str] = []
    approved = frozenset(normalize(name) for name in preference_list(state, APPROVED_KEY))
    globs = preference_list(state, ACCEPTED_KEY)
    findings = census_findings(found, reader, base, theme)
    findings += suppression_findings(found, reader, base, theme)
    findings += number_findings(found, reader, base, theme)
    findings += gate_findings(found, reader, base, theme, (tree(worktree, base), tree(worktree, theme)))
    installs, used = dependency_findings(found, reader, base, theme, approved, warnings)
    findings += installs
    accepted = [finding for finding in findings if accepted_by(finding, globs)]
    stops = [finding for finding in findings if finding not in accepted]
    if state is None:
        warnings.append(f"no --state: no dependency is approved and no gate change is accepted ({APPROVED_KEY})")
    if _git(worktree, ["status", "--porcelain", "--untracked-files=no"]) not in (None, b""):
        warnings.append("the worktree has uncommitted changes; only the commits up to --theme were checked")
    warnings += [
        f"{path} is larger than {MAX_FILE_BYTES} bytes and was not read" for path in sorted(set(reader.skipped))
    ]
    if stops:
        count = len(stops)
        raise _common.ValidationFailed(
            f"check_gates: {count} finding{'' if count == 1 else 's'} on the theme branch; stop the theme and ask the "
            "owner",
            errors=[finding.line() for finding in stops],
            hint=f"the owner fixes it, or records the choice: pref set {APPROVED_KEY} or {ACCEPTED_KEY}",
        )
    kept, omitted = _common.bound_items([finding.to_json() for finding in accepted])
    data: dict[str, Any] = {
        "status": "clean",
        "base": base,
        "theme": theme,
        "changed_count": len(found),
        "accepted": kept,
        "approved_added": used,
    }
    if omitted:
        data["omitted"] = {"accepted": omitted}
    summary = f"check_gates: clean; {len(found)} changed paths, {len(accepted)} accepted by the owner"
    return _common.Result(data=data, summary=summary, warnings=warnings, truncated=bool(omitted))


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
