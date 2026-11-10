# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check that every ADR in this repository follows ``docs/ADR_POLICY.md``.

    adr_lint.py [root]      lint the ADR folders under ``root`` (default: the current directory)

Each numbered ADR (``NNNN-slug.md``) in :data:`ADR_FOLDERS` must:

* open with ``# NNNN. Title``, the number matching the file name;
* carry no lifecycle field (Status, Date, Last reviewed, Deciders) and no ``## Lifecycle`` footer;
* not be a tombstone: no superseded, deprecated, rejected or obsolete marker (the audit's DOC-04 rule);
* hold the four template sections, in order: Context, Decision, Alternatives Considered, Consequences;
* have a row, a link by path, in each index of :data:`INDEXES` that covers its folder: the root index covers every
  folder, and the engine's architecture page covers the engine's.

An index must not link a numbered ADR that does not exist. No Markdown page may name an ADR that does not exist: a
path such as ``adrs/0004-slug.md`` must resolve in an ADR folder, and "ADR 0004" must be a number some folder uses.
Generated history (``CHANGELOG.md``), fixtures, scratch and the greenfield templates (whose ADR numbers belong to a
new project) are not read. The number check cannot tell folders apart: "ADR 0001" passes while any folder has one.

Exit 0 when all hold, 1 when one fails (each failure is printed), 2 on a usage error. ``make adr-lint`` runs it
inside ``make check``. Standard library only.
"""

from __future__ import annotations

import argparse
import importlib
import os
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
ENGINE_INDEX = "audit/engine/docs/architecture/README.md"
#: Each index and the ADR folders it must list in full.
INDEXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (INDEX, ADR_FOLDERS),
    (ENGINE_INDEX, ("audit/engine/docs/architecture/adrs",)),
)
SECTIONS = ("Context", "Decision", "Alternatives Considered", "Consequences")

ADR_FILE = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
LIFECYCLE_FIELD = re.compile(r"^[ \t>*_-]*(status|date|last reviewed|deciders)[ \t*_]*:", re.IGNORECASE | re.MULTILINE)
LIFECYCLE_FOOTER = re.compile(r"^#{1,6}\s*lifecycle\b", re.IGNORECASE | re.MULTILINE)
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
ADR_NUMBER_MENTION = re.compile(r"\bADR[- ]?(\d{1,4})\b")
ADR_PATH_MENTION = re.compile(r"(?:adrs|decisions)/(\d{4}-[A-Za-z0-9._-]+\.md)")
#: Directories never read for mentions: scratch (off-limits), generated output, fixtures and the greenfield templates.
SKIP_DIRS = {".git", "node_modules", ".venv", "artefacts", "fixtures", "testdata", "dist", "__pycache__"}
SKIP_PREFIXES = ("greenfield/templates/",)
SKIP_FILES = {"CHANGELOG.md"}


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


def index_links(index: Path) -> set[Path]:
    """The files ``index`` links to, resolved."""
    text = index.read_text(encoding="utf-8")
    return {(index.parent / target).resolve() for target in LINK.findall(text) if "://" not in target}


def lint_index(root: Path, index_rel: str, folders: tuple[str, ...], adrs: list[Path]) -> list[str]:
    """``index_rel`` links every ADR in ``folders``, and no numbered ADR there that does not exist."""
    index = root / index_rel
    covered = {(root / folder).resolve() for folder in folders}
    if not index.is_file():
        holds = any(path.resolve().parent in covered for path in adrs)
        return [f"{index_rel}: the ADR index is missing"] if holds else []
    linked = index_links(index)
    failures = [
        f"{path.relative_to(root).as_posix()}:1: no row in {index_rel}"
        for path in adrs
        if path.resolve().parent in covered and path.resolve() not in linked
    ]
    for target in sorted(linked):
        if target.parent in covered and ADR_FILE.match(target.name) and not target.is_file():
            failures.append(f"{index_rel}: links {target.relative_to(root.resolve()).as_posix()}, which does not exist")
    return failures


def markdown_pages(root: Path) -> list[Path]:
    """The Markdown pages read for ADR mentions; skipped folders are pruned before the walk enters them."""
    pages: list[Path] = []
    for directory, subdirs, files in os.walk(root):
        rel_dir = Path(directory).relative_to(root).as_posix()
        subdirs[:] = sorted(
            d for d in subdirs if d not in SKIP_DIRS and not f"{rel_dir}/{d}/".lstrip("./").startswith(SKIP_PREFIXES)
        )
        pages += [Path(directory) / name for name in sorted(files) if name.endswith(".md") and name not in SKIP_FILES]
    return pages


def lint_mentions(root: Path, adrs: list[Path]) -> list[str]:
    """Every mention of an ADR number or path that no ADR folder holds."""
    numbers = {path.name[:4] for path in adrs}
    names = {path.name for path in adrs}
    indexes = {index_rel for index_rel, _ in INDEXES}
    failures: list[str] = []
    for page in markdown_pages(root):
        rel = page.relative_to(root).as_posix()
        # An index's ADR paths are its rows, which lint_index checks; report each dead row once.
        path_mention = None if rel in indexes else ADR_PATH_MENTION
        for number, line in enumerate(page.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for match in ADR_NUMBER_MENTION.finditer(line):
                if match.group(1).zfill(4) not in numbers:
                    failures.append(f"{rel}:{number}: names {match.group(0)}, which no ADR folder holds")
            for match in path_mention.finditer(line) if path_mention else ():
                if match.group(1) not in names:
                    failures.append(f"{rel}:{number}: names {match.group(1)}, which no ADR folder holds")
    return failures


def lint(root: Path) -> list[str]:
    """Every failure under ``root``, each as ``<path>:<line>: <message>``."""
    failures: list[str] = []
    adrs = adr_files(root)
    for path in adrs:
        rel = path.relative_to(root).as_posix()
        failures += [f"{rel}:{problem}" for problem in lint_adr(path, path.read_text(encoding="utf-8"))]
    for index_rel, folders in INDEXES:
        failures += lint_index(root, index_rel, folders, adrs)
    return failures + lint_mentions(root, adrs)


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
