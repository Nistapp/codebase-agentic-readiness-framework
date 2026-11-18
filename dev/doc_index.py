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

:func:`query` takes ``<address> [--at REF]`` and prints a node and its edges, or ``--report [--at REF]`` and prints
the reports of plan 9.4 (a report only, never a gate).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence

DEV = Path(__file__).resolve().parent
REPO = DEV.parent
CONFIG = DEV / "docindex.config.json"
QUERY = "query"

if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from docindex import cli, extract, ids, manifest  # noqa: E402
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
