# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Private cross-pack check helpers.

This module is **not** a rule pack. It defines no checks, contributes nothing to the catalogue, and
is deliberately absent from ``MODULE_NAMES`` in ``audit/rules/checks/__init__.py`` — so it is never
loaded by the registry and never appears in ``--list-checks``. Packs import it directly
(``from audit.rules.checks._common import ...``).

It exists only to answer questions more than one pack asks. The pair that motivated it:

* **"what verbs exist, and what does each run?"** — CMD-01, EXEC-06, CI-02, AGT-05, TOOL-01/02/04
  and TST-01 all need one answer, so it is computed once (``resolve_verbs``);
* **"which commands does the documentation actually show?"** — EXEC-06 and TST-04 both read fenced
  shell blocks (``extract_fenced_commands``).

Keep it small. If a helper is used by exactly one check it belongs in that pack, not here.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from audit.ignore import tracked_files
from audit.scan import Inventory
from audit.stack import (
    FORMAT_CHECK_ALIASES,
    VERBS,
    MakeError,
    Stack,
    extract_npm_scripts,
    parse_makefile,
    parse_makefile_targets,
)


@dataclass(frozen=True)
class VerbBinding:
    """One resolved framework verb: where it is declared and what it runs.

    ``runner`` is the manifest the verb was read from, ``command`` is the raw string the runner
    declares, and ``argv`` is a best-effort tokenisation of it (shell operators are not interpreted).
    """

    verb: str
    runner: str
    command: str
    argv: tuple[str, ...]


#: Runner precedence when more than one manifest defines the same verb. Fixed and documented so a
#: target with both a Makefile and package.json resolves deterministically.
RUNNER_PRECEDENCE: tuple[str, ...] = (
    "package.json",
    "Makefile",
    "Taskfile.yml",
    "Taskfile.yaml",
    "pyproject.toml",
    "build.gradle",
    "build.gradle.kts",
    "pom.xml",
    "gradlew",
    "mvnw",
)


def tracked_in_scope(target, inventory: Inventory) -> set[str] | None:
    """The paths git tracks under the target, less the ones ``--exclude`` took out of the audit.

    ``None`` still means that git could not answer. A check that reads the tracked set asks here, so that an
    excluded path is out of the audit for it as it is for the walk.
    """
    tracked = tracked_files(target.path)
    if tracked is None:
        return None
    return {rel for rel in tracked if not inventory.is_excluded(rel)}


def resolve_all_verbs(inventory: Inventory, stack: Stack) -> dict[str, tuple[VerbBinding, ...]]:
    """Resolve **every** binding for every framework verb the target declares.

    Unlike :func:`resolve_verbs`, which collapses to the single highest-precedence binding per verb,
    this keeps the full list so a caller can tell that a verb is defined on more than one runner.
    Bindings for each verb are ordered by :data:`RUNNER_PRECEDENCE`. ``stack`` is accepted so callers
    can pass the detected stack even though resolution reads the inventory directly in v1.
    """
    candidates: dict[str, list[VerbBinding]] = {}
    for runner, declared in runner_commands(inventory):
        commands = {**_lifecycle_commands(runner, inventory), **declared}
        for verb in VERBS:
            command = commands.get(verb)
            if command:
                candidates.setdefault(verb, []).append(
                    VerbBinding(verb=verb, runner=runner, command=command, argv=_split_argv(command))
                )
    return {
        verb: tuple(sorted(bindings, key=lambda b: _runner_rank(b.runner))) for verb, bindings in candidates.items()
    }


def resolve_verbs(inventory: Inventory, stack: Stack) -> dict[str, VerbBinding]:
    """Resolve every framework verb the target declares, keyed by verb name.

    Only verbs that are actually declared are returned; callers compare the result against
    :data:`audit.stack.VERBS` to find the missing ones. ``stack`` is accepted so callers can pass the
    detected stack even though resolution reads the inventory directly in v1.
    """
    return {verb: bindings[0] for verb, bindings in resolve_all_verbs(inventory, stack).items()}


def runner_commands(inventory: Inventory) -> tuple[tuple[str, dict[str, str]], ...]:
    """Every present verb runner and its declared ``{verb: command}`` map, in precedence order.

    A runner is present when its manifest is present, whether or not it declares any framework verb;
    callers that care about verb coverage read the map, callers that care about runners read the name.
    A ``Makefile`` that GNU Make refuses to parse is not a runner: nothing in it can run, so it is left
    out, and :func:`makefile_errors` says why.

    ``format:check`` is declared under the spelling its runner accepts (``FORMAT_CHECK_ALIASES``) and is
    returned under its own name, so callers see one verb whichever spelling the manifest used.
    """
    return tuple((runner, _with_spellings(runner, commands)) for runner, commands in _runner_commands(inventory))


def makefile_errors(inventory: Inventory) -> tuple[MakeError, ...]:
    """What GNU Make refuses in the root ``Makefile``; empty when it parses or there is none."""
    return parse_makefile(inventory).errors if inventory.has("Makefile") else ()


#: Fenced-code languages treated as shell for command extraction.
SHELL_FENCE_LANGS: frozenset[str] = frozenset({"bash", "sh", "shell", "console", "zsh"})

_FENCE_RE = re.compile(r"^\s*(?:```|~~~)\s*([A-Za-z0-9_+-]*)\s*$")
_PROMPT_RE = re.compile(r"^\s*(?:\$|>|%|❯|PS>)\s+")


def extract_fenced_commands(text: str) -> list[tuple[str, int, str]]:
    """Extract shell commands from fenced ``bash``/``sh``/``shell``/``console`` blocks.

    Returns ``(language, line_no, command)`` with ``line_no`` 1-based within ``text``. A leading
    shell prompt is stripped; comment lines are skipped. In a ``console`` block a line without a
    prompt is treated as program output and skipped, since a transcript interleaves both.
    """
    commands: list[tuple[str, int, str]] = []
    language: str | None = None
    for line_no, raw in enumerate(text.splitlines(), start=1):
        fence = _FENCE_RE.match(raw)
        if fence:
            language = None if language is not None else fence.group(1).lower()
            continue
        if language is None or language not in SHELL_FENCE_LANGS:
            continue
        prompt = _PROMPT_RE.match(raw)
        command = _PROMPT_RE.sub("", raw).strip()
        if not command or command.startswith("#"):
            continue
        if language == "console" and prompt is None:
            continue
        commands.append((language, line_no, command))
    return commands


# ---------------------------------------------------------------------------
# runner readers
# ---------------------------------------------------------------------------


def _runner_commands(inventory: Inventory):
    """Yield ``(runner, {verb: command})`` for every manifest present, in precedence order."""
    if inventory.has("package.json"):
        yield "package.json", extract_npm_scripts(inventory)
    if inventory.has("Makefile") and not makefile_errors(inventory):
        yield "Makefile", parse_makefile_targets(inventory)
    for name in ("Taskfile.yml", "Taskfile.yaml"):
        if inventory.has(name):
            text = inventory.read(name)
            if text:
                yield name, _parse_taskfile(text)
    if inventory.has("pyproject.toml"):
        text = inventory.read("pyproject.toml")
        if text:
            yield "pyproject.toml", _parse_pyproject_tasks(text)
    for name in ("build.gradle", "build.gradle.kts"):
        if inventory.has(name):
            text = inventory.read(name)
            if text:
                yield name, _parse_gradle_tasks(text, inventory)
    if inventory.has("pom.xml"):
        text = inventory.read("pom.xml")
        if text:
            yield "pom.xml", _parse_maven_plugins(text, inventory)


def _with_spellings(runner: str, commands: dict[str, str]) -> dict[str, str]:
    """``commands`` with ``format:check`` bound to the first of its spellings that has a command."""
    for spelling in ("format:check", *FORMAT_CHECK_ALIASES.get(runner, ())):
        if commands.get(spelling):
            return {**commands, "format:check": commands[spelling]}
    return commands


def _lifecycle_commands(runner: str, inventory: Inventory) -> dict[str, str]:
    """The verbs a runner provides itself, which the repository does not declare.

    Gradle's ``java`` plugin gives a build ``test`` and ``check`` tasks, and every Maven project has the
    ``test`` and ``verify`` phases. They resolve as verbs, but are not a definition of ``check``: ``CMD-03``
    reads ``runner_commands``, which leaves them out, so a Gradle build beside an npm project is not a second
    gate.
    """
    if runner in ("build.gradle", "build.gradle.kts"):
        text = inventory.read(runner)
        return _gradle_lifecycle(text, inventory) if text else {}
    if runner == "pom.xml":
        return _maven_lifecycle(inventory)
    return {}


def _runner_rank(runner: str) -> int:
    try:
        return RUNNER_PRECEDENCE.index(runner)
    except ValueError:
        return len(RUNNER_PRECEDENCE)


def _split_argv(command: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(command))
    except ValueError:
        return tuple(command.split())


# ---------------------------------------------------------------------------
# minimal, stdlib-only manifest parsers (deliberately crude — documented as such)
# ---------------------------------------------------------------------------


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _parse_taskfile(text: str) -> dict[str, str]:
    """Minimal Taskfile reader: top-level ``tasks:`` mapping, ``cmd:`` scalar and ``cmds:`` list.

    No YAML library is available (stdlib only), so this understands the common shape and nothing
    exotic: anchors, ``includes``, templating and nested ``deps`` are not interpreted.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if re.match(r"^tasks:\s*(#.*)?$", line))
    except StopIteration:
        return {}

    base = _indent(lines[start])
    tasks: dict[str, list[str]] = {}
    order: list[str] = []
    header_indent: int | None = None
    current: str | None = None

    for line in lines[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = _indent(line)
        if indent <= base:
            break
        if header_indent is None:
            header_indent = indent
        header = re.match(r"^([A-Za-z0-9_:-]+):\s*$", line.strip())
        if indent == header_indent and header:
            current = header.group(1)
            if current not in tasks:
                tasks[current] = []
                order.append(current)
            continue
        if current is None or indent <= header_indent:
            continue
        scalar = re.match(r"^cmd:\s*(.+)$", line.strip())
        if scalar:
            tasks[current].append(scalar.group(1).strip())
            continue
        item = re.match(r"^-\s*(.+)$", line.strip())
        if item:
            tasks[current].append(item.group(1).strip())

    return {name: " && ".join(tasks[name]) for name in order if tasks[name]}


def _parse_pyproject_tasks(text: str) -> dict[str, str]:
    """Minimal pyproject reader for task runners (``[tool.poe.tasks]``, ``[tool.taskipy.tasks]``).

    Reads any ``[tool.<runner>.tasks]`` section, accepting ``name = "cmd"`` and
    ``name = { cmd = "cmd" }``. A TOML parser is not in the standard library, so this is deliberately
    shallow and ignores everything else in the file.
    """
    tasks: dict[str, str] = {}
    section: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        header = re.match(r"^\[([^\]]+)\]$", line)
        if header:
            section = header.group(1)
            continue
        if not section or not section.startswith("tool.") or not section.endswith(".tasks"):
            continue
        scalar = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]*)"', line)
        if scalar:
            tasks[scalar.group(1)] = scalar.group(2)
            continue
        table = re.match(r"^([A-Za-z0-9_.-]+)\s*=\s*\{(.*)\}\s*$", line)
        if table:
            command = re.search(r'(?:cmd|command|script)\s*[:=]\s*["\']([^"\']+)["\']', table.group(2))
            if command:
                tasks[table.group(1)] = command.group(1)
    return tasks


_GRADLE_TASK_PATTERNS = (
    re.compile(r"\btasks\.register\(\s*['\"]([A-Za-z0-9_:-]+)['\"]"),
    re.compile(r"\bregister\(\s*['\"]([A-Za-z0-9_:-]+)['\"]"),
    re.compile(r"^\s*task\s+([A-Za-z0-9_:-]+)"),
)

#: How a build names a plugin: ``id 'java'``, ``id("java")``, ``apply plugin: 'java'`` and ``kotlin("jvm")``;
#: a Kotlin build also lists a core plugin bare, in the ``plugins`` block (java, `java-library`).
_GRADLE_PLUGIN_ID_RES = (
    re.compile(r"""\bid\s*\(?\s*['"]([\w.\-]+)['"]"""),
    re.compile(r"""\bapply\s+plugin\s*:\s*['"]([\w.\-]+)['"]"""),
)
_GRADLE_KOTLIN_JVM_RE = re.compile(r"""\bkotlin\s*\(\s*['"]jvm['"]\s*\)""")
_GRADLE_PLUGINS_BLOCK_RE = re.compile(r"\bplugins\s*\{([^}]*)\}")
_GRADLE_BARE_PLUGIN_RE = re.compile(r"^\s*`?([\w\-]+)`?\s*$")

#: Plugins that register ``test`` and ``check`` on a build (Quarkus applies the ``java`` plugin itself).
_GRADLE_LIFECYCLE_PLUGINS = frozenset(
    {"java", "java-library", "application", "groovy", "scala", "war", "org.jetbrains.kotlin.jvm", "io.quarkus"}
)


def _parse_gradle_tasks(text: str, inventory: Inventory) -> dict[str, str]:
    """Declared Gradle task names, invoked through the committed wrapper when one exists.

    Gradle has no verb table: a verb resolves when the build file registers a task of that name, or, for
    ``test`` and ``check``, when a plugin gives the build one (:func:`_gradle_lifecycle`).
    """
    names: set[str] = set()
    for line in text.splitlines():
        for pattern in _GRADLE_TASK_PATTERNS:
            match = pattern.search(line)
            if match:
                names.add(match.group(1))
    launcher = _launcher(inventory, "gradlew", "gradle")
    return {name: f"{launcher} {name}" for name in sorted(names)}


def _gradle_plugins(text: str) -> set[str]:
    plugins = {match for pattern in _GRADLE_PLUGIN_ID_RES for match in pattern.findall(text)}
    if _GRADLE_KOTLIN_JVM_RE.search(text):
        plugins.add("org.jetbrains.kotlin.jvm")
    for block in _GRADLE_PLUGINS_BLOCK_RE.findall(text):
        for line in block.splitlines():
            bare = _GRADLE_BARE_PLUGIN_RE.match(line)
            if bare:
                plugins.add(bare.group(1))
    return plugins


def _gradle_lifecycle(text: str, inventory: Inventory) -> dict[str, str]:
    """``test`` and ``check`` for a build that applies a plugin which registers them."""
    if not _gradle_plugins(text) & _GRADLE_LIFECYCLE_PLUGINS:
        return {}
    launcher = _launcher(inventory, "gradlew", "gradle")
    return {"test": f"{launcher} test", "check": f"{launcher} check"}


#: Maven has no named tasks. A verb is a lifecycle phase, or a goal of a plugin the pom declares, spelled as
#: the spec's table gives it; the plugins are the table's defaults (Spotless, Checkstyle, OWASP dependency-check).
_MAVEN_PLUGIN_GOALS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("spotless-maven-plugin", (("format", "spotless:apply"), ("format:check", "spotless:check"))),
    ("maven-checkstyle-plugin", (("lint", "checkstyle:check"),)),
    ("dependency-check-maven", (("security", "org.owasp:dependency-check-maven:check"),)),
)
_MAVEN_LIFECYCLE_PHASES = (("test", "test"), ("typecheck", "compile test-compile"), ("check", "verify"))


def _launcher(inventory: Inventory, wrapper: str, fallback: str) -> str:
    return f"./{wrapper}" if inventory.has(wrapper) else fallback


def _parse_maven_plugins(text: str, inventory: Inventory) -> dict[str, str]:
    """The verbs of the plugins a pom declares, invoked through the committed wrapper when one exists.

    A plugin is declared by its ``artifactId``. A ``<goal>`` inside an execution is not a verb: it names
    what the plugin runs, and ``./mvnw check`` is not a Maven command.
    """
    launcher = _launcher(inventory, "mvnw", "mvn")
    commands: dict[str, str] = {}
    for artifact, goals in _MAVEN_PLUGIN_GOALS:
        if re.search(rf"<artifactId>\s*{re.escape(artifact)}\s*</artifactId>", text):
            commands.update({verb: f"{launcher} {goal}" for verb, goal in goals})
    return commands


def _maven_lifecycle(inventory: Inventory) -> dict[str, str]:
    launcher = _launcher(inventory, "mvnw", "mvn")
    return {verb: f"{launcher} {phase}" for verb, phase in _MAVEN_LIFECYCLE_PHASES}
