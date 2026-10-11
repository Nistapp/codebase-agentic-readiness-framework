# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Stage S4 — stack and layout detection.

Decides which rule packs apply to a target. Detection never guesses: an ecosystem this module
does not recognise produces ``UNKNOWN`` verdicts for the checks that need it, plus a visible note
in the report. Nothing is ever passed by omission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from audit.scan import Inventory

#: ecosystem -> (manifest globs, verb-runner hints)
ECOSYSTEM_SIGNALS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "node": (("package.json",), ("package.json",)),
    "python": (("pyproject.toml", "setup.py", "requirements*.txt", "Pipfile"), ("pyproject.toml", "Makefile")),
    "jvm": (("pom.xml", "build.gradle", "build.gradle.kts"), ("pom.xml", "build.gradle", "Makefile")),
    "go": (("go.mod",), ("Makefile",)),
    "rust": (("Cargo.toml",), ("Makefile",)),
    "dotnet": (("*.csproj", "*.sln"), ("*.sln",)),
    "ruby": (("Gemfile",), ("Rakefile", "Makefile")),
    "php": (("composer.json",), ("composer.json",)),
}

PACKAGE_MANAGERS: dict[str, tuple[str, ...]] = {
    "npm": ("package-lock.json",),
    "pnpm": ("pnpm-lock.yaml",),
    "yarn": ("yarn.lock",),
    "bun": ("bun.lockb",),
    "pip": ("requirements.txt",),
    "poetry": ("poetry.lock",),
    "uv": ("uv.lock",),
    "pipenv": ("Pipfile.lock",),
    "gradle": ("gradle.lockfile",),
    "maven": ("pom.xml",),
    "cargo": ("Cargo.lock",),
    "gomod": ("go.sum",),
    "bundler": ("Gemfile.lock",),
    "composer": ("composer.lock",),
}

CI_PROVIDERS: dict[str, tuple[str, ...]] = {
    "github": (".github/workflows/*.yml", ".github/workflows/*.yaml"),
    "gitlab": (".gitlab-ci.yml",),
    "jenkins": ("Jenkinsfile",),
    "azure": ("azure-pipelines.yml",),
    "circleci": (".circleci/config.yml",),
    "buildkite": (".buildkite/*.yml",),
}

TEST_FRAMEWORKS: dict[str, tuple[str, ...]] = {
    "vitest": ("vitest.config.ts", "vitest.config.js", "vitest.config.mts"),
    "jest": ("jest.config.js", "jest.config.ts", "jest.config.mjs"),
    "pytest": ("pytest.ini", "conftest.py"),
    "tox": ("tox.ini",),
    "junit": ("src/test/java/**",),
    "go-test": ("*_test.go",),
    "cargo-test": ("tests/*.rs",),
}

HOOK_MANAGERS: dict[str, tuple[str, ...]] = {
    "husky": (".husky/*",),
    "lefthook": ("lefthook.yml", "lefthook.yaml"),
    "pre-commit": (".pre-commit-config.yaml",),
    "gradle-hooks": (".githooks/*",),
}

VERB_RUNNERS = (
    "package.json",
    "Taskfile.yml",
    "Taskfile.yaml",
    "Makefile",
    "pyproject.toml",
    "build.gradle",
    "build.gradle.kts",
    "pom.xml",
)

#: The seven verbs of the framework's standardized command surface.
VERBS = ("format", "format:check", "lint", "typecheck", "test", "check", "security")

#: Spellings of ``format:check`` that a runner accepts besides the verb's own name, which every runner
#: accepts. The colon is not a portable name character: Make writes it ``format\:check`` (read as the
#: verb's own name) or ``format-check``, pyproject task runners ``format-check`` and Gradle ``formatCheck``.
#: Source: ``spec/command-surface.md``, "Spelling per runner". Maven has no named tasks and is read by
#: ``_common._parse_maven_plugins`` instead.
FORMAT_CHECK_ALIASES: dict[str, tuple[str, ...]] = {
    "Makefile": ("format-check",),
    "pyproject.toml": ("format-check",),
    "build.gradle": ("formatCheck",),
    "build.gradle.kts": ("formatCheck",),
}

_VERB_OF_SPELLING: dict[str, str] = {
    spelling: "format:check" for spellings in FORMAT_CHECK_ALIASES.values() for spelling in spellings
}


def canonical_verb(name: str) -> str:
    """The framework verb a name stands for: ``format\\:check``, ``format-check`` and ``formatCheck`` are
    ``format:check``; any other name is returned as it is, with a backslash before a colon removed."""
    name = name.replace("\\:", ":")
    return _VERB_OF_SPELLING.get(name, name)


@dataclass
class Stack:
    ecosystems: set[str] = field(default_factory=set)
    package_managers: set[str] = field(default_factory=set)
    ci_providers: set[str] = field(default_factory=set)
    test_frameworks: set[str] = field(default_factory=set)
    hook_managers: set[str] = field(default_factory=set)
    verb_runners: list[str] = field(default_factory=list)
    component_manifest_hint: str | None = None
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        parts = []
        if self.ecosystems:
            parts.append("ecosystems: " + ", ".join(sorted(self.ecosystems)))
        if self.ci_providers:
            parts.append("ci: " + ", ".join(sorted(self.ci_providers)))
        return " · ".join(parts) or "stack not recognised"


def detect_stack(inv: Inventory) -> Stack:
    stack = Stack()
    names = {f.rel.split("/")[-1] for f in inv.files}

    for eco, (manifests, runners) in ECOSYSTEM_SIGNALS.items():
        for pattern in manifests:
            if "*" in pattern:
                if inv.match(pattern):
                    stack.ecosystems.add(eco)
                    break
            elif pattern in names or inv.has(pattern):
                stack.ecosystems.add(eco)
                break
        for runner in runners:
            if runner in names and runner in VERB_RUNNERS and runner not in stack.verb_runners:
                stack.verb_runners.append(runner)

    for name, signals in PACKAGE_MANAGERS.items():
        if any(inv.has(s) for s in signals):
            stack.package_managers.add(name)

    for provider, globs in CI_PROVIDERS.items():
        if inv.match(*globs):
            stack.ci_providers.add(provider)

    for framework, signals in TEST_FRAMEWORKS.items():
        if inv.match(*signals):
            stack.test_frameworks.add(framework)

    for manager, globs in HOOK_MANAGERS.items():
        if inv.match(*globs):
            stack.hook_managers.add(manager)

    if not stack.ecosystems:
        stack.notes.append("no recognised build manifest — stack-dependent checks report UNKNOWN")
    return stack


def extract_npm_scripts(inv: Inventory, manifest: str = "package.json") -> dict[str, str]:
    """Read the ``scripts`` map from an npm manifest. Returns {} when absent or unparsable."""
    import json

    text = inv.read(manifest)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


@dataclass(frozen=True)
class MakeError:
    """A line that GNU Make refuses. With one, ``make`` stops, so no target of the file can run."""

    line: int
    text: str
    message: str


@dataclass(frozen=True)
class MakeRule:
    """One target: the targets it needs first, in order, and its recipe lines."""

    prerequisites: tuple[str, ...]
    recipe: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class ParsedMakefile:
    rules: dict[str, MakeRule]
    errors: tuple[MakeError, ...]


_MAKE_DIRECTIVES = frozenset(
    {
        "include",
        "-include",
        "sinclude",
        "ifeq",
        "ifneq",
        "ifdef",
        "ifndef",
        "else",
        "endif",
        "define",
        "endef",
        "export",
        "unexport",
        "override",
        "private",
        "undefine",
        "vpath",
    }
)
_SPECIAL_TARGET = re.compile(r"^\.[A-Z_]+$")
#: ``:=``, ``::=`` and ``:::=`` assign; a bare ``::`` makes a double-colon rule.
_ASSIGNMENT_COLONS = re.compile(r":{1,3}=")


def _trailing_backslashes(text: str) -> int:
    return len(text) - len(text.rstrip("\\"))


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Physical lines joined at a trailing backslash, each with the number of its first line.

    The backslash and the line break become one space. A backslash that is itself escaped (an even run of
    them at the end) does not continue the line.
    """
    lines: list[tuple[int, str]] = []
    pending: str | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        if pending is None:
            start = number
            pending = raw
        else:
            pending += " " + raw.strip()
        if _trailing_backslashes(pending) % 2 == 1:
            pending = pending[:-1].rstrip()
            continue
        lines.append((start, pending))
        pending = None
    if pending is not None:
        lines.append((start, pending))
    return lines


def _unescaped(text: str, char: str) -> list[int]:
    """Where ``char`` occurs outside a backslash escape and outside ``$(...)`` and ``${...}``."""
    found: list[int] = []
    depth = 0
    index = 0
    while index < len(text):
        current = text[index]
        if current == "\\":
            index += 2
            continue
        if current == "$" and text[index + 1 : index + 2] in ("(", "{"):
            depth += 1
            index += 2
            continue
        if depth and current in ")}":
            depth -= 1
        elif current == char and not depth:
            found.append(index)
        index += 1
    return found


def _words(text: str) -> list[str]:
    """Names in a target or prerequisite list, with ``\\:`` read as ``:``. A name that holds a variable, a
    pattern or an assignment is not a name this reader can know, so it is left out."""
    return [word.replace("\\:", ":") for word in text.split() if not set(word) & set("$%=|")]


def parse_makefile(inv: Inventory) -> ParsedMakefile:
    """Read the rules of the root ``Makefile``: target names, prerequisites and recipe lines.

    Reads what GNU Make reads for a plain rule. A colon in a target name is escaped (``format\\:check:``) and
    is read as part of the name. Prerequisites are kept, in order, because ``check: a b c`` runs ``a``, ``b``
    and ``c`` before its own recipe. A rule is plain unless it has a pattern (``%``) or a variable in a name,
    and those are left out. Assignments, directives and ``define`` blocks end a rule and are not read.

    The one parse error it reports is the one that sank the engine's own fixture: an unescaped colon in a
    target name (``format:check:``) is a static pattern rule, whose pattern has no ``%``, and Make refuses
    the whole file with ``target pattern contains no '%'``.
    """
    text = inv.read("Makefile")
    if not text:
        return ParsedMakefile(rules={}, errors=())
    rules: dict[str, dict] = {}
    errors: list[MakeError] = []
    current: list[str] = []
    in_define = False
    for number, line in _logical_lines(text):
        if in_define:
            in_define = line.split()[:1] != ["endef"]
            continue
        if line.startswith("\t"):
            step = line.strip()
            if step and not step.startswith("#"):
                for name in current:
                    rules[name]["recipe"].append(step)
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        first = stripped.split()[0]
        if first in _MAKE_DIRECTIVES:
            in_define = first == "define"
            current = []
            continue
        colons = _unescaped(stripped, ":")
        if not colons or "=" in stripped[: colons[0]] or _ASSIGNMENT_COLONS.match(stripped, colons[0]):
            current = []
            continue
        head, tail = stripped[: colons[0]], stripped[colons[0] + 1 :]
        if tail.startswith(":"):
            tail = tail[1:]
        semicolons = _unescaped(tail, ";")
        inline = tail[semicolons[0] + 1 :].strip() if semicolons else ""
        needs = tail[: semicolons[0]] if semicolons else tail
        pattern_colons = _unescaped(needs, ":")
        if pattern_colons:
            pattern = needs[: pattern_colons[0]]
            if "%" not in pattern and "$" not in pattern:
                errors.append(MakeError(number, stripped[:200], "target pattern contains no '%'"))
            current = []
            continue
        names = [name for name in _words(head) if not _SPECIAL_TARGET.match(name)]
        prerequisites = _words(needs)
        current = names
        for name in names:
            rule = rules.setdefault(name, {"prerequisites": [], "recipe": [], "line": number})
            rule["prerequisites"].extend(p for p in prerequisites if p not in rule["prerequisites"])
            if inline:
                rule["recipe"].append(inline)
    return ParsedMakefile(
        rules={
            name: MakeRule(tuple(rule["prerequisites"]), tuple(rule["recipe"]), rule["line"])
            for name, rule in rules.items()
        },
        errors=tuple(errors),
    )


def parse_makefile_targets(inv: Inventory) -> dict[str, str]:
    """``{target: what running it does}`` for a Makefile that parses; ``{}`` when Make would refuse it.

    What running a target does is each prerequisite that is itself a target of the file, as ``make <name>``,
    then the recipe lines, joined with ``&&``. A prerequisite keeps its name, so ``check: format\\:check
    typecheck test`` is read as the three verbs it runs, the way ``npm run format:check && ...`` is.
    """
    parsed = parse_makefile(inv)
    if parsed.errors:
        return {}
    return {
        name: " && ".join([f"make {p}" for p in rule.prerequisites if p in parsed.rules] + list(rule.recipe))
        for name, rule in parsed.rules.items()
    }
