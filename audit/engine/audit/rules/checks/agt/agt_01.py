# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-01: Instruction file present, canonical, and non-trivial."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules import variants as V
from audit.rules.checks.agt._shared import instruction_paths, _rule_line_count

SPEC = declare("AGT-01", "Instruction file present, canonical, and non-trivial", "A", Severity.BLOCKER)


#: An instruction file below this size, or matching a stub marker, is present but not governance.
MIN_INSTRUCTION_CHARS = 400
#: Phrases that mark an unfilled template wherever they stand.
STUB_PHRASES = ("lorem ipsum", "<describe", "coming soon", "fill this in")

#: A word stands as a marker when it opens a line (after the punctuation that a list, a heading, a quote or a comment
#: puts there, a list number included) and ends it or is followed by a colon, a dash or a closing bracket, or when it
#: sits in brackets. In a sentence it is an ordinary word: "never commit placeholder values", "leave no TODO in a commit".
_STUB_WORD_RES = (
    re.compile(
        r"^[\s>*#\-\u2022\[(<!/\d.)]*(todo|tbd|placeholder)\b\s*(?:[:\-\u2013\u2014\])>]|$)",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(r"[\[(<]\s*(todo|tbd|placeholder)\s*[\])>]", re.IGNORECASE),
)


def _trivial_reason(text: str) -> str | None:
    if len(text.strip()) < MIN_INSTRUCTION_CHARS:
        return f"only {len(text.strip())} characters (minimum {MIN_INSTRUCTION_CHARS})"
    lowered = text.lower()
    for phrase in STUB_PHRASES:
        if phrase in lowered:
            return f"contains the placeholder marker {phrase!r}"
    for pattern in _STUB_WORD_RES:
        found = pattern.search(text)
        if found:
            return f"contains the placeholder marker {found.group(1).lower()!r}"
    return None


# ---------------------------------------------------------------------------
# AGT-01 — instruction file present, canonical, non-trivial
# ---------------------------------------------------------------------------


def check_agt01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    present = instruction_paths(inventory)
    classified = V.classify_present(present)
    findings: list[Finding] = []

    canonical_root = "AGENTS.md" in present
    canonical_nested = sorted(p for p in present if p.endswith("/AGENTS.md"))
    mis_cased = V.mis_cased_canonical_candidates(present)
    aliases = classified["aliases"]
    overrides = classified["overrides"]
    vendor_only = classified["vendor_only"]

    if not present:
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "learn the project's conventions", "no agent-instruction file exists anywhere in the repository"
                ),
                remediation="Create AGENTS.md at the repository root with the adapt-agents-md playbook: the "
                "headings of the framework's greenfield template, each section filled with this repository's facts.",
            )
        )
    else:
        if canonical_root:
            text = inventory.read("AGENTS.md") or ""
            reason = _trivial_reason(text)
            if reason:
                findings.append(
                    Finding(
                        check=spec.id,
                        severity=spec.severity,
                        phase=spec.phase,
                        verdict=Verdict.FAIL,
                        statement=statement(
                            "work to this project's conventions", f"AGENTS.md exists but is a stub — {reason}"
                        ),
                        evidence=[Evidence("AGENTS.md", note=f"{_rule_line_count(text)} rule lines")],
                        remediation="Fill AGENTS.md with this repository's facts, using the adapt-agents-md "
                        "playbook: verbs, boundaries, definition of done, prohibitions.",
                        path="AGENTS.md",
                    )
                )
        if mis_cased:
            findings.append(
                Finding(
                    check=spec.id,
                    severity=Severity.DEGRADER,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "rely on the instruction file being found",
                        f"{', '.join(mis_cased)} differs from AGENTS.md only by case, and "
                        f"case-sensitive filesystems will not find it",
                    ),
                    evidence=[Evidence(p) for p in mis_cased],
                    remediation="Rename to AGENTS.md exactly (Warp also requires ALL CAPS).",
                    path=mis_cased[0],
                )
            )
        if not canonical_root and (aliases or vendor_only):
            owner = (
                ", ".join(sorted(set(tool for name in aliases for tool in V.NON_CANONICAL_ALIASES.get(name, ()))))
                or "one harness"
            )
            findings.append(
                Finding(
                    check=spec.id,
                    severity=Severity.DEGRADER,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "share one set of project rules across harnesses",
                        f"instruction content lives only in vendor-specific files "
                        f"({', '.join(sorted(aliases + vendor_only))}) that {owner} reads",
                    ),
                    remediation="Add AGENTS.md as the canonical file and reduce vendor files to a "
                    "one-line pointer, or a symlink where the harness supports it.",
                    path="vendor-only",
                )
            )
        if not canonical_root and canonical_nested:
            findings.append(
                Finding(
                    check=spec.id,
                    severity=Severity.DEGRADER,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "find the project rules at the repository root",
                        f"AGENTS.md exists only below the root ({', '.join(canonical_nested[:6])}"
                        f"{'…' if len(canonical_nested) > 6 else ''}), so a harness that reads the root file "
                        f"finds no instruction file",
                    ),
                    evidence=[Evidence(p) for p in canonical_nested[:12]],
                    remediation="Add AGENTS.md at the repository root with the adapt-agents-md playbook, and keep "
                    "each nested AGENTS.md for what is local to its folder.",
                    path="nested-only",
                )
            )
        if overrides:
            for override in overrides:
                tool = V.OVERRIDE_PATHS.get(override, "some harness")
                findings.append(
                    Finding(
                        check=spec.id,
                        severity=Severity.DEGRADER,
                        phase=spec.phase,
                        verdict=Verdict.PARTIAL,
                        statement=statement(
                            "rely on AGENTS.md in every directory",
                            f"{override} is present for {tool} and makes the AGENTS.md beside it inert",
                        ),
                        evidence=[Evidence(override)],
                        remediation="Delete the override, or make it a deliberate, documented superset.",
                        path=override,
                    )
                )

    if not findings:
        verdict = Verdict.PASS
    else:
        verdict = Verdict.FAIL if any(f.verdict is Verdict.FAIL for f in findings) else Verdict.PARTIAL

    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=_agt01_summary(present, canonical_nested),
        findings=findings,
    )


def _agt01_summary(present: list[str], canonical_nested: list[str]) -> str:
    """One sentence that names the instruction files the verdict rests on; never empty (issue #21)."""
    if not present:
        return "no agent-instruction file in the repository"
    if canonical_nested:
        return f"{len(canonical_nested)} nested instruction file(s)"
    shown = sorted(present)
    more = f" and {len(shown) - 6} more" if len(shown) > 6 else ""
    return f"instruction file(s): {', '.join(shown[:6])}{more}"


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
        what=What("exists"),
        binding="file",
        threshold="AGENTS.md at the root, at least 400 characters, no stub marker",
        note=(
            "The root AGENTS.md text is read for its length, four stub phrases and the words todo, tbd and "
            "placeholder at a line start or in brackets; a root agents.md is the only mis-cased name found. A"
            " fixed harness path with a folder (.github/copilot-instructions.md) counts only from the root."
        ),
    )
