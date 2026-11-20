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
``glob`` is a glob from the root, where ``**/`` also matches no folder.

A place with ``via`` is read upstream, before any check runs: ``scan-kind`` when the scan's file kinds
(``Kind.TEST``, ``Kind.GENERATED``) match it by name, ``components`` when component detection reads it. The
check then asks for no such path itself. A place with ``case`` ``fold`` is matched in lower case, so a name
in any case meets it. A declaration with ``named_by_text`` also reads paths that the target's own text names,
which no place can list; the field gives the reason. A place with ``unexercised`` is read by the code, but no
fixture can make the check ask for it; the field gives the reason, so the recording test does not need to see it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import ModuleType

from audit import ignore
from audit.rules.checks import _common, con, doc, hyg, idx, tst

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
    ``unexercised`` says why no fixture can make the check ask for it.
    """

    path: str
    scope: str
    constant: str | None = None
    via: str | None = None
    case: str = EXACT
    unexercised: str | None = None


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


#: The reads of every implemented engine check, in registry order. The agent checks have no code and no entry.
READS: dict[str, Reads] = {
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
                ".junie/rules/*.md",
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
            *_at(GLOB, "**/AGENTS.md"),
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
            "must exist, matched as a path suffix at any depth. The suffix test runs over agt.instruction_paths,"
            " which scans every instruction file name, but only a path ending in <component>/AGENTS.md counts,"
            " so the other names are never read for this check."
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
                ".junie/rules/*.md",
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
            *_at(GLOB, ".github/rulesets/*.json"),
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
    "DOC-01": Reads(
        where=(
            *_at(GLOB, "docs/**/*.md", "docs/**/*.markdown"),
            *_at(ROOT, "docs"),
        ),
        what=What("exists"),
        binding="file",
        threshold="one or more Markdown files under docs/",
        note=("With no Markdown file, the folder docs is looked for on disk: present is PARTIAL, absent is FAIL."),
    ),
    "DOC-02": Reads(
        where=(*_at(ROOT, "docs/STYLE_GUIDE.md", "AGENTS.md", "CLAUDE.md"),),
        what=What("exists"),
        binding="file",
        threshold="present and named",
        note=(
            "The exact path docs/STYLE_GUIDE.md, never a suffix match. The entry file (doc.py's own reader) "
            "must hold STYLE_GUIDE.md on any line, else PARTIAL."
        ),
    ),
    "DOC-03": Reads(
        where=(
            *_held(doc, "_SCRATCH_ROOTS", ROOT),
            *_held(ignore, "IGNORE_FILE_NAMES", ROOT, {".gitignore": ANY_DEPTH}),
        ),
        what=What("exists"),
        binding="file",
        note=(
            "The scratch folders in the scan or on disk, the files git tracks there, and every ignore rule: "
            "the five root ignore files and each nested .gitignore. The folder's own .gitignore and a file a "
            "! rule re-includes are allowed."
        ),
    ),
    "DOC-04": Reads(
        where=(
            *_at(GLOB, "docs/architecture/adrs/**/*.md", "docs/adr/**/*.md"),
            *_at(
                ROOT,
                "docs/architecture/adrs/README.md",
                "docs/architecture/adrs/index.md",
                "docs/architecture/adrs/_index.md",
                "docs/architecture/README.md",
                "docs/architecture/index.md",
                "docs/adr/README.md",
                "docs/adr/index.md",
                "docs/adr/_index.md",
                "docs/README.md",
                "docs/index.md",
            ),
        ),
        what=What("exists"),
        binding="file",
        threshold="every ADR listed in the index and none retired",
        note=(
            "Entries are NNN- or NNNN-slug.md files in the first folder that holds a file, less a template; "
            "each must appear in the index by file name or its first four characters. A status line, a "
            "superseded-by or replaced-by line, or a Status section that retires a record is PARTIAL."
        ),
    ),
    "DOC-05": Reads(
        where=(*_at(GLOB, "docs/**/*.md", "docs/**/*.markdown"),),
        what=What(
            "word-list",
            (
                "simply",
                "just",
                "obviously",
                "clearly",
                "basically",
                "easily",
                "utilize",
                "utilise",
                "leverage",
                "in order to",
                "and/or",
                "etc",
            ),
        ),
        binding="file",
        threshold="at most 10% long sentences and 1 vague word per 1,000 words",
        note=(
            "Prose only (fences, tables, headings, comments, code spans and prose-check off regions skipped);"
            " a sentence over 25 words, or 20 in a numbered step, is long. Each page under docs/explanation/ "
            "or docs/tutorials/, less README.md and index.md, needs a Mermaid block."
        ),
    ),
    "CMD-01": Reads(
        where=(*_runners(),),
        what=What(
            "key",
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
        threshold="all seven verbs on one runner",
        note=(
            "Every runner (package.json, the Makefile, the Taskfile, pyproject.toml, the Gradle and the Maven "
            "build) counts only at the root, where it is read. A root gradlew or mvnw only chooses the launcher. "
            "format:check is also read under the spelling its runner accepts."
        ),
    ),
    "CMD-02": Reads(
        where=(*_runners(), *_at(ROOT, "settings.gradle", "settings.gradle.kts")),
        what=What("key", ("check",)),
        binding="section",
        threshold="check composes format-check, typecheck and test",
        note=(
            "The command of the resolved check verb, split at shell operators; in a Makefile a prerequisite "
            "that is no verb is followed once, and so is a package script that is no verb. A Gradle check is read "
            "from the build file's plugins and check dependsOn wiring; a settings file that includes subprojects, "
            "or an unknown plugin or task, makes a check still missing a concern UNKNOWN. A Maven lifecycle check "
            "is UNKNOWN."
        ),
    ),
    "CMD-03": Reads(
        where=(*_runners(),),
        what=What("key", ("check",)),
        binding="section",
        threshold="every second check delegates to the first",
        note=(
            "Every runner that declares check (lifecycle tasks left out); each after the first must call the "
            "first by a per-runner pattern or a check call through another runner."
        ),
    ),
    "CMD-04": Reads(
        where=(*_runners(),),
        what=What(
            "key",
            (
                "format:check",
                "lint",
                "typecheck",
                "test",
                "check",
                "security",
            ),
        ),
        binding="section",
        threshold="no read-only verb invokes a write verb",
        note=(
            "The command of each resolved read-only verb, segment by segment: a write verb through a runner "
            "or a writing tool form (prettier --write, ruff format, eslint --fix, npm install and others) "
            "fails."
        ),
    ),
    "TOOL-01": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".prettierrc",
                ".prettierrc.json",
                ".prettierrc.json5",
                ".prettierrc.yml",
                ".prettierrc.yaml",
                ".prettierrc.toml",
                ".prettierrc.js",
                ".prettierrc.cjs",
                ".prettierrc.mjs",
                "prettier.config.js",
                "prettier.config.cjs",
                "prettier.config.mjs",
                "biome.json",
                "biome.jsonc",
                ".dprint.json",
                "dprint.json",
                "ruff.toml",
                ".ruff.toml",
                "black.toml",
                ".black.toml",
                "rustfmt.toml",
                ".rustfmt.toml",
                ".clang-format",
                "pint.json",
                ".php-cs-fixer.php",
                ".php-cs-fixer.dist.php",
            ),
            *_runners(),
        ),
        what=What("key"),
        binding="file",
        note=(
            "Formatter config names count on presence at any depth; the root pyproject.toml is read for "
            "[tool.black|ruff|autopep8|yapf] and the root package.json for a prettier key. The format verb is"
            " resolved from the runner manifests."
        ),
    ),
    "TOOL-02": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".eslintrc",
                ".eslintrc.json",
                ".eslintrc.js",
                ".eslintrc.cjs",
                ".eslintrc.mjs",
                ".eslintrc.yml",
                ".eslintrc.yaml",
                "eslint.config.js",
                "eslint.config.cjs",
                "eslint.config.mjs",
                "eslint.config.ts",
                "biome.json",
                "biome.jsonc",
                "ruff.toml",
                ".ruff.toml",
                ".flake8",
                ".pylintrc",
                "pylintrc",
                ".golangci.yml",
                ".golangci.yaml",
                ".golangci.toml",
                "clippy.toml",
                ".clippy.toml",
                ".rubocop.yml",
                "checkstyle.xml",
                ".stylelintrc",
                ".stylelintrc.json",
                "phpcs.xml",
                ".phpcs.xml",
            ),
            *_runners(),
        ),
        what=What("key"),
        binding="file",
        note=(
            "Linter config names count on presence at any depth; the root pyproject.toml is read for "
            "[tool.ruff|pylint|flake8] and the root package.json for an eslintConfig key. The lint verb is "
            "resolved from the runner manifests."
        ),
    ),
    "TOOL-03": Reads(
        where=(
            *_at(ROOT, "tsconfig.json", "jsconfig.json"),
            *_at(ANY_DEPTH, "mypy.ini", ".mypy.ini"),
            *_at(ANY_DEPTH, "pyproject.toml", "setup.cfg"),
            *_at(ROOT, "pyrightconfig.json"),
            *_at(ANY_DEPTH, "*.csproj", "Directory.Build.props", "Directory.Build.targets", "global.json"),
            *_runners(),
        ),
        what=What("key"),
        binding="file",
        note=(
            "mypy.ini, .mypy.ini, pyproject.toml and setup.cfg are kept when found at any depth but read at "
            "the root, so a nested-only copy counts as present but not strict; global.json counts on presence"
            " only. The typecheck verb is resolved from the runner manifests and must carry --strict."
        ),
    ),
    "TOOL-04": Reads(
        where=(
            *_runners(),
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/*.yml"),
        ),
        what=What("phrase"),
        binding="line",
        note=(
            "A resolved verb, a root-Makefile recipe line it reaches, or one workflow line must run a "
            "dependency-audit command (npm audit, pip-audit, osv-scanner and others) or a scanner action or "
            "template. Commented workflow lines are skipped; Dependabot and Renovate do not count."
        ),
    ),
    "TOOL-05": Reads(
        where=(
            *_at(ANY_DEPTH, ".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml"),
            *_at(GLOB, ".githooks/*", ".husky/*", "**"),
            *_runners(),
        ),
        what=What("exists"),
        binding="file",
        note=(
            "A hook-manager file at any depth, or core.hooksPath in any manifest, config, script, CI or build"
            " file (glob **), is wired; .husky/ is wired only when a root package.json script names husky. "
            "With no hook chain, the FAIL cites the runner manifests that the runner resolver finds."
        ),
    ),
    "TOOL-06": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                "commitlint.config.js",
                "commitlint.config.cjs",
                "commitlint.config.mjs",
                "commitlint.config.ts",
                ".commitlintrc",
                ".commitlintrc.json",
                ".commitlintrc.js",
                ".commitlintrc.cjs",
                ".commitlintrc.yml",
                ".commitlintrc.yaml",
                ".commitlintrc.toml",
            ),
            *_at(
                ANY_DEPTH,
                ".husky/commit-msg",
                ".githooks/commit-msg",
                ".pre-commit-config.yaml",
                "lefthook.yml",
                "lefthook.yaml",
            ),
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/*.yml"),
            *_runners(),
            *_at(GLOB, ".githooks/*", ".husky/*", "**"),
        ),
        what=What("phrase"),
        binding="line",
        note=(
            "Local: commitlint config names at any depth, a commitlint key in the root package.json, a "
            "commit-msg hook file (presence matched at any depth), or commit-msg/commitlint/conventional in "
            "the root hook-manager files. CI: one workflow line runs a commit-message tool, a pull-request "
            "title action, a script the local commit-msg stage names, or a runner target that does. The FAIL "
            "path reads the hook wiring as TOOL-05 does: hook-manager files, .githooks/, .husky/, core.hooksPath."
        ),
    ),
    "TOOL-07": Reads(
        where=(
            *_at(ROOT, ".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml"),
            *_at(ANY_DEPTH, "pre-commit", "commit-msg"),
            *_at(GLOB, ".githooks/*", ".husky/*", "**"),
            *_at(ROOT, "package.json"),
            *_at(GLOB, ".github/rulesets/*.json"),
            *_at(ROOT, ".github/settings.yml"),
            *_at(ANY_DEPTH, "*.tf"),
        ),
        what=What("phrase"),
        binding="line",
        note=(
            "The branch read (git symbolic-ref HEAD, git branch --show-current, git rev-parse --abbrev-ref "
            "HEAD) is one line, and its non-zero exit must be in the same indented block of a hook-manager "
            "file or anywhere in a pre-commit or commit-msg script outside .git/. The hook-manager files are "
            "found at any depth but read at the root; core.hooksPath is grepped in every manifest, config, "
            "script, CI and build file (glob **)."
        ),
    ),
    "CI-01": Reads(
        where=(
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/*.yml"),
        ),
        what=What(
            "key",
            (
                "pull_request",
                "pull_request_target",
                "merge_request",
                "pr",
                "changeRequest",
            ),
        ),
        binding="file",
        threshold="a workflow with a pull-request trigger",
        note=(
            "GitHub needs the key at a line start or pull_request in an on: [...] list, Azure pr: at a line "
            "start; GitLab and Jenkins match anywhere, CircleCI and Buildkite never count. Inventory.match "
            "also compares the base name, so .gitlab-ci.yml, Jenkinsfile and azure-pipelines.yml are found at"
            " any depth."
        ),
    ),
    "CI-02": Reads(
        where=(
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/*.yml"),
            *_runners(),
        ),
        what=What(
            "key",
            (
                "run",
                "script",
                "command",
                "commands",
                "bash",
            ),
        ),
        binding="line",
        threshold="no CI verb without a local definition",
        note=(
            "Each step command (inline or each line of a block), split at shell operators, is mapped to a "
            "verb by runner or known tool and compared with the verbs resolved on the runner manifests."
        ),
    ),
    "CI-03": Reads(
        where=(
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/*.yml"),
            *_runners(),
        ),
        what=What(
            "key",
            (
                "run",
                "script",
                "command",
                "commands",
                "bash",
            ),
        ),
        binding="line",
        threshold="no CI-only step",
        note=(
            "A step command that calls a runner target that is no verb, no package-manager built-in and no "
            "target of any local runner fails."
        ),
    ),
    "CI-05": Reads(
        where=(
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/*.yml", "**"),
        ),
        what=What(
            "word-list",
            (
                "actionlint",
                "zizmor",
                "check-jsonschema",
                "glab ci lint",
                "circleci config validate",
            ),
        ),
        binding="line",
        threshold="every provider's workflows linted locally",
        note=(
            "Local evidence is any line of a file of kind manifest, build, config, script or other that names"
            " the provider's linter (check-jsonschema by its schema or hook names), never a workflow, a "
            "lockfile or a dependabot or renovate config. Then each workflow line is read for the same names."
        ),
    ),
    "BASE-01": Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".eslint-baseline*",
                ".ruff-baseline*",
                ".mypy-baseline*",
                "baseline.json",
                "*baseline*.json",
                "*baseline*.xml",
                "coverage-baseline.*",
                "*.baseline",
                ".secrets.baseline",
                ".snyk",
                ".gitleaksignore",
            ),
            *_at(ROOT, "AGENTS.md", "CLAUDE.md", "setup.cfg", "tox.ini"),
            *_at(
                ANY_DEPTH,
                ".eslintrc*",
                "eslint.config.*",
                "biome.json",
                "biome.jsonc",
                ".ruff.toml",
                "ruff.toml",
                ".flake8",
                "pylintrc",
                ".pylintrc",
                "mypy.ini",
                ".mypy.ini",
                ".golangci.yml",
                ".golangci.yaml",
                "clippy.toml",
                ".gitleaks.toml",
                "sonar-project.properties",
                ".semgrep.yml",
                ".semgrep.yaml",
            ),
            *_runners(),
            *_at(
                ANY_DEPTH,
                "setup.py",
                "requirements*.txt",
                "Pipfile",
                "go.mod",
                "Cargo.toml",
                "Gemfile",
                "composer.json",
            ),
        ),
        what=What(
            "phrase",
            (
                "quality baseline",
                "baseline file",
                "baseline report",
                "baseline artifact",
                "baseline count",
                "baseline json",
                "no new violations",
                "violation budget",
                "suppression file",
                "suppression list",
                "suppression count",
            ),
        ),
        binding="file",
        note=(
            "A baseline name at any depth, or a mechanism phrase in the root AGENTS.md or CLAUDE.md, passes; "
            "the phrase words are joined by \\s+ so they may span lines. The counting-tool configs, root "
            "pyproject.toml, setup.cfg and tox.ini and the lint, typecheck and security verbs only give "
            "PARTIAL. With no detected ecosystem, a project manifest at any depth still makes the check apply."
        ),
    ),
    "BASE-02": Reads(
        where=(
            *_at(
                ROOT,
                "setup.cfg",
                "tox.ini",
            ),
            *_at(
                ANY_DEPTH,
                ".eslintrc*",
                "eslint.config.*",
                "biome.json",
                "biome.jsonc",
                ".ruff.toml",
                "ruff.toml",
                ".flake8",
                "pylintrc",
                ".pylintrc",
                "mypy.ini",
                ".mypy.ini",
                ".golangci.yml",
                ".golangci.yaml",
                "clippy.toml",
                ".gitleaks.toml",
                ".snyk",
                "sonar-project.properties",
                ".semgrep.yml",
                ".semgrep.yaml",
                ".eslint-baseline*",
                ".ruff-baseline*",
                ".mypy-baseline*",
                "baseline.json",
                "*baseline*.json",
                "*baseline*.xml",
                "coverage-baseline.*",
                "*.baseline",
                ".secrets.baseline",
                ".gitleaksignore",
            ),
            *_runners(),
            *_at(
                ANY_DEPTH,
                "setup.py",
                "requirements*.txt",
                "Pipfile",
                "go.mod",
                "Cargo.toml",
                "Gemfile",
                "composer.json",
            ),
        ),
        what=What("phrase"),
        binding="line",
        note=(
            "A numeric budget (--max-warnings N, max-warnings|max-issues|max-problems N, violation-budget N) "
            "on one line of the five root runner manifests, a counting config at any depth, or a resolved "
            "verb command. Counting tools or baseline artifacts only give PARTIAL; the check never fails. With "
            "no detected ecosystem, a project manifest at any depth still makes the check apply."
        ),
    ),
    "BASE-03": Reads(
        where=(
            *_at(
                ROOT,
                "AGENTS.md",
                "CLAUDE.md",
                "README.md",
                "CONTRIBUTING.md",
            ),
            *_at(
                ANY_DEPTH,
                ".eslintrc*",
                "eslint.config.*",
                "biome.json",
                "biome.jsonc",
                ".ruff.toml",
                "ruff.toml",
                ".flake8",
                "pylintrc",
                ".pylintrc",
                "mypy.ini",
                ".mypy.ini",
                ".golangci.yml",
                ".golangci.yaml",
                "clippy.toml",
                ".gitleaks.toml",
                ".snyk",
                "sonar-project.properties",
                ".semgrep.yml",
                ".semgrep.yaml",
                ".eslint-baseline*",
                ".ruff-baseline*",
                ".mypy-baseline*",
                "baseline.json",
                "*baseline*.json",
                "*baseline*.xml",
                "coverage-baseline.*",
                "*.baseline",
                ".secrets.baseline",
                ".gitleaksignore",
            ),
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/*.yml"),
            *_runners(),
            *_at(
                ANY_DEPTH,
                "setup.py",
                "requirements*.txt",
                "Pipfile",
                "go.mod",
                "Cargo.toml",
                "Gemfile",
                "composer.json",
            ),
        ),
        what=What(
            "phrase",
            (
                "ratchet",
                "no new violations",
                "violation budget",
                "compare",
                "comparison",
                "regression",
                "baseline",
            ),
        ),
        binding="line",
        note=(
            "First a BASE-02 budget, then a baseline artifact whose base name appears in any CI file, then a "
            "ratchet phrase in the four root documents; compare, comparison or regression must be within 48 "
            "characters of baseline on one line. With no detected ecosystem, a project manifest at any depth "
            "still makes the check apply."
        ),
    ),
    "BASE-04": Reads(
        where=(
            *_at(
                ROOT,
                ".coveragerc",
                ".coveragerc.toml",
                "setup.cfg",
                "tox.ini",
                "pytest.ini",
                "pyproject.toml",
                "package.json",
                "AGENTS.md",
                "CLAUDE.md",
                "README.md",
                "CONTRIBUTING.md",
            ),
            *_at(
                ANY_DEPTH,
                "vitest.config.*",
                "jest.config.*",
                "vite.config.*",
                "karma.conf.*",
                "package.json",
                "pyproject.toml",
                "setup.py",
                "requirements*.txt",
                "Pipfile",
                "pom.xml",
                "build.gradle",
                "build.gradle.kts",
                "go.mod",
                "Cargo.toml",
                "Gemfile",
                "composer.json",
            ),
        ),
        what=What("phrase"),
        binding="line",
        note=(
            "Config: fail_under = N or --cov-fail-under N in six root files, coverageThreshold in the root "
            "package.json, a threshold key in a runner config at any depth (whole-line // comments dropped). "
            "Prose (PARTIAL): coverage within 40 characters of threshold, minimum, fail, floor or at least, "
            "or within 20 of a percentage, on one line of the four root documents. With no detected ecosystem, "
            "a project manifest at any depth still makes the check apply."
        ),
    ),
    "CON-01": Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What("code-span"),
        binding="section",
        threshold="a named path that exists",
        note=(
            "Every code span on the lines of every prohibitions section; a span counts when it has no command"
            " characters and holds a slash, a glob or a dot, or names something that exists. Existence is "
            "checked in the scan and on disk. In a section opened by its body alone, only the spans of a list"
            " item or paragraph that holds a prohibition line count."
        ),
        named_by_text="each code span of the prohibitions section is looked up in the scan and on disk",
    ),
    "CON-02": Reads(
        where=(
            *_at(ROOT, "AGENTS.md", "CLAUDE.md"),
            *_at(ANY_DEPTH, "test", "tests", "__tests__"),
        ),
        what=What("code-span"),
        binding="section",
        threshold="every test directory named",
        note=(
            "The prohibitions-section code spans of CON-01, read like ignore entries, against every folder "
            "segment named test, tests or __tests__ in the scan plus those folders at the root on disk."
        ),
    ),
    "CON-03": Reads(
        where=(
            *_held(con, "_CON_ROOTS", ROOT),
            *_held(ignore, "IGNORE_FILE_NAMES", ROOT, {".gitignore": ANY_DEPTH}),
        ),
        what=What("exists"),
        binding="file",
        threshold="every present folder ignored and untracked",
        note=(
            "The top-level scratch and agent-state folders in the scan or on disk, the tracked files under "
            "them, and the ignore rules as DOC-03 reads them."
        ),
    ),
    "CON-04": Reads(
        where=(*_at(GLOB, "**"),),
        what=What("exists"),
        binding="file",
        note=(
            "Only paths are read, never content: each scanned file is sorted into secrets, migrations, "
            "generated, tests, infrastructure as code and production by name and folder. With --emit-baseline"
            " it writes do-not-do.draft.md beside the report, never inside the target; else UNKNOWN."
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
                ROOT,
                "package.json",
                "pyproject.toml",
                "requirements.txt",
                "requirements-dev.txt",
                "Cargo.toml",
                "Directory.Build.props",
                "Directory.Build.targets",
                "Directory.Packages.props",
            ),
            *_at(ROOT, "go.mod", unexercised=_GO_FIXTURE),
            *_at(GLOB, "*.csproj", "*.fsproj", "*.vbproj"),
        ),
        what=What("exists"),
        binding="file",
        threshold="a tracked lockfile that agrees with the manifest",
        note=(
            "Lockfiles of each ecosystem's package managers (stack.PACKAGE_MANAGERS) at any depth, shallowest"
            " first, and whether git tracks them; a tracked lockfile the walk skipped as ignored counts too. Only a root lockfile is compared with the root manifests' "
            "dependency names; for .NET those are the PackageReference names of the project files in the root "
            "folder, and a package reference in a root Directory.* file leaves the lockfile unverified."
        ),
    ),
    "EXEC-03": Reads(
        where=(
            *_at(ROOT, "README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"),
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
            ),
            *_at(GLOB, ".devcontainer/*.json"),
            *_at(ROOT, "Makefile", "package.json"),
        ),
        what=What("fenced-command"),
        binding="line",
        threshold="a documented non-interactive setup command",
        note=(
            "A fenced shell command or an inline code span in the four docs whose tool and first argument install "
            "or set up passes. "
            "Else a setup file or a setup target (setup, bootstrap, install, dev, dev-setup) of the root "
            "Makefile or package.json named anywhere in the four docs passes; present but not named is "
            "PARTIAL."
        ),
    ),
    "EXEC-04": Reads(
        where=(
            *_at(GLOB, "**/*.sh", "**/*.bash", "**/*.zsh", "**/*.fish", "**/*.ksh", "**/*.ps1"),
            *_at(ANY_DEPTH, "Dockerfile"),
            *_at(GLOB, "**"),
            *_at(ROOT, ".env.example", ".env.sample", ".env.template", "env.example"),
        ),
        what=What("key"),
        binding="line",
        threshold="every referenced key declared",
        note=(
            "References: ${VAR} and ${VAR:?msg} in shell files and Dockerfile, less the keys the same file assigns, "
            "and os.environ, getenv, process.env and ENV[...] in every file of kind source or script. A shell "
            "reference with a fallback (${VAR:-x}, ${VAR-x}, ${VAR:=x}, ${VAR:+x}) is optional: listed, never "
            "missing. Declared keys are the KEY= lines of the four root example files; a fixed allow-list of host, "
            "CI and shell-set names is exempt."
        ),
    ),
    "EXEC-05": Reads(
        where=(
            *_at(
                GLOB,
                "**/dist/**",
                "**/build/**",
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
            "(scan._GENERATED_HINTS) or by suffix; only tracked ones are read. The marker must stand in the "
            "first 20 lines, case-insensitive."
        ),
    ),
    "EXEC-06": Reads(
        where=(
            *_at(ROOT, "README.md", "AGENTS.md", "CLAUDE.md"),
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
            *_at(GLOB, "tests/*.rs"),
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
            "--allow-probe test. Every runner manifest counts only at the root, where it is read."
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
            *_at(GLOB, "tests/*.rs"),
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
            "is read with the same patterns. A file is kept when Inventory.has finds its name at any "
            "depth but read by its exact root path, so a nested-only copy is skipped silently. The test files "
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
            " when a build manifest is found under it. The root counts as declared when any of the nine "
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
        binding="window",
        window=2,
        note=(
            "Python: a def, async def or class at column 0 with a public name is documented when the next "
            "non-blank line opens a docstring; TypeScript or JavaScript: an export declaration is documented "
            "when the line before (blank lines skipped) ends a /** */ block. Only the main language is read."
        ),
    ),
    "SEC-01": Reads(
        where=(
            *_at(ANY_DEPTH, ".env", ".env.*", ".gitignore"),
            *_at(ROOT, ".cbmignore", ".cursorignore", ".aiderignore", ".rooignore"),
        ),
        what=What("exists"),
        binding="file",
        note=(
            "Tracked files (git) whose base name is .env or starts with .env., less six template names, fail;"
            " the ignore rules (the five root ignore files and every nested .gitignore) are probed with .env "
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
            "nested .gitignore files come from the scan and from git ls-files."
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
        where=(*_at(REPOSITORY_LEVEL, "*release*"),),
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
            *_at(GLOB, ".github/rulesets/*.json"),
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
