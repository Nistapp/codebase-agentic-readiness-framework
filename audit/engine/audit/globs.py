# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine's one path-glob matcher: a glob from the root, matched folder by folder.

Scope contract
--------------
Every check that names a place in the target with a wildcard (a workflow folder, a hook folder, a harness's rules
folder) matches it here, so a pattern means the same thing in every check and in the consistency map's ``glob``
scope (``dev/consistency_map.py``). The module is pure: it reads no file, and it raises nothing for any input.

Semantics
---------
A pattern and a path are split at ``/``. ``*``, ``?`` and ``[...]`` match inside one folder or file name, so ``*``
never crosses ``/``: ``.github/workflows/*.yml`` finds ``.github/workflows/ci.yml`` and not
``.github/workflows/sub/ci.yml``. A ``**`` name matches any number of folders, none included:
``docs/**/*.md`` finds ``docs/a.md`` and ``docs/a/b.md``, and ``.opencode/**`` finds everything under
``.opencode/``. This is not ``fnmatch`` on the whole path, whose ``*`` crosses ``/`` and whose ``**/`` needs at
least one folder. Operator ``--exclude`` globs and ignore files have their own rules (``audit/scan.py``,
``audit/ignore.py``).
"""

from __future__ import annotations

import fnmatch
import functools


def glob_match(pattern: str, path: str, *, fold_case: bool = False) -> bool:
    """Whether ``path``, a path from the root, matches ``pattern``, a glob from the root, folder by folder.

    ``fold_case`` matches each name as ``fnmatch.fnmatch`` does, case folded where the platform folds it (Windows);
    otherwise case is exact everywhere. The empty path is the root, with no name.
    """
    parts = pattern.split("/") if pattern else []
    names = path.split("/") if path else []
    one = fnmatch.fnmatch if fold_case else fnmatch.fnmatchcase

    @functools.lru_cache(maxsize=None)
    def at(i: int, j: int) -> bool:
        if i == len(parts):
            return j == len(names)
        if parts[i] == "**":
            return at(i + 1, j) or (j < len(names) and at(i, j + 1))
        return j < len(names) and one(names[j], parts[i]) and at(i + 1, j + 1)

    return at(0, 0)


def path_match(pattern: str, path: str, *, fold_case: bool = False) -> bool:
    """Whether a file at ``path`` is found by ``pattern``, as ``Inventory.match`` finds it.

    A pattern with a ``/`` is a glob from the root (``glob_match``). A pattern with no ``/`` is a base name, which
    may hold a wildcard, at any depth: ``package.json`` and ``*.csproj`` find the file in any folder.
    """
    if "/" in pattern:
        return glob_match(pattern, path, fold_case=fold_case)
    base = path.rsplit("/", 1)[-1]
    return (fnmatch.fnmatch if fold_case else fnmatch.fnmatchcase)(base, pattern)
