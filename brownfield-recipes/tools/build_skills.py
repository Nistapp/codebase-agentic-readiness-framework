# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Build the agentic-readiness-audit skill bundle: a self-contained copy of the audit recipe.

One command::

    build_skills.py [--out-dir DIR]

The bundle is what a harness installs and runs with no checkout of this repository: `skills-ref validate`
(S4.5.2) and an install smoke-run (S4.5.3) both act on it, never on the source tree directly. It is written
to ``<repo>/brownfield-recipes/dist/skills/agentic-readiness-audit/`` by default (``*.pyz`` and
``/brownfield-recipes/dist/`` are both gitignored); ``--out-dir`` changes where ``skills/`` itself goes, for a
build that is not meant to land there.

It has three parts, replaced whole on every run so a stale leftover from an earlier build can never survive:

- ``SKILL.md``: the recipe's own file (``audit/SKILL.md``), with its frontmatter ``name`` rewritten from
  ``audit`` (the source folder's name, which `recipe_lint.py` requires there) to the bundle's own name,
  ``agentic-readiness-audit`` (the name `skills-ref` checks against the bundle's folder name).
- ``references/``: the check files (``audit/checks/``), the stack profiles (``stacks/``) and the schema docs
  (``schema/*.schema.json``, ``SCHEMA.md``, ``LICENSING.md``) — read by the model, not run.
- ``scripts/``: the five tools the recipe's Tools table calls (``facts.py``, ``engine.py``, ``report.py``,
  ``validate_report.py``, ``render_report.py``) and the private modules they import; the schema files and
  ``catalogue.json`` those tools read at a fixed path next to themselves (``validate_report.RECIPES``);
  the engine's own ``audit`` package, which ``engine.py`` imports from ``../deterministic-audit`` relative to
  itself, so this mirrors that one folder level inside ``scripts/`` too; and ``audit.pyz``, the engine's
  single-file build, for a person who wants to run it directly with no Python path setup at all.

Some of ``SKILL.md``'s own relative links point outside what this bundle carries (the Tools CLI reference,
``spec/command-surface.md``, ``brownfield-legacy/Phased-Approach.md`` from the check files) — found, not
fixed, here: scoping the bundle to a self-contained, link-resolving tree is left to a later leaf (S4.5.2,
which validates the bundle, or S4.5.3's smoke run) to confirm whether it matters in practice.

``audit.pyz`` is produced by running the engine's own ``tools/build.py`` as a subprocess (never imported;
``deterministic-audit/tools/`` is excluded from the engine's own standard-library-only boundary) and copying
its output in. Everything else is a plain file copy, so two builds from the same source tree are byte-for-byte
identical apart from ``audit.pyz``, whose zip entries carry the source files' own modification times — which
do not change between two builds in the same session.

Failure behaviour: a target problem (the engine's ``tools/build.py`` is missing, or exits nonzero) is exit 1
with the subprocess's stderr in ``data.errors``. Nothing else in this tool can fail the way a user-facing
argument can, since it takes none but ``--out-dir``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import _common

INFO = _common.ToolInfo(
    name="build_skills",
    summary="Build the agentic-readiness-audit skill bundle under dist/skills/.",
    synopsis=("build_skills.py [--out-dir DIR]",),
    writes=(
        "dist/skills/agentic-readiness-audit/ (SKILL.md, references/, scripts/), replaced whole on each run; "
        "--out-dir changes where dist/skills/ itself goes."
    ),
)

RECIPES = Path(__file__).resolve().parent.parent
BUNDLE_NAME = "agentic-readiness-audit"
DEFAULT_OUT_DIR = RECIPES / "dist" / "skills"

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
#: these must sit beside `scripts/tools/` the same way they sit beside `tools/` in this repository.
SCHEMA_FILES = (
    "audit-intake.schema.json",
    "audit-report.schema.json",
    "catalogue.schema.json",
    "eval-expected.schema.json",
    "facts.schema.json",
    "SCHEMA.md",
    "LICENSING.md",
)

SKILL_MD_SOURCE_NAME = "name: audit\n"
SKILL_MD_BUNDLE_NAME = f"name: {BUNDLE_NAME}\n"


def _copy_tree(source: Path, dest: Path) -> None:
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


def _write_skill_md(bundle_dir: Path) -> None:
    text = (RECIPES / "audit" / "SKILL.md").read_text(encoding="utf-8")
    if SKILL_MD_SOURCE_NAME not in text:
        raise _common.ToolError(
            f"audit/SKILL.md's frontmatter does not contain {SKILL_MD_SOURCE_NAME!r}; "
            "it may have been renamed without updating this tool"
        )
    (bundle_dir / "SKILL.md").write_text(text.replace(SKILL_MD_SOURCE_NAME, SKILL_MD_BUNDLE_NAME), encoding="utf-8")


def _write_references(bundle_dir: Path) -> None:
    references = bundle_dir / "references"
    _copy_tree(RECIPES / "audit" / "checks", references / "checks")
    _copy_tree(RECIPES / "stacks", references / "stacks")
    schema_dir = references / "schema"
    schema_dir.mkdir(parents=True)
    for name in SCHEMA_FILES:
        shutil.copy2(RECIPES / "schema" / name, schema_dir / name)


def _build_pyz(dest: Path) -> None:
    build_script = RECIPES / "deterministic-audit" / "tools" / "build.py"
    try:
        subprocess.run([sys.executable, str(build_script)], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise _common.ToolError(
            "deterministic-audit/tools/build.py failed to build audit.pyz",
            errors=[line for line in exc.stderr.splitlines() if line],
        ) from None
    shutil.copy2(RECIPES / "deterministic-audit" / "dist" / "audit.pyz", dest)


def _write_scripts(bundle_dir: Path) -> None:
    scripts = bundle_dir / "scripts"
    tools_dir = scripts / "tools"
    tools_dir.mkdir(parents=True)
    for name in TOOL_FILES:
        shutil.copy2(RECIPES / "tools" / name, tools_dir / name)
    schema_dir = scripts / "schema"
    schema_dir.mkdir()
    for name in SCHEMA_FILES:
        shutil.copy2(RECIPES / "schema" / name, schema_dir / name)
    shutil.copy2(RECIPES / "catalogue.json", scripts / "catalogue.json")
    _copy_tree(RECIPES / "deterministic-audit" / "audit", scripts / "deterministic-audit" / "audit")
    _build_pyz(scripts / "audit.pyz")


def build_bundle(out_dir: Path) -> Path:
    """Build the bundle fresh under `out_dir` and return its path."""
    bundle_dir = out_dir / BUNDLE_NAME
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    _write_skill_md(bundle_dir)
    _write_references(bundle_dir)
    _write_scripts(bundle_dir)
    return bundle_dir


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="build_skills.py", description=INFO.summary)
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        metavar="DIR",
        help=f"where to build skills/ (default: {DEFAULT_OUT_DIR.relative_to(RECIPES.parent)})",
    )
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    out_dir = Path(args.out_dir).expanduser().resolve()
    bundle_dir = build_bundle(out_dir)
    files = sorted(p.relative_to(bundle_dir).as_posix() for p in bundle_dir.rglob("*") if p.is_file())
    return _common.Result(
        data={"bundle": str(bundle_dir), "files": len(files)},
        summary=f"build_skills: wrote {len(files)} files to {bundle_dir}",
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
