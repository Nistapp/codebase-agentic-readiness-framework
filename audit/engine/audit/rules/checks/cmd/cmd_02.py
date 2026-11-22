# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CMD-02: check composes the read-only verbs."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import (
    GRADLE_LIFECYCLE_PLUGINS,
    VerbBinding,
    gradle_plugins,
    resolve_verbs,
    runner_commands,
    runner_kind,
)
from audit.stack import canonical_verb
from audit.rules.checks.cmd._shared import (
    _NPM_RE,
    _RUNNER_INVOCATIONS,
    _YARN_RE,
    _no_runner,
    _outcome,
    _runner_target,
    _segments,
    _unknown,
)

SPEC = declare("CMD-02", "check composes the read-only verbs", "B", Severity.BLOCKER)


#: The three read-only concerns a `check` gate must compose, in catalogue order.
CONCERNS = ("format-check", "typecheck", "test")

#: Which resolved verb satisfies which concern. `lint` composes into `format:check` in the framework's
#: reference surface, so it is not a concern of its own here.
_CONCERN_OF_VERB = {"format:check": "format-check", "typecheck": "typecheck", "test": "test"}

#: Runners whose `check` is a lifecycle task: what it runs is set by the build's task graph, not by a command.
_LIFECYCLE_RUNNERS = ("build.gradle", "build.gradle.kts", "pom.xml")

#: Runners whose `check` is followed into the runner's own targets, and how a segment calls that runner. In a
#: `Makefile` a prerequisite is a target too, so every invocation form counts there.
_FOLLOWED_RUNNERS: dict[str, tuple[re.Pattern, ...]] = {
    "Makefile": _RUNNER_INVOCATIONS,
    "package.json": (_NPM_RE, _YARN_RE),
}

#: Documented tool equivalents, used only when `check` calls a tool directly rather than a verb.
_DIRECT_CONCERN_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "format-check",
        (
            r"\bbiome\s+(?:ci|check)\b",
            r"\bprettier\b[^&|;]*--check\b",
            r"\bruff\s+format\b[^&|;]*--(?:check|diff)\b",
            r"\bruff\s+check\b",
            r"\bblack\b[^&|;]*--check\b",
            r"\bdprint\s+check\b",
            r"\bcargo\s+fmt\b[^&|;]*--check\b",
            r"\bgofmt\b[^&|;]*\s-l\b",
            r"\bdotnet\s+format\b[^&|;]*--verify-no-changes\b",
        ),
    ),
    (
        "typecheck",
        (
            r"\btsc\b",
            r"\bmypy\b",
            r"\bpyright\b",
            r"\bbasedpyright\b",
            r"\bcargo\s+check\b",
            r"\bgo\s+vet\b",
        ),
    ),
    (
        "test",
        (
            r"\bvitest\b",
            r"\bjest\b",
            r"\bmocha\b",
            r"\bpytest\b",
            r"python3?\s+-m\s+(?:unittest|pytest)",
            r"\bgo\s+test\b",
            r"\bcargo\s+test\b",
            r"\bdotnet\s+test\b",
            r"\brspec\b",
            r"\bphpunit\b",
            r"\btox\b",
        ),
    ),
)


# ===========================================================================
# CMD-02 — check composes the read-only verbs
# ===========================================================================


def _composition_concerns(
    command: str,
    resolved: dict[str, VerbBinding],
    targets: dict[str, str] | None = None,
    followed: frozenset[str] = frozenset(),
    invocations: tuple[re.Pattern, ...] = (),
) -> set[str]:
    """The concerns ``command`` covers: a verb it invokes by name, or a documented tool.

    ``targets`` is the runner's own ``{name: command}`` map (:data:`_FOLLOWED_RUNNERS`). An invoked name that
    is not a concern of its own is followed into its command, once, so ``check: lint types test`` is read
    through ``types`` and ``npm run test:coverage`` through ``jest --coverage``. Only a segment that calls the
    runner itself (``invocations``) is followed, so ``make x`` in a package script is not read as script ``x``.
    The alias of a verb names that verb: ``format-check`` is ``format:check``.
    """
    concerns: set[str] = set()
    for segment in _segments(command):
        target = _runner_target(segment)
        verb = canonical_verb(target) if target else None
        concern = _CONCERN_OF_VERB.get(verb) if verb in resolved else None
        if concern:
            concerns.add(concern)
        elif (
            targets
            and target in targets
            and target not in followed
            and any(pattern.search(segment) for pattern in invocations)
        ):
            concerns |= _composition_concerns(targets[target], resolved, targets, followed | {target}, invocations)
        for concern, patterns in _DIRECT_CONCERN_PATTERNS:
            if concern not in concerns and any(re.search(p, segment) for p in patterns):
                concerns.add(concern)
    return concerns


#: What a plugin wires into Gradle's `check`, by concern. A JVM plugin's `check` runs `test`, which compiles the main
#: and test sources first; that compile is the typecheck, as Maven's `typecheck` verb is `compile test-compile`.
_GRADLE_PLUGIN_CONCERNS: dict[str, frozenset[str]] = {
    **{plugin: frozenset({"typecheck", "test"}) for plugin in GRADLE_LIFECYCLE_PLUGINS},
    "com.diffplug.spotless": frozenset({"format-check"}),
    "org.jlleitschuh.gradle.ktlint": frozenset({"format-check"}),
}

#: Plugins known to wire no format-check, typecheck or test into `check`. A linter's own task (Checkstyle, PMD,
#: SpotBugs) is not one of the three concerns. Any other plugin may wire one, so the engine does not guess.
_GRADLE_INERT_PLUGINS = frozenset(
    {
        "base",
        "checkstyle",
        "codenarc",
        "com.github.ben-manes.versions",
        "com.github.johnrengelman.shadow",
        "com.github.spotbugs",
        "com.google.cloud.tools.jib",
        "com.gradleup.shadow",
        "distribution",
        "eclipse",
        "idea",
        "io.freefair.lombok",
        "io.spring.dependency-management",
        "jacoco",
        "java-platform",
        "java-test-fixtures",
        "maven-publish",
        "org.cyclonedx.bom",
        "org.graalvm.buildtools.native",
        "org.owasp.dependencycheck",
        "org.sonarqube",
        "org.springframework.boot",
        "pmd",
        "signing",
        "version-catalog",
    }
)

#: Tasks a known plugin registers, by the concern they cover, for a `dependsOn` that names one.
_GRADLE_TASK_CONCERNS = {
    "spotlessCheck": "format-check",
    "ktlintCheck": "format-check",
    "compileJava": "typecheck",
    "compileTestJava": "typecheck",
    "compileKotlin": "typecheck",
    "compileTestKotlin": "typecheck",
}

_GRADLE_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
_GRADLE_CHECK_DEPENDS_RE = re.compile(r"(?<![\w.])(?:tasks\s*\.\s*)?check\s*\.\s*dependsOn\b([^\n]*)")
_GRADLE_CHECK_BLOCK_RE = re.compile(
    r"""(?:\btasks\s*\.\s*(?:named|getByName)\s*(?:<[^>\n]*>)?\s*\(\s*['"]check['"]\s*\)"""
    r"""|(?<![\w.])(?:tasks\s*\.\s*)?check)\s*\{"""
)
_GRADLE_DEPENDS_RE = re.compile(r"\bdependsOn\b([^\n]*)")
_GRADLE_OPAQUE_RE = re.compile(r"\bsetDependsOn\b|\benabled\b|\bonlyIf\b|\.clear\s*\(")
_GRADLE_CHECK_MENTION_RE = re.compile(r"""(?<![\w.:-])check(?![\w-])|['"]check['"]""")
_GRADLE_QUOTED_RE = re.compile(r"""['"]([^'"\n]*)['"]""")
_GRADLE_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_GRADLE_ACCESSORS = frozenset({"tasks", "named", "getByName", "project", "provider", "map", "get", "dependsOn"})
_GRADLE_SPOTLESS_OFF_RE = re.compile(r"\b(?:is)?[eE]nforceCheck\s*(?:=\s*)?false\b")
_GRADLE_ALIAS_RE = re.compile(r"\balias\s*\(")
_GRADLE_APPLY_FROM_RE = re.compile(r"\bapply\s*\(?\s*from\b")
_GRADLE_INCLUDE_RE = re.compile(r"^\s*include(?:Build)?\b", re.MULTILINE)

#: The settings files that make a Gradle build multi-project, read at the root.
_GRADLE_SETTINGS = ("settings.gradle", "settings.gradle.kts")


def _block_at(text: str, open_brace: int) -> str:
    """The text inside the brace block that opens at ``open_brace``, up to its matching close or the end."""
    depth = 0
    for index in range(open_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1 : index]
    return text[open_brace + 1 :]


def _depends_names(argument: str) -> list[str]:
    """The task names a ``dependsOn`` argument gives: quoted names, then bare task references."""
    names = [name for name in _GRADLE_QUOTED_RE.findall(argument)]
    bare = _GRADLE_QUOTED_RE.sub(" ", argument)
    names += [name for name in _GRADLE_IDENT_RE.findall(bare) if name not in _GRADLE_ACCESSORS]
    return names


def _gradle_check(text: str, settings: str, resolved: dict[str, VerbBinding]) -> tuple[set[str], list[str]]:
    """The concerns a Gradle build's `check` runs, and what else may add to it that the engine does not read.

    The concerns come from the plugins the build applies and from the tasks its own `check` wiring depends on
    (``check.dependsOn``, ``tasks.named('check') { dependsOn ... }``). A plugin, a script, a subproject or a task the
    engine does not know may add a concern, so each is named rather than read as adding nothing.
    """
    code = _GRADLE_COMMENT_RE.sub("", text)
    concerns: set[str] = set()
    unread: list[str] = []
    for plugin in sorted(gradle_plugins(code)):
        if plugin == "com.diffplug.spotless" and _GRADLE_SPOTLESS_OFF_RE.search(code):
            continue
        if plugin in _GRADLE_PLUGIN_CONCERNS:
            concerns |= _GRADLE_PLUGIN_CONCERNS[plugin]
        elif plugin not in _GRADLE_INERT_PLUGINS:
            unread.append(f"the plugin {plugin}")
    if _GRADLE_ALIAS_RE.search(code):
        unread.append("a plugin applied through a version-catalog alias")
    if _GRADLE_APPLY_FROM_RE.search(code):
        unread.append("a script applied with apply from")
    if _GRADLE_INCLUDE_RE.search(settings):
        unread.append("the subprojects the settings file includes")

    names: list[str] = []
    read_spans: list[tuple[int, int]] = []
    for match in _GRADLE_CHECK_DEPENDS_RE.finditer(code):
        names += _depends_names(match.group(1))
        read_spans.append(match.span())
    for match in _GRADLE_CHECK_BLOCK_RE.finditer(code):
        block = _block_at(code, match.end() - 1)
        read_spans.append((match.start(), match.end() + len(block) + 1))
        if _GRADLE_OPAQUE_RE.search(block):
            unread.append("a check configuration the engine does not read")
        for depends in _GRADLE_DEPENDS_RE.finditer(block):
            names += _depends_names(depends.group(1))
    if any(
        not any(start <= mention.start() < end for start, end in read_spans)
        for mention in _GRADLE_CHECK_MENTION_RE.finditer(code)
    ):
        unread.append("a check configuration the engine does not read")

    for name in names:
        verb = canonical_verb(name)
        concern = _CONCERN_OF_VERB.get(verb) if verb in resolved else _GRADLE_TASK_CONCERNS.get(name)
        if concern:
            concerns.add(concern)
        else:
            unread.append(f"the task {name}")
    return concerns, list(dict.fromkeys(unread))


def check_cmd02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    declared = runner_commands(inventory)
    if not declared:
        return _no_runner(spec, inventory, "no check verb can be read")

    resolved = resolve_verbs(inventory, stack)
    check = resolved.get("check")
    if check is None:
        return _outcome(
            spec,
            Verdict.FAIL,
            "the check verb is not defined on any runner",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "run one gate that composes the read-only verbs", "no runner defines a check verb"
                    ),
                    remediation="Define check as format-check, then typecheck, then test.",
                )
            ],
        )

    gradle = runner_kind(check.runner) in ("build.gradle", "build.gradle.kts")
    if runner_kind(check.runner) in _LIFECYCLE_RUNNERS and not gradle:
        return _unknown(
            spec,
            f"the {check.runner} check is a build lifecycle task, and what it composes is set by the build's task "
            "graph, which the engine does not read",
        )

    unread: list[str] = []
    if gradle:
        settings = next((text for name in _GRADLE_SETTINGS if (text := inventory.read(name))), "")
        concerns, unread = _gradle_check(inventory.read(check.runner) or "", settings, resolved)
    else:
        invocations = _FOLLOWED_RUNNERS.get(runner_kind(check.runner), ())
        own_targets = dict(declared).get(check.runner, {}) if invocations else None
        concerns = _composition_concerns(check.command, resolved, own_targets, invocations=invocations)
    present = [c for c in CONCERNS if c in concerns]
    missing = [c for c in CONCERNS if c not in concerns]
    detail = f"check ({check.runner}) composes: " + (", ".join(present) if present else "nothing")
    if missing and unread:
        return _unknown(
            spec,
            f"{detail} — {', '.join(unread)} may add {', '.join(missing)}, and the engine does not read what they "
            "wire into check",
        )

    if not missing:
        return _outcome(spec, Verdict.PASS, detail)

    verdict = Verdict.PARTIAL if present else Verdict.FAIL
    return _outcome(
        spec,
        verdict,
        detail + f" — missing {', '.join(missing)}",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=verdict,
                statement=statement(
                    "trust one gate to verify the change set",
                    f"the {check.runner} check verb does not invoke {', '.join(missing)}",
                ),
                evidence=[Evidence(check.runner, note=check.command)],
                remediation=(
                    f"Wire check to depend on {', '.join(missing)} (for example "
                    "`tasks.named('check') { dependsOn 'formatCheck' }`), so one command is the gate."
                    if gradle
                    else "Make check invoke a format-check, a typecheck and the test suite, in that order, so one "
                    "command is the gate."
                ),
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at, _runners

    return Reads(
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
    )
