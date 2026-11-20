# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Stage S3 — bounded traversal and inventory.

Unbounded traversal is how a scanning tool becomes unusable on the repositories that need it
most. This module walks the target once, produces metadata only (never holding file contents in
memory), and record's every path it chose not to inspect.

Carried data (templates, examples, fixtures: ADR-0008) is walked and then set aside: it leaves
``Inventory.files`` and is recorded in ``Inventory.set_aside``, so no check can read it as the project.

The walk skips what the target's ignore files ignore, read with the scoped matcher of ADR-0009 (nested
``.gitignore`` files, anchoring, ``**`` and ``!``), and never skips a file git tracks. Known limitation,
deliberately recorded rather than hidden: the matcher is a parser of a documented subset of gitignore, not
``git check-ignore``, and it reads neither ``.git/info/exclude`` nor a global excludes file. Checks that depend
on ignore certainty must therefore report ``UNKNOWN`` rather than ``PASS`` when they cannot be sure — see
docs/architecture/contributor-deep-dive/01-scan-engine-and-tiering.md § 3.
"""

from __future__ import annotations

import enum
import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

from audit.ignore import decide_path, load_ignore_file, load_scoped_rules, tracked_files
from audit.target import HARD_EXCLUDE_DIRS

#: Files larger than this are inventoried but their content is never read for content checks.
#: Raised from 256 KiB (S3.6.4): a real `package-lock.json` at 514 KiB tripped it, degrading
#: `EXEC-02` to "unverified" for a lockfile that was in fact consistent. 2 MiB covers lockfiles of
#: realistic size while still bounding memory for the pathological case.
CONTENT_READ_LIMIT = 2 * 1024 * 1024

#: Bytes sniffed to decide whether a file is binary.
BINARY_SNIFF = 8192


class Kind(str, enum.Enum):
    """Coarse classification that drives which checks look at a file."""

    MANIFEST = "manifest"
    BUILD = "build"
    CONFIG = "config"
    SOURCE = "source"
    TEST = "test"
    DOC = "doc"
    CI = "ci"
    SCRIPT = "script"
    GENERATED = "generated"
    BINARY = "binary"
    OTHER = "other"


_NAME_KINDS: dict[str, Kind] = {
    "package.json": Kind.MANIFEST,
    "pyproject.toml": Kind.MANIFEST,
    "setup.py": Kind.MANIFEST,
    "requirements.txt": Kind.MANIFEST,
    "Pipfile": Kind.MANIFEST,
    "pom.xml": Kind.BUILD,
    "build.gradle": Kind.BUILD,
    "build.gradle.kts": Kind.BUILD,
    "settings.gradle": Kind.BUILD,
    "go.mod": Kind.MANIFEST,
    "Cargo.toml": Kind.MANIFEST,
    "Gemfile": Kind.MANIFEST,
    "composer.json": Kind.MANIFEST,
    "Makefile": Kind.BUILD,
    "Taskfile.yml": Kind.BUILD,
    "Taskfile.yaml": Kind.BUILD,
    "gradlew": Kind.SCRIPT,
    "mvnw": Kind.SCRIPT,
    ".env.example": Kind.CONFIG,
    ".nvmrc": Kind.CONFIG,
    ".tool-versions": Kind.CONFIG,
    ".editorconfig": Kind.CONFIG,
    ".aider.conf.yml": Kind.CONFIG,
    "opencode.json": Kind.CONFIG,
}

_SUFFIX_KINDS: dict[str, Kind] = {
    ".md": Kind.DOC,
    ".rst": Kind.DOC,
    ".txt": Kind.DOC,
    ".py": Kind.SOURCE,
    ".ts": Kind.SOURCE,
    ".tsx": Kind.SOURCE,
    ".js": Kind.SOURCE,
    ".jsx": Kind.SOURCE,
    ".java": Kind.SOURCE,
    ".kt": Kind.SOURCE,
    ".go": Kind.SOURCE,
    ".rs": Kind.SOURCE,
    ".rb": Kind.SOURCE,
    ".cs": Kind.SOURCE,
    ".php": Kind.SOURCE,
    ".sh": Kind.SCRIPT,
    ".bash": Kind.SCRIPT,
    ".ps1": Kind.SCRIPT,
    ".json": Kind.CONFIG,
    ".yaml": Kind.CONFIG,
    ".yml": Kind.CONFIG,
    ".toml": Kind.CONFIG,
    ".ini": Kind.CONFIG,
    ".cfg": Kind.CONFIG,
    ".properties": Kind.CONFIG,
    ".min.js": Kind.GENERATED,
    ".map": Kind.GENERATED,
    ".pb.go": Kind.GENERATED,
}

_TEST_HINTS = ("test_", "_test.", ".test.", ".spec.", "tests/", "test/", "__tests__/")

_GENERATED_HINTS = (
    "dist/",
    "build/",
    "generated/",
    ".g.cs",
    ".designer.cs",
    ".pb.go",
    ".lock.gen",
    "vendor/",
    ".min.css",
    ".min.js",
)


#: Directory names that mark the files under them as *carried data*: files the repository ships or tests
#: with rather than files that are the repository (ADR-0008). Compared whole and case-insensitively. The
#: single place the list lives.
CARRIED_DATA_DIRS: tuple[str, ...] = (
    "templates",
    "template",
    "examples",
    "example",
    "fixtures",
    "samples",
    "testdata",
    "scaffold",
)

#: The language folders of a JVM source root, ``src/<source set>/<language>/``. A folder below one is a
#: package (``com/example/``), never carried data (ADR-0008). Compared exactly, as the build tools do.
_JVM_SOURCE_LANGUAGES = frozenset({"java", "kotlin", "scala", "groovy"})

#: The manifests whose presence outside carried data means the repository has its own project.
_PROJECT_MANIFESTS = frozenset(name for name, kind in _NAME_KINDS.items() if kind in (Kind.MANIFEST, Kind.BUILD))


@dataclass(frozen=True)
class FileEntry:
    rel: str
    size: int
    kind: Kind
    has_text: bool


@dataclass(frozen=True)
class SetAside:
    """One outermost carried-data directory and the number of files under it."""

    path: str
    files: int


@dataclass
class Inventory:
    """Metadata for every inspected file, plus a record of what was skipped and what was set aside."""

    root: Path
    files: list[FileEntry] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    truncated: bool = False
    #: Path globs the operator took out of the audit with ``--exclude``.
    excludes: tuple[str, ...] = ()
    #: Carried-data directories (``CARRIED_DATA_DIRS``) whose files are not in ``files``. Sorted by path.
    set_aside: list[SetAside] = field(default_factory=list)
    #: Directories the walk did not enter because an ignore rule covers them and git tracks nothing in them.
    #: Sorted by path. ``HARD_EXCLUDE_DIRS`` are not listed.
    ignored_dirs: list[str] = field(default_factory=list)

    # -- lookups ---------------------------------------------------------
    def is_excluded(self, rel: str) -> bool:
        return any(fnmatch.fnmatch(rel, pattern) for pattern in self.excludes)

    def is_set_aside(self, rel: str) -> bool:
        """Whether ``rel`` lies under a directory this inventory set aside as carried data."""
        return any(rel == entry.path or rel.startswith(entry.path + "/") for entry in self.set_aside)

    @property
    def files_set_aside(self) -> int:
        return sum(entry.files for entry in self.set_aside)

    def paths(self, kind: Kind | None = None) -> list[str]:
        return [f.rel for f in self.files if kind is None or f.kind is kind]

    def has(self, rel: str) -> bool:
        rel = rel.strip("/")
        return any(f.rel == rel or f.rel.endswith("/" + rel) for f in self.files)

    def match(self, *patterns: str) -> list[str]:
        out: list[str] = []
        for f in self.files:
            if any(fnmatch.fnmatch(f.rel, p) or fnmatch.fnmatch(os.path.basename(f.rel), p) for p in patterns):
                out.append(f.rel)
        return out

    def with_suffix(self, *suffixes: str) -> list[str]:
        return [f.rel for f in self.files if f.rel.endswith(suffixes)]

    # -- content ---------------------------------------------------------
    def read(self, rel: str, limit: int = CONTENT_READ_LIMIT) -> str | None:
        """Read one file, bounded. Returns None for binary, oversized or unreadable files."""
        entry = next((f for f in self.files if f.rel == rel), None)
        if entry is None or not entry.has_text or entry.size > limit:
            return None
        try:
            return (self.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def grep(self, pattern, *, kinds: tuple[Kind, ...] | None = None, limit: int = 200) -> list[tuple[str, int, str]]:
        """Dot-less search across eligible text files. Returns (rel, line_no, line)."""
        import re

        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        hits: list[tuple[str, int, str]] = []
        for entry in self.files:
            if kinds and entry.kind not in kinds:
                continue
            if not entry.has_text or entry.size > CONTENT_READ_LIMIT:
                continue
            text = self.read(entry.rel)
            if not text:
                continue
            for no, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    hits.append((entry.rel, no, line.strip()[:240]))
                    if len(hits) >= limit:
                        return hits
        return hits


def _classify(rel: str) -> Kind:
    base = os.path.basename(rel)
    if base in _NAME_KINDS:
        return _NAME_KINDS[base]
    if rel.startswith(".github/workflows/") or base in (
        ".gitlab-ci.yml",
        "Jenkinsfile",
        "azure-pipelines.yml",
        ".circleci",
    ):
        return Kind.CI
    lowered = rel.lower()
    if any(h in lowered for h in _GENERATED_HINTS):
        return Kind.GENERATED
    if any(h in lowered for h in _TEST_HINTS):
        return Kind.TEST
    for suffix in sorted(_SUFFIX_KINDS, key=len, reverse=True):
        if rel.endswith(suffix):
            return _SUFFIX_KINDS[suffix]
    return Kind.OTHER


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(BINARY_SNIFF)
    except OSError:
        return True


def _tracked_directories(tracked: set[str] | None) -> set[str]:
    """Every directory that holds a tracked file at some depth."""
    directories: set[str] = set()
    for rel in tracked or ():
        parts = rel.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            directories.add("/".join(parts[:index]))
    return directories


def build_inventory(
    root: Path, *, extra_excludes: tuple[str, ...] = (), max_files: int = 250_000, max_depth: int = 24
) -> Inventory:
    """Walk the target once. Never follows symlinks; never leaves ``root``.

    The ignore files decide what the walk skips, with the scoped matcher of ADR-0009: the root ignore files, each
    nested ``.gitignore`` as the walk enters its directory, anchoring, ``**`` and ``!``. A file git tracks is never
    skipped by an ignore rule, because git tracks it whatever the rules say; the walk enters an ignored directory
    only to reach such files. ``HARD_EXCLUDE_DIRS`` and ``--exclude`` still apply to tracked files.
    """
    root = root.resolve()
    rules = load_scoped_rules(root)
    tracked = tracked_files(root)
    tracked_dirs = _tracked_directories(tracked)
    #: Directories the walk entered although an ignore rule covers them (it holds tracked files).
    entered_ignored: set[str] = set()
    inv = Inventory(root=root, excludes=extra_excludes)

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        here = current.relative_to(root).as_posix()
        here = "" if here == "." else here
        depth = len(current.relative_to(root).parts)
        if depth >= max_depth:
            inv.skipped.append((str(current.relative_to(root)), "max-depth"))
            dirnames[:] = []
            continue
        inside_ignored = here in entered_ignored
        if here and not inside_ignored and ".gitignore" in filenames:
            rules.extend(load_ignore_file(root, f"{here}/.gitignore"))

        kept: list[str] = []
        for d in sorted(dirnames):
            if d in HARD_EXCLUDE_DIRS:
                continue
            rel_dir = f"{here}/{d}" if here else d
            if inside_ignored or decide_path(rel_dir, rules, is_dir=True).ignored:
                if rel_dir not in tracked_dirs:
                    inv.ignored_dirs.append(rel_dir)
                    continue
                entered_ignored.add(rel_dir)
            kept.append(d)
        dirnames[:] = kept

        for name in sorted(filenames):
            if len(inv.files) >= max_files:
                inv.truncated = True
                break
            path = current / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                inv.skipped.append((rel, "symlink"))
                continue
            ignored = inside_ignored or decide_path(rel, rules).ignored
            if (ignored and (tracked is None or rel not in tracked)) or inv.is_excluded(rel):
                inv.skipped.append((rel, "ignored"))
                continue
            try:
                size = path.stat().st_size
            except OSError:
                inv.skipped.append((rel, "unreadable"))
                continue
            if size == 0:
                inv.files.append(FileEntry(rel, 0, _classify(rel), has_text=True))
                continue
            binary = _looks_binary(path)
            inv.files.append(
                FileEntry(
                    rel=rel,
                    size=size,
                    kind=Kind.BINARY if binary else _classify(rel),
                    has_text=not binary,
                )
            )
        if inv.truncated:
            break

    inv.ignored_dirs.sort()
    _set_carried_data_aside(inv)
    return inv


def _carried_directory(rel: str) -> str | None:
    """The outermost directory of ``rel`` named in ``CARRIED_DATA_DIRS``, or ``None``.

    A name below a JVM source root (``src/<set>/<java|kotlin|scala|groovy>/``, at any depth) is a package and
    never counts, so ``src/main/java/com/example/`` stays while ``src/main/resources/templates/`` is set aside.
    """
    parts = rel.split("/")[:-1]
    for index, part in enumerate(parts):
        if index >= 2 and parts[index - 2] == "src" and part in _JVM_SOURCE_LANGUAGES:
            return None
        if part.lower() in CARRIED_DATA_DIRS:
            return "/".join(parts[: index + 1])
    return None


def _set_carried_data_aside(inv: Inventory) -> None:
    """Move the files under a carried-data directory out of ``inv.files`` and record them (ADR-0008).

    Nothing is set aside when the repository's only manifests are inside carried directories: that
    directory is then the project, and removing it would leave the audit nothing to read.
    """
    carried: dict[str, int] = {}
    kept: list[FileEntry] = []
    carried_manifest = False
    project_manifest = False
    for entry in inv.files:
        directory = _carried_directory(entry.rel)
        is_manifest = os.path.basename(entry.rel) in _PROJECT_MANIFESTS
        if directory is None:
            kept.append(entry)
            project_manifest = project_manifest or is_manifest
        else:
            carried[directory] = carried.get(directory, 0) + 1
            carried_manifest = carried_manifest or is_manifest
    if not carried or (carried_manifest and not project_manifest):
        return
    inv.files = kept
    inv.set_aside = [SetAside(path, carried[path]) for path in sorted(carried)]
