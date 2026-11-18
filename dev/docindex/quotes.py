# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check every quote a report folder cites: a model proposes a quote, this script checks it.

A report folder holds Markdown reports and a ``quotes.json``: a JSON list of objects
``{"id": "Q1", "path": "<repo path>", "quote": "<exact text>"}``. A report cites a quote by its id in square
brackets, for example ``[Q12]``. :func:`verify` checks that:

- every ``quotes.json`` under the folder (subfolders included) is a list of such objects, with ids of the form
  ``Q<n>`` that are unique within the file;
- each entry's ``path`` is a repository-relative path, never under ``artefacts/`` and never a ``.env`` file, that
  names a file in the working tree (or at a git ref);
- each entry's ``quote`` occurs in that file, after whitespace runs on both sides collapse to one space. Nothing else
  is normalised: case, punctuation and words must match;
- every ``[Qn]`` in a Markdown file under the folder resolves to an entry of the nearest ``quotes.json``: the one in
  the Markdown file's own folder, else in the closest parent folder up to the checked folder.

A failure names the id, a path and the reason. The folder is a usage error when it is not a folder or holds no
``quotes.json``. This module imports nothing outside the standard library and this package.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from .gitread import RefTree

__all__ = [
    "CITATION",
    "QUOTES_FILE",
    "Failure",
    "Result",
    "Unreadable",
    "UsageError",
    "normalise",
    "path_problem",
    "ref_reader",
    "verify",
    "working_tree_reader",
]

QUOTES_FILE = "quotes.json"

#: A citation in a report: a quote id in square brackets.
CITATION = re.compile(r"\[(Q[0-9]+)\]")

_ID = re.compile(r"Q[0-9]+")

#: The top folder no quote may cite: scratch notes, kept out of git.
_FORBIDDEN_TOP = "artefacts"


class UsageError(Exception):
    """The command was called wrongly: the folder is missing, or holds no ``quotes.json``."""


class Unreadable(Exception):
    """A quoted path cannot be read; the message is the reason."""


@dataclass(frozen=True)
class Failure:
    """One check that failed: the quote id, the path it concerns and why."""

    id: str
    path: str
    reason: str

    def line(self) -> str:
        return f"{self.id}: {self.path}: {self.reason}"


@dataclass(frozen=True)
class Result:
    """The outcome of :func:`verify`."""

    quotes: int
    citations: int
    failures: tuple[Failure, ...]

    @property
    def passed(self) -> bool:
        return not self.failures

    def summary(self) -> str:
        failed = len(self.failures)
        return f"verify-quotes: {self.quotes} quotes and {self.citations} citations checked, {failed} failed"


Reader = Callable[[str], str]


def normalise(text: str) -> str:
    """``text`` with each whitespace run, line breaks included, collapsed to one space, and no outer whitespace."""
    return " ".join(text.split())


def _is_env_file(name: str) -> bool:
    return name == ".env" or name.startswith(".env.") or name.endswith(".env")


def path_problem(path: str) -> str | None:
    """Why ``path`` may not be quoted, or ``None`` when it is a plain repository-relative path that may be."""
    if not path:
        return "the path is empty"
    pure = PurePosixPath(path)
    if pure.is_absolute() or "\\" in path or re.match(r"[A-Za-z]:", path):
        return "the path is not repository-relative"
    if ".." in pure.parts or pure.as_posix() != path:
        return "the path is not a plain repository-relative path (no '.', '..', '//' or trailing '/')"
    if pure.parts[0] == _FORBIDDEN_TOP:
        return f"a quote may not cite a file under {_FORBIDDEN_TOP}/"
    if _is_env_file(pure.name):
        return "a quote may not cite a .env file"
    return None


def working_tree_reader(root: Path) -> Reader:
    """A reader of the files in the working tree at ``root``. A symbolic link must stay inside ``root``."""
    base = root.resolve()

    def read(path: str) -> str:
        real = (base / path).resolve()
        try:
            target = real.relative_to(base).as_posix()
        except ValueError:
            raise Unreadable("the path leads outside the repository") from None
        if target != path:
            problem = path_problem(target)
            if problem is not None:
                raise Unreadable(f"the path leads to {target}: {problem}")
        if not real.is_file():
            raise Unreadable("no such file in the working tree")
        try:
            return real.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise Unreadable(f"the file cannot be read: {exc.strerror or exc}") from None

    return read


def ref_reader(root: Path, ref: str) -> Reader:
    """A reader of the files at the git ``ref`` of the repository at ``root``; raises ``GitError`` for a bad ref."""
    tree = RefTree(root, ref)
    files = set(tree.files())

    def read(path: str) -> str:
        text = tree.read(path) if path in files else None
        if text is None:
            raise Unreadable(f"no such file at {ref}")
        return text

    return read


def _shown(folder: Path, relative: PurePosixPath) -> str:
    return (folder / relative).as_posix()


def _label(entry: Any, number: int) -> str:
    if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]:
        return str(entry["id"])
    return f"entry {number}"


def _check_entry(entry: Any, read: Reader, cache: dict[str, str | Unreadable]) -> tuple[str, str | None]:
    """The path to show for ``entry`` and the reason it fails, or ``None`` when it passes."""
    if not isinstance(entry, dict):
        return "-", "the entry is not a JSON object"
    path = entry.get("path")
    quote = entry.get("quote")
    shown = path if isinstance(path, str) and path else "-"
    ident = entry.get("id")
    if not isinstance(ident, str) or not _ID.fullmatch(ident):
        return shown, "the id is not a string of the form Q<n>"
    if not isinstance(path, str):
        return shown, "the path is missing or not a string"
    if not isinstance(quote, str):
        return shown, "the quote is missing or not a string"
    problem = path_problem(path)
    if problem is not None:
        return shown, problem
    wanted = normalise(quote)
    if not wanted:
        return shown, "the quote is empty"
    if path not in cache:
        try:
            cache[path] = normalise(read(path))
        except Unreadable as exc:
            cache[path] = exc
    text = cache[path]
    if isinstance(text, Unreadable):
        return shown, str(text)
    if wanted not in text:
        return shown, "the quote does not occur in the file"
    return shown, None


def _load(file: Path) -> tuple[list[Any] | None, str | None]:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{QUOTES_FILE} cannot be read as JSON: {exc}"
    if not isinstance(data, list):
        return None, f"{QUOTES_FILE} is not a JSON list"
    return data, None


def _sorted_files(folder: Path, pattern: str) -> list[PurePosixPath]:
    found = (path for path in folder.rglob(pattern) if path.is_file())
    return sorted((PurePosixPath(path.relative_to(folder).as_posix()) for path in found), key=lambda p: p.as_posix())


def _nearest(directory: PurePosixPath, tables: dict[PurePosixPath, set[str]]) -> PurePosixPath | None:
    current = directory
    while True:
        if current in tables:
            return current
        if current == PurePosixPath("."):
            return None
        current = current.parent


def verify(folder: Path, read: Reader) -> Result:
    """Check every ``quotes.json`` and every citation under ``folder``, reading quoted files with ``read``.

    Paths in a failure are shown under ``folder`` as given, so a relative folder gives relative paths.
    """
    if not folder.is_dir():
        raise UsageError(f"{folder.as_posix()} is not a folder")
    quote_files = _sorted_files(folder, QUOTES_FILE)
    if not quote_files:
        raise UsageError(f"{folder.as_posix()} holds no {QUOTES_FILE}")

    failures: list[Failure] = []
    tables: dict[PurePosixPath, set[str]] = {}
    cache: dict[str, str | Unreadable] = {}
    quotes = 0
    for relative in quote_files:
        shown_file = _shown(folder, relative)
        entries, error = _load(folder / relative)
        ids: set[str] = set()
        tables[relative.parent] = ids
        if entries is None:
            failures.append(Failure("-", shown_file, error or "unreadable"))
            continue
        for number, entry in enumerate(entries, start=1):
            quotes += 1
            label = _label(entry, number)
            path, reason = _check_entry(entry, read, cache)
            if reason is not None:
                failures.append(Failure(label, path, f"{reason} ({shown_file})"))
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                if entry["id"] in ids:
                    failures.append(Failure(label, path, f"the id is not unique ({shown_file})"))
                ids.add(entry["id"])

    citations = 0
    for relative in _sorted_files(folder, "*.md"):
        shown_md = _shown(folder, relative)
        try:
            text = (folder / relative).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            failures.append(Failure("-", shown_md, f"the report cannot be read: {exc.strerror or exc}"))
            continue
        cited = sorted(set(CITATION.findall(text)), key=lambda ident: int(ident[1:]))
        citations += len(cited)
        home = _nearest(relative.parent, tables)
        for ident in cited:
            if home is None:
                failures.append(Failure(ident, shown_md, f"the cited id has no {QUOTES_FILE} in reach"))
            elif ident not in tables[home]:
                where = _shown(folder, home / QUOTES_FILE)
                failures.append(Failure(ident, shown_md, f"the cited id has no entry in {where}"))
    return Result(quotes=quotes, citations=citations, failures=tuple(failures))
