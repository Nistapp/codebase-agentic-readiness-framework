# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Build the two skill bundles: self-contained copies of the audit recipe and of the implement recipe.

One command::

    build_skills.py [--out-dir DIR]

A bundle is what a harness installs and runs with no checkout of this repository: `skills-ref validate`
(S4.5.2) and an install smoke-run (S4.5.3) both act on it, never on the source tree directly. Both are written
under ``<repo>/dev/dist/skills/`` by default (``*.pyz`` and ``dev/dist/`` are both gitignored); ``--out-dir``
changes where ``skills/`` itself goes, for a build that is not meant to land there.
Each bundle is replaced whole on every run, so a stale leftover from an earlier build can never survive.

**agentic-readiness-audit** has three parts and a ``LICENSE`` (the repository's ``LICENSE-CODE``, AGPL-3.0):

- ``SKILL.md``: the recipe's own file (``audit/SKILL.md``), with its frontmatter ``name`` rewritten from
  ``audit`` (the source folder's name, which `recipe_lint.py` requires there) to the bundle's own name,
  ``agentic-readiness-audit`` (the name `skills-ref` checks against the bundle's folder name), and a
  ``metadata.version`` key added: the release version from ``.release-please-manifest.json``
  (:func:`stamp_frontmatter`), so an installed bundle says which release it is.
- ``references/``: the check files (``audit/checks/``), the stack profiles (``audit/stacks/``), the shared prompt
  on how to talk to the user (``audit/prompts/talking-to-the-user.md``, which the implement bundle carries too) and
  the schema docs (``audit/schema/*.schema.json``, ``SCHEMA.md``, ``LICENSING.md``) — read by the model, not run.
  ``SKILL.md``'s link to the prompt is rewritten to its place under ``references/prompts/``.
- ``scripts/``: the five tools the recipe's Tools table calls (``facts.py``, ``engine.py``, ``report.py``,
  ``validate_report.py``, ``render_report.py``, from ``audit/tools/``) and the private modules they import; the
  schema files and ``catalogue.json`` those tools read at a fixed path next to themselves
  (``validate_report.RECIPES``); the engine's own ``audit`` package, which ``engine.py`` imports from ``../engine``
  relative to itself, so ``scripts/`` has the same shape as ``audit/`` in this repository (``scripts/engine/audit/``);
  and ``audit.pyz``, the engine's single-file build, for a person who wants to run it directly with no Python path
  setup at all.

Some of the audit ``SKILL.md``'s own relative links point outside what that bundle carries (the Tools CLI
reference, ``spec/command-surface.md``, ``docs/framework/phased-approach.md`` from the check files) — found,
not fixed, for the audit bundle.

**agentic-readiness-implement** carries the implement recipe, a ``LICENSE`` like the audit bundle's, and resolves
every link it keeps:

- ``SKILL.md``: ``implement/SKILL.md``, its ``name`` rewritten from ``implement`` to the bundle's name, and the
  same ``metadata.version`` added.
- ``references/``: the state contract, the playbooks, the kickoff prompt, the shared prompt on how to talk to the
  user (from ``audit/prompts/``), the check files, the stack profiles,
  ADR 0003, the ADR policy and the ADR template, ``spec/command-surface.md`` and the spec decisions, the state schema and its docs, and the parts of
  the Tools CLI reference that cover the carried tools (:data:`TOOLS_CLI_SECTIONS`).
- ``scripts/``: ``progress.py``, ``check_drift.py`` and ``compare_reports.py`` (from ``implement/tools/``), and
  ``validate_report.py`` with the private modules they import (from ``audit/tools/``), side by side in
  ``scripts/tools/``; ``_audit_tools_path.py``, which the implement tools import first and which does nothing in the
  bundle (there is no ``../../audit/tools`` there); the schema files and ``catalogue.json``; and an ``engine.py`` shim
  (:data:`ENGINE_SHIM`). The engine itself is not copied: the shim loads ``engine.py`` from the
  agentic-readiness-audit skill installed in the same skills folder, so the two skills share one engine copy
  (``validate_report.py`` reads the engine's credential patterns).

Every carried Markdown file is rewritten in two ways. A command ``python3 audit/tools/<tool>.py`` or
``python3 implement/tools/<tool>.py`` becomes the path from the skill's own folder
(``python3 scripts/tools/<tool>.py``; ``engine.py`` points at the audit skill beside it). A relative link to a
carried file is rewritten to that file's place in the bundle; a link to anything else becomes plain text naming the
framework path, so no link leaves the bundle.

``audit.pyz`` is produced by running the engine's own ``audit/engine/build.py`` as a subprocess (never imported;
the build script is excluded from the engine's own standard-library-only boundary) and copying
its output in. Everything else is a file copy or a deterministic text rewrite, so two builds from the same source
tree are byte-for-byte identical apart from ``audit.pyz``, whose zip entries carry the source files' own
modification times — which do not change between two builds in the same session.

Failure behaviour: a target problem (the engine's ``build.py`` is missing, or exits nonzero) is exit 1
with the subprocess's stderr in ``data.errors``; so is a source file whose frontmatter ``name`` line or Tools CLI
section is missing, or whose frontmatter already has a ``metadata`` key. Nothing else in this tool can fail the way a user-facing argument can, since it takes none
but ``--out-dir``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

REPO = Path(__file__).resolve().parent.parent
AUDIT = REPO / "audit"
AUDIT_TOOLS = AUDIT / "tools"
AUDIT_SCHEMA = AUDIT / "schema"
ENGINE = AUDIT / "engine"
IMPLEMENT = REPO / "implement"
IMPLEMENT_TOOLS = IMPLEMENT / "tools"
LICENSE_CODE = REPO / "LICENSE-CODE"
MANIFEST = REPO / ".release-please-manifest.json"

# `_common` (and `recipe_lint`'s own `_common` import) live in audit/tools/, not beside this script.
if str(AUDIT_TOOLS) not in sys.path:
    sys.path.insert(0, str(AUDIT_TOOLS))

import _common  # noqa: E402

INFO = _common.ToolInfo(
    name="build_skills",
    summary="Build the agentic-readiness-audit and agentic-readiness-implement skill bundles under dev/dist/skills/.",
    synopsis=("build_skills.py [--out-dir DIR]",),
    writes=(
        "dev/dist/skills/agentic-readiness-audit/ and dev/dist/skills/agentic-readiness-implement/ (SKILL.md, LICENSE, "
        "references/, scripts/), each replaced whole on each run; "
        "--out-dir changes where skills/ itself goes."
    ),
)

BUNDLE_NAME = "agentic-readiness-audit"
IMPLEMENT_BUNDLE_NAME = "agentic-readiness-implement"
DEFAULT_OUT_DIR = REPO / "dev" / "dist" / "skills"

#: The five tools `audit/SKILL.md`'s Tools table calls, plus the private modules they import (checked by
#: grepping their own `import` lines, not guessed).
TOOL_FILES = (
    "facts.py",
    "engine.py",
    "report.py",
    "validate_report.py",
    "render_report.py",
    "_common.py",
    "_engine_adapter.py",
    "_jsonschema_subset.py",
    "_summary.py",
)

#: Read directly by the tools above at a path fixed relative to themselves (`validate_report.RECIPES`), so
#: these must sit beside `scripts/tools/` the same way they sit beside `audit/tools/` in this repository.
SCHEMA_FILES = (
    "audit-intake.schema.json",
    "audit-report.schema.json",
    "catalogue.schema.json",
    "eval-expected.schema.json",
    "facts.schema.json",
    "SCHEMA.md",
    "LICENSING.md",
)

#: The prompts in `audit/prompts/` the audit bundle carries, under `references/prompts/`. `kickoff.md` stays out:
#: a person pastes it into a harness; the skill does not read it.
AUDIT_PROMPT_FILES = ("talking-to-the-user.md",)

#: `audit/SKILL.md` links each carried prompt relative to itself, with or without a heading anchor; in the bundle
#: the prompt sits under `references/`.
AUDIT_SKILL_LINK_REWRITES = tuple((f"](prompts/{name}", f"](references/prompts/{name}") for name in AUDIT_PROMPT_FILES)

SKILL_MD_SOURCE_NAME = "name: audit\n"
SKILL_MD_BUNDLE_NAME = f"name: {BUNDLE_NAME}\n"


def _copy_tree(source: Path, dest: Path) -> None:
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


def _write_license(bundle_dir: Path) -> None:
    shutil.copy2(LICENSE_CODE, bundle_dir / "LICENSE")


def release_version() -> str:
    """The release version: the root package's entry in `.release-please-manifest.json` (ADR 0005)."""
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["."]
    if not isinstance(version, str):
        raise _common.ToolError(f".release-please-manifest.json: the '.' entry is not a string: {version!r}")
    return version


def stamp_frontmatter(text: str, source: str, source_name: str, bundle_name: str, version: str) -> str:
    """Rewrite a `SKILL.md` for its bundle: the `name` line, and a `metadata.version` key before the closing `---`.

    The Agent Skills spec allows `metadata` (a string map) and rejects a top-level `version`, so the release
    version goes under `metadata`. `source` names the file in an error.
    """
    if source_name not in text:
        raise _common.ToolError(
            f"{source}'s frontmatter does not contain {source_name!r}; it may have been renamed without updating this tool"
        )
    if not text.startswith("---\n") or "\n---\n" not in text[3:]:
        raise _common.ToolError(f"{source} does not start with a frontmatter block between two '---' lines")
    end = text.index("\n---\n", 3) + 1
    frontmatter = text[:end]
    if "\nmetadata:" in frontmatter:
        raise _common.ToolError(f"{source}'s frontmatter already has a metadata key; merge the version into it here")
    frontmatter = frontmatter.replace(source_name, bundle_name, 1) + f'metadata:\n  version: "{version}"\n'
    return frontmatter + text[end:]


def _write_skill_md(bundle_dir: Path) -> None:
    text = (AUDIT / "SKILL.md").read_text(encoding="utf-8")
    for old, new in AUDIT_SKILL_LINK_REWRITES:
        text = text.replace(old, new)
    stamped = stamp_frontmatter(text, "audit/SKILL.md", SKILL_MD_SOURCE_NAME, SKILL_MD_BUNDLE_NAME, release_version())
    (bundle_dir / "SKILL.md").write_text(stamped, encoding="utf-8")


def _write_references(bundle_dir: Path) -> None:
    references = bundle_dir / "references"
    _copy_tree(AUDIT / "checks", references / "checks")
    _copy_tree(AUDIT / "stacks", references / "stacks")
    prompts_dir = references / "prompts"
    prompts_dir.mkdir(parents=True)
    for name in AUDIT_PROMPT_FILES:
        shutil.copy2(AUDIT / "prompts" / name, prompts_dir / name)
    schema_dir = references / "schema"
    schema_dir.mkdir(parents=True)
    for name in SCHEMA_FILES:
        shutil.copy2(AUDIT_SCHEMA / name, schema_dir / name)


def _build_pyz(dest: Path) -> None:
    build_script = ENGINE / "build.py"
    try:
        subprocess.run([sys.executable, str(build_script)], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise _common.ToolError(
            "audit/engine/build.py failed to build audit.pyz",
            errors=[line for line in exc.stderr.splitlines() if line],
        ) from None
    shutil.copy2(ENGINE / "dist" / "audit.pyz", dest)


def _write_scripts(bundle_dir: Path) -> None:
    scripts = bundle_dir / "scripts"
    tools_dir = scripts / "tools"
    tools_dir.mkdir(parents=True)
    for name in TOOL_FILES:
        shutil.copy2(AUDIT_TOOLS / name, tools_dir / name)
    schema_dir = scripts / "schema"
    schema_dir.mkdir()
    for name in SCHEMA_FILES:
        shutil.copy2(AUDIT_SCHEMA / name, schema_dir / name)
    shutil.copy2(AUDIT / "catalogue.json", scripts / "catalogue.json")
    _copy_tree(ENGINE / "audit", scripts / "engine" / "audit")
    _build_pyz(scripts / "audit.pyz")


def build_bundle(out_dir: Path) -> Path:
    """Build the bundle fresh under `out_dir` and return its path."""
    bundle_dir = out_dir / BUNDLE_NAME
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    _write_license(bundle_dir)
    _write_skill_md(bundle_dir)
    _write_references(bundle_dir)
    _write_scripts(bundle_dir)
    return bundle_dir


# --- The implement bundle ----------------------------------------------------------------------------------

#: The implement recipe's own tools (in `implement/tools/`), and `_audit_tools_path`, which they import first: in a
#: checkout it puts `audit/tools/` on `sys.path`; in the bundle that folder does not exist, so it does nothing.
IMPLEMENT_OWN_TOOL_FILES = (
    "progress.py",
    "check_drift.py",
    "compare_reports.py",
    "_audit_tools_path.py",
)

#: The shared modules the implement tools import (in `audit/tools/`): `progress`, `check_drift` and
#: `compare_reports` import `validate_report`, which imports `_summary` and `engine`; `engine` is the shim.
IMPLEMENT_SHARED_TOOL_FILES = (
    "validate_report.py",
    "_common.py",
    "_jsonschema_subset.py",
    "_summary.py",
)

#: Every file in the implement bundle's `scripts/tools/` apart from the engine shim, in one flat folder.
IMPLEMENT_TOOL_FILES = IMPLEMENT_OWN_TOOL_FILES + IMPLEMENT_SHARED_TOOL_FILES

#: Read at a fixed path next to the tools (`validate_report.RECIPES`, `progress.STATE_SCHEMA`).
IMPLEMENT_SCHEMA_FILES = (
    "audit-report.schema.json",
    "catalogue.schema.json",
    "readiness-state.schema.json",
)

#: The level-2 sections of the Tools CLI reference the implement bundle carries, in page order.
TOOLS_CLI_SECTIONS = ("Every tool", "validate_report.py", "progress.py", "check_drift.py", "compare_reports.py")

#: The source of each carried Markdown file or folder (relative to the repository root) and its place in the
#: bundle. A folder carries every Markdown file in it. Order matters only for the shown order of a listing.
IMPLEMENT_REFERENCES = (
    ("implement/SKILL.md", "SKILL.md"),
    ("implement/state.md", "references/state.md"),
    ("implement/playbooks", "references/playbooks"),
    ("implement/prompts", "references/prompts"),
    ("audit/prompts/talking-to-the-user.md", "references/prompts/talking-to-the-user.md"),
    ("audit/checks", "references/checks"),
    ("audit/stacks", "references/stacks"),
    (
        "implement/docs/architecture/adrs/0003-push-and-pr-policy.md",
        "references/adrs/0003-push-and-pr-policy.md",
    ),
    ("docs/ADR_POLICY.md", "references/adr-policy/ADR_POLICY.md"),
    ("docs/templates/adr-template.md", "references/adr-policy/adr-template.md"),
    ("spec/command-surface.md", "references/spec/command-surface.md"),
    ("spec/decisions/0001-constraint-artifact.md", "references/spec/decisions/0001-constraint-artifact.md"),
    ("spec/decisions/0002-lint-in-the-gate.md", "references/spec/decisions/0002-lint-in-the-gate.md"),
    ("audit/schema/SCHEMA.md", "references/schema/SCHEMA.md"),
    ("docs/reference/tools-cli.md", "references/tools-cli.md"),
)

IMPLEMENT_SKILL_SOURCE_NAME = "name: implement\n"
IMPLEMENT_SKILL_BUNDLE_NAME = f"name: {IMPLEMENT_BUNDLE_NAME}\n"

#: Tool commands in the source text are written for a framework checkout. In the bundle they run from the skill's
#: own folder, where the audit and implement tools sit side by side in `scripts/tools/`; the engine is the audit
#: skill's, installed beside this one. The engine rule comes first, so it wins over the general audit rule.
COMMAND_REWRITES = (
    ("python3 audit/tools/engine.py", f"python3 ../{BUNDLE_NAME}/scripts/tools/engine.py"),
    ("python3 audit/tools/", "python3 scripts/tools/"),
    ("python3 implement/tools/", "python3 scripts/tools/"),
)

#: Written as `scripts/tools/engine.py` in the implement bundle. It holds no engine code of its own.
ENGINE_SHIM = f'''# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Engine shim of the {IMPLEMENT_BUNDLE_NAME} skill, written by build_skills.py.

The implement skill has no engine copy of its own: this module loads engine.py from the {BUNDLE_NAME}
skill installed in the same skills folder, so both skills run one engine. validate_report.py imports it for the
engine's credential patterns. Run the engine itself as ../{BUNDLE_NAME}/scripts/tools/engine.py.
"""

import importlib.util
import sys
from pathlib import Path

import _common

AUDIT_ENGINE = Path(__file__).resolve().parents[3] / "{BUNDLE_NAME}" / "scripts" / "tools" / "engine.py"
MISSING = (
    f"the {BUNDLE_NAME} skill is not installed beside {IMPLEMENT_BUNDLE_NAME}: {{AUDIT_ENGINE}} does not exist; "
    "install both skills, from the same framework release, in the same skills folder"
)

if AUDIT_ENGINE.is_file():
    _spec = importlib.util.spec_from_file_location("engine", AUDIT_ENGINE)
    assert _spec is not None and _spec.loader is not None
    _engine = importlib.util.module_from_spec(_spec)
    sys.modules["engine"] = _engine
    _spec.loader.exec_module(_engine)
else:
    _engine = None

    def load_engine():
        raise _common.UsageError(MISSING)


if __name__ == "__main__":
    if _engine is None:
        sys.exit(f"engine: {{MISSING}}")
    raise SystemExit(_common.run_tool(_engine.INFO, _engine.handler, sys.argv[1:]))
'''

_FENCE = re.compile(r"^\s*(```+|~~~+)")
_LINK = re.compile(r"(?<!!)\[([^\]\n]*)\]\(([^)\s]+)\)")
_EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:|^mailto:")
_LEVEL2 = re.compile(r"^## (.+?)\s*$")


def _carried_markdown() -> dict[Path, str]:
    """Every carried Markdown source file (absolute) and its path in the bundle (POSIX, relative)."""
    carried: dict[Path, str] = {}
    for source, dest in IMPLEMENT_REFERENCES:
        path = REPO / source
        if path.is_dir():
            for file in sorted(path.rglob("*.md")):
                carried[file.resolve()] = f"{dest}/{file.relative_to(path).as_posix()}"
        else:
            carried[path.resolve()] = dest
    return carried


def _carried_other() -> dict[Path, str]:
    """The carried files that are not Markdown: tools and schema files, which links may point at too."""
    carried = {(IMPLEMENT_TOOLS / name).resolve(): f"scripts/tools/{name}" for name in IMPLEMENT_OWN_TOOL_FILES}
    for name in IMPLEMENT_SHARED_TOOL_FILES:
        carried[(AUDIT_TOOLS / name).resolve()] = f"scripts/tools/{name}"
    for name in IMPLEMENT_SCHEMA_FILES:
        carried[(AUDIT_SCHEMA / name).resolve()] = f"references/schema/{name}"
    carried[(AUDIT / "catalogue.json").resolve()] = "scripts/catalogue.json"
    carried[LICENSE_CODE.resolve()] = "LICENSE"
    return carried


def extract_sections(text: str, titles: Sequence[str]) -> str:
    """The page's title line, a note, and only the level-2 sections named in `titles`, in page order."""
    lines = text.splitlines(keepends=True)
    sections: dict[str, list[str]] = {}
    current: str | None = None
    fenced = False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        heading = None if fenced else _LEVEL2.match(line)
        if heading:
            current = heading.group(1)
            sections[current] = []
        if current is not None:
            sections[current].append(line)
    missing = [title for title in titles if title not in sections]
    if missing:
        raise _common.ToolError(f"docs/reference/tools-cli.md has no section {', '.join(missing)}")
    title = lines[0] if lines and lines[0].startswith("# ") else "# Tools CLI Reference\n"
    note = (
        "\nThe sections of the framework's Tools CLI reference that cover the tools this skill carries. The "
        f"engine's own section is in the {BUNDLE_NAME} skill.\n\n"
    )
    body = "".join("".join(sections[t]).rstrip("\n") + "\n\n" for t in titles)
    return title + note + body.rstrip("\n") + "\n"


def _heading_slugs(text: str) -> set[str]:
    import recipe_lint  # a sibling tool; imported here so the audit-only path does not need it

    return recipe_lint.heading_slugs(Path("x.md"), text.splitlines())


def rewrite_text(text: str, source: Path, dest: str, carried: dict[Path, str], slugs: dict[str, set[str]]) -> str:
    """Rewrite one carried file's tool commands and relative links for its place `dest` in the bundle."""
    for old, new in COMMAND_REWRITES:
        text = text.replace(old, new)
    out: list[str] = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if _FENCE.match(line):
            fenced = not fenced
        if not fenced:
            line = _LINK.sub(lambda match: _rewrite_link(match, source, dest, carried, slugs), line)
        out.append(line)
    return "".join(out)


def _plain(label: str, where: str) -> str:
    return f"{label} (framework: `{where}`)" if where else label


def _rewrite_link(
    match: "re.Match[str]", source: Path, dest: str, carried: dict[Path, str], slugs: dict[str, set[str]]
) -> str:
    label, target = match.group(1), match.group(2)
    if _EXTERNAL.match(target):
        return match.group(0)
    path_part, _, fragment = target.partition("#")
    if not path_part:
        return match.group(0) if fragment in slugs.get(dest, set()) else label
    resolved = (source.parent / path_part).resolve()
    try:
        framework_path = resolved.relative_to(REPO).as_posix()
    except ValueError:
        framework_path = path_part
    bundle_path = carried.get(resolved)
    if bundle_path is None:
        return _plain(label, framework_path)
    if fragment and bundle_path.endswith(".md") and fragment not in slugs.get(bundle_path, set()):
        return _plain(label, f"{framework_path}#{fragment}")
    relative = os.path.relpath(bundle_path, os.path.dirname(dest) or ".").replace(os.sep, "/")
    return f"[{label}]({relative}{'#' + fragment if fragment else ''})"


def build_implement_bundle(out_dir: Path) -> Path:
    """Build the implement bundle fresh under `out_dir` and return its path."""
    bundle_dir = out_dir / IMPLEMENT_BUNDLE_NAME
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    _write_license(bundle_dir)
    markdown = _carried_markdown()
    carried = {**_carried_other(), **markdown}
    texts: dict[str, tuple[Path, str]] = {}
    for source, dest in markdown.items():
        text = source.read_text(encoding="utf-8")
        if dest == "SKILL.md":
            text = stamp_frontmatter(
                text, "implement/SKILL.md", IMPLEMENT_SKILL_SOURCE_NAME, IMPLEMENT_SKILL_BUNDLE_NAME, release_version()
            )
        elif dest == "references/tools-cli.md":
            text = extract_sections(text, TOOLS_CLI_SECTIONS)
        texts[dest] = (source, text)
    slugs = {dest: _heading_slugs(text) for dest, (_, text) in texts.items()}
    for dest, (source, text) in texts.items():
        target = bundle_dir / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rewrite_text(text, source, dest, carried, slugs), encoding="utf-8")
    for name in IMPLEMENT_SCHEMA_FILES:
        shutil.copy2(AUDIT_SCHEMA / name, bundle_dir / "references" / "schema" / name)
    tools_dir = bundle_dir / "scripts" / "tools"
    tools_dir.mkdir(parents=True)
    for name in IMPLEMENT_OWN_TOOL_FILES:
        shutil.copy2(IMPLEMENT_TOOLS / name, tools_dir / name)
    for name in IMPLEMENT_SHARED_TOOL_FILES:
        shutil.copy2(AUDIT_TOOLS / name, tools_dir / name)
    (tools_dir / "engine.py").write_text(ENGINE_SHIM, encoding="utf-8")
    schema_dir = bundle_dir / "scripts" / "schema"
    schema_dir.mkdir()
    for name in IMPLEMENT_SCHEMA_FILES:
        shutil.copy2(AUDIT_SCHEMA / name, schema_dir / name)
    shutil.copy2(AUDIT / "catalogue.json", bundle_dir / "scripts" / "catalogue.json")
    return bundle_dir


def _file_count(bundle_dir: Path) -> int:
    return sum(1 for p in bundle_dir.rglob("*") if p.is_file())


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="build_skills.py", description=INFO.summary)
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        metavar="DIR",
        help=f"where to build skills/ (default: {DEFAULT_OUT_DIR.relative_to(REPO)})",
    )
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    out_dir = Path(args.out_dir).expanduser().resolve()
    bundle_dir = build_bundle(out_dir)
    implement_dir = build_implement_bundle(out_dir)
    bundles = [{"name": d.name, "bundle": str(d), "files": _file_count(d)} for d in (bundle_dir, implement_dir)]
    return _common.Result(
        data={"bundle": str(bundle_dir), "files": bundles[0]["files"], "bundles": bundles},
        summary="build_skills: wrote " + "; ".join(f"{b['files']} files to {b['bundle']}" for b in bundles),
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
