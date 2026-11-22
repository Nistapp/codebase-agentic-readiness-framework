# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""DOC-05: Docs are readable."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks import _prose
from audit.rules.payloads import Counter
from audit.rules.checks.doc._shared import _outcome

SPEC = declare("DOC-05", "Docs are readable", "B", Severity.COSMETIC)


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
