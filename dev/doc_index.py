# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The project entry point of the document index: ``python3 dev/doc_index.py <command> ...``.

It puts ``dev/`` on ``sys.path``, loads this repository's config, ``dev/docindex.config.json``, and calls
:func:`docindex.cli.main`. The ``docindex`` package is the generic core and imports no other ``dev/`` module; this
file is the one place that may (ADR 0011 in ``docs/architecture/adrs/``). The subcommands are in
:mod:`docindex.cli`, except ``query``: :func:`main` routes it to :func:`query`, which runs
:func:`docindex.ids.query_main` on the index of the full config.

For the sweep, :func:`bundle_sources` loads the module that ``sweep.bundle_references.module`` names
(``dev/build_skills.py``) and reads the constants that ``sweep.bundle_references.constants`` names
(``AUDIT_REFERENCES`` and ``IMPLEMENT_REFERENCES``, each a tuple of ``(source, place in the bundle)`` pairs). The
sources, files and folders, are the bundle part of the sweep scope. They are read from the working tree's module even
with ``--at``; the core then resolves them in the tree at the ref.

For the index's ``bundles`` edges, :func:`bundle_files` reads the same module and lists, for each of the two
bundles, the files it ships, as :func:`build_skills.build_bundle` and :func:`build_skills.build_implement_bundle`
copy them: each reference source (a folder carries its Markdown files), the tools, the schema files, the catalogue,
the licence and, for the audit bundle, the engine package. Each bundle is keyed by its build folder,
``dev/dist/skills/<bundle name>``. :func:`main` puts them in the config's ``bundle_files`` key, which
:func:`docindex.extract.extract` reads; ``dev/build_skills.py`` itself does not change.

For ``manifest``, :func:`build_bundles` loads the same module and calls its ``build_bundle`` and
``build_implement_bundle`` with the folder it is given: the core's fresh temporary folder, never
``dev/dist/skills/``. A build failure (the module's ``ToolError``) becomes :class:`docindex.manifest.BuildError`.

For ``evidence run``, :func:`evidence_project` names the engine folder, ``audit/engine/``, and :func:`evidence_targets`
gives the targets of each kind:

- ``repo``: this repository with the excludes of ``make self-audit`` (:data:`SELF_AUDIT_EXCLUDES`);
- ``fixtures``: every engine fixture that ``dev/eval/generate_fixture_expected.py`` generates an expected file for,
  materialised into the run's temporary folder by that module's ``materialise`` (a one-commit git repository with a
  fixed identity and date), with an isolated ``HOME`` for a fixture in ``NEEDS_ISOLATED_ENV``, as that module
  prepares it. Loading the engine's fixture matrix writes no bytecode into ``audit/``;
- ``scaffold``: :func:`scaffold_targets` runs the greenfield scaffolder, ``greenfield/bootstrap/bootstrap.py``, in
  process on ``greenfield/templates/`` into the run's temporary folder, as the engine's positive-fixture test does
  (ADR 0010). Every input is fixed, so two runs of the same tree give the same scaffold: the arguments
  (:data:`SCAFFOLD_ARGS`), the date the scaffolder writes into ``docs/architecture/`` (:data:`SCAFFOLD_DATE`), and
  the one commit on ``dev``, made with the fixed identity and date of ``generate_fixture_expected.py``. The engine
  audits it with an isolated ``HOME``, so the operator's index store does not reach the report.

:func:`query` takes ``<address> [--at REF]`` and prints a node and its edges, or ``--report [--at REF]`` and prints
the reports of plan 9.4 (a report only, never a gate).
"""

from __future__ import annotations

import contextlib
import datetime
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence

DEV = Path(__file__).resolve().parent
REPO = DEV.parent
CONFIG = DEV / "docindex.config.json"
QUERY = "query"
ENGINE_DIR = REPO / "audit" / "engine"
FIXTURE_GENERATOR = DEV / "eval" / "generate_fixture_expected.py"
#: The ``--exclude`` globs of ``SELF_AUDIT_FLAGS`` in the Makefile.
SELF_AUDIT_EXCLUDES: tuple[str, ...] = ("artefacts/*", "dist/*")
SCAFFOLDER = REPO / "greenfield" / "bootstrap" / "bootstrap.py"
TEMPLATES = REPO / "greenfield" / "templates"
#: The report name and folder name of the ``scaffold`` target.
SCAFFOLD = "scaffold"
#: The scaffolder's arguments after the target: every value it would read from git config is given, and it makes no
#: commit of its own (:func:`scaffold_targets` makes one with a fixed identity and date).
SCAFFOLD_ARGS: tuple[str, ...] = (
    "--name",
    SCAFFOLD,
    "--author",
    "agentic-readiness-eval",
    "--email",
    "eval@agentic-readiness.invalid",
    "--github-owner",
    "agentic-readiness-eval",
    "--no-git",
)
#: The date the scaffolder writes for ``YYYY-MM-DD`` in ``docs/architecture/``, in place of today.
SCAFFOLD_DATE = datetime.date(2026, 1, 1)
#: The branch of the scaffold's one commit, as the scaffolder's own ``git init -b dev``.
SCAFFOLD_BRANCH = "dev"
SCAFFOLD_COMMIT_MESSAGE = "chore: scaffold project"

if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from docindex import cli, evidence, extract, ids, manifest  # noqa: E402
from docindex.gitread import RefTree, Tree, WorkTree  # noqa: E402
from docindex.model import Index  # noqa: E402


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    """The project config: a JSON object."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return data


def _bundle_module(config: Mapping[str, Any]) -> ModuleType | None:
    """The bundle module that ``sweep.bundle_references.module`` names, loaded once; ``None`` when none is named."""
    references = config.get("sweep", {}).get("bundle_references")
    if not references:
        return None
    path = REPO / references["module"]
    name = f"_doc_index_{path.stem}"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {references['module']}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return module


def bundle_sources(config: Mapping[str, Any]) -> list[str]:
    """The repository paths of every file and folder the skill bundles carry, sorted, from the bundle module."""
    module = _bundle_module(config)
    if module is None:
        return []
    sources: set[str] = set()
    for constant in config["sweep"]["bundle_references"]["constants"]:
        for source, _place in getattr(module, constant):
            sources.add(str(source))
    return sorted(sources)


def _relative(module: ModuleType, path: Path) -> str:
    return Path(path).relative_to(module.REPO).as_posix()


def _references(module: ModuleType, pairs: Iterable[tuple[str, str]]) -> list[str]:
    """The bundle entries of reference sources: a folder carries every Markdown file under it."""
    return [f"{source}/*.md" if (Path(module.REPO) / source).is_dir() else str(source) for source, _place in pairs]


def bundle_files(config: Mapping[str, Any]) -> dict[str, list[str]]:
    """Each bundle's build folder (relative to the repository) and its entries, read from the bundle module.

    An entry is a file, ``<folder>/*.md`` (every Markdown file under the folder) or ``<folder>/`` (every file).
    """
    module = _bundle_module(config)
    if module is None:
        return {}
    out = _relative(module, module.DEFAULT_OUT_DIR)
    shared = [_relative(module, module.AUDIT / "catalogue.json"), _relative(module, module.LICENSE_CODE)]
    audit = [
        *_references(module, module.AUDIT_REFERENCES),
        *(_relative(module, module.AUDIT_TOOLS / name) for name in module.TOOL_FILES),
        *(_relative(module, module.AUDIT_SCHEMA / name) for name in module.SCHEMA_FILES),
        *shared,
        _relative(module, module.ENGINE / "audit") + "/",
    ]
    implement = [
        *_references(module, module.IMPLEMENT_REFERENCES),
        *(_relative(module, module.IMPLEMENT_TOOLS / name) for name in module.IMPLEMENT_OWN_TOOL_FILES),
        *(_relative(module, module.AUDIT_TOOLS / name) for name in module.IMPLEMENT_SHARED_TOOL_FILES),
        *(_relative(module, module.AUDIT_SCHEMA / name) for name in module.IMPLEMENT_SCHEMA_FILES),
        *(_relative(module, module.IMPLEMENT_TEMPLATES / name) for name in module.IMPLEMENT_TEMPLATE_FILES),
        *shared,
    ]
    return {
        f"{out}/{module.BUNDLE_NAME}": sorted(set(audit)),
        f"{out}/{module.IMPLEMENT_BUNDLE_NAME}": sorted(set(implement)),
    }


def build_bundles(config: Mapping[str, Any], out_dir: Path) -> None:
    """Build both skill bundles into ``out_dir`` with the bundle module; raise ``BuildError`` when that fails."""
    module = _bundle_module(config)
    if module is None:
        raise manifest.BuildError("the config names no bundle module (sweep.bundle_references.module)")
    if Path(out_dir).resolve() == Path(module.DEFAULT_OUT_DIR).resolve():
        raise manifest.BuildError("refusing to build the manifest into the project's own bundle folder")
    try:
        module.build_bundle(out_dir)
        module.build_implement_bundle(out_dir)
    except module._common.ToolError as exc:
        raise manifest.BuildError(f"the bundle build failed: {exc}") from exc


def _load_once(name: str, path: Path) -> ModuleType:
    """The module at ``path``, loaded once under ``name``, with no bytecode written while it loads."""
    module = sys.modules.get(name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path.relative_to(REPO)}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    finally:
        sys.dont_write_bytecode = previous
    return module


def _fixture_generator() -> ModuleType:
    """``dev/eval/generate_fixture_expected.py``, loaded once, with no bytecode written while it loads the engine."""
    return _load_once("_doc_index_generate_fixture_expected", FIXTURE_GENERATOR)


def fixture_targets(work: Path) -> list[evidence.Target]:
    """Every engine fixture with a row in the engine's fixture matrix, materialised under ``work``."""
    generator = _fixture_generator()
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        matrix = generator.engine_matrix()
    finally:
        sys.dont_write_bytecode = previous
    targets: list[evidence.Target] = []
    for name in sorted(matrix.MATRIX):
        if not matrix.MATRIX[name]:
            continue
        try:
            fixture = matrix.support.fixture(name)
            path = generator.materialise(fixture, name, work / "targets", matrix.FORCE_ADD.get(name))
        except (OSError, RuntimeError) as exc:
            raise evidence.EvidenceError(f"cannot materialise the fixture {name}: {exc}") from exc
        env: dict[str, str] = {}
        if name in matrix.NEEDS_ISOLATED_ENV:
            home = work / "homes" / name
            home.mkdir(parents=True)
            env = {"HOME": str(home), "AUDIT_INDEX_STORE": str(home / "absent-store")}
        targets.append(evidence.Target(name=name, path=path, env=env))
    return targets


class _FixedDate(datetime.date):
    """A date whose ``today`` is :data:`SCAFFOLD_DATE`."""

    @classmethod
    def today(cls) -> _FixedDate:
        return cls(SCAFFOLD_DATE.year, SCAFFOLD_DATE.month, SCAFFOLD_DATE.day)


def _scaffold(target: Path, templates: Path) -> None:
    """Run the scaffolder's ``main`` in process into ``target``, with :data:`SCAFFOLD_DATE` as today."""
    scaffolder = _load_once("_doc_index_bootstrap", SCAFFOLDER)
    argv = [str(target), "--templates", str(templates), *SCAFFOLD_ARGS]
    out = io.StringIO()
    previous = scaffolder.dt
    setattr(scaffolder, "dt", SimpleNamespace(date=_FixedDate))
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = scaffolder.main(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    finally:
        setattr(scaffolder, "dt", previous)
    if code != 0:
        raise evidence.EvidenceError(f"the scaffolder failed (exit {code}): {out.getvalue().strip()}")


def _commit(target: Path, identity: Mapping[str, str]) -> None:
    """Make ``target`` a git repository on :data:`SCAFFOLD_BRANCH` with one commit by ``identity``, no hook run."""
    env = {**os.environ, **identity}
    for args in (
        ("init", "--quiet", "-b", SCAFFOLD_BRANCH),
        ("add", "-A"),
        ("commit", "--quiet", "--no-gpg-sign", "--no-verify", "-m", SCAFFOLD_COMMIT_MESSAGE),
    ):
        proc = subprocess.run(["git", "-C", str(target), *args], capture_output=True, text=True, env=env, check=False)
        if proc.returncode != 0:
            raise evidence.EvidenceError(f"git {args[0]} failed in the scaffold: {proc.stderr.strip()}")


def scaffold_targets(work: Path, templates: Path = TEMPLATES) -> list[evidence.Target]:
    """A fresh scaffold of ``templates`` under ``work``, committed, with an isolated ``HOME`` for the engine."""
    target = work / "targets" / SCAFFOLD
    target.mkdir(parents=True)
    _scaffold(target, templates)
    _commit(target, _fixture_generator().GIT_COMMIT_ENV)
    home = work / "homes" / SCAFFOLD
    home.mkdir(parents=True)
    env = {"HOME": str(home), "AUDIT_INDEX_STORE": str(home / "absent-store")}
    return [evidence.Target(name=SCAFFOLD, path=target, env=env)]


def evidence_targets(kind: str, work: Path) -> list[evidence.Target]:
    """The targets of ``evidence run``: this repository (``repo``), the engine fixtures (``fixtures``) or a fresh
    scaffold of the greenfield templates (``scaffold``)."""
    if kind == "repo":
        return [evidence.Target(name="repo", path=REPO, excludes=SELF_AUDIT_EXCLUDES)]
    if kind == SCAFFOLD:
        return scaffold_targets(work)
    return fixture_targets(work)


def evidence_project() -> evidence.Project:
    """The audit engine of this repository and its targets."""
    return evidence.Project(engine_dir=ENGINE_DIR, repo=REPO, targets=evidence_targets)


def full_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The project config with its ``bundle_files`` key filled from the bundle module."""
    loaded = dict(load_config() if config is None else config)
    loaded[extract.BUNDLE_FILES] = bundle_files(loaded)
    return loaded


def build_index(config: Mapping[str, Any], at: str | None = None, root: Path = REPO) -> Index:
    """The index of the working tree, or of the tree at the git ref ``at``."""
    tree: Tree = RefTree(root, at) if at is not None else WorkTree(root)
    return extract.extract(tree, config).index


def query(argv: Sequence[str], config: Mapping[str, Any] | None = None) -> int:
    """Run ``query <address> [--at REF]`` or ``query --report [--at REF]`` (the arguments after ``query``)."""
    loaded = full_config() if config is None else config
    code, out, err = ids.query_main(argv, lambda at: build_index(loaded, at))
    sys.stdout.write(out)
    sys.stderr.write(err)
    return code


def main(argv: Sequence[str] | None = None) -> int:
    """Run one subcommand: ``query`` with :func:`query`, every other one with :func:`docindex.cli.main`."""
    config = full_config()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == [QUERY]:
        return query(arguments[1:], config)
    return cli.main(
        arguments,
        config,
        root=REPO,
        bundle_sources=lambda: bundle_sources(config),
        build_bundles=lambda out_dir: build_bundles(config, out_dir),
        evidence_project=evidence_project(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
