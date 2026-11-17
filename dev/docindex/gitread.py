# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Read a repository's tracked files from the working tree or at a git ref, never by a checkout.

A :class:`Tree` lists tracked file paths (POSIX, relative to the repository root) and reads one file's text:

- :class:`WorkTree`: the tracked files of the working tree (``git ls-files``), read from disk. A tracked file that
  is gone from disk reads as ``None``.
- :class:`RefTree`: the files at a git ref (``git ls-tree -r --name-only <ref>``), read with
  ``git show <ref>:<path>``. A path that is not in the tree at the ref reads as ``None``.

Every git call runs ``git -C <root> ...`` with ``-z`` output where git offers it, so a path with a space or a
non-ASCII character comes back as written. A failed call raises :class:`GitError`. This module imports nothing
outside the standard library.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

__all__ = ["GitError", "RefTree", "Tree", "WorkTree"]


class GitError(Exception):
    """A git call failed, or a ref does not name a commit."""


class Tree(Protocol):
    """The tracked files of a repository, at one state."""

    def files(self) -> list[str]:
        """Every tracked file path, sorted."""
        ...

    def read(self, path: str) -> str | None:
        """The text of the file at ``path``, or ``None`` when there is no such file."""
        ...


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    except OSError as exc:
        raise GitError(f"git could not run: {exc}") from None
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip() or f"exit {result.returncode}"
        raise GitError(f"git {args[0]} failed: {message}")
    return result.stdout


def _paths(output: bytes) -> list[str]:
    return sorted(path for path in output.decode("utf-8", errors="replace").split("\0") if path)


class WorkTree:
    """The tracked files of the working tree at ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def files(self) -> list[str]:
        return _paths(_git(self.root, "ls-files", "-z"))

    def read(self, path: str) -> str | None:
        file = self.root / path
        if not file.is_file():
            return None
        return file.read_text(encoding="utf-8", errors="replace")


class RefTree:
    """The files at the git ``ref`` of the repository at ``root``. The ref must name a commit."""

    def __init__(self, root: Path, ref: str) -> None:
        if not ref or ref.startswith("-"):
            raise GitError(f"not a git ref: {ref!r}")
        try:
            _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        except GitError:
            raise GitError(f"{ref!r} does not name a commit in {root.name or root}") from None
        self.root = root
        self.ref = ref

    def files(self) -> list[str]:
        return _paths(_git(self.root, "ls-tree", "-r", "-z", "--name-only", self.ref))

    def read(self, path: str) -> str | None:
        try:
            data = _git(self.root, "show", f"{self.ref}:{path}")
        except GitError:
            return None
        return data.decode("utf-8", errors="replace")
