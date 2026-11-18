# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The bundle manifest and its diff: what each skill bundle ships, file by file, and what changed between two.

:func:`manifest` takes a folder whose every subfolder is one bundle (as ``build_skills.py --out-dir`` writes them)
and returns the manifest: for each bundle, each file's path relative to the bundle (POSIX), its size and its
SHA-256. :func:`to_json` writes it as deterministic JSON (sorted, no timestamps, no absolute paths).

An archive file (by default ``audit.pyz``) gets no ``sha256``: its zip entries carry the source files' modification
times, so two builds of the same source can differ byte for byte. It gets ``members_sha256`` in its place, the
SHA-256 of its members' names and contents in name order, which ignores the entry metadata. :func:`compare`
compares a file by ``sha256`` and ``size``, or an archive by ``members_sha256`` and ``size``.

:func:`compare` takes two manifests and lists, per bundle, the files added, removed and changed, each sorted. A
bundle that is on one side only has all its files added or removed. :func:`to_text` and :func:`diff_to_json` write
the report.

This module is part of the generic core: it builds nothing and imports no other ``dev/`` module. The entry point,
``dev/doc_index.py``, builds the bundles into a temporary folder and passes that folder in.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

MANIFEST_FORMAT = "docindex-bundle-manifest/1"
DIFF_FORMAT = "docindex-bundle-manifest-diff/1"
ARCHIVES: tuple[str, ...] = ("audit.pyz",)
_CHUNK = 1 << 16


class ManifestError(ValueError):
    """A folder or a manifest that this module cannot read: a stray top-level file, a bad archive, a bad shape."""


class BuildError(RuntimeError):
    """The bundle build failed; the entry point raises it, so the core needs no type of ``dev/build_skills.py``."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def members_sha256(path: Path) -> str:
    """The SHA-256 of an archive's members, in name order: each name and content, length-prefixed; no metadata."""
    digest = hashlib.sha256()
    try:
        with zipfile.ZipFile(path) as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                name = info.filename.encode("utf-8")
                data = archive.read(info.filename)
                digest.update(len(name).to_bytes(8, "big") + name)
                digest.update(len(data).to_bytes(8, "big") + data)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ManifestError(f"{path.name}: not a readable zip archive: {exc}") from exc
    return digest.hexdigest()


def _entry(file: Path, relative: str, archives: Sequence[str]) -> dict[str, Any]:
    entry: dict[str, Any] = {"path": relative, "size": file.stat().st_size}
    if file.name in archives:
        entry["members_sha256"] = members_sha256(file)
    else:
        entry["sha256"] = _sha256_file(file)
    return entry


def _bundle_entries(bundle: Path, archives: Sequence[str]) -> list[dict[str, Any]]:
    entries = [
        _entry(file, file.relative_to(bundle).as_posix(), archives) for file in bundle.rglob("*") if file.is_file()
    ]
    return sorted(entries, key=lambda entry: str(entry["path"]))


def manifest(folder: Path, archives: Sequence[str] = ARCHIVES) -> dict[str, Any]:
    """The manifest of every bundle in ``folder``: each subfolder is one bundle, named by its folder name.

    ``archives`` names the files (by file name) that get ``members_sha256`` in place of ``sha256``. A file directly
    in ``folder`` belongs to no bundle and raises :class:`ManifestError`.
    """
    stray = sorted(child.name for child in folder.iterdir() if not child.is_dir())
    if stray:
        raise ManifestError(f"a file outside every bundle: {', '.join(stray)}")
    bundles = {child.name: _bundle_entries(child, archives) for child in folder.iterdir() if child.is_dir()}
    return {"format": MANIFEST_FORMAT, "bundles": {name: bundles[name] for name in sorted(bundles)}}


def to_json(data: Mapping[str, Any]) -> str:
    """The one JSON form of a manifest or a diff: sorted keys, two-space indent, a final newline."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _check_entry(bundle: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ManifestError(f"bundle {bundle}: an entry is not an object: {raw!r}")
    entry: dict[str, Any] = {str(key): value for key, value in raw.items()}
    if not isinstance(entry.get("path"), str) or not isinstance(entry.get("size"), int):
        raise ManifestError(f"bundle {bundle}: an entry without a path and a size: {raw!r}")
    if not isinstance(entry.get("sha256"), str) and not isinstance(entry.get("members_sha256"), str):
        raise ManifestError(f"bundle {bundle}: {entry['path']} has neither sha256 nor members_sha256")
    return entry


def load(data: Any) -> dict[str, dict[str, dict[str, Any]]]:
    """Each bundle's entries by path, from a parsed manifest; a wrong shape raises :class:`ManifestError`."""
    if not isinstance(data, dict) or data.get("format") != MANIFEST_FORMAT:
        raise ManifestError(f"not a bundle manifest (format {MANIFEST_FORMAT})")
    bundles = data.get("bundles")
    if not isinstance(bundles, dict):
        raise ManifestError("the manifest has no bundles object")
    loaded: dict[str, dict[str, dict[str, Any]]] = {}
    for name, entries in bundles.items():
        if not isinstance(entries, list):
            raise ManifestError(f"bundle {name}: the entries are not a list")
        by_path: dict[str, dict[str, Any]] = {}
        for raw in entries:
            entry = _check_entry(name, raw)
            if entry["path"] in by_path:
                raise ManifestError(f"bundle {name}: {entry['path']} is listed twice")
            by_path[entry["path"]] = entry
        loaded[name] = by_path
    return loaded


def _fingerprint(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    return (entry.get("sha256"), entry.get("members_sha256"), entry["size"])


@dataclass(frozen=True)
class BundleChange:
    """The files of one bundle that were added, removed or changed, each sorted."""

    bundle: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]


def compare(old: Any, new: Any) -> tuple[BundleChange, ...]:
    """The changes from the manifest ``old`` to the manifest ``new``, one per bundle that changed, by bundle name."""
    before, after = load(old), load(new)
    changes: list[BundleChange] = []
    for bundle in sorted(set(before) | set(after)):
        old_files, new_files = before.get(bundle, {}), after.get(bundle, {})
        common = set(old_files) & set(new_files)
        change = BundleChange(
            bundle=bundle,
            added=tuple(sorted(set(new_files) - set(old_files))),
            removed=tuple(sorted(set(old_files) - set(new_files))),
            changed=tuple(
                sorted(path for path in common if _fingerprint(old_files[path]) != _fingerprint(new_files[path]))
            ),
        )
        if change.added or change.removed or change.changed:
            changes.append(change)
    return tuple(changes)


def diff_to_json(changes: Sequence[BundleChange]) -> str:
    """The diff as deterministic JSON: each changed bundle's added, removed and changed paths."""
    bundles = {
        change.bundle: {"added": list(change.added), "removed": list(change.removed), "changed": list(change.changed)}
        for change in changes
    }
    return to_json({"format": DIFF_FORMAT, "bundles": bundles})


def to_text(changes: Sequence[BundleChange]) -> str:
    """The diff as text: one block per changed bundle, one line per file; a single line when nothing changed."""
    if not changes:
        return "no bundle file changed\n"
    lines: list[str] = []
    for change in changes:
        lines.append(
            f"bundle {change.bundle}: {len(change.added)} added, {len(change.removed)} removed, "
            f"{len(change.changed)} changed"
        )
        for label, paths in (("added", change.added), ("removed", change.removed), ("changed", change.changed)):
            lines.extend(f"  {label:<8}{path}" for path in paths)
    return "\n".join(lines) + "\n"
