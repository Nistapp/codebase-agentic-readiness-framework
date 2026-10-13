# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Lint the recipe Markdown under ``brownfield-recipes/`` for broken links, bad ``SKILL.md`` frontmatter and
oversize files.

    recipe_lint.py <root>

``<root>`` is the repository that holds ``brownfield-recipes/``; a link may climb out of that folder (a check
file citing ``brownfield-legacy/Phased-Approach.md`` does), but never out of ``<root>``. Three checks, each
independent of the others:

- **Links.** Every inline Markdown link (``[text](target)``, never an image or a reference-style link, neither
  of which this project's recipes use today) whose target is not an external URL must resolve inside ``<root>``.
  A target ending in ``.md`` with a ``#fragment`` needs a heading in that file whose GitHub-style slug is the
  fragment; any other target with a fragment needs the fragment to be an ``L<n>`` or ``L<n>-L<n>`` line range
  inside the file. The placeholder links in ``docs/templates/`` are examples (``NNNN-title.md``) and are
  skipped on purpose.
- **Frontmatter.** A ``SKILL.md`` must open with ``---``-delimited frontmatter holding a ``name`` (at most 64
  lowercase letters, digits and hyphens, matching its own folder's name) and a ``description`` (at most 1,024
  characters), one ``key: value`` pair per line (R-10's grammar; this is not a YAML parser).
- **Size.** A ``SKILL.md``, and a check-family file under ``audit/checks/`` (``NN-*.md``), must be 500 lines or
  fewer (R-10's ``SKILL.md`` budget, shared by the family files for the same reason: an agent loads the whole
  file at once, D46).

Nothing is written. Standard library only.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import _common

INFO = _common.ToolInfo(
    name="recipe_lint",
    summary="Check the recipe Markdown under brownfield-recipes/ for broken links, bad SKILL.md frontmatter and "
    "oversize files.",
    synopsis=("recipe_lint.py <root>",),
    writes="nothing",
)

RECIPES_DIRNAME = "brownfield-recipes"
LINE_BUDGET = 500  # SKILL.md's own budget (R-10); check-family files share it (D46).
MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1024

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")
CHECK_FAMILY_FILE = re.compile(r"^[0-9]{2}-[a-z0-9-]+\.md\Z")
LINE_ANCHOR = re.compile(r"^L([0-9]+)(?:-L([0-9]+))?\Z")

# Whole files whose links are examples and are never meant to resolve, as a path prefix relative to <root>.
EXCLUDED_FROM_LINKS = (f"{RECIPES_DIRNAME}/docs/templates/",)

_FENCE = re.compile(r"^(```+|~~~+)")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*\Z")
_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://|^mailto:")
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_FIELD = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*)\Z")


@dataclass
class Outcome:
    """What the lint found. `errors` is `path:line: message`, path relative to the root that was linted."""

    errors: list[str] = field(default_factory=list)

    def error(self, path: Path, line: int, message: str) -> None:
        self.errors.append(f"{path}:{line}: {message}")


# --- Reading a file without its fenced code -----------------------------------------------------------


def scan_lines(lines: Sequence[str]) -> list[tuple[int, str]]:
    """`(line number, text)` for each line outside a fenced code block, its backticks dropped.

    A fence closes on any line starting with three or more of the same fence character, regardless of the
    opening fence's exact length, which is what a renderer does too. Backticks are dropped, not the inline
    code they delimit, so a heading's code span keeps its word (GitHub renders it, then anchors on the text).
    Link matching is unaffected either way: a code span's own brackets and parentheses are not backticks.
    """
    kept: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(lines, start=1):
        if _FENCE.match(line.strip()):
            fenced = not fenced
            continue
        if fenced:
            continue
        kept.append((number, line.replace("`", "")))
    return kept


def slugify(heading: str) -> str:
    """GitHub's heading-to-anchor algorithm: drop punctuation, lower case, one hyphen per space character.

    Consecutive spaces give consecutive hyphens (confirmed against this repository's own anchors, including one
    with a double hyphen where an em dash's surrounding spaces both survive), and a trailing space from a
    stripped trailing character gives a trailing hyphen.
    """
    text = re.sub(r"[^\w\s-]", "", heading.lower())
    return text.replace(" ", "-")


def heading_slugs(path: Path, lines: Sequence[str]) -> set[str]:
    """Every heading's slug, with GitHub's `-1`, `-2`, ... suffix on a slug seen again."""
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    for _, text in scan_lines(lines):
        found = _HEADING.match(text)
        if found is None:
            continue
        base = slugify(found.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        slugs.add(base if count == 0 else f"{base}-{count}")
    return slugs


# --- The link rule --------------------------------------------------------------------------------------


def line_anchor_problem(resolved: Path, anchor: str) -> str | None:
    found = LINE_ANCHOR.match(anchor)
    if found is None:
        return f"the anchor #{anchor} is not L<n> or L<n>-L<n>"
    start = int(found.group(1))
    end = int(found.group(2)) if found.group(2) is not None else start
    try:
        with resolved.open("r", encoding="utf-8", errors="replace") as handle:
            total = sum(1 for _ in handle)
    except OSError as exc:
        return f"cannot read {resolved} to check the anchor #{anchor}: {exc.strerror or exc}"
    if end < start or end > total:
        return f"the anchor #{anchor} is out of range: {resolved.name} has {total} lines"
    return None


def check_link(
    root: Path, file: Path, line_number: int, target: str, cache: dict[Path, set[str]], out: Outcome
) -> None:
    if _EXTERNAL.match(target):
        return
    path_part, _, anchor = target.partition("#")
    try:
        resolved = file if path_part == "" else (file.parent / path_part).resolve()
    except (OSError, RuntimeError):
        out.error(file, line_number, f"cannot resolve the link {target!r}")
        return
    if not _common.is_within(root, resolved):
        out.error(file, line_number, f"the link {target!r} leaves {root}")
        return
    if not resolved.exists():
        out.error(file, line_number, f"the link {target!r} does not resolve: no such file or directory")
        return
    if not anchor:
        return
    if resolved.suffix == ".md":
        slugs = cache.get(resolved)
        if slugs is None:
            slugs = heading_slugs(resolved, resolved.read_text(encoding="utf-8").splitlines())
            cache[resolved] = slugs
        if anchor not in slugs:
            out.error(file, line_number, f"the anchor #{anchor} in {target!r} matches no heading")
    else:
        problem = line_anchor_problem(resolved, anchor)
        if problem is not None:
            out.error(file, line_number, f"{target!r}: {problem}")


def check_links(root: Path, file: Path, lines: Sequence[str], cache: dict[Path, set[str]], out: Outcome) -> None:
    for line_number, text in scan_lines(lines):
        for match in _LINK.finditer(text):
            check_link(root, file, line_number, match.group(1), cache, out)


def excluded_from_links(file: Path, root: Path) -> bool:
    relative = file.relative_to(root).as_posix()
    return any(relative.startswith(prefix) for prefix in EXCLUDED_FROM_LINKS)


# --- The frontmatter rule -------------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """The frontmatter's fields, one `key: value` per line (plain or quoted). `None` with no frontmatter block."""
    found = _FRONTMATTER.match(text)
    if found is None:
        return None
    fields: dict[str, str] = {}
    for line in found.group(1).split("\n"):
        field_match = _FIELD.match(line)
        if field_match is None:
            continue
        value = field_match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[field_match.group(1)] = value
    return fields


def check_frontmatter(path: Path, text: str, out: Outcome) -> None:
    fields = parse_frontmatter(text)
    if fields is None:
        out.error(path, 1, "a SKILL.md must open with '---' frontmatter and a closing '---'")
        return
    name = fields.get("name")
    if name is None:
        out.error(path, 1, "the frontmatter has no 'name'")
    elif len(name) > MAX_NAME_CHARS or NAME_PATTERN.match(name) is None:
        out.error(
            path,
            1,
            f"name {name!r} must be lowercase letters, digits and hyphens, at most {MAX_NAME_CHARS} characters",
        )
    elif name != path.parent.name:
        out.error(path, 1, f"name {name!r} must match its folder, {path.parent.name!r}")
    description = fields.get("description")
    if description is None:
        out.error(path, 1, "the frontmatter has no 'description'")
    elif len(description) > MAX_DESCRIPTION_CHARS:
        out.error(path, 1, f"description is {len(description)} characters; at most {MAX_DESCRIPTION_CHARS} are allowed")


# --- The size rule ---------------------------------------------------------------------------------------


def is_check_family_file(path: Path) -> bool:
    return (
        path.parent.name == "checks"
        and path.parent.parent.name == "audit"
        and CHECK_FAMILY_FILE.match(path.name) is not None
    )


def check_size(path: Path, lines: Sequence[str], out: Outcome) -> None:
    if path.name != "SKILL.md" and not is_check_family_file(path):
        return
    if len(lines) > LINE_BUDGET:
        out.error(path, LINE_BUDGET + 1, f"{path.name} has {len(lines)} lines; the budget is {LINE_BUDGET}")


# --- Putting it together ----------------------------------------------------------------------------------


def find_markdown(root: Path) -> list[Path]:
    recipes = root / RECIPES_DIRNAME
    if not recipes.is_dir():
        raise _common.UsageError(f"{root} has no {RECIPES_DIRNAME}/ directory")
    return sorted(recipes.rglob("*.md"))


def lint(root: Path, files: Sequence[Path]) -> Outcome:
    out = Outcome()
    cache: dict[Path, set[str]] = {}
    for file in files:
        text = file.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not excluded_from_links(file, root):
            check_links(root, file, lines, cache, out)
        if file.name == "SKILL.md":
            check_frontmatter(file, text, out)
        check_size(file, lines, out)
    out.errors.sort()
    return out


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="recipe_lint.py", description=INFO.summary)
    parser.add_argument("root", help=f"the repository that holds {RECIPES_DIRNAME}/")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    root = _common.resolve_target(args.root)
    files = find_markdown(root)
    outcome = lint(root, files)
    if outcome.errors:
        count = len(outcome.errors)
        raise _common.ValidationFailed(
            f"{count} problem{'' if count == 1 else 's'} in {len(files)} files under {RECIPES_DIRNAME}/",
            errors=outcome.errors,
        )
    return _common.Result(
        data={"root": str(root), "files": len(files)},
        summary=f"recipe_lint: clean ({len(files)} files under {RECIPES_DIRNAME}/)",
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
