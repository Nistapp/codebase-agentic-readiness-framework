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

from audit.rules.checks.doc import doc_01, doc_02, doc_03, doc_04, doc_05
from audit.rules.checks.doc._shared import _outcome as _outcome, _has_exact as _has_exact
from audit.rules.checks.doc.doc_01 import check_doc01 as check_doc01
from audit.rules.checks.doc.doc_02 import (
    STYLE_GUIDE as STYLE_GUIDE,
    _instruction_text as _instruction_text,
    check_doc02 as check_doc02,
)
from audit.rules.checks.doc.doc_03 import (
    _SCRATCH_ROOTS as _SCRATCH_ROOTS,
    _inventory_scratch as _inventory_scratch,
    check_doc03 as check_doc03,
)
from audit.rules.checks.doc.doc_04 import (
    _ADR_DIRS as _ADR_DIRS,
    _ADR_FILE_RE as _ADR_FILE_RE,
    _adr_dir as _adr_dir,
    _ADR_TEMPLATE_RE as _ADR_TEMPLATE_RE,
    _adr_entries as _adr_entries,
    _TOMBSTONE_STATUS_RE as _TOMBSTONE_STATUS_RE,
    _TOMBSTONE_POINTER_RE as _TOMBSTONE_POINTER_RE,
    _STATUS_SECTION_RE as _STATUS_SECTION_RE,
    _adr_tombstone as _adr_tombstone,
    _adr_index as _adr_index,
    check_doc04 as check_doc04,
)
from audit.rules.checks.doc.doc_05 import (
    LONG_SHARE_PASS as LONG_SHARE_PASS,
    LONG_SHARE_FAIL as LONG_SHARE_FAIL,
    VAGUE_PER_1000_PASS as VAGUE_PER_1000_PASS,
    MIN_SENTENCES as MIN_SENTENCES,
    _CITE as _CITE,
    check_doc05 as check_doc05,
)
from audit.rules.spec import CheckSpec

#: The DOC checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    doc_01.SPEC,
    doc_02.SPEC,
    doc_03.SPEC,
    doc_04.SPEC,
    doc_05.SPEC,
)

IMPLEMENTATIONS = {
    "DOC-01": check_doc01,
    "DOC-02": check_doc02,
    "DOC-03": check_doc03,
    "DOC-04": check_doc04,
    "DOC-05": check_doc05,
}
