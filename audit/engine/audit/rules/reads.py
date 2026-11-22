# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""What each engine check reads in a target: the places, the text and how close its parts must be.

One declaration per implemented check, keyed by check id. Each check module declares its own in
``reads()``, and this module gathers them in registry order; a family that is still one module keeps its
entries in ``_DECLARED`` here. A place built with
``_held`` takes its paths from the engine constant the check itself uses (``module:NAME``), so a name
added to or removed from that constant changes the declaration with it. The map's ``constants`` field
names them when they hold every place of the entry.

The declaration is data for the framework's own tools, never for a verdict: a check module imports this
module only inside ``reads()``, so an audit run never loads it, the ruleset hash does not take it in, and
no report shows it. ``dev/consistency_map_reads.py``
writes the ``reads`` part of the folder ``dev/consistency-map/`` from this table, and
``tests/test_check_reads.py`` runs every check with a recording inventory and compares the paths it
asks for with the declaration (ADR 0012 in the repository's ``docs/architecture/adrs/``).

Scopes, as the map's schema states them: ``root`` is the exact path at the root; ``any-depth`` is the
base name in any folder; ``repository-level`` is the root, ``.github/``, ``.gitlab/`` or ``docs/``;
``glob`` is a glob from the root, where ``**/`` also matches no folder. A ``glob`` place matches folder by
folder: its ``*`` stays inside one name. The engine matches its own globs the same way (``audit/globs.py``), so
the place for the engine's ``.husky/*`` is ``.husky/*``.

A place with ``via`` is read upstream, before any check runs: ``scan-kind`` when the scan's file kinds
(``Kind.TEST``, ``Kind.GENERATED``) match it by name, ``components`` when component detection reads it. The
check then asks for no such path itself. A place with ``case`` ``fold`` is matched in lower case, so a name
in any case meets it. A declaration with ``named_by_text`` also reads paths that the target's own text names,
which no place can list; the field gives the reason. A place with ``unexercised`` is read by the code, but no
fixture can make the check ask for it; the field gives the reason, so the recording test does not need to see it.
A place with ``monotone`` can only gain from added text: whole lines or keys added to the file, at a block
boundary, never lower the check's verdict there (:data:`MONOTONE`, rule R5 of ADR 0012).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import ModuleType

from audit.rules.checks import _common, idx, tst

ROOT = "root"
ANY_DEPTH = "any-depth"
REPOSITORY_LEVEL = "repository-level"
GLOB = "glob"

SCOPES: tuple[str, ...] = (ROOT, ANY_DEPTH, REPOSITORY_LEVEL, GLOB)
KINDS: tuple[str, ...] = ("phrase", "word-list", "fenced-command", "code-span", "key", "exists")
BINDINGS: tuple[str, ...] = ("line", "window", "paragraph", "section", "file")

SCAN_KIND = "scan-kind"
COMPONENTS = "components"

VIAS: tuple[str, ...] = (SCAN_KIND, COMPONENTS)

EXACT = "exact"
FOLD = "fold"

CASES: tuple[str, ...] = (EXACT, FOLD)


@dataclass(frozen=True)
class Place:
    """One path a check reads, at one scope.

    ``constant`` names the engine constant it comes from; ``via`` names the upstream step that reads it for the
    check, ``scan-kind`` or ``components``; ``case`` is ``fold`` when the check matches the name in lower case;
    ``unexercised`` says why no fixture can make the check ask for it; ``monotone`` is true when text added to the
    place can only raise the check's verdict (:data:`MONOTONE`).
    """

    path: str
    scope: str
    constant: str | None = None
    via: str | None = None
    case: str = EXACT
    unexercised: str | None = None
    monotone: bool = False


@dataclass(frozen=True)
class What:
    """What the check looks for in the places: a kind, and the phrases or words when the kind has them."""

    kind: str
    text: tuple[str, ...] = ()


@dataclass(frozen=True)
class Reads:
    """One check's contract with the text it reads."""

    where: tuple[Place, ...]
    what: What
    binding: str
    window: int | None = None
    threshold: str | None = None
    note: str | None = None
    named_by_text: str | None = None

    @property
    def constants(self) -> tuple[str, ...]:
        """The engine constants that hold the whole list of places the check reads itself, in first-seen order.

        Empty when such a place comes from no constant: the map names constants only when they hold every path of
        the entry, since its test compares the two lists both ways (ADR 0012 rule 3). A place with ``via`` is read
        upstream, by the scan or component detection, so it is not on the check's own list.
        """
        references = [place.constant for place in self.where if place.via is None]
        if not references or None in references:
            return ()
        return tuple(dict.fromkeys(reference for reference in references if reference))


def _at(
    scope: str, *paths: str, via: str | None = None, case: str = EXACT, unexercised: str | None = None
) -> tuple[Place, ...]:
    return tuple(Place(path, scope, via=via, case=case, unexercised=unexercised) for path in paths)


def _unexercised(places: tuple[Place, ...], reason: str, *paths: str) -> tuple[Place, ...]:
    """``places`` with ``paths`` marked unexercised for ``reason``; each path must be one of them."""
    missing = set(paths) - {place.path for place in places}
    if missing:
        raise ValueError(f"no such place: {', '.join(sorted(missing))}")
    return tuple(replace(place, unexercised=reason) if place.path in paths else place for place in places)


def _held(module: ModuleType, name: str, scope: str, scopes: dict[str, str] | None = None) -> tuple[Place, ...]:
    """The places one engine constant holds, in its order; ``scopes`` gives a path its own scope."""
    values = getattr(module, name)
    reference = f"{module.__name__}:{name}"
    return tuple(Place(path, (scopes or {}).get(path, scope), reference) for path in values)


def _runners() -> tuple[Place, ...]:
    """The runner manifests and wrappers (``_common.RUNNER_PRECEDENCE``), each read at the root only (``_at_root``)."""
    return _held(_common, "RUNNER_PRECEDENCE", ROOT)


#: The harness paths with a folder and no wildcard (``agt.INSTRUCTION_FIXED_PATHS``), matched as whole paths from
#: the root; ``.claude/CLAUDE.md``, ``.claude/AGENTS.md`` and ``.junie/AGENTS.md`` are left out, since their base
#: names are any-depth places already.
_FOLDER_INSTRUCTION_PATHS: tuple[str, ...] = (
    ".devin/global_rules.md",
    ".gemini/styleguide.md",
    ".github/copilot-instructions.md",
    ".idx/airules.md",
    ".junie/guidelines.md",
    ".junie/playbook.md",
)

#: Why no fixture reaches a go.mod.
_GO_FIXTURE = (
    "no Go fixture: an honest module needs go.sum lines, whose hashes are key-shaped, and EXEC-02 reads a module "
    "with no dependencies, so with no go.sum, as unlocked"
)


#: The reads that a family with no module per check still declares here, keyed by check id.
_DECLARED: dict[str, Reads] = {
    "IDX-01": Reads(
        where=(*_held(idx, "_PROJECT_CONFIGS", ANY_DEPTH),),
        what=What("phrase", ("codebase-memory-mcp",)),
        binding="file",
        note=(
            "Each config is kept when Inventory.has finds its name at any depth but read by its exact root "
            "path, so a nested-only copy reads as unreadable (UNKNOWN). Three user configs under $HOME are "
            "read too, unless --no-user-config, and Claude Code's ~/.claude.json is parsed: its top-level "
            "mcpServers or the projects entry of this checkout's path."
        ),
    ),
    "IDX-02": Reads(
        where=(*_at(ROOT, ".codebase-memory/graph.db.zst"),),
        what=What("exists"),
        binding="file",
        note=(
            "The store is looked for in AUDIT_INDEX_STORE, then three folders under $HOME, then this team "
            "artifact in the target; only a *.db store is opened, and its projects table is read for a "
            "root_path that resolves to the target."
        ),
    ),
    "IDX-03": Reads(
        where=(
            *_at(
                ROOT,
                ".codebase-memory/graph.db.zst",
                unexercised="IDX-03 looks for the store only as a Tier-C probe (--run-gates) on a git target, and "
                "the recording runs no probe",
            ),
        ),
        what=What("exists"),
        binding="file",
        note=(
            "The store of IDX-02 (no repository text); a git-revision column of the matching project row is "
            "compared with HEAD as a probe. With no such column, its indexed_at is compared with the time HEAD "
            "last moved (git's committer time and reflog)."
        ),
    ),
    "TST-01": Reads(
        where=(
            *_runners(),
            *_at(
                GLOB,
                "**/*test_*",
                "**/*_test.*",
                "**/*.test.*",
                "**/*.spec.*",
                "**/tests/**",
                "**/test/**",
                "**/__tests__/**",
                via=SCAN_KIND,
            ),
            *_at(ANY_DEPTH, "*_test.go"),
            *_at(GLOB, "tests/**/*.rs"),
        ),
        what=What("key"),
        binding="file",
        note=(
            "The test verb is resolved from the runner manifests. A test file is a scanned file whose "
            "lower-case path holds a test hint (test_, _test., .test., .spec., tests/, test/, __tests__/) and"
            " has a test-source suffix, plus *_test.go and tests/*.rs; the globs approximate that substring "
            "match."
        ),
    ),
    "TST-02": Reads(
        where=(*_runners(),),
        what=What("key"),
        binding="file",
        note=(
            "No file text: the resolved test verb runs as a read-only probe, only with --run-gates and "
            "--allow-probe test. Every runner manifest counts only at the root, where it is read. A "
            "package.json verb runs with node_modules/.bin first on PATH."
        ),
    ),
    "TST-03": Reads(
        where=(
            *_at(
                GLOB,
                "**/*test_*",
                "**/*_test.*",
                "**/*.test.*",
                "**/*.spec.*",
                "**/tests/**",
                "**/test/**",
                "**/__tests__/**",
                via=SCAN_KIND,
            ),
            *_at(ANY_DEPTH, "*_test.go"),
            *_at(GLOB, "tests/**/*.rs"),
        ),
        what=What("phrase"),
        binding="file",
        note=(
            "Each readable test file of TST-01 is searched for skip, ignore and expected-failure markers of "
            "its language family (by suffix), for example @pytest.mark.skip, it.skip, t.Skip(, #[ignore], "
            "@Disabled. A census: any count passes."
        ),
    ),
    "TST-04": Reads(
        where=(
            *_held(tst, "_FASTPATH_DOCS", ANY_DEPTH),
            *_at(
                GLOB,
                "**/*test_*",
                "**/*_test.*",
                "**/*.test.*",
                "**/*.spec.*",
                "**/tests/**",
                "**/test/**",
                "**/__tests__/**",
                via=SCAN_KIND,
            ),
            *_held(tst, "_FRAMEWORK_TEST_GLOBS", ANY_DEPTH, {"tests/*.rs": GLOB}),
        ),
        what=What("fenced-command"),
        binding="line",
        note=(
            "Only bash, sh, shell, console or zsh fences count, each physical line is one command, and a "
            "plain full-suite run does not count. With no fenced match, an inline code span outside any fence "
            "is read with the same patterns. A file is kept only at the root, so a nested-only copy is "
            "skipped. README.md stands for the root README: the root file whose name starts with readme, any "
            "case, README.md first, as for HYG-01. The test files "
            "give the runner family: the scanned files with a test hint, as in TST-01, and the two framework globs."
        ),
    ),
    "TST-05": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".coveragerc",
                ".coveragerc.toml",
                ".nycrc",
                ".nycrc.json",
                ".nycrc.yml",
                ".nycrc.yaml",
                "nyc.config.js",
                "nyc.config.cjs",
                ".c8rc",
                ".c8rc.json",
                "codecov.yml",
                ".codecov.yml",
                ".codecov.yaml",
                "coveralls.yml",
                ".coveralls.yml",
            ),
            *_at(
                ROOT,
                "setup.cfg",
                "tox.ini",
                "pytest.ini",
            ),
            *_at(ANY_DEPTH, "vitest.config.*", "jest.config.*", "vite.config.*", "karma.conf.*"),
            *_runners(),
        ),
        what=What("key"),
        binding="file",
        note=(
            "Coverage config names count on presence at any depth; the root files are read for "
            "[tool.coverage, [coverage, --cov or jacoco; a runner config at any depth for a coverage key; "
            "package scripts and resolved verbs for --coverage, --cov, c8, nyc, jacoco or go test -cover."
        ),
    ),
}

#: Rule R5 of ADR 0012: the places where text added to a file can only raise the check's verdict, by check. "Added"
#: means whole lines or keys, put in at a block boundary (between paragraphs, list items or sections; a new heading
#: only where a section ends), in a file that already exists, with nothing changed or removed, and the file still
#: well formed (balanced fences, a manifest its tool still parses). The consistency map then infers no touch from such
#: a place for a move marked ``mode: add``. Each set was confirmed against the check's code:
#:
#: - ``AGT-03``, ``AGT-06``, ``AGT-09``: a pattern found on any line, or a branch named anywhere, in the entry file;
#:   another line only adds matches. The other ``AGT-09`` places declare branches, so a line there can add an
#:   unnamed one.
#: - ``AGT-05``: the names half (``_mentioned_verbs``). A runner manifest is the resolution half, and stays out.
#: - ``AGT-07``: the concerns are found on any prohibition line of the file. A section opened by its heading word
#:   stays open; one opened by three prohibition lines keeps them, since a new heading goes only where a section ends.
#: - ``AGT-08``: only the root ``AGENTS.md`` text is read, for the statement of harnesses. A vendor file is not
#:   monotone: a line added to a pointer file makes it a competitor (``is_agents_md_pointer``).
#: - ``BASE-01``, ``BASE-03``, ``BASE-04``: a baseline, ratchet or coverage phrase found in a document adds evidence;
#:   no document line takes any away.
#: - ``CON-01``, ``CON-02``: more code spans in the prohibitions sections. ``CON-01`` passes on any span that exists,
#:   ``CON-02`` when every test folder is covered. A new block is quiet or not by its own lines (``_quiet_lines``).
#: - ``EXEC-03``, ``TST-04``: the first documented setup or single-test command passes; another cannot remove it.
#: - ``HYG-13``: each item is file-wide or, for the gate item, one paragraph; a new paragraph splits no other.
#: - ``CI-02``, ``CI-03``, ``TST-01`` on the runner manifests: a local verb, target or test verb that exists keeps
#:   existing, and ``CI-02`` fails only on a CI verb with no local definition. A key added where no local verb
#:   resolved yet can turn ``CI-02`` from ``UNKNOWN`` into ``FAIL``; a move that can do so stays ``replace``.
#:
#: Left out after the same review: ``CMD-01``, since a verb added on a second runner turns ``PASS`` into ``PARTIAL``
#: (``check_cmd01``), and the ``CLAUDE.md`` place of ``AGT-08``.


def _gathered() -> dict[str, Reads]:
    """The reads of every implemented engine check, in registry order. The agent checks have no code and no entry.

    A check's reads come from its own module's ``reads()``, or from ``_DECLARED`` while its family keeps one module.
    """
    import importlib

    from audit.rules.registry import REGISTRY

    table: dict[str, Reads] = {}
    for spec in REGISTRY:
        if spec.id in _DECLARED:
            table[spec.id] = _DECLARED[spec.id]
        elif spec.impl is not None:
            table[spec.id] = importlib.import_module(spec.impl.__module__).reads()
    return table


READS: dict[str, Reads] = _gathered()


_ENTRY_FILES: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md")
_ROOT_DOCUMENTS: tuple[str, ...] = (*_ENTRY_FILES, "README.md", "CONTRIBUTING.md")
_RUNNER_PATHS: tuple[str, ...] = tuple(place.path for place in _runners())
MONOTONE: dict[str, tuple[str, ...]] = {
    "AGT-03": _ENTRY_FILES,
    "AGT-05": _ENTRY_FILES,
    "AGT-06": _ENTRY_FILES,
    "AGT-07": _ENTRY_FILES,
    "AGT-08": ("AGENTS.md",),
    "AGT-09": _ENTRY_FILES,
    "CI-02": _RUNNER_PATHS,
    "CI-03": _RUNNER_PATHS,
    "BASE-01": _ENTRY_FILES,
    "BASE-03": (*_ROOT_DOCUMENTS, "README*"),
    "BASE-04": (*_ROOT_DOCUMENTS, "README*"),
    "CON-01": _ENTRY_FILES,
    "CON-02": _ENTRY_FILES,
    "EXEC-03": (*_ROOT_DOCUMENTS, "README*"),
    "TST-01": _RUNNER_PATHS,
    "TST-04": _ROOT_DOCUMENTS,
    "HYG-13": ("CONTRIBUTING*",),
}


def _with_monotone(check: str, declared: Reads) -> Reads:
    """``declared`` with the places :data:`MONOTONE` names for ``check`` marked; each named path must be a place."""
    paths = set(MONOTONE.get(check, ()))
    missing = paths - {place.path for place in declared.where}
    if missing:
        raise ValueError(f"{check}: no such place: {', '.join(sorted(missing))}")
    return replace(declared, where=tuple(replace(place, monotone=place.path in paths) for place in declared.where))


READS = {check: _with_monotone(check, declared) for check, declared in READS.items()}
