# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Lint the recipe Markdown under ``audit/``, ``implement/`` and ``docs/`` for broken links, bad ``SKILL.md``
frontmatter and oversize files.

    recipe_lint.py <root>
    recipe_lint.py <root> --write-catalogue

``<root>`` is the framework repository, the one that holds ``audit/`` (and, beside it, ``implement/`` and
``docs/``); a link may climb out of those folders (a check file citing ``docs/framework/phased-approach.md`` or
``spec/`` does), but never out of ``<root>``. Ten checks, each independent of the others. The link rule also
covers the framework pages outside those folders (the root ``README.md``, ``AGENTS.md``, ``CONTRIBUTING.md``,
``RELEASE_PROCESS.md`` and ``SECURITY.md``, ``spec/`` and ``greenfield/``; the
framework pages under ``docs/framework/`` are already recipe Markdown); no other check reads them:

- **Links.** Every inline Markdown link (``[text](target)``, never an image or a reference-style link, neither
  of which this project's recipes use today) whose target is not an external URL must resolve inside ``<root>``.
  A target ending in ``.md`` with a ``#fragment`` needs a heading in that file whose GitHub-style slug is the
  fragment; any other target with a fragment needs the fragment to be an ``L<n>`` or ``L<n>-L<n>`` line range
  inside the file. The placeholder links in ``docs/templates/`` and ``greenfield/templates/`` are examples
  (``NNNN-title.md``) and are skipped on purpose.
- **Frontmatter.** A ``SKILL.md`` must open with ``---``-delimited frontmatter holding a ``name`` (at most 64
  lowercase letters, digits and hyphens, matching its own folder's name) and a ``description`` (at most 1,024
  characters), one ``key: value`` pair per line (R-10's grammar; this is not a YAML parser).
- **Size.** A ``SKILL.md``, and a check-family file under ``audit/checks/`` (``NN-*.md``), must be 500 lines or
  fewer (R-10's ``SKILL.md`` budget, shared by the family files for the same reason: an agent loads the whole
  file at once, D46).
- **User prompt.** Each recipe's ``SKILL.md`` (``audit/SKILL.md`` and ``implement/SKILL.md``) must hold an inline
  link, outside a code fence, to the shared prompt ``audit/prompts/talking-to-the-user.md``: how the agent writes to
  the person who runs it. A tree without that prompt has nothing to link to, and the check is skipped.
- **Tool references.** Every ``audit/tools/<name>.py`` or ``implement/tools/<name>.py`` named in a command or a
  code span, wherever it appears in a line, must exist in that folder and answer ``--describe`` with the
  contract's envelope, inside a time limit. A line that admits the tool is not built yet (starts with ``TBD:``,
  after any list or quote markers) is skipped, which is how this project already marks a tool that is Planned.
  A bare ``tools/...`` with no ``audit/`` or ``implement/`` in front of it is some other project's own tools
  folder (the engine's ``audit/engine/tools/build.py`` does not even follow this contract) and is never checked;
  neither is ``<word>-audit/tools/...``, which is another folder's name, nor a relative link's
  ``../audit/tools/...``, which the link rule checks instead.
- **Check references.** A catalogue check ID (``CMD-01``, ``AGT-11``, ...), wherever a line names one, must be
  in ``audit/catalogue.json``.
- **Requirement references.** A requirement ID (``REQ-SH-022``, ``REQ-BF-004``, ...) must be a heading in
  ``spec/readiness-requirements.md``.
- **Playbook references.** A playbook named as ``Playbook `<name>` `` or ``"playbook": "<name>"`` must be one
  ``audit/catalogue.json`` names. A playbook may be named before its file exists under ``implement/playbooks/``
  (``audit/schema/SCHEMA.md``, "Rules beyond the schema", rule 2: the catalogue, not the folder, is what
  "exists" means), so this never checks the folder.
- **Playbook commits.** A playbook, ``implement/playbooks/<name>.md`` other than ``README.md``, must hold a
  ``## Commits`` section between ``## Steps`` and ``## Continue on error`` (the anatomy in
  ``implement/playbooks/README.md``). Its table has the header ``| # | Commit | Checks | Kind |`` and at least one
  row; ``#`` counts up from 1; ``Kind`` is ``hand``, ``bulk``, ``config`` or ``wiring``; and ``Checks`` is ``-`` or
  a comma-separated list of check IDs that the playbook's ``## Checks resolved`` section names. So the Stage 3
  commit loop of ``implement/SKILL.md`` always has a commit list to follow.
- **Tool catalogue.** ``audit/tools/CATALOGUE.md`` must be byte-identical to what every ``<name>.py
  --describe`` directly in ``audit/tools/`` and in ``implement/tools/`` (every file there not starting with
  ``_``) would generate: the audit tools first, sorted by tool name, then the implement tools, sorted by tool
  name, so each recipe's tools stay together. ``--write-catalogue`` regenerates it in place instead of linting;
  nothing else runs in that mode. A tree with no ``audit/tools/`` (the catalogue's home) has no catalogue to
  keep fresh and is skipped.

These last three read ``audit/catalogue.json`` and ``spec/readiness-requirements.md`` under ``<root>``; when
either is missing or unreadable, the check it feeds is silently skipped rather than failing the whole run, so the
rule still works on a minimal tree that has no catalogue or spec of its own. They skip ``audit/engine/``
entirely: the engine has its own check registry and its own fixtures, which are data, not recipe prose, and
neither is governed by ``catalogue.json``.

Nothing is written, apart from a tool's own ``--describe`` (which the contract guarantees does no work and
writes nothing either) and, with ``--write-catalogue``, an atomic in-place replace of
``audit/tools/CATALOGUE.md`` itself: a second, documented exception to "a tool never replaces a file"
(``audit/tools/README.md`` rule 7), alongside the draft report. Standard library only; ``_common`` is imported
from ``audit/tools/``, which this module puts on ``sys.path`` because ``dev/`` is not a package.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

_AUDIT_TOOLS = str(Path(__file__).resolve().parent.parent / "audit" / "tools")
if _AUDIT_TOOLS not in sys.path:
    sys.path.insert(0, _AUDIT_TOOLS)

import _common  # noqa: E402

INFO = _common.ToolInfo(
    name="recipe_lint",
    summary="Check the recipe Markdown under audit/, implement/ and docs/ for broken links, bad SKILL.md "
    "frontmatter and oversize files.",
    synopsis=("recipe_lint.py <root>", "recipe_lint.py <root> --write-catalogue"),
    writes="nothing, unless --write-catalogue is given, which replaces audit/tools/CATALOGUE.md in place",
)

# The folders that hold recipe Markdown, relative to <root>. The first is required: it marks <root> as the
# framework repository, and it holds catalogue.json and the tool catalogue.
RECIPE_DIRS = ("audit", "implement", "docs")
REQUIRED_DIR = RECIPE_DIRS[0]
# The folders whose `<name>.py` tools are cited, described and catalogued, in catalogue order.
TOOL_DIRS = ("audit/tools", "implement/tools")
CATALOGUE_FILE = "audit/tools/CATALOGUE.md"
CATALOGUE_JSON = "audit/catalogue.json"
LINE_BUDGET = 500  # SKILL.md's own budget (R-10); check-family files share it (D46).
MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1024
DESCRIBE_TIMEOUT_S = 15.0

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")
CHECK_FAMILY_FILE = re.compile(r"^[0-9]{2}-[a-z0-9-]+\.md\Z")
LINE_ANCHOR = re.compile(r"^L([0-9]+)(?:-L([0-9]+))?\Z")
# `audit/tools/<name>.py` or `implement/tools/<name>.py` as a path from <root>, the way a command names it: not
# preceded by a word character, a hyphen, a dot or a slash, so neither `audit/engine/tools/build.py`, nor some
# `<word>-audit/tools/...` folder, nor a relative link's `../audit/tools/...` (the link rule's to check) is one.
TOOL_REFERENCE = re.compile(
    rf"(?<![\w./-])({'|'.join(re.escape(folder) for folder in TOOL_DIRS)})/([A-Za-z_][A-Za-z0-9_]*)\.py"
)
TBD_LINE = re.compile(r"^\s*(?:[-*>]\s*)*TBD:")
ENVELOPE_KEYS = ("tool", "version", "ok", "data", "warnings", "truncated")
REQUIREMENT_ID = re.compile(r"\bREQ-[A-Z]+-[0-9]+\b")
REQUIREMENT_HEADING = re.compile(r"^### (REQ-[A-Z]+-[0-9]+)\b", re.MULTILINE)
# The shared prompt on how a recipe's agent writes to its user, and the recipe files that must link it.
USER_PROMPT = "audit/prompts/talking-to-the-user.md"
RECIPE_SKILLS = ("audit/SKILL.md", "implement/SKILL.md")
# The playbook folder, its commit table's header and the kinds of commit the table allows.
PLAYBOOK_DIR = "implement/playbooks"
COMMITS_HEADER = ("#", "Commit", "Checks", "Kind")
COMMIT_KINDS = frozenset({"hand", "bulk", "config", "wiring"})
CHECK_ID = re.compile(r"\b[A-Z]+-[0-9]{2}\b")
PLAYBOOK_REFERENCE = re.compile(r'Playbook `([a-z][a-z0-9-]*)`|"playbook":\s*"([a-z][a-z0-9-]*)"')

# Whole files whose links are examples and are never meant to resolve, as a path prefix relative to <root>.
EXCLUDED_FROM_LINKS = ("docs/templates/", "greenfield/templates/")
# The framework pages outside the recipe folders whose links are checked, and nothing else about them: the root
# README.md and the folders below (the framework pages under docs/framework/ are recipe Markdown already).
# Templates under greenfield/ are copied into new projects, so their links are examples relative to the
# destination and are skipped by EXCLUDED_FROM_LINKS above.
# The root process documents join them: a broken link there misleads a contributor as much as one in the README.
# CHANGELOG.md is left out on purpose: its entries before v0.3.0 name the old layout's paths, as written then.
ROOT_PAGE_FILES = ("README.md", "AGENTS.md", "CONTRIBUTING.md", "RELEASE_PROCESS.md", "SECURITY.md")
ROOT_PAGE_DIRS = ("spec", "greenfield")
# Files the catalogue, requirement and playbook checks never read: the engine's own registry and fixtures.
EXCLUDED_FROM_CATALOGUE = ("audit/engine/",)
# Never swept at all: gitignored build output (build_skills.py's bundle, the engine's audit.pyz), not
# authored content, wherever a recipe folder holds a dist/. A bundle's own copy of a check file has links
# relative to the bundle, not to <root>, so it is never this tool's to lint; `skills-ref validate` (S4.5.2) is.
EXCLUDED_DIRNAMES = tuple(f"{folder}/dist/" for folder in RECIPE_DIRS) + ("audit/engine/dist/",)

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


# --- The user-prompt rule -------------------------------------------------------------------------------


def links_to(file: Path, lines: Sequence[str], target: Path) -> bool:
    """Whether an inline link outside a code fence in `file` resolves to `target`."""
    for _, text in scan_lines(lines):
        for match in _LINK.finditer(text):
            path_part = match.group(1).partition("#")[0]
            if path_part and not _EXTERNAL.match(path_part) and (file.parent / path_part).resolve() == target:
                return True
    return False


def check_user_prompt(root: Path, out: Outcome) -> None:
    prompt = (root / USER_PROMPT).resolve()
    if not prompt.is_file():
        return
    for relative in RECIPE_SKILLS:
        skill = root / relative
        if skill.is_file() and not links_to(skill, skill.read_text(encoding="utf-8").splitlines(), prompt):
            out.error(skill, 1, f"a recipe's SKILL.md must link the shared prompt {USER_PROMPT}")


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


# --- The tool-reference rule -------------------------------------------------------------------------------


def tool_name_occurrences(lines: Sequence[str]) -> list[tuple[int, str]]:
    """`(line number, reference)` for each `audit/tools/<name>.py` or `implement/tools/<name>.py` the raw lines name.

    The reference is the folder and file as cited, relative to `<root>`.

    Fenced code blocks are read too (unlike `scan_lines`): a Synopsis is exactly where the primary citation
    lives. A line admitting the tool is not built yet (`TBD:`, after any list or quote markers) is skipped.
    """
    found: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        if TBD_LINE.match(line):
            continue
        for match in TOOL_REFERENCE.finditer(line):
            found.append((number, f"{match.group(1)}/{match.group(2)}.py"))
    return found


def describe_manifest(path: Path, timeout: float) -> tuple[dict[str, Any], None] | tuple[None, str]:
    """`(manifest, None)` from a valid, successful `<path> --describe`; otherwise `(None, why not)`."""
    try:
        result = subprocess.run(
            [sys.executable, str(path), "--describe"], capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return None, f"did not finish within {timeout}s"
    except OSError as exc:
        return None, f"could not be run: {exc.strerror or exc}"
    if result.returncode != 0:
        tail = result.stderr.strip().splitlines()[-1:] or [""]
        return None, f"exited {result.returncode}: {tail[0]}"
    try:
        envelope = json.loads(result.stdout)
    except ValueError:
        return None, "printed no valid JSON envelope on stdout"
    if not isinstance(envelope, dict) or any(key not in envelope for key in ENVELOPE_KEYS):
        return None, f"printed an envelope missing one of {', '.join(ENVELOPE_KEYS)}"
    if envelope["ok"] is not True:
        return None, f"printed ok: {envelope['ok']!r}"
    return envelope["data"], None


def describe_tool(path: Path, timeout: float) -> str | None:
    """`None` when `<path> --describe` prints a valid, successful envelope; otherwise why it did not."""
    return describe_manifest(path, timeout)[1]


def check_tool_references(
    root: Path, file: Path, lines: Sequence[str], cache: dict[str, str | None], out: Outcome, *, timeout: float
) -> None:
    for line_number, reference in tool_name_occurrences(lines):
        resolved = root / reference
        if not resolved.is_file():
            out.error(file, line_number, f"the tool {reference} does not exist")
            continue
        if reference not in cache:
            cache[reference] = describe_tool(resolved, timeout)
        problem = cache[reference]
        if problem is not None:
            out.error(file, line_number, f"{reference} --describe {problem}")


def excluded_from_catalogue_checks(file: Path, root: Path) -> bool:
    relative = file.relative_to(root).as_posix()
    return any(relative.startswith(prefix) for prefix in EXCLUDED_FROM_CATALOGUE)


# --- The check-reference rule -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Catalogue:
    """What `catalogue.json` says exists, for the check and playbook reference rules."""

    check_ids: frozenset[str]
    playbooks: frozenset[str]
    check_id_pattern: "re.Pattern[str] | None"


def load_catalogue(root: Path) -> Catalogue | None:
    """The catalogue under `<root>`, or `None` when it cannot be read: the check it feeds is then skipped."""
    path = root / CATALOGUE_JSON
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    checks = data.get("checks", [])
    check_ids = frozenset(check["id"] for check in checks if "id" in check)
    playbooks = frozenset(name for check in checks for name in check.get("playbooks", []))
    families = sorted({check_id.split("-")[0] for check_id in check_ids if "-" in check_id}, key=len, reverse=True)
    pattern = (
        re.compile(rf"\b(?:{'|'.join(re.escape(family) for family in families)})-[0-9]{{2}}\b") if families else None
    )
    return Catalogue(check_ids=check_ids, playbooks=playbooks, check_id_pattern=pattern)


def load_requirement_ids(root: Path) -> frozenset[str] | None:
    """Every requirement ID headed in `spec/readiness-requirements.md` under `<root>`, or `None` if unreadable."""
    path = root / "spec" / "readiness-requirements.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return frozenset(REQUIREMENT_HEADING.findall(text))


def check_catalogue_references(file: Path, lines: Sequence[str], catalogue: Catalogue, out: Outcome) -> None:
    if catalogue.check_id_pattern is None:
        return
    for number, line in enumerate(lines, start=1):
        for match in catalogue.check_id_pattern.finditer(line):
            if match.group(0) not in catalogue.check_ids:
                out.error(file, number, f"the check {match.group(0)!r} is not in catalogue.json")


def check_requirement_references(
    file: Path, lines: Sequence[str], requirement_ids: frozenset[str], out: Outcome
) -> None:
    for number, line in enumerate(lines, start=1):
        for match in REQUIREMENT_ID.finditer(line):
            if match.group(0) not in requirement_ids:
                out.error(file, number, f"the requirement {match.group(0)!r} is not in spec/readiness-requirements.md")


def check_playbook_references(file: Path, lines: Sequence[str], catalogue: Catalogue, out: Outcome) -> None:
    for number, line in enumerate(lines, start=1):
        for match in PLAYBOOK_REFERENCE.finditer(line):
            name = match.group(1) or match.group(2)
            if name not in catalogue.playbooks:
                out.error(file, number, f"the catalogue names no playbook {name!r}")


# --- The playbook commits rule ---------------------------------------------------------------------------


def is_playbook(file: Path, root: Path) -> bool:
    relative = file.relative_to(root)
    return relative.parent.as_posix() == PLAYBOOK_DIR and file.name != "README.md"


def table_cells(line: str) -> list[str]:
    """The cells of one Markdown table row, stripped, without the outer pipes."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def check_playbook_commits(file: Path, lines: Sequence[str], out: Outcome) -> None:
    """The `## Commits` section of one playbook: where it sits, its table's shape, and the checks it names."""
    headings = [(number, text[3:].strip()) for number, text in scan_lines(lines) if text.startswith("## ")]
    names = [name for _, name in headings]
    if "Commits" not in names:
        out.error(file, 1, "a playbook needs a '## Commits' section (implement/playbooks/README.md, Anatomy)")
        return
    at = names.index("Commits")
    start = headings[at][0]
    if at == 0 or names[at - 1] != "Steps" or at + 1 >= len(names) or names[at + 1] != "Continue on error":
        out.error(file, start, "the Commits section goes right after Steps and right before Continue on error")
    end = headings[at + 1][0] if at + 1 < len(headings) else len(lines) + 1
    resolved: set[str] = set()
    if "Checks resolved" in names:
        r_at = names.index("Checks resolved")
        r_end = headings[r_at + 1][0] if r_at + 1 < len(headings) else len(lines) + 1
        resolved = set(CHECK_ID.findall("\n".join(lines[headings[r_at][0] : r_end - 1])))
    rows: list[tuple[int, str]] = []
    for number in range(start + 1, end):
        line = lines[number - 1]
        if line.lstrip().startswith("|"):
            rows.append((number, line))
        elif rows:
            break  # the first table only: a later one is prose, not the commit list
    if len(rows) < 3:
        out.error(file, start, "the Commits section needs a table with a header row and at least one commit")
        return
    header = tuple(table_cells(rows[0][1]))
    if header != COMMITS_HEADER:
        out.error(file, rows[0][0], f"the Commits table's header must be | {' | '.join(COMMITS_HEADER)} |")
        return
    for expected, (number, line) in enumerate(rows[2:], start=1):
        cells = table_cells(line)
        if len(cells) != len(COMMITS_HEADER):
            out.error(file, number, f"a Commits row has {len(cells)} cells; it needs {len(COMMITS_HEADER)}")
            continue
        order, _, checks, kind = cells
        if order != str(expected):
            out.error(file, number, f"the Commits row numbered {order!r} should be {expected}")
        if kind.strip("`") not in COMMIT_KINDS:
            out.error(file, number, f"the Commits kind {kind!r} is not one of {', '.join(sorted(COMMIT_KINDS))}")
        if checks.strip("`") == "-":
            continue
        named = CHECK_ID.findall(checks)
        if not named:
            out.error(file, number, f"the Commits checks {checks!r} name no check ID; write '-' for none")
        for check_id in named:
            if check_id not in resolved:
                out.error(file, number, f"the Commits row names {check_id}, which Checks resolved does not list")


# --- The tool catalogue ---------------------------------------------------------------------------------

CATALOGUE_HEADER = (
    "# Tool Catalogue\n"
    "\n"
    "Generated by `recipe_lint.py <root> --write-catalogue` from every tool's own `--describe` output: the tools "
    "in `audit/tools/` sorted by name, then the tools in `implement/tools/` sorted by name. Do not edit by hand: "
    "a stale file fails `make check`.\n"
)


def catalogue_path(root: Path) -> Path:
    return root / CATALOGUE_FILE


def discover_tools(root: Path) -> list[Path]:
    """Every `<name>.py` directly in each of `TOOL_DIRS`, apart from the private `_*.py` helpers.

    Folder by folder in `TOOL_DIRS` order, each folder's tools sorted by file name; a missing folder adds none.
    """
    found: list[Path] = []
    for folder in TOOL_DIRS:
        tools_dir = root / folder
        if tools_dir.is_dir():
            found.extend(sorted(path for path in tools_dir.glob("*.py") if not path.name.startswith("_")))
    return found


def render_catalogue(manifests: Sequence[dict[str, Any]]) -> str:
    """Byte-stable Markdown for `manifests`, which callers must already have put in catalogue order."""
    parts = [CATALOGUE_HEADER]
    for manifest in manifests:
        parts.append(f"\n## {manifest['name']}.py\n\n")
        parts.append(f"**Version:** {manifest['version']}  \n**Writes:** {manifest['writes']}\n\n")
        parts.append(f"{manifest['summary']}\n\n")
        parts.append("```text\n")
        for line in manifest["synopsis"]:
            parts.append(f"{line}\n")
        parts.append("```\n")
    return "".join(parts)


def build_catalogue(root: Path, *, timeout: float) -> tuple[str | None, list[str]]:
    """The catalogue text for `root`'s tools in catalogue order (`TOOL_DIRS` order, then by tool name within each
    folder), or `(None, errors)` when one of them fails `--describe`."""
    errors: list[str] = []
    manifests: list[dict[str, Any]] = []
    tools = discover_tools(root)
    for folder in TOOL_DIRS:
        folder_manifests: list[dict[str, Any]] = []
        for path in (tool for tool in tools if tool.parent == root / folder):
            manifest, problem = describe_manifest(path, timeout)
            if problem is not None or manifest is None:
                errors.append(f"{folder}/{path.name} --describe {problem}")
                continue
            folder_manifests.append(manifest)
        folder_manifests.sort(key=lambda manifest: manifest["name"])
        manifests.extend(folder_manifests)
    if errors:
        return None, errors
    return render_catalogue(manifests), []


def check_catalogue_fresh(root: Path, out: Outcome, *, timeout: float) -> None:
    if not catalogue_path(root).parent.is_dir():
        return  # a minimal tree with no audit/tools/ of its own has no catalogue to keep fresh.
    path = catalogue_path(root)
    expected, errors = build_catalogue(root, timeout=timeout)
    if errors:
        for message in errors:
            out.error(path, 1, message)
        return
    assert expected is not None
    how = "regenerate it with 'recipe_lint.py <root> --write-catalogue'"
    if not path.is_file():
        out.error(path, 1, f"{CATALOGUE_FILE} is missing; {how}")
        return
    if path.read_text(encoding="utf-8") != expected:
        out.error(path, 1, f"{CATALOGUE_FILE} is stale; {how}")


def write_catalogue(root: Path, *, timeout: float) -> _common.Result:
    text, errors = build_catalogue(root, timeout=timeout)
    if errors:
        raise _common.ValidationFailed(
            f"{len(errors)} tool{'' if len(errors) == 1 else 's'} could not be described", errors=errors
        )
    assert text is not None
    path = catalogue_path(root)
    _common.atomic_write_text(path, text)
    return _common.Result(
        data={"file": str(path), "bytes": len(text.encode("utf-8")), "tools": len(discover_tools(root))},
        summary=f"recipe_lint: wrote {path}",
    )


# --- Putting it together ----------------------------------------------------------------------------------


def excluded_dirname(file: Path, root: Path) -> bool:
    relative = file.relative_to(root).as_posix()
    return any(relative.startswith(prefix) for prefix in EXCLUDED_DIRNAMES)


def find_markdown(root: Path) -> list[Path]:
    """Every `*.md` under the recipe folders that exist; `<root>` must at least hold `audit/`."""
    if not (root / REQUIRED_DIR).is_dir():
        raise _common.UsageError(f"{root} has no {REQUIRED_DIR}/ directory")
    found: list[Path] = []
    for folder in RECIPE_DIRS:
        recipes = root / folder
        if recipes.is_dir():
            found.extend(path for path in recipes.rglob("*.md") if not excluded_dirname(path, root))
    return sorted(found)


def find_root_pages(root: Path) -> list[Path]:
    """The framework pages outside the recipe folders whose relative links are checked (MR08, I20)."""
    found = [root / name for name in ROOT_PAGE_FILES if (root / name).is_file()]
    for dirname in ROOT_PAGE_DIRS:
        folder = root / dirname
        if folder.is_dir():
            found.extend(folder.rglob("*.md"))
    return sorted(found)


def lint(
    root: Path,
    files: Sequence[Path],
    *,
    describe_timeout: float = DESCRIBE_TIMEOUT_S,
    root_pages: Sequence[Path] = (),
) -> Outcome:
    out = Outcome()
    link_cache: dict[Path, set[str]] = {}
    tool_cache: dict[str, str | None] = {}
    catalogue = load_catalogue(root)
    requirement_ids = load_requirement_ids(root)
    for file in files:
        text = file.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not excluded_from_links(file, root):
            check_links(root, file, lines, link_cache, out)
        if file.name == "SKILL.md":
            check_frontmatter(file, text, out)
        check_size(file, lines, out)
        check_tool_references(root, file, lines, tool_cache, out, timeout=describe_timeout)
        if is_playbook(file, root):
            check_playbook_commits(file, lines, out)
        if not excluded_from_catalogue_checks(file, root):
            if catalogue is not None:
                check_catalogue_references(file, lines, catalogue, out)
                check_playbook_references(file, lines, catalogue, out)
            if requirement_ids is not None:
                check_requirement_references(file, lines, requirement_ids, out)
    check_user_prompt(root, out)
    for page in root_pages:
        if not excluded_from_links(page, root):
            check_links(root, page, page.read_text(encoding="utf-8").splitlines(), link_cache, out)
    out.errors.sort()
    return out


SWEPT = ", ".join(f"{folder}/" for folder in RECIPE_DIRS)


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="recipe_lint.py", description=INFO.summary)
    parser.add_argument("root", help=f"the framework repository, which holds {REQUIRED_DIR}/")
    parser.add_argument(
        "--write-catalogue",
        action="store_true",
        help=f"regenerate {CATALOGUE_FILE} from every tool's --describe output and exit; lints nothing else",
    )
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    root = _common.resolve_target(args.root)
    if args.write_catalogue:
        return write_catalogue(root, timeout=DESCRIBE_TIMEOUT_S)
    files = find_markdown(root)
    root_pages = find_root_pages(root)
    outcome = lint(root, files, root_pages=root_pages)
    check_catalogue_fresh(root, outcome, timeout=DESCRIBE_TIMEOUT_S)
    if outcome.errors:
        outcome.errors.sort()
        count = len(outcome.errors)
        raise _common.ValidationFailed(
            f"{count} problem{'' if count == 1 else 's'} in {len(files)} files under {SWEPT}",
            errors=outcome.errors,
        )
    return _common.Result(
        data={"root": str(root), "files": len(files)},
        summary=f"recipe_lint: clean ({len(files)} files under {SWEPT})",
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
