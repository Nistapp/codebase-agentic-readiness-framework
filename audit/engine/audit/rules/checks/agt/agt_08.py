# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-08: No competing instruction files, and the reach matrix is stated."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules import variants as V
from audit.rules.payloads import HarnessMatrix
from audit.rules.checks.agt._shared import instruction_paths

SPEC = declare("AGT-08", "No competing instruction files, and the reach matrix is stated", "B", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-08 — competing instruction files + reach matrix
# ---------------------------------------------------------------------------


#: The scopes of `AGT-08`'s findings, which have no one path, so that each finding has an id of its own: the id is
#: the check and a path, and the baseline ratchet compares ids. A shadowed pair is named by the pair.
_AGT08_COMPETITORS = "vendor-files"
_AGT08_REACH = "harness-reach"


#: The accepted statement of supported harnesses: a line of the root `AGENTS.md` that says "read by" or "supported
#: harnesses" and names at least one harness of the variant table. A statement is the owner's, so the engine takes it
#: as the answer to the reach gap and says so; it does not verify that each named harness really loads the file.
_AGT08_STATEMENT_RE = re.compile(r"(?i)\b(?:read\s+by|supported\s+harnesses?)\b")


def _harness_aliases(tool: str) -> tuple[str, ...]:
    """Short lower-case names for one table entry: ``Anthropic Claude Code`` -> ``claude code``."""
    out = []
    for part in re.split(r"\s*[/(]\s*", tool.replace(")", "")):
        name = re.sub(r"^(?:openai|anthropic|google|github)\s+", "", part.strip().lower())
        name = re.sub(r"\s+cli$", "", name)
        if name:
            out.append(name)
    return tuple(out)


def stated_harnesses(text: str) -> tuple[int, list[str]]:
    """The first statement line of supported harnesses in ``text``: its 1-based line number and the names it holds."""
    aliases = {a: h.tool for h in V.HARNESSES for a in _harness_aliases(h.tool)}
    aliases["opencode"] = "opencode"
    for number, line in enumerate(text.splitlines(), 1):
        if not _AGT08_STATEMENT_RE.search(line):
            continue
        low = line.lower()
        named = sorted({tool for alias, tool in aliases.items() if re.search(rf"\b{re.escape(alias)}\b", low)})
        if named:
            return number, named
    return 0, []


#: Claude Code's import syntax for the canonical file: `@AGENTS.md`, `@./AGENTS.md` or `@../AGENTS.md`, alone on a line
#: or inside a sentence. A file that imports `AGENTS.md` loads it, so it never shadows it.
_AGENTS_IMPORT_RE = re.compile(r"(?<![\w`])@(?:\.{1,2}/)*AGENTS\.md\b")

#: The most content lines a pointer file may hold. A pointer says where the rules are; it does not hold them.
_POINTER_MAX_LINES = 5


def _content_lines(text: str) -> list[str]:
    """The lines of ``text`` that say something: not blank, not a heading, not inside an HTML comment."""
    text = re.sub(r"(?s)<!--.*?-->", "", text)
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def imports_agents_md(text: str) -> bool:
    """True when ``text`` imports the canonical file with Claude Code's ``@AGENTS.md`` syntax."""
    return bool(_AGENTS_IMPORT_RE.search(text))


def is_agents_md_pointer(text: str) -> bool:
    """True when every content line of ``text`` names ``AGENTS.md`` (``@AGENTS.md``, "See AGENTS.md") and there are few.

    Such a vendor file holds no rules of its own: it sends its harness to the canonical file, so it neither competes
    with nor shadows it (issue #26).
    """
    lines = _content_lines(text)
    return 0 < len(lines) <= _POINTER_MAX_LINES and all("AGENTS.md" in line for line in lines)


def _pointer_files(inventory: Inventory, vendor: list[str]) -> tuple[set[str], set[str]]:
    """The vendor files that only point at ``AGENTS.md``, and those that import it beside rules of their own."""
    pointers: set[str] = set()
    importers: set[str] = set()
    for rel in vendor:
        text = inventory.read(rel)
        if text is None:
            continue
        if is_agents_md_pointer(text):
            pointers.add(rel)
        elif imports_agents_md(text):
            importers.add(rel)
    return pointers, importers


def check_agt08(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    present = instruction_paths(inventory)
    classified = V.classify_present(present)
    # A vendor file that only points at the root AGENTS.md is a pointer, not a competitor; one that imports it loads
    # it, so it shadows nothing. Both still give their harness its reach. With no root AGENTS.md a pointer points at
    # nothing, and AGT-01 and AGT-10 own that gap.
    pointers, importers = (
        _pointer_files(inventory, list(classified["vendor_only"])) if "AGENTS.md" in present else (set(), set())
    )
    competitors = [p for p in classified["vendor_only"] if p not in pointers]
    shadowed = (
        V.classify_present(present - pointers - importers)["shadowed"]
        if pointers or importers
        else classified["shadowed"]
    )
    reached = classified["harnesses_reached"]
    missed = classified["harnesses_missed"]
    findings: list[Finding] = []

    if competitors:
        beside = "alongside the canonical one" if "AGENTS.md" in present else "with no canonical AGENTS.md at the root"
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "know which instruction file is authoritative",
                    f"{len(competitors)} vendor-specific instruction files exist {beside} "
                    f"({', '.join(competitors[:8])}{'…' if len(competitors) > 8 else ''})",
                ),
                evidence=[Evidence(p) for p in competitors[:12]],
                remediation="Keep AGENTS.md canonical; reduce each vendor file to a pointer at it, or "
                "delete it if the harness reads AGENTS.md natively.",
                path=_AGT08_COMPETITORS,
            )
        )
    for winner, loser in shadowed:
        findings.append(
            Finding(
                check=spec.id,
                severity=Severity.DEGRADER,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "be sure that both files are read",
                    f"{winner} shadows {loser} for the harness that defines the pair, so only one of "
                    f"the two is ever loaded",
                ),
                evidence=[Evidence(winner), Evidence(loser)],
                remediation="Reconcile the two files, or delete the shadowed one — a file nobody "
                "reads still gets edited.",
                path=f"{winner}>{loser}",
            )
        )
    stated_at, stated = stated_harnesses(inventory.read("AGENTS.md") or "") if "AGENTS.md" in present else (0, [])
    if missed and ("AGENTS.md" in present or competitors) and not stated:
        findings.append(
            Finding(
                check=spec.id,
                severity=Severity.COSMETIC,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "assume every harness on the team sees the project rules",
                    f"{len(reached)} of {len(reached) + len(missed)} known harnesses reach an "
                    f"instruction file; {', '.join(missed[:8])}{'…' if len(missed) > 8 else ''} reach "
                    f"nothing",
                ),
                remediation="Either state the supported harnesses in AGENTS.md, or add the vendor "
                "pointer files for the harnesses in use.",
                path=_AGT08_REACH,
            )
        )

    verdict = (
        Verdict.FAIL
        if any(f.verdict is Verdict.FAIL for f in findings)
        else (Verdict.PARTIAL if findings else Verdict.PASS)
    )
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=f"{len(reached)}/{len(reached) + len(missed)} harnesses reached"
        + (f"; AGENTS.md:{stated_at} states the supported harnesses ({', '.join(stated)})" if stated else "")
        + (f"; pointer files at AGENTS.md, not competitors: {', '.join(sorted(pointers))}" if pointers else "")
        + (f"; files that import @AGENTS.md, so shadow nothing: {', '.join(sorted(importers))}" if importers else ""),
        data=HarnessMatrix(
            reached=len(reached),
            total=len(reached) + len(missed),
            reached_tools=tuple(sorted(reached)),
            unreached_tools=tuple(sorted(missed)),
        ),
        findings=findings,
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, ROOT, Reads, What, _FOLDER_INSTRUCTION_PATHS, _at

    return Reads(
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
    )
