# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The consistency map's gate, in change mode: what a branch changed in the text the checks read (ADR 0012).

``python3 dev/consistency_map.py --base [REF]`` runs the static gate, then this mode against ``REF`` (default
``origin/dev``). The new side is the working tree, or the commit ``--at`` names. Change mode reports four groups:

- ``review`` (never a problem): each section that was moved, renamed, edited or removed in a Markdown file a reads
  entry names, and each other such file that was added, changed or deleted, with the checks that read it. A section
  that moved out of a read's scope says so. A template under ``greenfield/templates/`` is read at the path the
  scaffolder writes it to. The text names a check on a line only when it reads that place through a place of its
  own; the checks that read it only through a broad place (every file of a kind, :func:`broad_places`) are named
  once under the group, and a line with no other reader is counted. ``--verbose`` and the JSON keep them all;
- ``lost-mention`` (a problem): a kept quote's section mentioned the check ID on the base side and no longer does,
  even when the quote still exists somewhere else. The section is followed through the index diff's moves and
  renames, whichever side the map's address names;
- ``left-scope`` (a problem): a file that a reads entry covers was renamed to a path outside that entry's scope;
- ``evidence`` (never a problem, rule 7): a check whose verdict or evidence changed, from the evidence comparison,
  when the check reads a file the diff touched. Changes in other checks are counted only.

Change mode reads the map itself (the ``cmap`` argument of :func:`change_report`) from the working tree only. It
never opens the map at the base ref, so a base that still holds the one file ``dev/consistency-map.json``, a base
that holds the folder ``dev/consistency-map/`` and a base with neither give the same report.

The evidence comparison copies each side's files into a fresh git repository with one commit (a fixed identity and
date), outside the repository, and runs this working tree's engine on both (:mod:`docindex.evidence`). Both sides get
the same engine and the same history, so a change in evidence comes from the text. ``--no-evidence`` skips it.
"""

from __future__ import annotations

import io
import os
import posixpath
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import consistency_map as cm
from docindex import diff as index_diff
from docindex import evidence, extract
from docindex.gitread import GitError, RefTree, Tree, WorkTree

DEFAULT_BASE = cm.DEFAULT_BASE
CHANGE_KINDS = ("lost-mention", "left-scope")
TEMPLATE_PREFIX = "greenfield/templates/"
#: The ``--exclude`` globs of ``make self-audit``, as ``dev/doc_index.py`` passes them.
EXCLUDES: tuple[str, ...] = ("artefacts/*", "dist/*")
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "consistency-map",
    "GIT_AUTHOR_EMAIL": "consistency-map@invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_NAME": "consistency-map",
    "GIT_COMMITTER_EMAIL": "consistency-map@invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}

#: Maps a repository path to the paths a check may read it at (the path itself, and a template's scaffolded path).
Targets = Callable[[str], list[str]]


#: Git variables that point a git call at another repository, index or object store. A git hook sets some of them,
#: so each call drops them and ``-C`` alone names the repository.
_GIT_LOCATION = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_NAMESPACE",
        "GIT_PREFIX",
    }
)
#: For the throwaway copies: no global or system config, so no hooks path, template folder, filter or signing.
_COPY_ENV = {**_GIT_ENV, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _git(root: Path, *args: str, env: Mapping[str, str] | None = None) -> bytes:
    full = {key: value for key, value in os.environ.items() if key not in _GIT_LOCATION}
    full.update(env or {})
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False, env=full)
    except OSError as exc:
        raise GitError(f"git could not run: {exc}") from None
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip() or f"exit {result.returncode}"
        raise GitError(f"git {args[0]} failed: {message}")
    return result.stdout


# --- Which checks read a path -----------------------------------------------------------------------------------


def scaffold_targets(path: str) -> list[str]:
    """``path`` and, for a greenfield template, the path the scaffolder writes it to (:data:`Targets`)."""
    if not path.startswith(TEMPLATE_PREFIX):
        return [path]
    bootstrap = cm.bootstrap_module()
    target = bootstrap.target_path_for(path[len(TEMPLATE_PREFIX) :])
    return [path] if target is None else [path, target]


def readers(path: str, reads: Sequence[dict[str, Any]], targets: Targets = scaffold_targets) -> list[str]:
    """The checks whose reads cover ``path``, at any of its targets, sorted."""
    places = targets(path)
    return sorted(
        {read["check"] for read in reads if any(cm.place_overlaps(p, w) for p in places for w in read["where"])}
    )


#: A place is broad when the tracked files it matches carry at least this share of the tree's distinct file names.
#: On this repository the broad places match 9% or more of the names (``docs/**/*.md``: 55 of 614) and the next
#: place 2% (``docs/architecture/**``: 13), so the line falls in the gap.
BROAD_SHARE = 0.05
_WILDCARDS = frozenset("*?[")

#: A read place as (path, scope).
Place = tuple[str, str]


def broad_places(reads: Sequence[dict[str, Any]], files: Sequence[str], share: float = BROAD_SHARE) -> set[Place]:
    """The read places that cover every file of a kind in ``files``, not one named file.

    A place is broad when its scope is ``glob`` or ``any-depth``, its path holds a wildcard, and the files it
    matches carry more than one distinct file name and at least ``share`` of all the distinct names in ``files``.
    Names are counted, not files: a name read at any depth (``package.json``) is one file wherever it sits, however
    many fixtures copy it.
    """
    names = {posixpath.basename(path) for path in files}
    floor = share * len(names)
    broad: set[Place] = set()
    seen: set[Place] = set()
    for read in reads:
        for where in read["where"]:
            place = (str(where["path"]), str(where["scope"]))
            if place in seen:
                continue
            seen.add(place)
            if place[1] not in ("glob", "any-depth") or not _WILDCARDS & set(place[0]):
                continue
            matched = {posixpath.basename(path) for path in files if cm.place_overlaps(path, where)}
            if len(matched) > 1 and len(matched) >= floor:
                broad.add(place)
    return broad


def broad_readers(
    paths: Iterable[str], reads: Sequence[dict[str, Any]], broad: set[Place], targets: Targets = scaffold_targets
) -> set[str]:
    """The checks that read ``paths`` through broad places only: no place of theirs that covers a path is specific."""
    places = [p for path in paths for p in targets(path)]
    out: set[str] = set()
    specific: set[str] = set()
    for read in reads:
        for where in read["where"]:
            if any(cm.place_overlaps(p, where) for p in places):
                if (str(where["path"]), str(where["scope"])) in broad:
                    out.add(read["check"])
                else:
                    specific.add(read["check"])
    return out - specific


def _file(address: str) -> str:
    return address.partition("#")[0]


# --- The index diff and the file changes ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileChange:
    """One file in ``git diff --name-status``: its status letter, its old path and its new path."""

    status: str
    old: str
    new: str


def _pair_untracked(root: Path, base: str, changes: list[FileChange], untracked: list[str]) -> list[FileChange]:
    """Pair each deleted file with an untracked file of the same content as a rename, as a plain ``mv`` leaves them.

    ``git diff`` sees only tracked files, so a move that is not staged shows as a deletion and a new file.
    """
    deleted = {change.old: change for change in changes if change.status == "D"}
    if not deleted or not untracked:
        return changes + [FileChange("A", path, path) for path in untracked]
    blobs: dict[str, str] = {}
    for path in deleted:
        try:
            blobs.setdefault(_git(root, "rev-parse", f"{base}:{path}").decode().strip(), path)
        except GitError:
            continue
    hashes = _git(root, "hash-object", "--", *untracked).decode().split()
    out = list(changes)
    for path, blob in zip(untracked, hashes, strict=True):
        old = blobs.pop(blob, None)
        if old is None:
            out.append(FileChange("A", path, path))
        else:
            out.remove(deleted[old])
            out.append(FileChange("R", old, path))
    return out


def file_changes(root: Path, base: str, at: str | None) -> list[FileChange]:
    """The files that differ from ``base`` to ``at`` (or the working tree, with its untracked files), renames found.

    In the working tree, a deleted tracked file and an untracked file with the same content count as a rename."""
    args = ["diff", "-M", "--name-status", "-z", base] + ([at] if at is not None else [])
    fields = [part for part in _git(root, *args).decode("utf-8", errors="replace").split("\0") if part]
    changes: list[FileChange] = []
    index = 0
    while index < len(fields):
        status = fields[index][0]
        if status in "RC":
            changes.append(FileChange(status, fields[index + 1], fields[index + 2]))
            index += 3
        else:
            changes.append(FileChange(status, fields[index + 1], fields[index + 1]))
            index += 2
    if at is None:
        others = _git(root, "ls-files", "-z", "--others", "--exclude-standard").decode("utf-8", errors="replace")
        changes = _pair_untracked(root, base, changes, [path for path in others.split("\0") if path])
    return sorted(changes, key=lambda change: (change.new, change.old))


def _scope_note(old: str, new: str, reads: Sequence[dict[str, Any]], targets: Targets) -> str:
    left = sorted(set(readers(old, reads, targets)) - set(readers(new, reads, targets)))
    return f" (leaves the scope of {', '.join(left)})" if left else ""


@dataclass(frozen=True)
class Review:
    """One change a reviewer should read: its line, the checks that read the changed place, and which of them read
    it through broad places only (:func:`broad_places`). ``place`` is the line without its checks."""

    line: str
    checks: tuple[str, ...]
    place: str = ""
    broad: tuple[str, ...] = ()

    @property
    def specific(self) -> tuple[str, ...]:
        """The checks that read the changed place through a place of their own, not a broad one."""
        return tuple(check for check in self.checks if check not in self.broad)


def reviews(
    found: index_diff.IndexDiff,
    files: Sequence[FileChange],
    reads: Sequence[dict[str, Any]],
    targets: Targets = scaffold_targets,
    broad: set[Place] | None = None,
) -> list[Review]:
    """The sections and files a reads entry names that the change moved, renamed, edited or removed.

    ``broad`` is the set of broad places; each review marks the checks that read it through them only."""
    out: list[Review] = []

    def add(what: str, old: str, new: str | None = None) -> None:
        checks = set(readers(_file(old), reads, targets))
        if new is not None:
            checks |= set(readers(_file(new), reads, targets))
        if not checks:
            return
        place = old if new is None or new == old else f"{old} -> {new}"
        note = _scope_note(_file(old), _file(new), reads, targets) if new is not None else ""
        paths = {_file(old)} | ({_file(new)} if new is not None else set())
        wide = broad_readers(paths, reads, broad, targets) if broad else set()
        head = f"{what} {place}{note}"
        out.append(
            Review(
                f"{head}: read by {', '.join(sorted(checks))}",
                tuple(sorted(checks)),
                head,
                tuple(sorted(wide & checks)),
            )
        )

    for moved in found.moved:
        add("moved", moved.old, moved.new)
    for renamed in found.renamed:
        add("renamed", renamed.old, renamed.new)
    for edited in found.edited:
        add("edited", edited.old_address, edited.address)
    for removed in found.removed:
        add("removed", removed.address)
    sectioned = {
        _file(address)
        for address in (
            *(m.old for m in found.moved),
            *(m.new for m in found.moved),
            *(r.old for r in found.renamed),
            *(r.new for r in found.renamed),
            *(e.address for e in found.edited),
            *(e.old_address for e in found.edited),
            *(node.address for node in found.removed),
        )
    }
    for change in files:
        if change.status in "MRCT" and change.old in sectioned and change.new in sectioned:
            continue  # its sections are in the index diff above; a file the index does not parse is listed below
        if change.status == "A":
            add("added file", change.new)
        elif change.status == "D":
            add("deleted file", change.old)
        elif change.status in "RC":
            add("renamed file" if change.status == "R" else "copied file", change.old, change.new)
        else:
            add("changed file", change.old, change.new)
    return out


def left_scope(
    files: Sequence[FileChange], reads: Sequence[dict[str, Any]], targets: Targets = scaffold_targets
) -> list[tuple[str, str]]:
    """Each renamed file that a reads entry covered at its old path and does not cover at its new path, as (the
    problem, the check)."""
    problems: list[tuple[str, str]] = []
    for change in files:
        if change.status != "R":
            continue
        new_places = targets(change.new)
        for read in reads:
            for where in read["where"]:
                was = any(cm.place_overlaps(p, where) for p in targets(change.old))
                if was and not any(cm.place_overlaps(p, w) for p in new_places for w in read["where"]):
                    line = (
                        f"{change.old} -> {change.new} leaves the scope of {read['check']} "
                        f"({where['path']}, {where['scope']})"
                    )
                    problems.append((line, read["check"]))
                    break
    return problems


# --- Lost mentions -------------------------------------------------------------------------------------------------


def _address_maps(found: index_diff.IndexDiff) -> tuple[dict[str, str], dict[str, str]]:
    forward: dict[str, str] = {}
    for moved in found.moved:
        forward[moved.old] = moved.new
    for renamed in found.renamed:
        forward[renamed.old] = renamed.new
    for edited in found.edited:
        if edited.old_address != edited.address:
            forward[edited.old_address] = edited.address
    return forward, {new: old for old, new in forward.items()}


def _follow(address: str, mapping: Mapping[str, str]) -> str:
    """``address`` through ``mapping``: the longest mapped ancestor (or the address itself) is replaced."""
    path, _, chain = address.partition("#")
    parts = chain.split("/") if chain else []
    for size in range(len(parts), 0, -1):
        prefix = f"{path}#{'/'.join(parts[:size])}"
        if prefix in mapping:
            rest = "/".join(parts[size:])
            return f"{mapping[prefix]}/{rest}" if rest else mapping[prefix]
    return address


def _mentions(address: str, check: str, read: cm.Reader) -> bool | None:
    """Whether the section at ``address`` mentions ``check``; ``None`` when the file or the section is gone."""
    path = _file(address)
    try:
        text = read(path)
    except (OSError, UnicodeDecodeError):
        return None
    if text is None:
        return None
    body = cm.section_text(path, address, text)
    if body is None:
        return None
    return re.search(rf"\b{re.escape(check)}\b", body) is not None


def lost_mentions(
    keeps: Iterable[dict[str, Any]], found: index_diff.IndexDiff, old_read: cm.Reader, new_read: cm.Reader
) -> list[str]:
    """Each kept quote whose section mentioned the check on the base side and does not on the new side.

    The map's address may name either side: an address that is not on the base side is followed back through the
    diff's moves and renames, and one that is not on the new side is followed forward.
    """
    forward, backward = _address_maps(found)
    problems = []
    for keep in keeps:
        if keep["status"] != "kept":
            continue
        check, address = keep["check"], keep["home"]["section"]
        old_address = address
        if _mentions(address, check, old_read) is None:
            old_address = _follow(address, backward)
        if not _mentions(old_address, check, old_read):
            continue
        new_address = address
        now = _mentions(address, check, new_read)
        if now is None:
            new_address = _follow(old_address, forward)
            now = _mentions(new_address, check, new_read)
        if now:
            continue
        where = "is gone" if now is None else "no longer mentions it"
        moved = f" (was {old_address})" if old_address != new_address else ""
        problems.append(f"{keep['move']} -> {check}: {new_address}{moved} {where}")
    return problems


# --- The evidence comparison ---------------------------------------------------------------------------------------


def _safe_extract(data: bytes, dest: Path) -> None:
    """Unpack a ``git archive`` tar into ``dest``, refusing a member that would land outside it.

    Python 3.11.4 and later have the ``data`` filter; before it, each member's path is checked by hand.
    """
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        if hasattr(tarfile, "data_filter"):
            archive.extractall(dest, filter="data")
            return
        top = dest.resolve()
        for member in archive.getmembers():
            if not (top / member.name).resolve().is_relative_to(top) or member.islnk() or member.isdev():
                raise GitError(f"git archive holds an unsafe member: {member.name}")
        archive.extractall(dest)  # noqa: S202  (every member checked above)


def materialise(root: Path, ref: str | None, dest: Path) -> Path:
    """Copy the files of ``root`` at ``ref`` (or the working tree's tracked and untracked, not ignored, files) into
    the new folder ``dest`` and commit them there with a fixed identity and date."""
    dest.mkdir(parents=True)
    if ref is not None:
        _safe_extract(_git(root, "archive", "--format=tar", ref), dest)
    else:
        listed = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        for path in sorted({p for p in listed.decode("utf-8", errors="replace").split("\0") if p}):
            source = root / path
            if source.is_file() or source.is_symlink():
                (dest / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest / path, follow_symlinks=False)
    _git(dest, "init", "--quiet", "--template=", env=_COPY_ENV)
    _git(dest, "add", "-A", "-f", env=_COPY_ENV)
    commit = ["commit", "--quiet", "--no-gpg-sign", "--no-verify", "--allow-empty", "-m", "consistency map side"]
    _git(dest, *commit, env=_COPY_ENV)
    return dest


@dataclass(frozen=True)
class EvidenceReport:
    """The evidence comparison of the two sides: the changes of checks the diff's reads cover, and the rest."""

    overlapping: tuple[evidence.CheckChange, ...] = ()
    others: tuple[evidence.CheckChange, ...] = ()


def _one_target(copy: Path) -> Callable[[str, Path], list[evidence.Target]]:
    """The ``targets`` of an evidence project that audits one copied tree, with the self-audit excludes."""

    def targets(_kind: str, _work: Path) -> list[evidence.Target]:
        return [evidence.Target(name="repo", path=copy, excludes=EXCLUDES)]

    return targets


def compare_evidence(
    root: Path,
    base: str,
    at: str | None,
    engine_dir: Path,
    runner: evidence.Runner = evidence.run_command,
) -> evidence.Comparison:
    """Run the engine on both sides, each copied into a temporary repository, and compare the runs."""
    with tempfile.TemporaryDirectory(prefix="consistency-map-") as scratch:
        work = Path(scratch)
        folders: dict[str, Path] = {}
        for side, ref in (("old", base), ("new", at)):
            try:
                copy = materialise(root, ref, work / "trees" / side)
            except (GitError, OSError, tarfile.TarError) as exc:
                raise evidence.EvidenceError(f"cannot copy the {side} side: {exc}") from exc
            project = evidence.Project(engine_dir=engine_dir, repo=copy, targets=_one_target(copy), runner=runner)
            folders[side] = work / "runs" / side
            evidence.run(folders[side], "repo", project, work / "targets" / side)
        _old, _new, comparison = evidence.compare(folders["old"], folders["new"])
    return comparison


def split_evidence(comparison: evidence.Comparison, checks: set[str]) -> EvidenceReport:
    """The changes of the checks in ``checks``, and the other changes."""
    return EvidenceReport(
        overlapping=tuple(change for change in comparison.changes if change.check in checks),
        others=tuple(change for change in comparison.changes if change.check not in checks),
    )


# --- The change report ---------------------------------------------------------------------------------------------


@dataclass
class ChangeReport:
    """Everything change mode found."""

    base: str
    at: str | None
    reviews: list[Review] = field(default_factory=list)
    problems: dict[str, list[str]] = field(default_factory=lambda: {kind: [] for kind in CHANGE_KINDS})
    scope_checks: set[str] = field(default_factory=set)
    evidence: EvidenceReport | None = None

    def checks(self) -> set[str]:
        """The checks whose reads the change touched."""
        return {check for review in self.reviews for check in review.checks} | self.scope_checks


def change_report(
    cmap: dict[str, Any],
    root: Path,
    base: str,
    at: str | None,
    config: Mapping[str, Any],
    *,
    engine_dir: Path | None = cm.ENGINE,
    targets: Targets = scaffold_targets,
    runner: evidence.Runner = evidence.run_command,
) -> ChangeReport:
    """Change mode from ``base`` to ``at`` (``None``: the working tree) in the repository at ``root``.

    ``engine_dir`` ``None`` skips the evidence comparison. Raises :class:`GitError` for a ref that names no commit.
    """
    old_tree = RefTree(root, base)
    new_tree: Tree = RefTree(root, at) if at is not None else WorkTree(root)
    found = index_diff.compare(
        extract.extract(old_tree, config).index,
        extract.extract(new_tree, config).index,
        old_body=index_diff.body_hashes(old_tree),
        new_body=index_diff.body_hashes(new_tree),
    )
    files = file_changes(root, base, at)
    report = ChangeReport(base=base, at=at)
    report.reviews = reviews(found, files, cmap["reads"], targets, broad_places(cmap["reads"], new_tree.files()))
    scope = left_scope(files, cmap["reads"], targets)
    report.problems["left-scope"] = [line for line, _check in scope]
    report.scope_checks = {check for _line, check in scope}
    report.problems["lost-mention"] = lost_mentions(cmap["keeps"], found, _reader(old_tree), _reader(new_tree))
    if engine_dir is not None:
        report.evidence = split_evidence(compare_evidence(root, base, at, engine_dir, runner), report.checks())
    return report


def _reader(tree: Tree) -> cm.Reader:
    def read(path: str) -> str:
        text = tree.read(path)
        if text is None:
            raise FileNotFoundError(path)
        return text

    return read


def _change_line(change: evidence.CheckChange) -> str:
    if change.kind == "verdict":
        head = f"{change.check}: verdict {change.old_verdict} -> {change.new_verdict}"
    elif change.kind == "evidence":
        head = f"{change.check}: same verdict {change.new_verdict}, evidence changed"
    else:
        head = f"{change.check}: check {change.kind}"
    return head + (f": {', '.join(change.evidence)}" if change.evidence else "")


def _review_lines(found: Sequence[Review], verbose: bool) -> list[str]:
    """The review group's lines: each review with its specific checks, the broad checks once.

    A review whose checks are all broad says nothing a diff does not say, so it counts in one line; ``verbose``
    lists it, and names the broad checks on each line.
    """
    lines: list[str] = []
    folded = 0
    for review in found:
        specific = ", ".join(review.specific)
        wide = ", ".join(review.broad)
        if not review.broad:
            lines.append(f"  {review.line}")
        elif not specific:
            folded += 1
            if verbose:
                lines.append(f"  {review.place}: read only by broad checks {wide}")
        else:
            lines.append(f"  {review.place}: read by {specific}" + (f"; and by broad checks {wide}" if verbose else ""))
    if folded and not verbose:
        lines.append(f"  and {folded} more read only by broad checks (--verbose lists them)")
    broad = sorted({check for review in found for check in review.broad})
    if broad:
        lines.append(f"  broad checks, which read every file of a kind: {', '.join(broad)}")
    return lines


def format_text(report: ChangeReport, verbose: bool = False) -> str:
    target = report.at if report.at is not None else "the working tree"
    lines = [f"change mode: {report.base} -> {target}"]
    lines.append(f"review (sections and files a read covers; not a problem): {len(report.reviews)}")
    lines += _review_lines(report.reviews, verbose)
    for kind in CHANGE_KINDS:
        lines.append(f"{kind}: {len(report.problems[kind])}")
        lines += [f"  {item}" for item in report.problems[kind]]
    if report.evidence is None:
        lines.append("evidence: not compared (--no-evidence)")
    else:
        lines.append(f"evidence (reported, never a problem): {len(report.evidence.overlapping)}")
        lines += [f"  {_change_line(change)}" for change in report.evidence.overlapping]
        if report.evidence.others:
            lines.append(f"  and {len(report.evidence.others)} changed check(s) whose reads the change does not touch")
    total = sum(len(items) for items in report.problems.values())
    lines.append(f"consistency map, change mode: {total} problem(s)")
    return "\n".join(lines) + "\n"


def _change_dict(change: evidence.CheckChange) -> dict[str, Any]:
    return {
        "check": change.check,
        "evidence": list(change.evidence),
        "kind": change.kind,
        "new_verdict": change.new_verdict,
        "old_verdict": change.old_verdict,
        "report": change.report,
    }


def to_dict(report: ChangeReport) -> dict[str, Any]:
    data: dict[str, Any] = {
        "base": report.base,
        "at": report.at,
        "review": [
            {"broad": list(review.broad), "checks": list(review.checks), "line": review.line}
            for review in report.reviews
        ],
        **report.problems,
    }
    if report.evidence is not None:
        data["evidence"] = {
            "overlapping": [_change_dict(change) for change in report.evidence.overlapping],
            "others": [_change_dict(change) for change in report.evidence.others],
        }
    return data


def project_config() -> dict[str, Any]:
    """This repository's document-index config, as ``dev/doc_index.py`` loads it."""
    import doc_index

    return doc_index.full_config()


__all__ = [
    "BROAD_SHARE",
    "CHANGE_KINDS",
    "DEFAULT_BASE",
    "ChangeReport",
    "EvidenceReport",
    "FileChange",
    "Review",
    "broad_places",
    "broad_readers",
    "change_report",
    "compare_evidence",
    "file_changes",
    "format_text",
    "left_scope",
    "lost_mentions",
    "materialise",
    "project_config",
    "readers",
    "reviews",
    "scaffold_targets",
    "split_evidence",
    "to_dict",
]
