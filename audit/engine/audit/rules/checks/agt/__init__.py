# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`AGT` pack — agent governance.

Implemented here: `AGT-01` (canonical instruction file), `AGT-02` (component coverage),
`AGT-03` (documentation contract), `AGT-04` (definition of done), `AGT-05` (seven verbs named),
`AGT-06` (architectural boundaries), `AGT-07` (prohibitions), `AGT-08` (competing files + reach
matrix), `AGT-09` (branch and release boundary), `AGT-10` (indirection), `AGT-12` (communication rules) and
`AGT-13` (coding conventions). `AGT-11` is judged by an agent and has no engine rule.

`AGT-13` does not read the entry instruction file alone: it finds a conventions file by name at the root or under
`docs/` or `.github/`, and a conventions section in `AGENTS.md` or `CONTRIBUTING.md`. With neither it is `FAIL`,
not `UNKNOWN`: no other check owns that absence.

`AGT-09` also compares the instruction file with the branch rules declared as code
(`_common.declared_branch_rules`, the list `HYG-11` and `TOOL-07` read): a branch a rule protects by its literal
name and that the file does not name is `PARTIAL`. `~DEFAULT_BRANCH`, `~ALL` and glob patterns name no branch, so
they are skipped.

`AGT-05` resolves its verbs through `CMD-01`'s resolver (`_common.resolve_verbs`) so the two checks
can never disagree: it is a `PASS` only when the entry instruction file names every framework verb
**and** those verbs resolve on a runner. Names without resolution is `PARTIAL`; neither is `FAIL`.
With no runner and no named verbs it degrades to `UNKNOWN`, deferring to `AGT-01` and `CMD-01`.

The content-contract checks (`03`, `04`, `06`, `07`, `09`, `12`) read the entry instruction file — the
canonical `AGENTS.md`, falling back to `CLAUDE.md` when the canonical file is absent. When no
instruction file exists they report `UNKNOWN`, not `FAIL`: the absence is already `AGT-01`'s finding
and piling on adds noise without adding information.

Anchor: Phased-Approach.md § Phase 1: Agentic Bootstrap.
"""

from __future__ import annotations

from audit.rules.checks.agt import (
    agt_01,
    agt_02,
    agt_03,
    agt_04,
    agt_05,
    agt_06,
    agt_07,
    agt_08,
    agt_09,
    agt_10,
    agt_12,
    agt_13,
)
from audit.rules.checks.agt._shared import (
    _instruction_basenames as _instruction_basenames,
    INSTRUCTION_BASENAMES as INSTRUCTION_BASENAMES,
    _instruction_fixed_paths as _instruction_fixed_paths,
    INSTRUCTION_FIXED_PATHS as INSTRUCTION_FIXED_PATHS,
    _config_gated_names as _config_gated_names,
    CONFIG_GATED_NAMES as CONFIG_GATED_NAMES,
    is_non_instruction as is_non_instruction,
    instruction_paths as instruction_paths,
    _rule_line_count as _rule_line_count,
    _unknown as _unknown,
    _first_line as _first_line,
    _MD_HEADING_RE as _MD_HEADING_RE,
    _MD_FENCE_RE as _MD_FENCE_RE,
)
from audit.rules.checks.agt.agt_01 import (
    MIN_INSTRUCTION_CHARS as MIN_INSTRUCTION_CHARS,
    STUB_PHRASES as STUB_PHRASES,
    _STUB_WORD_RES as _STUB_WORD_RES,
    _trivial_reason as _trivial_reason,
    check_agt01 as check_agt01,
    _agt01_summary as _agt01_summary,
)
from audit.rules.checks.agt.agt_02 import (
    check_agt02 as check_agt02,
)
from audit.rules.checks.agt.agt_03 import (
    _DOCS_NAME_RE as _DOCS_NAME_RE,
    _STYLE_GUIDE_RE as _STYLE_GUIDE_RE,
    _SCRATCH_DIR_RE as _SCRATCH_DIR_RE,
    check_agt03 as check_agt03,
)
from audit.rules.checks.agt.agt_04 import (
    _CHANGE_SET_RE as _CHANGE_SET_RE,
    _DOD_TRIGGER_RE as _DOD_TRIGGER_RE,
    check_agt04 as check_agt04,
)
from audit.rules.checks.agt.agt_05 import (
    _VERB_SPELLINGS as _VERB_SPELLINGS,
    _mentioned_verbs as _mentioned_verbs,
    _verb_binding_surface as _verb_binding_surface,
    check_agt05 as check_agt05,
)
from audit.rules.checks.agt.agt_06 import (
    _BOUNDARY_CONTEXT_RE as _BOUNDARY_CONTEXT_RE,
    _PATH_TOKEN_RE as _PATH_TOKEN_RE,
    _path_is_real as _path_is_real,
    check_agt06 as check_agt06,
)
from audit.rules.checks.agt.agt_07 import (
    _AGT07_CONCERNS as _AGT07_CONCERNS,
    check_agt07 as check_agt07,
)
from audit.rules.checks.agt.agt_08 import (
    _AGT08_COMPETITORS as _AGT08_COMPETITORS,
    _AGT08_REACH as _AGT08_REACH,
    _AGT08_STATEMENT_RE as _AGT08_STATEMENT_RE,
    _harness_aliases as _harness_aliases,
    stated_harnesses as stated_harnesses,
    _AGENTS_IMPORT_RE as _AGENTS_IMPORT_RE,
    _POINTER_MAX_LINES as _POINTER_MAX_LINES,
    _content_lines as _content_lines,
    imports_agents_md as imports_agents_md,
    is_agents_md_pointer as is_agents_md_pointer,
    _pointer_files as _pointer_files,
    check_agt08 as check_agt08,
)
from audit.rules.checks.agt.agt_09 import (
    _BRANCH_RE as _BRANCH_RE,
    _RELEASE_RE as _RELEASE_RE,
    _names_branch as _names_branch,
    check_agt09 as check_agt09,
)
from audit.rules.checks.agt.agt_10 import (
    _REFERENCE_RE as _REFERENCE_RE,
    _DEFER_RE as _DEFER_RE,
    _configured_targets as _configured_targets,
    _from_root as _from_root,
    check_agt10 as check_agt10,
    _broken_pointer as _broken_pointer,
)
from audit.rules.checks.agt.agt_12 import (
    _COMMUNICATION_HEADING_RE as _COMMUNICATION_HEADING_RE,
    _COMMUNICATION_FILE_RE as _COMMUNICATION_FILE_RE,
    _COMMUNICATION_ELEMENTS as _COMMUNICATION_ELEMENTS,
    _communication_sections as _communication_sections,
    _linked_rules_files as _linked_rules_files,
    check_agt12 as check_agt12,
)
from audit.rules.checks.agt.agt_13 import (
    _CONVENTIONS_FILE_GLOBS as _CONVENTIONS_FILE_GLOBS,
    _CONVENTIONS_FILE_SUFFIXES as _CONVENTIONS_FILE_SUFFIXES,
    _DOCS_STYLE_GUIDE as _DOCS_STYLE_GUIDE,
    _CONVENTIONS_SECTION_FILES as _CONVENTIONS_SECTION_FILES,
    _CONVENTIONS_HEADING_RE as _CONVENTIONS_HEADING_RE,
    _NOT_CODE_HEADING_RE as _NOT_CODE_HEADING_RE,
    _CONVENTIONS_STUB_RE as _CONVENTIONS_STUB_RE,
    _CODE_SPAN_RE as _CODE_SPAN_RE,
    _CONVENTIONS_ITEMS as _CONVENTIONS_ITEMS,
    _conventions_files as _conventions_files,
    _conventions_sections as _conventions_sections,
    _stub_word as _stub_word,
    check_agt13 as check_agt13,
)
from audit.rules.spec import CheckSpec

#: The AGT checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    agt_01.SPEC,
    agt_02.SPEC,
    agt_03.SPEC,
    agt_04.SPEC,
    agt_05.SPEC,
    agt_06.SPEC,
    agt_07.SPEC,
    agt_08.SPEC,
    agt_09.SPEC,
    agt_10.SPEC,
    agt_12.SPEC,
    agt_13.SPEC,
)

IMPLEMENTATIONS = {
    "AGT-01": check_agt01,
    "AGT-02": check_agt02,
    "AGT-03": check_agt03,
    "AGT-04": check_agt04,
    "AGT-05": check_agt05,
    "AGT-06": check_agt06,
    "AGT-07": check_agt07,
    "AGT-08": check_agt08,
    "AGT-09": check_agt09,
    "AGT-10": check_agt10,
    "AGT-12": check_agt12,
    "AGT-13": check_agt13,
}
