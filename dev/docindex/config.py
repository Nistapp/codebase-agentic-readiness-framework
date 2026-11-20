# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The checks of the project config, so that a typo in it cannot drop or misfile files without a word.

- :func:`check_keys` refuses a key that no rule of the index reads: at the top, under ``exclude`` and ``sweep``
  (and its ``bundle_references`` and ``triggers``), and in each ``ids`` kind and its ``define``. It also refuses an
  ID kind that the model does not know, a section that is not a JSON object, and a ``generated`` entry whose value
  is not a string (the command that writes the file). The entry point,
  ``dev/doc_index.py``, runs it when it loads the config; a refused config is a usage error, exit 1.
- :func:`unmatched` names each path entry that no tracked file of a tree lies at or under: the ``exclude.skip``,
  ``exclude.list_only``, ``generated``, ``zones``, ``ids.<kind>.defined_in`` and ``sweep.paths`` prefixes, and the
  ``sweep.file_names`` names. It is a warning in the ``build`` summary, never a failure: an index of an older ref
  (``--at``, or the old side of ``diff``) can lack a folder that the config names today.

This module imports nothing outside the standard library and this package.
"""

from __future__ import annotations

import posixpath
from typing import Any, Iterable, Mapping

from .model import ID_KINDS

__all__ = ["BUNDLE_FILES", "ConfigError", "check_keys", "unmatched"]

#: The config key that the entry point fills with each bundle's entries (``dev/doc_index.py``). It is not part of
#: the JSON config file: the lists come from the project's bundle module at run time.
BUNDLE_FILES = "bundle_files"

_TOP = frozenset(
    {"default_zone", "description", "exclude", "file_kinds", "generated", "ids", "sweep", "zones", BUNDLE_FILES}
)
_EXCLUDE = frozenset({"list_only", "skip"})
_SWEEP = frozenset({"bundle_references", "file_names", "paths", "triggers"})
_BUNDLE_REFERENCES = frozenset({"constants", "module"})
_TRIGGERS = frozenset({"group1", "group2"})
_ID_KIND = frozenset({"address", "define", "defined_in", "pattern", "runs"})
_DEFINE = frozenset({"files", "heading", "json", "level"})
_DEFINE_JSON = frozenset({"id", "list", "title"})


class ConfigError(ValueError):
    """The config holds a key that no rule reads, or a section that is not a JSON object."""


def _object(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{where} is not a JSON object")
    return value


def _known(value: Any, where: str, known: frozenset[str]) -> Mapping[str, Any]:
    section = _object(value, where)
    unknown = sorted(set(section) - known)
    if unknown:
        names = ", ".join(f"{where}.{key}" if where != "the config" else key for key in unknown)
        raise ConfigError(f"unknown key in {where}: {names}; known keys: {', '.join(sorted(known))}")
    return section


def check_keys(config: Any) -> None:
    """Raise :class:`ConfigError` when ``config`` holds a key that no rule reads, or an unknown ID kind."""
    top = _known(config, "the config", _TOP)
    if "exclude" in top:
        _known(top["exclude"], "exclude", _EXCLUDE)
    if "sweep" in top:
        sweep = _known(top["sweep"], "sweep", _SWEEP)
        if "bundle_references" in sweep:
            _known(sweep["bundle_references"], "sweep.bundle_references", _BUNDLE_REFERENCES)
        if "triggers" in sweep:
            _known(sweep["triggers"], "sweep.triggers", _TRIGGERS)
    for path, by in _object(top.get("generated", {}), "generated").items():
        if not isinstance(by, str) or not by:
            raise ConfigError(f"generated.{path} is not a non-empty string naming the command that writes it")
    for kind, entry in _object(top.get("ids", {}), "ids").items():
        if kind not in ID_KINDS:
            raise ConfigError(f"unknown ID kind ids.{kind}; known kinds: {', '.join(ID_KINDS)}")
        found = _known(entry, f"ids.{kind}", _ID_KIND)
        if "define" in found:
            define = _known(found["define"], f"ids.{kind}.define", _DEFINE)
            if "json" in define:
                _known(define["json"], f"ids.{kind}.define.json", _DEFINE_JSON)


def _under(path: str, prefix: str) -> bool:
    prefix = prefix.rstrip("/")
    return path == prefix or path.startswith(prefix + "/")


def unmatched(config: Mapping[str, Any], files: Iterable[str]) -> list[str]:
    """One line per path entry of ``config`` that none of the tracked ``files`` lies at or under, sorted."""
    tracked = list(files)
    names = {posixpath.basename(path) for path in tracked}
    exclude = config.get("exclude", {})
    sweep = config.get("sweep", {})
    prefixes: list[tuple[str, str]] = [
        *(("exclude.skip", prefix) for prefix in exclude.get("skip", [])),
        *(("exclude.list_only", prefix) for prefix in exclude.get("list_only", [])),
        *(("generated", prefix) for prefix in config.get("generated", {})),
        *(("zones", prefix) for prefix in config.get("zones", {})),
        *(("sweep.paths", prefix) for prefix in sweep.get("paths", [])),
    ]
    for kind, entry in sorted(config.get("ids", {}).items()):
        prefixes.extend((f"ids.{kind}.defined_in", prefix) for prefix in entry.get("defined_in", []))
    problems = [
        f"{where}: {prefix!r} matches no tracked file"
        for where, prefix in prefixes
        if not any(_under(path, prefix) for path in tracked)
    ]
    problems.extend(
        f"sweep.file_names: {name!r} names no tracked file" for name in sweep.get("file_names", []) if name not in names
    )
    return sorted(problems)
