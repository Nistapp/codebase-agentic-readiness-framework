# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""What each engine check reads in a target: the places, the text and how close its parts must be.

One declaration per implemented check, keyed by check id, beside the registry. A place built with
``_held`` takes its paths from the engine constant the check itself uses (``module:NAME``), so a name
added to or removed from that constant changes the declaration with it. The map's ``constants`` field
names them when they hold every place of the entry.

The declaration is data for the framework's own tools, never for a verdict: no check imports this
module, the ruleset hash does not take it in, and no report shows it. ``dev/consistency_map_reads.py``
writes the ``reads`` part of ``dev/consistency-map.json`` from this table, and
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

from audit import ignore
from audit.rules.checks import _common, hyg, idx, tst

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
    "AGT-01": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".augment-guidelines",
                ".clinerules",
                ".cursorrules",
                ".goosehints",
                ".roorules",
                ".rules",
                ".voidrules",
                ".windsurfrules",
                "AGENT.md",
                "AGENTS.local.md",
                "AGENTS.md",
                "AGENTS.override.md",
                "AmazonQ.md",
                "CLAUDE.local.md",
                "CLAUDE.md",
                "CONVENTIONS.md",
                "CRUSH.md",
                "GEMINI.md",
                "QWEN.md",
                "WARP.md",
                "agents.md",
                "replit.md",
            ),
            *_at(ROOT, *_FOLDER_INSTRUCTION_PATHS),
            *_at(
                GLOB,
                ".claude/rules/**/*.md",
                ".github/instructions/**/*.instructions.md",
                ".cursor/rules/**/*.mdc",
                ".devin/rules/**/*.md",
                ".windsurf/rules/**/*.md",
                ".continue/rules/**/*.md",
                ".clinerules/**",
                ".cline/rules/**",
                ".roo/rules/**",
                ".roo/rules-*/**",
                ".roorules-*",
                ".junie/rules/**/*.md",
                ".amazonq/rules/**/*.md",
                ".kiro/steering/**/*.md",
                ".trae/rules/**/*.md",
                ".augment/rules/**/*.md",
            ),
            *_at(ANY_DEPTH, ".aider.conf.yml"),
        ),
        what=What("exists"),
        binding="file",
        threshold="AGENTS.md at the root, at least 400 characters, no stub marker",
        note=(
            "The root AGENTS.md text is read for its length, four stub phrases and the words todo, tbd and "
            "placeholder at a line start or in brackets; a root agents.md is the only mis-cased name found. A"
            " fixed harness path with a folder (.github/copilot-instructions.md) counts only from the root."
        ),
    ),
    "AGT-02": Reads(
        where=(
            *_at(GLOB, "*/**/AGENTS.md"),
            *_at(
                ROOT,
                "package.json",
                "pnpm-workspace.yaml",
                "pom.xml",
                "settings.gradle",
                "settings.gradle.kts",
                "go.work",
                "Cargo.toml",
                via=COMPONENTS,
            ),
        ),
        what=What("exists"),
        binding="file",
        threshold="every declared component has an AGENTS.md",
        note=(
            "The root manifests declare the components (components.py); for each one <component>/AGENTS.md "
            "must exist, matched as a path suffix at any depth. The root component is left out, so the root "
            "AGENTS.md never counts. The suffix test runs over agt.instruction_paths, which scans every "
            "instruction file name, but only a path ending in <component>/AGENTS.md counts, so the other names "
            "are never read for this check."
        ),
    ),
    "AGT-03": Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What(
            "word-list",
            (
                "docs/",
                "docs",
                "STYLE_GUIDE.md",
                "artefact/",
                "artefacts/",
                "artifact/",
                "artifacts/",
            ),
        ),
        binding="file",
        threshold="all three named",
        note=(
            "Three items, each on any line: docs, the style guide name and the scratch folder. CLAUDE.md is "
            "read only when the root AGENTS.md is missing or empty."
        ),
    ),
    "AGT-04": Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What(
            "phrase",
            (
                "same changeset",
                "same change set",
            ),
        ),
        binding="window",
        window=5,
        note=(
            "A trigger word (public interface, observable behaviour, architecture, ADR, documentation, docs) "
            "must stand within the two lines before or after the phrase: a five-line window."
        ),
    ),
    "AGT-05": Reads(
        where=(
            *_at(ROOT, "AGENTS.md", "CLAUDE.md"),
            *_runners(),
        ),
        what=What(
            "word-list",
            (
                "format",
                "format:check",
                "lint",
                "typecheck",
                "test",
                "check",
                "security",
            ),
        ),
        binding="file",
        threshold="all seven named and resolved",
        note=(
            "Each verb must stand as a whole token (format inside format:check does not count). format:check "
            "also counts as format-check or formatCheck, the spellings spec/command-surface.md accepts; no "
            "other script name counts. The resolution half reads the runner manifests as CMD-01 does."
        ),
    ),
    "AGT-06": Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What("word-list"),
        binding="line",
        threshold="two or more boundary rules naming real paths",
        note=(
            "A line with one of 18 rule words (must, never, only, module, owns, import, layer and others) "
            "and, on the same line, a path token with a slash that names a scanned file or a folder above "
            "one."
        ),
        named_by_text="each path token of a boundary line is looked up with Inventory.has",
    ),
    "AGT-07": Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What("word-list"),
        binding="line",
        threshold="all four concerns covered",
        note=(
            "A prohibitions section must exist (a heading word, or three prohibition lines under a heading). "
            "Then any line of the whole file with a prohibition word and a concern word on that line: tests, "
            "generated files, the default branch, secrets."
        ),
    ),
    "AGT-08": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".augment-guidelines",
                ".clinerules",
                ".cursorrules",
                ".goosehints",
                ".roorules",
                ".rules",
                ".voidrules",
                ".windsurfrules",
                "AGENT.md",
                "AGENTS.local.md",
                "AGENTS.md",
                "AGENTS.override.md",
                "AmazonQ.md",
                "CLAUDE.local.md",
                "CLAUDE.md",
                "CONVENTIONS.md",
                "CRUSH.md",
                "GEMINI.md",
                "QWEN.md",
                "WARP.md",
                "agents.md",
                "replit.md",
            ),
            *_at(ROOT, *_FOLDER_INSTRUCTION_PATHS),
            *_at(
                GLOB,
                ".claude/rules/**/*.md",
                ".github/instructions/**/*.instructions.md",
                ".cursor/rules/**/*.mdc",
                ".devin/rules/**/*.md",
                ".windsurf/rules/**/*.md",
                ".continue/rules/**/*.md",
                ".clinerules/**",
                ".cline/rules/**",
                ".roo/rules/**",
                ".roo/rules-*/**",
                ".roorules-*",
                ".junie/rules/**/*.md",
                ".amazonq/rules/**/*.md",
                ".kiro/steering/**/*.md",
                ".trae/rules/**/*.md",
                ".augment/rules/**/*.md",
            ),
            *_at(ANY_DEPTH, ".aider.conf.yml"),
        ),
        what=What(
            "phrase",
            (
                "read by",
                "supported harness",
                "supported harnesses",
                "AGENTS.md",
                "@AGENTS.md",
            ),
        ),
        binding="line",
        note=(
            "The instruction-file set of AGT-01 gives the competitors and the reach. The statement is read in"
            " the root AGENTS.md only, never CLAUDE.md, and needs a known harness name on the same line. With a root"
            " AGENTS.md, each vendor file is read too: one whose few content lines all name AGENTS.md is a pointer,"
            " not a competitor, and one that imports @AGENTS.md shadows nothing."
        ),
    ),
    "AGT-09": Reads(
        where=(
            *_at(ROOT, "AGENTS.md", "CLAUDE.md"),
            *_at(GLOB, ".github/rulesets/**/*.json"),
            *_at(ANY_DEPTH, ".github/settings.yml"),
            *_at(GLOB, "**/*.tf"),
        ),
        what=What(
            "word-list",
            (
                "branch",
                "branches",
                "branching",
                "main",
                "dev",
                "trunk",
                "tag",
                "release",
                "publish",
                "deploy",
                "push",
            ),
        ),
        binding="file",
        threshold="a branch word, a release word and every protected branch named",
        note=(
            "Each literal branch the declared rules protect (ruleset JSON, the Settings app's branches:, "
            "Terraform protection resources) must stand as a whole word anywhere in the entry file. "
            ".github/settings.yml passes Inventory.has at any depth but is read at the root only."
        ),
    ),
    "AGT-10": Reads(
        where=(
            *_at(
                ROOT,
                ".aider.conf.yml",
                ".codex/config.toml",
                ".gemini/settings.json",
                "opencode.json",
                "AGENTS.md",
                "CLAUDE.md",
            ),
        ),
        what=What("phrase"),
        binding="line",
        note=(
            "Each file a config names (aider read:, three Codex keys, Gemini context.fileName, opencode "
            "instructions) must exist. A deferral phrase (first read, read ... first, before you ... read, "
            "start by reading, refer to ... first) with an existing .md, .txt, .yml, .yaml, .json or .toml "
            "reference on the same line, unnamed by any config, fails."
        ),
        named_by_text="each file a harness config names must exist",
    ),
    "AGT-12": Reads(
        where=(
            *_at(ROOT, "AGENTS.md", "CLAUDE.md"),
            *_at(GLOB, "**/*communicat*.md", case=FOLD),
        ),
        what=What("word-list"),
        binding="section",
        threshold="the reader, how to report and how to ask for a decision",
        note=(
            "A heading outside a fence that matches communicat*, write for people, how to write, reporting "
            "and others opens a section with its subsections; a Markdown file whose name holds communicat, "
            "named in a link or code span, is read whole. Three element word groups must appear in those "
            "bodies and files together."
        ),
    ),
    "AGT-13": Reads(
        where=(
            *_at(
                GLOB,
                "*convention*",
                "code_style*",
                "coding_standards*",
                "*coding-guidelines*",
                "docs/**/*convention*",
                "docs/**/code_style*",
                "docs/**/coding_standards*",
                "docs/**/*coding-guidelines*",
                ".github/**/*convention*",
                ".github/**/code_style*",
                ".github/**/coding_standards*",
                ".github/**/*coding-guidelines*",
                case=FOLD,
            ),
            *_at(ROOT, "AGENTS.md", "CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"),
        ),
        what=What("word-list"),
        binding="file",
        threshold="all five items and no stub word",
        note=(
            "Conventions files match the globs by lower-case base name at the root or anywhere under docs/ or"
            " .github/, with a prose extension or none, never docs/STYLE_GUIDE.md; the four root files give "
            "level 2-6 conventions sections that are not about git or docs. Five items over all sources "
            "together (naming, layering, error handling and logging, testing, a formatter or linter config "
            "name), plus TBD or TODO outside code."
        ),
    ),
    "EXEC-01": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".nvmrc",
                ".node-version",
                ".python-version",
                "gradlew",
                "mvnw",
                "global.json",
                "rust-toolchain.toml",
                "rust-toolchain",
                ".ruby-version",
                ".php-version",
                ".tool-versions",
                "package.json",
                "pyproject.toml",
                "go.mod",
                "composer.json",
            ),
        ),
        what=What("exists"),
        binding="file",
        threshold="every ecosystem pinned and every module reached",
        note=(
            "Pin files count by existence; .tool-versions needs a line for the ecosystem (java for jvm), package.json "
            "engines.node, pyproject.toml requires-python, go.mod a go directive and composer.json "
            "config.platform.php or require.php. A module manifest no pin"
            " reaches (its folder or a parent) is PARTIAL; a parent go.mod or composer.json does not reach a"
            " nested one."
        ),
    ),
    "EXEC-02": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                "package-lock.json",
                "npm-shrinkwrap.json",
                "pnpm-lock.yaml",
                "yarn.lock",
                "bun.lock",
                "bun.lockb",
                "poetry.lock",
                "uv.lock",
                "Pipfile.lock",
                "pdm.lock",
                "gradle.lockfile",
                "Cargo.lock",
                "go.sum",
                "Gemfile.lock",
                "composer.lock",
                "packages.lock.json",
            ),
            *_at(
                ANY_DEPTH,
                "package.json",
                "pyproject.toml",
                "requirements.txt",
                "requirements-dev.txt",
                "Cargo.toml",
                "Directory.Build.props",
                "Directory.Build.targets",
                "Directory.Packages.props",
            ),
            *_at(ANY_DEPTH, "go.mod", unexercised=_GO_FIXTURE),
            *_at(GLOB, "**/*.csproj", "**/*.fsproj", "**/*.vbproj"),
        ),
        what=What("exists"),
        binding="file",
        threshold="every lockfile tracked and in step with the manifest beside it",
        note=(
            "Lockfiles of each ecosystem's package managers (stack.PACKAGE_MANAGERS) at any depth, shallowest"
            " first, and whether git tracks each one; a tracked lockfile the walk skipped as ignored counts "
            "too. Every tracked lockfile is compared with the dependency "
            "names of the manifests in its own folder; for .NET those are the PackageReference names of the "
            "project files in that folder, and a package reference in a Directory.* file in that folder or "
            "above it leaves the lockfile unverified."
        ),
    ),
    "EXEC-03": Reads(
        where=(
            *_at(ROOT, "README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"),
            *_at(GLOB, "README*"),
            *_at(
                ANY_DEPTH,
                ".devcontainer/devcontainer.json",
                ".devcontainer.json",
                "docker-compose.yml",
                "docker-compose.yaml",
                "compose.yml",
                "compose.yaml",
                "Dockerfile",
                "setup.sh",
                "bootstrap.sh",
                "dev-setup.sh",
                "Dockerfile.*",
                "*.Dockerfile",
                "*.dockerfile",
            ),
            *_at(GLOB, ".devcontainer/*.json", ".devcontainer/*/devcontainer.json"),
            *_at(ROOT, "Makefile", "package.json"),
        ),
        what=What("fenced-command"),
        binding="line",
        threshold="a documented non-interactive setup command",
        note=(
            "A fenced shell command or an inline code span in the four docs whose tool and first argument "
            "install or set up passes. "
            "Else a setup file (at any depth, a Dockerfile with a variant in its name included) or a setup "
            "target (setup, bootstrap, install, dev, dev-setup) of the root Makefile or package.json named "
            "anywhere in the four docs passes; present but not named is PARTIAL."
        ),
    ),
    "EXEC-04": Reads(
        where=(
            *_at(GLOB, "**/*.sh", "**/*.bash", "**/*.zsh", "**/*.fish", "**/*.ksh", "**/*.ps1"),
            *_at(ANY_DEPTH, "Dockerfile"),
            *_at(GLOB, "**"),
            *_at(ANY_DEPTH, ".env.example", ".env.sample", ".env.template", "env.example"),
        ),
        what=What("key"),
        binding="line",
        threshold="every referenced key declared by an example file that covers each file reading it",
        note=(
            "References: ${VAR} and ${VAR:?msg} in shell files and Dockerfile, less the keys the same file "
            "assigns, and os.environ, getenv, process.env and ENV[...] in every file of kind source or script. "
            "A shell reference with a fallback (${VAR:-x}, ${VAR-x}, ${VAR:=x}, ${VAR:+x}) is optional: listed, "
            "never missing. Declared keys are the KEY= lines of the four example file names at any depth; an "
            "example file covers the files in its own folder and below it, so a key counts when every file "
            "reading it is covered by one that names it. A fixed allow-list of host, CI and shell-set names "
            "is exempt."
        ),
    ),
    "EXEC-05": Reads(
        where=(
            *_at(
                GLOB,
                "**/dist/**",
                "**/generated/**",
                "**/vendor/**",
                "**/*.min.js",
                "**/*.min.css",
                "**/*.map",
                "**/*.pb.go",
                "**/*.g.cs",
                "**/*.designer.cs",
                "**/*.lock.gen",
                via=SCAN_KIND,
            ),
            *_at(GLOB, "**/build/**"),
            *_held(ignore, "IGNORE_FILE_NAMES", ROOT, {".gitignore": ANY_DEPTH}),
        ),
        what=What(
            "phrase",
            (
                "@generated",
                "do not edit",
                "generated by",
                "code generated",
                "auto-generated",
                "autogenerated",
                "this file is generated",
            ),
        ),
        binding="window",
        window=20,
        threshold="every tracked generated file carries a marker",
        note=(
            "The scan classifies a file as generated by a case-insensitive substring of its path "
            "(scan._GENERATED_HINTS), a folder named dist (scan._GENERATED_DIRS) or by suffix. A tracked text file "
            "under a folder named build (scan.SIGNED_GENERATED_DIRS) counts too when an ignore rule (the root "
            "ignore files and every nested .gitignore) also matches it; another file there keeps its own kind. "
            "Only tracked files are read. The marker must stand in the first 20 lines, case-insensitive."
        ),
    ),
    "EXEC-06": Reads(
        where=(
            *_at(ROOT, "README.md", "AGENTS.md", "CLAUDE.md"),
            *_at(GLOB, "README*"),
            *_runners(),
            *_at(ANY_DEPTH, "gradlew", "mvnw"),
        ),
        what=What("fenced-command"),
        binding="line",
        threshold="every documented command resolves",
        note=(
            "Fenced bash, sh, shell, console and zsh blocks in the three root docs only, continuations "
            "joined, repeats and placeholders skipped. The first word must be a known tool, a shell keyword, "
            "a resolved verb, an npm script or bin of the root package.json, a root Makefile target or a real"
            " path."
        ),
    ),
    "EXEC-07": Reads(
        where=(
            *_at(GLOB, "eslint.config.*"),
            *_at(ROOT, ".eslintrc"),
            *_at(GLOB, ".eslintrc.*"),
            *_at(
                ROOT,
                "biome.json",
                "biome.jsonc",
                "ruff.toml",
                ".ruff.toml",
                ".flake8",
                ".pylintrc",
                ".golangci.yml",
                ".golangci.yaml",
                "clippy.toml",
                ".stylelintrc",
            ),
            *_at(GLOB, ".stylelintrc.*"),
            *_at(ROOT, "oxlint.json", ".oxlintrc.json"),
            *_at(GLOB, "prettier.config.*"),
            *_at(ROOT, ".prettierrc"),
            *_at(GLOB, ".prettierrc.*"),
            *_at(ROOT, ".clang-format", "rustfmt.toml", ".rustfmt.toml", "dprint.json"),
            *_at(GLOB, "vitest.config.*", "jest.config.*"),
            *_at(ROOT, "pytest.ini", "tox.ini"),
            *_at(GLOB, ".mocharc.*"),
            *_at(ROOT, "karma.conf.js"),
            *_at(GLOB, "cypress.config.*"),
            *_at(
                ROOT,
                "tsconfig.json",
                "jsconfig.json",
                "mypy.ini",
                ".mypy.ini",
                "pyrightconfig.json",
                ".gitleaks.toml",
                "semgrep.yml",
                ".semgrep.yml",
                ".snyk",
                "osv-scanner.toml",
                ".bandit",
            ),
            *_unexercised(
                _runners(),
                "EXEC-07 resolves the typecheck verb only when one pyright config stands beside one mypy config, and "
                "the resolver looks a wrapper up only for a Gradle or Maven build; no fixture is both",
                "gradlew",
                "mvnw",
            ),
        ),
        what=What("exists"),
        binding="file",
        threshold="one config per concern",
        note=(
            "Root files only, matched by fnmatch against the configs of six concerns, plus the [tool.*] "
            "tables of the root pyproject.toml; more than one for a concern fails. One pyright config beside "
            "one mypy config is a mirror when the typecheck verb, resolved on the runner manifests and "
            "followed through the root Makefile, runs mypy."
        ),
    ),
    "EXEC-08": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".gitlab-ci.yml",
                ".justfile",
                ".lefthook.yaml",
                ".lefthook.yml",
                "GNUmakefile",
                "Justfile",
                "Makefile",
                "Taskfile.yaml",
                "Taskfile.yml",
                "justfile",
                "lefthook.yaml",
                "lefthook.yml",
                "makefile",
                "package.json",
            ),
            *_at(GLOB, "**/*.mk", ".github/workflows/**/*.yml", ".github/workflows/**/*.yaml", ".husky/*"),
            *_at(ROOT, "renovate.json", ".renovaterc", ".renovaterc.json", ".github/renovate.json"),
            *_at(ANY_DEPTH, "pyproject.toml"),
            *_at(ANY_DEPTH, "go.mod", unexercised=_GO_FIXTURE),
            *_at(ANY_DEPTH, "Cargo.toml"),
            *_at(GLOB, "**/requirements*.txt"),
        ),
        what=What("word-list"),
        binding="line",
        threshold="no literal tool version outside a manifest",
        note=(
            "Each non-comment line, split at shell operators: a launcher (npx, uvx, pip install, go install, "
            "cargo install and others) then a name@version or name==version token in the same segment; in a "
            "workflow also the version input of four installer actions. A file a Renovate custom manager "
            "matches is skipped, and every package.json, pyproject.toml, requirements*.txt, go.mod and "
            "Cargo.toml is read to see whether a manifest holds the version."
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
    "NAV-01": Reads(
        where=(
            *_at(
                ROOT,
                "package.json",
                "pnpm-workspace.yaml",
                "pom.xml",
                "settings.gradle",
                "settings.gradle.kts",
                "go.work",
                "Cargo.toml",
                via=COMPONENTS,
            ),
            *_at(
                ROOT,
                "pyproject.toml",
                "build.gradle",
                "build.gradle.kts",
                "go.mod",
                "Gemfile",
                "composer.json",
                via=COMPONENTS,
            ),
            *_at(ROOT, "*.sln", "*.slnx", "*.csproj", "*.fsproj", "*.vbproj", via=COMPONENTS),
            *_at(
                GLOB,
                "apps/*",
                "services/*",
                "packages/*",
                "components/*",
                "modules/*",
                "libs/*",
                "workers/*",
                via=COMPONENTS,
            ),
        ),
        what=What("key"),
        binding="file",
        note=(
            "Workspace members are read from the root manifests (components.py); a member or candidate counts"
            " when a build manifest is found under it. When the root folder itself holds no build manifest, a"
            " top-level folder with one in it is a candidate too. The root counts as declared when any of the nine "
            "manifest names is found at any depth, or a .NET solution or project file is in the root folder"
            " itself (in a member's or candidate's own folder for that member or candidate)."
        ),
    ),
    "NAV-02": Reads(
        where=(
            *_at(
                ROOT,
                "package.json",
                "index.js",
                "index.ts",
                "index.mjs",
                "index.cjs",
                "src/index.js",
                "src/index.ts",
                "src/index.mjs",
                "server.js",
                "server.ts",
                "src/server.js",
                "src/server.ts",
                "main.js",
                "main.ts",
                "main.mjs",
                "main.cjs",
                "src/main.js",
                "src/main.ts",
                "app.js",
                "app.ts",
                "src/app.js",
                "src/app.ts",
                "main.py",
                "app.py",
                "src/main.py",
                "src/app.py",
                "manage.py",
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "src/main.rs",
                "src/bin/main.rs",
                "main.rs",
                "Cargo.toml",
                "Program.cs",
                "program.cs",
                "src/Program.cs",
                "config.ru",
                "app.rb",
                "main.rb",
                "bin/rails",
                "bin/setup",
                "index.php",
                "public/index.php",
                "bin/console",
            ),
            *_at(ANY_DEPTH, "__main__.py"),
            *_at(GLOB, "**"),
        ),
        what=What("exists"),
        binding="line",
        note=(
            "Fixed names are matched by exact path per detected ecosystem; source files (glob **) are grepped"
            " for a line that starts with func main(, a JVM main method or a Spring Boot or Quarkus marker,"
            " and build files for io.quarkus. A Python __main__ guard alone is not read."
        ),
    ),
    "NAV-03": Reads(
        where=(*_at(GLOB, "**"),),
        what=What("exists"),
        binding="file",
        note=(
            "Every scanned file: over 512 KiB, a folder with more than 50 files of its own, a binary, or a "
            "generated file with .min. in its path. A file whose exact base name is a lockfile name "
            "(stack.LOCKFILE_NAMES) is left out of the size count."
        ),
    ),
    "NAV-04": Reads(
        where=(
            *_at(GLOB, "docs/architecture/**", "docs/adr/**"),
            *_at(ANY_DEPTH, "*.mmd", "*.puml", "*.drawio", "*.excalidraw", "*.svg", "*.png"),
        ),
        what=What("exists"),
        binding="file",
        note=(
            "Any file under docs/architecture/ or docs/adr/, or any file whose lower-case name ends with a "
            "diagram suffix; a Mermaid block inside a page does not count."
        ),
    ),
    "NAV-05": Reads(
        where=(*_at(ANY_DEPTH, "*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs", "*.cjs"),),
        what=What("phrase"),
        binding="file",
        note=(
            "Python, parsed with ast: a module-level def, async def or class and a method of a public class, "
            "each with a public name, is documented when ast finds its docstring; a test file (a tests or test "
            "folder, a test_*.py or *_test.py name) is not read, and a file that does not parse falls back to "
            "column-0 lines with the docstring on the next non-blank line. TypeScript or JavaScript: an export "
            "declaration is documented when the line before (blank lines skipped) ends a /** */ block. Only the "
            "main language is read."
        ),
    ),
    "SEC-01": Reads(
        where=(
            *_at(ANY_DEPTH, ".env", ".env.*", "*.env", "env.*", ".gitignore"),
            *_at(ROOT, ".cbmignore", ".cursorignore", ".aiderignore", ".rooignore"),
        ),
        what=What("exists"),
        binding="file",
        note=(
            "Tracked files (git) whose base name is .env or starts with .env., less six template names, fail;"
            " so does a tracked file an ignore rule also matches whose base name starts with .env, ends with .env"
            " or starts with env., less the templates. The ignore rules (the five root ignore files and every nested .gitignore) are probed with .env "
            "and .env.local at the root and one folder down."
        ),
    ),
    "SEC-02": Reads(
        where=(
            *_at(GLOB, "**"),
            *_at(ROOT, ".secrets.baseline", ".gitleaksignore", ".gitleaks.toml"),
        ),
        what=What("phrase"),
        binding="line",
        note=(
            "Each line of every tracked text file (less template names) is tested for a key shape or a "
            "keyword with a secret-looking literal; a line with a placeholder word is skipped. The root "
            "allowlists suppress a hit, .secrets.baseline and .gitleaksignore by path and line number."
        ),
    ),
    "SEC-03": Reads(
        where=(*_held(ignore, "IGNORE_FILE_NAMES", ROOT, {".gitignore": ANY_DEPTH}),),
        what=What("exists"),
        binding="file",
        note=(
            "The ignore rules are probed with eleven sample paths (.env, .env.local, id_rsa, server.pem, "
            "server.key, server.p12, server.pfx, app.keystore, server.crt, server.cer, .aws/credentials); "
            "nested .gitignore files come from the scan and from git ls-files. A tracked file an ignore rule also "
            "matches whose name is one of the nine non-dotenv shapes fails."
        ),
    ),
    "HYG-01": Reads(
        where=(*_at(GLOB, "README*"),),
        what=What(
            "word-list",
            (
                "todo",
                "tbd",
                "placeholder",
                "lorem ipsum",
                "coming soon",
                "fill this in",
                "<describe",
            ),
        ),
        binding="file",
        note=(
            "Root files whose base name starts with readme, any case; README.md is read first. It needs 200 "
            "trimmed characters, no stub marker, and one line that is not a heading. Under 400 characters a marker "
            "anywhere counts, and lorem ipsum or <describe counts at any length; in a longer README a word marker "
            "counts only when it opens a line and the line's end or punctuation follows it."
        ),
    ),
    "HYG-02": Reads(
        where=(*_at(REPOSITORY_LEVEL, "CODEOWNERS"),),
        what=What("exists"),
        binding="file",
    ),
    "HYG-03": Reads(
        where=(*_at(REPOSITORY_LEVEL, "pull_request_template*"),),
        what=What("exists"),
        binding="file",
        note="The base name is matched case-insensitively.",
    ),
    "HYG-04": Reads(
        where=(
            *_at(GLOB, ".github/ISSUE_TEMPLATE/**"),
            *_at(ROOT, ".github/ISSUE_TEMPLATE.md"),
        ),
        what=What("exists"),
        binding="file",
    ),
    "HYG-05": Reads(
        where=(*_at(REPOSITORY_LEVEL, "CONTRIBUTING*"),),
        what=What("exists"),
        binding="file",
        note=(
            "The base name starts with contributing, any case, and has a doc suffix (.md, .rst, .txt, "
            ".markdown, .adoc) or none."
        ),
    ),
    "HYG-06": Reads(
        where=(*_at(REPOSITORY_LEVEL, "SECURITY*"),),
        what=What("exists"),
        binding="file",
        note="The base name starts with security, any case, and has a doc suffix or none.",
    ),
    "HYG-07": Reads(
        where=(*_at(REPOSITORY_LEVEL, "CHANGELOG*", "CHANGES*", "HISTORY*"),),
        what=What("exists"),
        binding="file",
        note=(
            "The first match in sort order (any case, doc suffix or none) is dated by git against HEAD; at "
            "most 365 days apart passes."
        ),
    ),
    "HYG-08": Reads(
        where=(*_at(REPOSITORY_LEVEL, "*release*", case=FOLD),),
        what=What("exists"),
        binding="file",
        note=(
            "The lower-case base name holds release and ends with a doc suffix, so a release.yml workflow never counts."
        ),
    ),
    "HYG-09": Reads(
        where=(*_held(hyg, "_DEPENDENCY_AUTOMATION", REPOSITORY_LEVEL),),
        what=What("key"),
        binding="file",
        note=(
            "Dependabot: the package-ecosystem of each updates item, and target-branch with ignore or groups "
            "is a defect; Renovate JSON: enabledManagers. Each detected ecosystem, plus github-actions with "
            "GitHub CI, must be covered."
        ),
    ),
    "HYG-10": Reads(
        where=(*_at(GLOB, "LICENSE*", "LICENCE*", "COPYING*", "COPYRIGHT*", "UNLICENSE*"),),
        what=What("exists"),
        binding="file",
        note="Root files only, any case, with a doc suffix or none.",
    ),
    "HYG-11": Reads(
        where=(
            *_at(GLOB, ".github/rulesets/**/*.json"),
            *_at(ANY_DEPTH, ".github/settings.yml", "*.tf"),
            *_at(
                GLOB,
                "**/*branch-protection*",
                "**/*branch_protection*",
                ".github/workflows/*.yml",
                ".github/workflows/*.yaml",
            ),
            *_at(ANY_DEPTH, ".gitlab-ci.yml"),
        ),
        what=What("key"),
        binding="line",
        note=(
            "Declared rules: ruleset JSON, the branches: list of .github/settings.yml, Terraform protection "
            "resources, and any path holding branch-protection or branch_protection (a document records, "
            "another file declares). With an integration branch and another protected branch, one GitHub or "
            "GitLab CI line must read the pull request's source branch, outside a group: or ref: key. "
            ".github/settings.yml passes Inventory.has at any depth but is read at the root only."
        ),
    ),
    "HYG-13": Reads(
        where=(*_at(REPOSITORY_LEVEL, "CONTRIBUTING*"),),
        what=What("phrase"),
        binding="paragraph",
        note=(
            "Item (b) needs a CI word and either same or the gate command in one paragraph (lines between "
            "blank lines); items (a), a link to README.md or AGENTS.md or a setup command, and (c), words for"
            " branches, commits and pull requests, are file-wide. The link target is never read."
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
