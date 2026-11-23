# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-13: Contributing rules written."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.hyg._shared import _finding, _named_documents, _outcome

SPEC = declare(
    "HYG-13",
    "Contributing rules written",
    "B",
    Severity.COSMETIC,
    scored=False,
    rule="The CONTRIBUTING document (root, .github/, .gitlab/ or docs/) points to the setup command, names the gate "
    "command and says CI runs the same, and states the rules for branches, commits and pull requests; no "
    "CONTRIBUTING document is UNKNOWN, because HYG-05 owns that finding.",
)


# ===========================================================================
# HYG-13 — contributing rules written
# ===========================================================================


#: (a) A Markdown link to the root README or AGENTS file, where the setup command lives: `[README.md](README.md)`,
#: `[setup](../README.md#development)`.
_SETUP_LINK_RE = re.compile(r"(?i)\]\(\s*/?(?:\.{1,2}/)*(?:readme|agents)\.md(?:#[^)\s]*)?\s*\)")

#: (a) A named setup command: `make setup`, `npm ci`, `pip install`, `uv sync`, `./scripts/bootstrap.sh`.
_SETUP_COMMAND_RE = re.compile(
    r"(?i)(?<![\w-])(?:"
    r"(?:make|just|task|mise run|(?:npm|pnpm|yarn|bun) run) (?:setup|bootstrap|install|init)"
    r"|(?:npm|pnpm|yarn|bun) (?:install|ci)"
    r"|(?:python3? -m )?pip install|uv sync|poetry install|pipenv install|bundle install|go mod download"
    r"|(?:\./)?(?:gradlew|mvnw) (?:build|assemble|install)|mvn install"
    r"|(?:\./)?(?:scripts?|bin)/(?:setup|bootstrap)"
    r")(?![\w-])"
)

#: (b) The gate command: a `check`, `verify`, `gate` or `ci` verb on a task runner: `make check`, `npm run check`,
#: `./gradlew check`, `mvn verify`.
_GATE_COMMAND_RE = re.compile(
    r"(?i)(?<![\w-])(?:make|just|task|mise run|(?:npm|pnpm|yarn|bun) run|pnpm|yarn|nox -s|tox -e|hatch run|poe"
    r"|(?:\./)?gradlew|(?:\./)?mvnw|mvn|gradle) (?:check|verify|gate|ci)(?![\w-])"
)

#: (b) A word that names CI. `CI` is upper case only, so "ci" in a command does not count.
_CI_WORD_RE = re.compile(r"\bCI\b|(?i:\bcontinuous integration\b|\bgithub actions\b|\bgitlab ci\b|\bpipelines?\b)")

#: (b) The word that says CI runs the same command as the contributor.
_SAME_RE = re.compile(r"(?i)\bsame\b")

#: (c) The three subjects whose rules the contributing file holds, each with the words that show it.
_WORKFLOW_SUBJECTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("branches", re.compile(r"(?i)\bbranch(?:es|ing)?\b")),
    ("commits", re.compile(r"(?i)\bcommit(?:s|ted|ting)?\b")),
    ("pull requests", re.compile(r"(?i:\bpull[ -]requests?\b|\bmerge requests?\b)|\bPRs?\b|\bMRs?\b")),
)

#: The three items of P9.3.3 a to c, in order, as the check names them.
_CONTRIBUTING_ITEMS = (
    "a pointer to the setup command",
    "the gate command, and that CI runs the same",
    "the rules for branches, commits and pull requests",
)


def _paragraphs(text: str) -> list[tuple[int, str]]:
    """Each paragraph of ``text`` (lines between blank lines) with the number of its first line."""
    out: list[tuple[int, str]] = []
    start = 0
    lines: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if not lines:
                start = number
            lines.append(line)
        elif lines:
            out.append((start, "\n".join(lines)))
            lines = []
    if lines:
        out.append((start, "\n".join(lines)))
    return out


def _first_line(text: str, pattern: re.Pattern[str]) -> int | None:
    """The 1-based line of the first match of ``pattern`` in ``text``, or ``None``."""
    match = pattern.search(text)
    return None if match is None else text.count("\n", 0, match.start()) + 1


def _ci_runs_the_gate(text: str) -> int | None:
    """The line of the first CI word in a paragraph that also says "same" or names the gate command."""
    for start, paragraph in _paragraphs(text):
        line = _first_line(paragraph, _CI_WORD_RE)
        if line and (_SAME_RE.search(paragraph) or _GATE_COMMAND_RE.search(paragraph)):
            return start + line - 1
    return None


def _contributing_items(rel: str, text: str) -> dict[int, list[Evidence]]:
    """For each item of P9.3.3 a to c (0, 1, 2) that ``text`` shows, the evidence lines that show it."""
    found: dict[int, list[Evidence]] = {}
    setup = _first_line(text, _SETUP_LINK_RE) or _first_line(text, _SETUP_COMMAND_RE)
    if setup:
        found[0] = [Evidence(rel, line=setup, note="setup pointer")]
    gate = _first_line(text, _GATE_COMMAND_RE)
    ci_line = _ci_runs_the_gate(text)
    if gate and ci_line:
        found[1] = [Evidence(rel, line=gate, note="gate command"), Evidence(rel, line=ci_line, note="CI runs it")]
    subjects = [(label, _first_line(text, pattern)) for label, pattern in _WORKFLOW_SUBJECTS]
    if all(line for _, line in subjects):
        found[2] = [Evidence(rel, line=line, note=label) for label, line in subjects if line]
    return found


def check_hyg13(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("contributing",))
    if not found:
        return _outcome(
            spec,
            Verdict.UNKNOWN,
            "no CONTRIBUTING document to read; HYG-05 (CONTRIBUTING present) owns that finding",
        )
    texts = [(rel, text) for rel in found if (text := inventory.read(rel)) is not None]
    if not texts:
        return _outcome(
            spec, Verdict.UNKNOWN, f"{', '.join(found)} present but not readable as text (binary or oversized)"
        )

    shown: dict[int, list[Evidence]] = {}
    for rel, text in texts:
        for item, evidence in _contributing_items(rel, text).items():
            shown.setdefault(item, evidence)
    where = ", ".join(rel for rel, _ in texts)
    held = [_CONTRIBUTING_ITEMS[i] for i in sorted(shown)]
    missing = [label for i, label in enumerate(_CONTRIBUTING_ITEMS) if i not in shown]
    if not missing:
        lines = "; ".join(f"{e.note} at {e.path}:{e.line}" for i in sorted(shown) for e in shown[i])
        return _outcome(spec, Verdict.PASS, f"{where} holds {', '.join(held)} ({lines})")

    verdict = Verdict.PARTIAL if shown else Verdict.FAIL
    because = f"{where} does not hold {'; '.join(missing)}"
    evidence = [e for i in sorted(shown) for e in shown[i]]
    evidence += [Evidence(rel, line=1, note="contributing file") for rel, _ in texts]
    return _outcome(
        spec,
        verdict,
        f"{where} holds {len(shown)} of 3 contributing items; missing: {'; '.join(missing)}",
        [
            _finding(
                spec,
                verdict,
                "learn how to set up, check and propose a change from the contributing file",
                because,
                evidence=evidence,
                path=texts[0][0],
                remediation="Complete the contributing file: link the setup command in README.md or AGENTS.md "
                "rather than copy it, name the gate command and say that CI runs the same command, and state "
                "the rules for branches, commits and pull requests (the greenfield CONTRIBUTING.md is a model).",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import REPOSITORY_LEVEL, Reads, What, _at

    return Reads(
        where=(*_at(REPOSITORY_LEVEL, "CONTRIBUTING*"),),
        what=What("phrase"),
        binding="paragraph",
        note=(
            "Item (b) needs a CI word and either same or the gate command in one paragraph (lines between "
            "blank lines); items (a), a link to README.md or AGENTS.md or a setup command, and (c), words for"
            " branches, commits and pull requests, are file-wide. The link target is never read."
        ),
    )
