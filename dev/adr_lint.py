# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check that every ADR in this repository follows ``docs/ADR_POLICY.md``.

    adr_lint.py [root]      lint the ADR folders under ``root`` (default: the current directory)

Each numbered ADR (``NNNN-slug.md``) in :data:`ADR_FOLDERS` must:

* open with ``# NNNN. Title``, the number matching the file name;
* carry no lifecycle field (Status, Date, Last reviewed, Deciders) and no ``## Lifecycle`` footer;
* not be a tombstone: no superseded, deprecated, rejected or obsolete marker (the audit's DOC-04 rule);
* hold the four template sections, in order: Context, Decision, Alternatives Considered, Consequences;
* have a row in the root index, :data:`INDEX`, which links it by path.

The index must not link a numbered ADR that does not exist. Exit 0 when all hold, 1 when one fails (each failure is
printed), 2 on a usage error. ``make adr-lint`` runs it inside ``make check``. Standard library only.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path
from typing import Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audit" / "engine"))

#: The audit's DOC-04 tombstone rule, so this lint and the audit agree. Loaded at run time: a static import would make
#: strict mypy on ``dev/`` type-check the whole engine, which is outside the typecheck ratchet.
_adr_tombstone: Callable[[str], int | None] = importlib.import_module("audit.rules.checks.doc")._adr_tombstone

ADR_FOLDERS = (
    "docs/architecture/adrs",
    "spec/decisions",
    "audit/docs/architecture/adrs",
    "implement/docs/architecture/adrs",
    "audit/engine/docs/architecture/adrs",
)
INDEX = "docs/architecture/adrs/README.md"
SECTIONS = ("Context", "Decision", "Alternatives Considered", "Consequences")

ADR_FILE = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
LIFECYCLE_FIELD = re.compile(r"^[ \t>*_-]*(status|date|last reviewed|deciders)[ \t*_]*:", re.IGNORECASE | re.MULTILINE)
LIFECYCLE_FOOTER = re.compile(r"^#{1,6}\s*lifecycle\b", re.IGNORECASE | re.MULTILINE)
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def adr_files(root: Path) -> list[Path]:
    """Every numbered ADR in :data:`ADR_FOLDERS`, sorted by path."""
    found: list[Path] = []
    for folder in ADR_FOLDERS:
        directory = root / folder
        if directory.is_dir():
            found += [p for p in directory.iterdir() if p.is_file() and ADR_FILE.match(p.name)]
    return sorted(found)


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def lint_adr(path: Path, text: str) -> list[str]:
    """The policy failures of one ADR, each as ``<line>: <message>``."""
    problems: list[str] = []
    number = path.name[:4]
    first = text.splitlines()[0] if text else ""
    if not first.startswith(f"# {number}. "):
        problems.append(f"1: the title must open with '# {number}. '")
    for match in LIFECYCLE_FIELD.finditer(text):
        problems.append(f"{line_of(text, match.start())}: lifecycle field '{match.group(1)}'; git holds it")
    for match in LIFECYCLE_FOOTER.finditer(text):
        problems.append(f"{line_of(text, match.start())}: lifecycle section; the policy page holds the rules")
    tombstone = _adr_tombstone(text)
    if tombstone is not None:
        problems.append(f"{tombstone}: retired-ADR marker; delete the ADR or overwrite it in place")
    headings = re.findall(r"^## (.+?)\s*$", text, re.MULTILINE)
    present = [h for h in headings if h in SECTIONS]
    if present != list(SECTIONS):
        missing = [s for s in SECTIONS if s not in headings]
        detail = f"missing {', '.join(missing)}" if missing else "out of order"
        problems.append(f"1: sections must be {', '.join(SECTIONS)} ({detail})")
    return problems


def index_links(root: Path) -> set[Path]:
    """The files the root index links to, resolved."""
    index = root / INDEX
    text = index.read_text(encoding="utf-8")
    return {(index.parent / target).resolve() for target in LINK.findall(text) if "://" not in target}


def lint(root: Path) -> list[str]:
    """Every failure under ``root``, each as ``<path>:<line>: <message>``."""
    failures: list[str] = []
    adrs = adr_files(root)
    for path in adrs:
        rel = path.relative_to(root).as_posix()
        failures += [f"{rel}:{problem}" for problem in lint_adr(path, path.read_text(encoding="utf-8"))]

    if not (root / INDEX).is_file():
        return failures + [f"{INDEX}: the ADR index is missing"]
    linked = index_links(root)
    for path in adrs:
        if path.resolve() not in linked:
            failures.append(f"{path.relative_to(root).as_posix()}:1: no row in {INDEX}")
    folders = {(root / folder).resolve() for folder in ADR_FOLDERS}
    for target in sorted(linked):
        if target.parent in folders and ADR_FILE.match(target.name) and not target.is_file():
            failures.append(f"{INDEX}: links {target.relative_to(root.resolve()).as_posix()}, which does not exist")
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", type=Path, help="the repository root")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"adr_lint: not a directory: {args.root}", file=sys.stderr)
        return 2

    failures = lint(root)
    for failure in failures:
        print(f"adr_lint: {failure}", file=sys.stderr)
    if failures:
        print("adr_lint: the rules are in docs/ADR_POLICY.md", file=sys.stderr)
        return 1
    print(f"adr_lint: {len(adr_files(root))} ADR(s) follow docs/ADR_POLICY.md and are indexed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
