# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check that every repository path a recipe page names in backticks still exists.

    recipe_paths.py <root>

``<root>`` is a git work tree of this framework repository. A path written in backticks, such as
``audit/engine/audit/rules/checks/nav/``, keeps no link a renderer or ``dev/recipe_lint.py`` could follow, so it goes
stale silently when its file moves. This check reads the pages below and fails on each such path that names nothing.

**The pages.** The Markdown files git lists (tracked, or untracked and not ignored, so a new page counts before
``git add``) in two groups:

- *Recipe pages* (:data:`RECIPE_PAGES`): ``audit/SKILL.md``, ``audit/checks/``, ``audit/stacks/``,
  ``audit/prompts/``, ``implement/SKILL.md``, ``implement/playbooks/`` and ``implement/prompts/``. They mostly talk
  about the audited repository, so only a path into a folder no audited repository has (:data:`FRAMEWORK_FOLDERS`)
  is checked. ``docs/missing.md`` there is the target's page and is ignored.
- *Repository pages*: every ``AGENTS.md``, apart from the fixtures and the greenfield templates (their paths belong
  to another repository). A path into any top-level folder is checked.

``docs/`` is not read: its pages name target paths, branch names and example paths in backticks too often to tell
apart without an allowlist. The history pages (:data:`HISTORY`) are never read: they name paths as they were then.

**A path.** Each whitespace-separated word of an inline code span outside a fenced block, after its surrounding
quotes and trailing punctuation are dropped. It counts only when its first segment is a top-level folder that git
lists. A ``#fragment`` or a ``:line`` suffix is dropped. A word with a glob or placeholder character (``* ? [ ] { }
< > $``), an ellipsis or an ``NN`` placeholder segment is not a path. Neither is a word whose first segment is no
top-level folder (``scripts/tools/``, ``tests/``): never guessed, never failed.

**Where it resolves.** From ``<root>``, with two engine-relative forms resolved under ``audit/engine/``: a word in a
page under ``audit/engine/`` (the engine's pages write paths from its folder) and ``audit/<name>/...`` where
``<name>`` is an entry of the engine's package ``audit/engine/audit/`` and not of the root ``audit/`` (as
``audit/rules/``). It exists when git lists it or a file below it. A missing path that git ignores (build output
such as ``dev/dist/skills/``, scratch under ``artefacts/``) is not a failure.

Exit 0 when every path resolves, 2 with each stale path as ``page:line: message``, 1 on a usage error (no git work
tree). ``make recipe-paths`` runs it inside ``make check``. Nothing is written. Standard library only; ``_common``
is imported from ``audit/tools/``, which this module puts on ``sys.path`` because ``dev/`` is not a package.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Sequence

_AUDIT_TOOLS = str(Path(__file__).resolve().parent.parent / "audit" / "tools")
if _AUDIT_TOOLS not in sys.path:
    sys.path.insert(0, _AUDIT_TOOLS)

import _common  # noqa: E402

INFO = _common.ToolInfo(
    name="recipe_paths",
    summary="Check that every repository path the recipe pages and AGENTS.md files name in backticks exists.",
    synopsis=("recipe_paths.py <root>",),
    writes="nothing",
)

#: The recipe pages, as a file or a folder prefix relative to <root>.
RECIPE_PAGES = (
    "audit/SKILL.md",
    "audit/checks/",
    "audit/stacks/",
    "audit/prompts/",
    "implement/SKILL.md",
    "implement/playbooks/",
    "implement/prompts/",
)
#: The top-level folders a recipe page can only mean in this repository: an audited repository has none of them.
FRAMEWORK_FOLDERS = frozenset({"audit", "implement", "greenfield", "dev"})
#: Pages that name paths as they were when written, never read.
HISTORY = frozenset({"CHANGELOG.md", "audit/engine/docs/reference/changelog.md"})
#: An AGENTS.md below one of these is another repository's: fixtures and the greenfield templates.
FOREIGN_SEGMENTS = frozenset({"fixtures"})
FOREIGN_PREFIXES = ("greenfield/templates/",)
ENGINE = "audit/engine"
ENGINE_PACKAGE = "audit/engine/audit"

_FENCE = re.compile(r"^\s*(```+|~~~+)")
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_NOT_A_PATH = re.compile(r"[*?\[\]{}<>$]|\.\.\.|(?:^|/)N{2,}")
_SUFFIX = re.compile(r"(?:#.*|:L?[0-9][0-9L-]*)\Z")
_STRIP_LEAD = "\"'("
_STRIP_TRAIL = "\"'.,;:)"


@dataclass(frozen=True)
class Tree:
    """What git lists under <root>: the files, every folder above one, and the entries of the two audit folders."""

    files: frozenset[str]
    folders: frozenset[str]

    @classmethod
    def from_paths(cls, paths: Sequence[str]) -> Tree:
        folders: set[str] = set()
        for path in paths:
            parts = path.split("/")
            folders.update("/".join(parts[:end]) for end in range(1, len(parts)))
        return cls(frozenset(paths), frozenset(folders))

    def exists(self, path: str) -> bool:
        return path in self.files or path in self.folders

    def top_level(self) -> frozenset[str]:
        return frozenset(folder for folder in self.folders if "/" not in folder)

    def entries(self, folder: str) -> frozenset[str]:
        prefix = folder + "/"
        return frozenset(path[len(prefix) :].split("/")[0] for path in self.files if path.startswith(prefix))


@dataclass
class Stale:
    """A path that resolves to nothing, before git's ignore rules have had their say."""

    page: str
    line: int
    word: str
    resolved: str


@dataclass
class Outcome:
    stale: list[Stale] = field(default_factory=list)
    checked: int = 0


def git_listed(root: Path) -> list[str]:
    """Every file git lists under `root` (tracked, or untracked and not ignored) that is on disk, sorted."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise _common.UsageError(f"git could not be run: {exc.strerror or exc}") from exc
    if result.returncode != 0:
        raise _common.UsageError(f"{root} is not a git work tree", hint="run it on a clone of this repository")
    names = {name for name in result.stdout.decode("utf-8").split("\0") if name}
    return sorted(name for name in names if (root / name).is_file())


def git_ignored(root: Path, paths: Sequence[str]) -> frozenset[str]:
    """The members of `paths` that git's ignore rules match, whether or not they exist."""
    if not paths:
        return frozenset()
    result = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--no-index", "--stdin"],
        input="\n".join(paths) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    return frozenset(line for line in result.stdout.splitlines() if line)


def page_kind(page: str) -> str | None:
    """`"recipe"`, `"repository"` or `None` (not read) for a listed file, relative to <root>."""
    if not page.endswith(".md") or page in HISTORY:
        return None
    if any(page == entry or (entry.endswith("/") and page.startswith(entry)) for entry in RECIPE_PAGES):
        return "recipe"
    if PurePosixPath(page).name != "AGENTS.md":
        return None
    if FOREIGN_SEGMENTS & set(page.split("/")[:-1]) or page.startswith(FOREIGN_PREFIXES):
        return None
    return "repository"


def code_words(lines: Sequence[str]) -> list[tuple[int, str]]:
    """`(line number, word)` for each whitespace-separated word of an inline code span outside a fenced block."""
    found: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(lines, start=1):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for span in _CODE_SPAN.finditer(line):
            found.extend((number, word) for word in span.group(2).split())
    return found


def as_path(word: str) -> str | None:
    """The repository-relative path a word spells, or `None` when it is no candidate path at all."""
    if _NOT_A_PATH.search(word):
        return None
    path = _SUFFIX.sub("", word.lstrip(_STRIP_LEAD).rstrip(_STRIP_TRAIL))
    if "/" not in path.rstrip("/") or path.startswith("/"):
        return None
    return path


def resolutions(path: str, page: str, engine_names: frozenset[str], root_names: frozenset[str]) -> list[str]:
    """The places `path` may name, the one a failure reports last."""
    places: list[str] = []
    if page.startswith(ENGINE + "/"):
        places.append(f"{ENGINE}/{path}")
    parts = path.split("/")
    if parts[0] == "audit" and parts[1] not in root_names and parts[1] in engine_names:
        places.append(f"{ENGINE}/{path}")
    else:
        places.append(path)
    return places


def check_page(page: str, kind: str, lines: Sequence[str], tree: Tree, out: Outcome) -> None:
    """Add each path of `page` that names nothing to `out.stale`; `page` is how a failure names the file."""
    top = tree.top_level()
    engine_names = tree.entries(ENGINE_PACKAGE)
    root_names = tree.entries("audit")
    for number, word in code_words(lines):
        path = as_path(word)
        if path is None:
            continue
        first = path.split("/")[0]
        if first not in top or (kind == "recipe" and first not in FRAMEWORK_FOLDERS):
            continue
        out.checked += 1
        places = resolutions(path, page, engine_names, root_names)
        if not any(tree.exists(place.rstrip("/")) for place in places):
            out.stale.append(Stale(page, number, word, places[-1]))


def check(root: Path, pages: Sequence[tuple[str, str]], tree: Tree) -> tuple[list[str], int]:
    """`(errors, paths checked)` for `(page, kind)` pairs, each page relative to `root`."""
    out = Outcome()
    for page, kind in pages:
        check_page(page, kind, (root / page).read_text(encoding="utf-8").splitlines(), tree, out)
    ignored = git_ignored(root, sorted({stale.resolved for stale in out.stale}))
    errors = [
        f"{stale.page}:{stale.line}: `{stale.word}` names {stale.resolved}, which does not exist"
        for stale in out.stale
        if stale.resolved not in ignored
    ]
    return sorted(errors), out.checked


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="recipe_paths.py", description=INFO.summary)
    parser.add_argument("root", help="a git work tree of the framework repository")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    root = _common.resolve_target(args.root)
    listed = git_listed(root)
    tree = Tree.from_paths(listed)
    pages = [(page, kind) for page in listed if (kind := page_kind(page)) is not None]
    errors, checked = check(root, pages, tree)
    if errors:
        count = len(errors)
        raise _common.ValidationFailed(
            f"{count} stale path{'' if count == 1 else 's'} in {len(pages)} pages", errors=errors
        )
    return _common.Result(
        data={"root": str(root), "pages": len(pages), "paths": checked},
        summary=f"recipe_paths: clean ({checked} paths in {len(pages)} pages)",
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
