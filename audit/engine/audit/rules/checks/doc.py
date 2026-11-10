# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`DOC` pack — documentation contract.

Anchor: `docs/framework/phased-approach.md` § Key Deliverables.

Implemented here: `DOC-01` … `DOC-05`. What each check reads, what makes a `PASS`, and the one place
``UNKNOWN`` is correct:

* **DOC-01** — a markdown file anywhere under `docs/` is the evidence. Absence of the directory is a
  real finding (`FAIL`), because a framework deliverable that does not exist is a fact, not an
  ambiguous one. `docs/` present with no markdown at all is `PARTIAL`. ``UNKNOWN`` is never used:
  the directory either has markdown or it does not.
* **DOC-02** — `docs/STYLE_GUIDE.md` present is the primary evidence; the entry instruction file
  naming it (the same reference `AGT-03` reads) is the second half. Present and named is `PASS`;
  present but unnamed is `PARTIAL`; absent is `FAIL`. `AGT-03` is **not** required to have passed.
* **DOC-03** — `artefacts/` (or `artifacts/`) present and matched by an ignore rule, with no tracked
  member, is `PASS`. No scratch directory in the inventory is `PASS` ("no scratch directory in
  use"). Present but unmatched by any ignore rule is `FAIL` — that half is knowable without git.
  When the directory is ignored but git cannot report the tracked set the check returns ``UNKNOWN``
  rather than infer it (the same degradation `SEC-01` uses).
* **DOC-04** — an ADR directory (`docs/architecture/adrs/` or `docs/adr/`) with numbered entries and
  an index (a `README.md`/`index.md` beside them, or the directory's parent README) that lists them.
  No directory is `FAIL`; entries without an index, or an index that omits some, is `PARTIAL`. An entry that
  is a tombstone (:func:`_adr_tombstone`: marked superseded, deprecated, rejected or obsolete) is `PARTIAL`
  too: an agent loads it as a current instruction.
* **DOC-05** — the plain-language measures of the prose in `docs/` (``audit.rules.checks._prose``): the share of
  sentences over 25 words (20 in a numbered step), vague words per 1,000 words, and explanation or tutorial pages
  without a Mermaid diagram. Within every pass level is `PASS`; a long-sentence share over
  :data:`LONG_SHARE_FAIL` is `FAIL`; anything else outside a pass level is `PARTIAL`. Fewer than
  :data:`MIN_SENTENCES` sentences, or prose that is not English, is ``UNKNOWN``: the rules are for English.

Deliberate limit, recorded rather than hidden: ignore matching is the documented subset in
``audit.ignore`` (anchoring and ``**`` approximated), and an empty `docs/` directory is only visible
through the filesystem, so DOC-01 consults the target directly for that one case.
"""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.ignore import decide
from audit.rules.checks._common import directory_decision, is_sanctioned_member, scoped_rules, tracked_in_scope
from audit.scan import Inventory
from audit.target import Target
from audit.rules.checks import _prose
from audit.rules.payloads import Counter, Payload

STYLE_GUIDE = "docs/STYLE_GUIDE.md"

#: Scratch directories the documentation contract keeps off-limits; both spellings are seen in the wild.
_SCRATCH_ROOTS: tuple[str, ...] = ("artefacts", "artifacts")

#: The two ADR locations the framework's own docs use.
_ADR_DIRS: tuple[str, ...] = ("docs/architecture/adrs", "docs/adr")

_ADR_FILE_RE = re.compile(r"^\d{3,4}-[A-Za-z0-9._-]+\.md$")


def _outcome(
    spec, verdict: Verdict, summary: str = "", findings: list[Finding] | None = None, data: Payload | None = None
) -> CheckOutcome:
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=summary,
        data=data,
        findings=findings or [],
    )


def _instruction_text(inventory: Inventory) -> tuple[str, str]:
    """The entry instruction file and its text: canonical first, then the CLAUDE.md fallback."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = inventory.read(name)
        if text:
            return name, text
    return "", ""


def _has_exact(inventory: Inventory, rel: str) -> bool:
    """Exact path membership: unlike ``Inventory.has``, never a suffix match at any depth."""
    return any(f.rel == rel for f in inventory.files)


def _inventory_scratch(inventory: Inventory) -> list[str]:
    return sorted(f.rel for f in inventory.files if f.rel.split("/", 1)[0] in _SCRATCH_ROOTS)


# ===========================================================================
# DOC-01 — docs/ exists with markdown
# ===========================================================================


def check_doc01(*, spec, target: Target, inventory, stack, components, session) -> CheckOutcome:
    markdown = sorted(
        f.rel for f in inventory.files if f.rel.startswith("docs/") and f.rel.lower().endswith((".md", ".markdown"))
    )
    if markdown:
        return _outcome(spec, Verdict.PASS, f"{len(markdown)} markdown file(s) under docs/")

    if (target.path / "docs").is_dir():
        return _outcome(
            spec,
            Verdict.PARTIAL,
            "docs/ exists but holds no markdown file",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "read the project's documentation", "docs/ exists but contains no markdown file"
                    ),
                    evidence=[Evidence("docs/")],
                    remediation="Add the canonical documentation pages to docs/ — a project overview "
                    "and the style guide at minimum.",
                ),
            ],
        )

    return _outcome(
        spec,
        Verdict.FAIL,
        "no docs/ directory",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement("find the project's documentation", "no docs/ directory exists in the repository"),
                remediation="Create docs/ as the canonical home for permanent knowledge, with "
                "docs/STYLE_GUIDE.md holding the authoring rules.",
            ),
        ],
    )


# ===========================================================================
# DOC-02 — docs/STYLE_GUIDE.md exists and is named
# ===========================================================================


def check_doc02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if not _has_exact(inventory, STYLE_GUIDE):
        return _outcome(
            spec,
            Verdict.FAIL,
            f"{STYLE_GUIDE} is not present",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "find the canonical authoring rules for documentation", f"{STYLE_GUIDE} does not exist"
                    ),
                    remediation="Create docs/STYLE_GUIDE.md and name it from the instruction file so "
                    "writers have one set of authoring rules.",
                ),
            ],
        )

    name, text = _instruction_text(inventory)
    if name and re.search(r"STYLE_GUIDE\.md", text):
        return _outcome(spec, Verdict.PASS, f"{STYLE_GUIDE} present and named in {name}")

    if name:
        why = f"{STYLE_GUIDE} exists but {name} does not name it"
    else:
        why = f"{STYLE_GUIDE} exists but no instruction file names it"
    return _outcome(
        spec,
        Verdict.PARTIAL,
        why,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement("know which authoring rules govern documentation", why),
                evidence=[Evidence(STYLE_GUIDE)],
                remediation=f"Name {STYLE_GUIDE} as canonical from the instruction file (see AGT-03).",
            ),
        ],
    )


# ===========================================================================
# DOC-03 — artefacts/ present and ignored
# ===========================================================================


def check_doc03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    scratch = _inventory_scratch(inventory)
    inventory_roots = {rel.split("/", 1)[0] for rel in scratch}
    fs_roots = {root for root in _SCRATCH_ROOTS if (target.path / root).is_dir()}
    present_roots = sorted(inventory_roots | fs_roots)

    tracked = tracked_in_scope(target, inventory)
    rules = scoped_rules(target, inventory)
    tracked_scratch = sorted(
        rel
        for rel in (tracked or set())
        if rel.split("/", 1)[0] in _SCRATCH_ROOTS and not is_sanctioned_member(rel, rel.split("/", 1)[0], rules)
    )

    if not present_roots and not tracked_scratch:
        return _outcome(spec, Verdict.PASS, "no scratch directory in use")

    if tracked_scratch:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"tracked: {', '.join(tracked_scratch[:8])}",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "treat the scratch directory as transient",
                        f"{len(tracked_scratch)} path(s) under {', '.join(present_roots or ['scratch'])}/"
                        f" are tracked by git",
                    ),
                    evidence=[Evidence(rel) for rel in tracked_scratch[:12]],
                    path=tracked_scratch[0],
                    remediation="Untrack the scratch contents (git rm --cached) — the ignore rule only "
                    "keeps future files out.",
                ),
            ],
        )

    decisions = {root: directory_decision(root, rules) for root in present_roots}
    for root in present_roots:
        if not decisions[root].ignored:
            for rel in scratch:
                inside = decide(rel, rules)
                if rel.startswith(root + "/") and inside.ignored:
                    decisions[root] = inside
                    break
    covered = any(decision.ignored for decision in decisions.values())
    if not covered:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"{', '.join(present_roots)}/ present but not matched by any ignore rule",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "rely on transient scratch staying out of the repository",
                        f"{', '.join(present_roots)}/ exists but no ignore rule covers it",
                    ),
                    evidence=[Evidence(rel) for rel in scratch[:12]],
                    remediation=f"Add `{present_roots[0]}/` to .gitignore so scratch documents cannot "
                    f"be committed and agents do not read them as source of truth.",
                ),
            ],
        )

    if tracked is None:
        return _outcome(
            spec,
            Verdict.UNKNOWN,
            f"ignore rules cover {', '.join(present_roots)}/, but git could not report the tracked set",
        )

    by = sorted({d.rule.source for d in decisions.values() if d.ignored and d.rule is not None})
    via = f" by {', '.join(by)}" if by else ""
    return _outcome(spec, Verdict.PASS, f"{', '.join(present_roots)}/ present, ignored{via}, and untracked")


# ===========================================================================
# DOC-04 — ADR directory and index
# ===========================================================================


def _adr_dir(inventory: Inventory) -> str | None:
    for directory in _ADR_DIRS:
        if any(f.rel.startswith(directory + "/") for f in inventory.files):
            return directory
    return None


#: ``0000-template.md`` is the blank a new ADR is copied from, not a decision.
_ADR_TEMPLATE_RE = re.compile(r"^\d{3,4}-(?:adr-)?template[._-]", re.IGNORECASE)


def _adr_entries(inventory: Inventory, directory: str) -> list[str]:
    return sorted(
        f.rel
        for f in inventory.files
        if f.rel.startswith(directory + "/")
        and _ADR_FILE_RE.match(f.rel.rsplit("/", 1)[-1])
        and not _ADR_TEMPLATE_RE.match(f.rel.rsplit("/", 1)[-1])
    )


#: A status line or field that retires the record: `Status: Superseded`, `* **Status:** Deprecated`,
#: `| Status | Rejected |` or front matter `status: superseded by ADR-0005`.
_TOMBSTONE_STATUS_RE = re.compile(
    r"^[ \t>*_|#-]*status[ \t*_:|-]*(superseded|deprecated|rejected|obsolete)\b", re.IGNORECASE | re.MULTILINE
)
#: A line that opens by pointing at the record that replaced this one.
_TOMBSTONE_POINTER_RE = re.compile(
    r"^[ \t>*_-]*(superseded\s+by|replaced\s+by|deprecated\s+(by|in\s+favou?r\s+of))\b",
    re.IGNORECASE | re.MULTILINE,
)
#: The MADR form: a `## Status` heading whose first line of text retires the record.
_STATUS_SECTION_RE = re.compile(
    r"^#{1,6}\s*status\s*\n(?:[ \t]*\n)*[ \t>*_-]*(superseded|deprecated|rejected|obsolete)\b",
    re.IGNORECASE | re.MULTILINE,
)


def _adr_tombstone(text: str) -> int | None:
    """The 1-based line that marks this ADR as retired, or ``None`` for a current record.

    Only a status line or field, a `## Status` section, or a line that opens with "superseded by",
    "replaced by" or "deprecated by / in favour of" counts. A word like "superseded" inside a sentence or a
    table of alternatives does not, so an ADR may still discuss a rejected option.
    """
    hits = [
        m.start() for rx in (_TOMBSTONE_STATUS_RE, _TOMBSTONE_POINTER_RE, _STATUS_SECTION_RE) for m in rx.finditer(text)
    ]
    if not hits:
        return None
    return text.count("\n", 0, min(hits)) + 1


def _adr_index(inventory: Inventory, directory: str) -> str | None:
    """A README/index beside the ADRs, falling back to the parent directory's README."""
    for candidate in (f"{directory}/README.md", f"{directory}/index.md", f"{directory}/_index.md"):
        if _has_exact(inventory, candidate):
            return candidate
    parent = directory.rsplit("/", 1)[0]
    for candidate in (f"{parent}/README.md", f"{parent}/index.md"):
        if _has_exact(inventory, candidate):
            return candidate
    return None


def check_doc04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    directory = _adr_dir(inventory)
    if directory is None:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no ADR directory",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "find the decisions of record", "no ADR directory (docs/architecture/adrs/ or docs/adr/) exists"
                    ),
                    remediation="Add docs/architecture/adrs/ with NNNN-short-title.md files and a "
                    "README index that lists them.",
                ),
            ],
        )

    entries = _adr_entries(inventory, directory)
    if not entries:
        return _outcome(spec, Verdict.PARTIAL, f"{directory}/ exists but holds no numbered ADR")

    index = _adr_index(inventory, directory)
    findings: list[Finding] = []
    summaries: list[str] = []

    if index is None:
        summaries.append(f"{len(entries)} ADR(s) present but no index file")
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "discover the decisions of record from one page",
                    f"{directory}/ holds {len(entries)} ADR(s) but no index lists them",
                ),
                evidence=[Evidence(rel) for rel in entries[:12]],
                remediation="Add a README (or index) beside the ADRs, or list them from the architecture README.",
            )
        )
    else:
        text = inventory.read(index) or ""
        listed = [
            rel
            for rel in entries
            if rel.rsplit("/", 1)[-1] in text or re.search(rf"\b{rel.rsplit('/', 1)[-1][:4]}\b", text)
        ]
        if len(listed) < len(entries):
            summaries.append(f"{len(listed)}/{len(entries)} ADR(s) listed in {index}")
            findings.append(
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "find every decision of record",
                        f"{index} lists {len(listed)} of {len(entries)} ADRs in {directory}/",
                    ),
                    evidence=[Evidence(index)],
                    remediation="Add a row to the ADR index for each entry, in the same change set that adds the ADR.",
                )
            )

    tombstones = [(rel, line) for rel in entries if (line := _adr_tombstone(inventory.read(rel) or "")) is not None]
    if tombstones:
        summaries.append(f"{len(tombstones)} ADR(s) marked superseded, deprecated or rejected")
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "trust that every ADR it loads is a current decision",
                    f"{len(tombstones)} ADR(s) in {directory}/ are marked superseded, deprecated or rejected, "
                    "and an agent can apply them as current rules",
                ),
                evidence=[Evidence(rel, line, note="retired record") for rel, line in tombstones[:12]],
                remediation="Delete each retired ADR, with its index row and every reference to it; git keeps its "
                "history. When a decision changed, overwrite the current ADR in place and list the old choice under "
                "Alternatives Considered.",
            )
        )

    if findings:
        return _outcome(spec, Verdict.PARTIAL, "; ".join(summaries), findings)
    return _outcome(spec, Verdict.PASS, f"{len(entries)} ADR(s) indexed in {index}")


# ===========================================================================
# DOC-05 — docs are readable
# ===========================================================================

#: Pass levels and the FAIL level, documented in the check catalogue (02-check-catalogue.md) and the rubric.
LONG_SHARE_PASS = 0.10
LONG_SHARE_FAIL = 0.25
VAGUE_PER_1000_PASS = 1.0
#: Below this many sentences there is too little prose to measure.
MIN_SENTENCES = 10
#: Each list of places a finding cites is capped at this many entries.
_CITE = 8


def check_doc05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    pages = sorted(
        f.rel
        for f in inventory.files
        if f.rel.startswith("docs/") and f.rel.lower().endswith((".md", ".markdown")) and f.has_text
    )
    if not pages:
        return _outcome(spec, Verdict.UNKNOWN, "no Markdown page under docs/ to read; DOC-01 owns that finding")

    total = _prose.ProseCounts()
    no_diagram: list[str] = []
    for rel in pages:
        counts, has_mermaid = _prose.measure(rel, inventory.read(rel) or "")
        total.add(counts)
        if _prose.needs_diagram(rel) and not has_mermaid:
            no_diagram.append(rel)

    if total.sentences < MIN_SENTENCES:
        return _outcome(
            spec,
            Verdict.UNKNOWN,
            f"{total.sentences} sentence(s) of prose in {len(pages)} page(s) under docs/; at least {MIN_SENTENCES} "
            "are needed to measure",
        )
    english = _prose.english_share(total)
    if english < _prose.ENGLISH_MIN_SHARE:
        return _outcome(
            spec,
            Verdict.UNKNOWN,
            f"the prose under docs/ does not read as English ({english:.0%} common English words, below "
            f"{_prose.ENGLISH_MIN_SHARE:.0%}); the plain-language rules are for English",
        )

    long_share = total.long_sentences / total.sentences
    vague_rate = 1000 * total.vague_words / total.words if total.words else 0.0
    data = Counter(
        value=total.long_sentences,
        unit="long sentences",
        breakdown={
            "sentences": total.sentences,
            "words": total.words,
            "long_sentences": total.long_sentences,
            "vague_words": total.vague_words,
            "pages": len(pages),
            "pages_without_diagram": len(no_diagram),
        },
    )
    measured = (
        f"{total.long_sentences}/{total.sentences} sentences over the limit ({long_share:.1%}), "
        f"{total.vague_words} vague word(s) ({vague_rate:.2f} per 1,000 words), "
        f"{len(no_diagram)} explanation or tutorial page(s) without a diagram, in {len(pages)} page(s)"
    )

    gaps: list[str] = []
    evidence: list[Evidence] = []
    if long_share > LONG_SHARE_PASS:
        gaps.append(f"{long_share:.1%} of sentences are over 25 words (pass: at most {LONG_SHARE_PASS:.0%})")
        evidence += [Evidence(rel, line=line, note="long sentence") for rel, line in total.long_at[:_CITE]]
    if vague_rate > VAGUE_PER_1000_PASS:
        gaps.append(f"{vague_rate:.2f} vague words per 1,000 words (pass: at most {VAGUE_PER_1000_PASS:g})")
        evidence += [Evidence(rel, line=line, note=f"vague: {word}") for rel, line, word in total.vague_at[:_CITE]]
    if no_diagram:
        gaps.append(f"{len(no_diagram)} explanation or tutorial page(s) have no Mermaid diagram")
        evidence += [Evidence(rel, note="no diagram") for rel in no_diagram[:_CITE]]

    if not gaps:
        return _outcome(spec, Verdict.PASS, measured, data=data)

    verdict = Verdict.FAIL if long_share > LONG_SHARE_FAIL else Verdict.PARTIAL
    why = "; ".join(gaps)
    return _outcome(
        spec,
        verdict,
        measured,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=verdict,
                statement=statement("rely on the documentation reading clearly to a new engineer", why),
                evidence=evidence,
                remediation="Rewrite the worst pages first: split sentences over 25 words, name the real item "
                "instead of a vague word, and add a Mermaid diagram to each explanation or tutorial page. Put the "
                "rules in docs/STYLE_GUIDE.md, and add a prose check with a baseline that only goes down.",
            ),
        ],
        data=data,
    )


IMPLEMENTATIONS = {
    "DOC-01": check_doc01,
    "DOC-02": check_doc02,
    "DOC-03": check_doc03,
    "DOC-04": check_doc04,
    "DOC-05": check_doc05,
}
