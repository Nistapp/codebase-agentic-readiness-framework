# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-10: Instruction indirection resolved."""

from __future__ import annotations

import json
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.agt._shared import _rule_line_count

SPEC = declare("AGT-10", "Instruction indirection resolved", "B", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-10 — indirection resolved
# ---------------------------------------------------------------------------

_REFERENCE_RE = re.compile(r"[`\"']?([A-Za-z0-9_./-]+\.(?:md|markdown|txt|yml|yaml|json|toml))[`\"']?")

#: The deferral pattern is deliberately narrow: "read this before you act", not any citation of
#: another file. A wider pattern flags legitimate prose — "refer to package.json for versions",
#: "every doc must follow docs/STYLE_GUIDE.md" — as indirection, and a check that fires on well
#: written instruction files is worse than no check. Calibrated against two real repositories
#: (agentic-tdd: no finding, correct; Digital-Assistant-Server: one finding, correct).
_DEFER_RE = re.compile(
    r"(?i)(first\s+(read|check|review|understand|study)|"
    r"read\s+[^.\n]{0,80}\s+first|"
    r"before\s+(you\s+|starting|beginning|making|editing|changing|any)[^.\n]{0,60}read|"
    r"start\s+by\s+reading|"
    r"refer\s+to\s+[^.\n]{0,60}\s+first)"
)


#: Config keys that name an instruction file elsewhere, and how to read them.
def _configured_targets(inventory: Inventory) -> dict[str, list[str]]:
    """Instruction files named by harness configuration, per config file.

    Only the formats this project can parse without a third-party parser are read. Anything else
    is reported as unparsed rather than assumed absent.
    """
    configured: dict[str, list[str]] = {}

    aider = inventory.read(".aider.conf.yml")
    if aider:
        targets: list[str] = []
        inline = re.search(r"^\s*read:\s*\[(.*?)\]", aider, re.MULTILINE | re.DOTALL)
        block = re.search(r"^\s*read:\s*\n((?:\s*-\s*.*\n?)+)", aider, re.MULTILINE)
        if inline:
            targets += [m.strip() for m in re.findall(r"['\"]([^'\"]+)['\"]", inline.group(1))]
        if block:
            targets += re.findall(r"-\s*['\"]?([^'\"\n]+)['\"]?", block.group(1))
        configured[".aider.conf.yml"] = [t.strip() for t in targets if t.strip()]

    codex = inventory.read(".codex/config.toml")
    if codex:
        targets = []
        for key in ("project_doc_fallback_filenames", "model_instructions_file", "experimental_instructions_file"):
            match = re.search(rf"{key}\s*=\s*(.+)", codex)
            if match:
                targets += re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
        configured[".codex/config.toml"] = targets

    gemini = inventory.read(".gemini/settings.json")
    if gemini:
        targets = []
        try:
            data = json.loads(gemini)
            names = data.get("context", {}).get("fileName") or data.get("contextFileName")
            targets = [names] if isinstance(names, str) else list(names or [])
        except (json.JSONDecodeError, AttributeError):
            targets = []
        configured[".gemini/settings.json"] = targets

    opencode = inventory.read("opencode.json")
    if opencode:
        targets = []
        try:
            instructions = json.loads(opencode).get("instructions", [])
            targets = [i for i in instructions if isinstance(i, str) and not i.startswith("http")]
        except (json.JSONDecodeError, AttributeError):
            targets = []
        configured["opencode.json"] = targets

    return configured


def _from_root(name: str) -> str:
    """A configured target as a path from the root: each leading ``./`` goes, and a dot folder keeps its dot."""
    rel = name.strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def check_agt10(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    findings: list[Finding] = []
    configured = _configured_targets(inventory)
    detail: list[str] = []

    # 1. a configured pointer that names a file which does not exist
    for config_file, targets in configured.items():
        for name in targets:
            rel = _from_root(name)
            exists = inventory.match(rel) if "*" in rel else inventory.has(rel)
            if not exists:
                findings.append(_broken_pointer(spec, config_file, name))
    broken = len(findings)
    if configured:
        detail.append(f"{len(configured)} config file(s) name instruction targets")

    # 2. deferral inside the entry file: rules live in another file, unnamed by any config
    entry = inventory.read("AGENTS.md") or inventory.read("CLAUDE.md") or ""
    if entry:
        named_elsewhere = {_from_root(t) for targets in configured.values() for t in targets}
        deferred: list[str] = []
        for line in entry.splitlines():
            if not _DEFER_RE.search(line):
                continue
            for reference in _REFERENCE_RE.findall(line):
                candidate = _from_root(reference)
                if candidate in {"AGENTS.md", "CLAUDE.md"}:
                    continue
                if inventory.has(candidate) and candidate not in named_elsewhere:
                    deferred.append(candidate)
        if deferred:
            findings.append(
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "trust that the referenced rules are actually loaded",
                        f"the instruction file defers its content to {', '.join(sorted(set(deferred)))} "
                        f"and no harness configuration names that file, so loading depends on the agent "
                        f"choosing to follow the pointer",
                    ),
                    evidence=[Evidence("AGENTS.md", note="deferral found: " + ", ".join(sorted(set(deferred))))],
                    remediation="Inline the rules that must always apply, or name the referenced file "
                    "in each harness's config (aider read:, opencode.json instructions, "
                    "Codex model_instructions_file).",
                )
            )
        if not _rule_line_count(entry) > 0:
            detail.append("instruction file has no rule lines")
        if deferred:
            detail.append(f"defers to {', '.join(sorted(set(deferred)))}, which no harness config names")
        else:
            detail.append("defers to no file that a harness config leaves unloaded")
    else:
        detail.append("no AGENTS.md or CLAUDE.md to read for a deferral")
    if not configured:
        detail.insert(0, "no harness config names an instruction target")
    if broken:
        detail.insert(0, f"{broken} configured pointer(s) name a missing file")

    verdict = Verdict.FAIL if findings else Verdict.PASS
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary="; ".join(detail),
        findings=findings,
    )


def _broken_pointer(spec, config_file: str, name: str) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=Verdict.FAIL,
        statement=statement(
            "receive project instructions from the configured file",
            f"{config_file} points at {name!r}, which does not exist in the repository",
        ),
        evidence=[Evidence(config_file, note=f"missing target: {name}")],
        remediation=f"Create {name}, or remove the stale entry from {config_file}.",
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at

    return Reads(
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
    )
