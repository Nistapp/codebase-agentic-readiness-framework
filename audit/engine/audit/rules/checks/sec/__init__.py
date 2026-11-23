# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`SEC` pack — security hygiene.

Anchor: `docs/framework/phased-approach.md` § Key Deliverables.

Implemented here: `SEC-01` … `SEC-03`.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **SEC-01** — the tracked `.env` half reads `audit.ignore.tracked_files`; the ignore half reads the
  ignore files directly (the scoped matcher, `audit.rules.checks._common.scoped_rules`), so a tracked `.env`
  that is *also* git-ignored is still seen. A tracked ``.env``/``.env.*`` (excluding committed templates such as
  ``.env.example``) is the blocker. So is a tracked file an ignore rule also matches
  (`audit.rules.checks._common.tracked_and_ignored`) with an env-like name: ``.env*``, ``*.env`` or ``env.*``,
  templates excepted (``config/prod.env`` force-added past ``*.env``). No tracked `.env` but ignore rules that miss the shape is
  `PARTIAL`. When git cannot report the tracked set the blocker half is `UNKNOWN` — never `PASS`,
  and the tracked set is never inferred from the walk.
* **SEC-02** — a pattern scan of **tracked text files** for the credential shapes in
  :data:`audit.probes.REDACTION_PATTERNS`. Findings carry path and line only; the matched value is
  never placed in the report (AGENTS.md §9). With no tracked set the scan falls back to the whole
  inventory and says so in `detail`. Committed templates (``*.example``/``*.sample``/``*.template``)
  and lines whose value is an obvious placeholder are skipped by a deterministic rule, so a
  documentation file that quotes the shape does not fail the check. A keyword (``token``, ``password``,
  ``api_key``) counts only when what it is assigned is a literal: a quoted string that is not a reference
  to the environment or a secret store (``os.environ/NAME``, ``${NAME}``, ``{{ secrets.NAME }}``), or,
  outside source code, a single plain unquoted token. In source code an unquoted value is a name or an
  expression (``token = match.group(1) or x``), never a literal. The keyword may end a compound name
  (``DB_PASSWORD``); a properties or env-style file counts a short value (6 characters, not 12); a token that
  names itself a sentinel (``Bearer sanity.check.invalid``) and a badge URL's public token do not count.
* **SEC-03** — ignore rules must cover a documented set of key/certificate/credential shapes
  (:data:`_SECRET_SHAPES`). Every required shape covered is `PASS`; some is `PARTIAL`; none is
  `FAIL`. The covered labels are stated in `detail`. A tracked file an ignore rule also matches whose name is
  one of the non-dotenv shapes (``server.key`` force-added past ``*.key``) is a `FAIL` with its own finding;
  when git cannot report the tracked set, that half is skipped and the coverage half stands alone.

Deliberate limits, recorded rather than hidden. Ignore matching is the documented subset in
``audit.ignore`` (ADR-0009), so a shape is only credited when one of the probes actually matches. Content
reads are bounded by ``audit.scan``; a tracked file that is binary, oversized, or under a hard-excluded
directory is not scanned, and SEC-02 says which set it scanned. A tracked file an ignore rule covers stays in
the walk, so SEC-02 scans it.
"""

from __future__ import annotations

from audit.rules.checks.sec import sec_01, sec_02, sec_03
from audit.rules.checks.sec._shared import (
    _ENV_TEMPLATE_BASENAMES as _ENV_TEMPLATE_BASENAMES,
    _MAX_SECRET_FILES as _MAX_SECRET_FILES,
    _outcome as _outcome,
    _is_template_file as _is_template_file,
    _path_covered as _path_covered,
    _nested_ignored as _nested_ignored,
    _leading_slash_rule as _leading_slash_rule,
    _root_only as _root_only,
    _shape_coverage as _shape_coverage,
    _shapes_payload as _shapes_payload,
    _gaps as _gaps,
)
from audit.rules.checks.sec.sec_01 import (
    _ENV_SHAPE_PROBES as _ENV_SHAPE_PROBES,
    _ENV_SHAPE_SUGGEST as _ENV_SHAPE_SUGGEST,
    _unknown as _unknown,
    _is_env_name as _is_env_name,
    _is_env_like_name as _is_env_like_name,
    check_sec01 as check_sec01,
)
from audit.rules.checks.sec.sec_02 import (
    _PLACEHOLDER_RE as _PLACEHOLDER_RE,
    _REDACTION_KEYWORD as _REDACTION_KEYWORD,
    _SHAPE_PATTERNS as _SHAPE_PATTERNS,
    _KEYWORD_PATTERN as _KEYWORD_PATTERN,
    _SENTINEL_RE as _SENTINEL_RE,
    _BADGE_URL_RE as _BADGE_URL_RE,
    _BEARER_SHAPE as _BEARER_SHAPE,
    _BEARER_RE as _BEARER_RE,
    _SHORT_VALUE_SUFFIXES as _SHORT_VALUE_SUFFIXES,
    _MIN_SECRET_LEN as _MIN_SECRET_LEN,
    _MIN_SECRET_LEN_CONFIG as _MIN_SECRET_LEN_CONFIG,
    _ASSIGNED_VALUE_RE as _ASSIGNED_VALUE_RE,
    _SECRET_VALUE_CHARSET_RE as _SECRET_VALUE_CHARSET_RE,
    _STRING_PREFIX_RE as _STRING_PREFIX_RE,
    _REFERENCE_RE as _REFERENCE_RE,
    _CODE_SUFFIXES as _CODE_SUFFIXES,
    _looks_secret_value as _looks_secret_value,
    _is_short_value_file as _is_short_value_file,
    _shape_hit as _shape_hit,
    _line_is_secret as _line_is_secret,
    _scan_secrets_allowlisted as _scan_secrets_allowlisted,
    _scan_secrets as _scan_secrets,
    _by_file as _by_file,
    check_sec02 as check_sec02,
)
from audit.rules.checks.sec.sec_03 import (
    _SECRET_SHAPES as _SECRET_SHAPES,
    _SECRET_SHAPE_SUGGEST as _SECRET_SHAPE_SUGGEST,
    _KEY_MATERIAL_RULES as _KEY_MATERIAL_RULES,
    _key_material as _key_material,
    check_sec03 as check_sec03,
    _committed_key_material as _committed_key_material,
)
from audit.rules.spec import CheckSpec

#: The SEC checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    sec_01.SPEC,
    sec_02.SPEC,
    sec_03.SPEC,
)

IMPLEMENTATIONS = {
    "SEC-01": check_sec01,
    "SEC-02": check_sec02,
    "SEC-03": check_sec03,
}
