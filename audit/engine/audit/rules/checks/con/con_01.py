# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CON-01: Allow/deny artifact present."""

from __future__ import annotations

from itertools import accumulate

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import entry_instruction_file, prohibitions_section
from audit.scan import Inventory
from audit.target import Target
from audit.rules.payloads import PathList
from audit.rules.checks.con._shared import _finding, _names_directory, _outcome, _split_pattern, _unknown

SPEC = declare(
    "CON-01",
    "Allow/deny artifact present",
    "B",
    Severity.BLOCKER,
    rule="The prohibitions section of the instruction file is the deny list (decision 0001): it names at least "
    "one path or pattern, in a code span, that matches a file or directory of the repository.",
)


# ===========================================================================
# CON-01 — the deny list names paths
# ===========================================================================

_GLOB_CHARS = "*?["
#: A code span with one of these in it is a command, a flag or an expression, not a path.
_NOT_A_PATH_CHARS = frozenset(" \t$|;&<>()'\"=")


def _path_like(span: str) -> bool:
    """Whether a code span reads as a path or a pattern: no command syntax, and a slash, a glob or a dot in it."""
    if not span or span.startswith("-") or any(char in _NOT_A_PATH_CHARS for char in span):
        return False
    return "/" in span or any(char in span for char in _GLOB_CHARS) or "." in span


def _repository_paths(inventory: Inventory) -> list[str]:
    """Every file of the scan and every directory above one, as paths from the root."""
    paths: set[str] = set()
    for entry in inventory.files:
        paths.update(accumulate(entry.rel.split("/"), lambda above, name: f"{above}/{name}"))
    return sorted(paths)


def _exists_in_repository(span: str, target: Target, paths: list[str]) -> bool:
    """Whether the path or pattern matches a file or directory of the repository.

    The scan leaves out what an ignore rule or the hard excludes name (``node_modules/``, ``dist/``), and those
    are the paths a deny list most often names, so a literal path is also looked for on disk.
    """
    if any(_names_directory(rel, span) for rel in paths):
        return True
    core, _anchored, _anywhere = _split_pattern(span)
    return bool(core) and not any(char in core for char in _GLOB_CHARS) and (target.path / core).exists()


def _listed(items: list[str], limit: int = 8) -> str:
    shown = ", ".join(items[:limit])
    extra = len(items) - limit
    return f"{shown} (+{extra} more)" if extra > 0 else shown


def check_con01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")
    section = prohibitions_section(text)
    if section is None:
        return _unknown(spec, f"{name} has no prohibitions section to read; AGT-07 owns that finding")

    paths = _repository_paths(inventory)
    named: list[tuple[int, str]] = []
    for line, span in section.code_spans():
        if (line, span) not in named and (_path_like(span) or _exists_in_repository(span, target, paths)):
            named.append((line, span))
    names = [span for _line, span in named]
    present = [span for span in dict.fromkeys(names) if _exists_in_repository(span, target, paths)]
    data = PathList(paths=tuple(dict.fromkeys(names)))

    if present:
        return _outcome(
            spec,
            Verdict.PASS,
            f"the prohibitions section of {name} names paths that exist: {_listed(present)}",
            data=data,
        )
    if named:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"the prohibitions section of {name} names {_listed(list(dict.fromkeys(names)))}, and none of it matches "
            "a file or directory of the repository",
            [
                _finding(
                    spec,
                    "trust the deny list to bound what an agent may change",
                    f"none of the paths the prohibitions section of {name} names "
                    f"({_listed(list(dict.fromkeys(names)))}) matches a file or directory of this repository",
                    Verdict.PARTIAL,
                    [Evidence(name, line=line, note=span) for line, span in named[:12]],
                    "Name paths that exist in this repository, or patterns that match some of it, in code spans "
                    f"in the prohibitions section of {name}.",
                )
            ],
            data=data,
        )
    return _outcome(
        spec,
        Verdict.FAIL,
        f"the prohibitions section of {name} names no path or pattern",
        [
            _finding(
                spec,
                "trust the deny list to bound what an agent may change",
                f"the prohibitions section of {name} names no path or pattern in a code span",
                Verdict.FAIL,
                [Evidence(name, line=line, note=title) for line, title in section.sections],
                "Name each path an agent must not change in a code span in the prohibitions section, for example "
                "`dist/`, `tests/` and `.env`.",
            )
        ],
        data=data,
    )
