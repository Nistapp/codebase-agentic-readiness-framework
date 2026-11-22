# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`NAV` pack — navigation.

Anchor: `docs/framework/phased-approach.md` § Key Deliverables.

Implemented here: `NAV-01` … `NAV-05`. The first three are scored; `NAV-04` and `NAV-05` are
informational (`scored=False` in the registry) and are reported but earn no credit.

* **NAV-01** — at least one non-root component declared by a build manifest is `PASS`. A single-root
  repository that still declares a manifest is `PASS` (the boundary exists, it is just the root).
  Candidate components (undeclared multi-app layouts) are `PARTIAL`, because the layout exists but
  nothing declares it. Nothing at all is ``UNKNOWN``, not `FAIL`: an unrecognised ecosystem is not
  proof that boundaries are absent.
* **NAV-02** — a language-appropriate entry point (npm `main`/`bin`/`exports`, a `__main__.py`, a
  conventional `main.py`/`app.py`/`manage.py` or a Python manifest script entry, JVM `main`, a `@SpringBootApplication`/`@QuarkusMain` annotation or a
  build dependency on `io.quarkus` (Quarkus apps conventionally have no literal `main` — the
  Quarkus runtime itself is the entry point), Go/Rust `func main`, a `bin/` script) is `PASS`. A
  recognised ecosystem with none is `FAIL`; no recognised ecosystem is ``UNKNOWN``. An
  `if __name__ == "__main__"` guard alone does not count: helper scripts and dev tools carry one too.
* **NAV-03** — a census, never a verdict on heuristics: oversized files, catch-all directories,
  checked-in binaries and minified assets. All-zero is `PASS`; any count is `PARTIAL`, with the
  counts and the documented thresholds in `detail`. It never `FAIL`s. A lockfile, matched by exact
  base name (`audit.stack.LOCKFILE_NAMES`), is left out of the size count, and `detail` names it.
* **NAV-04** — informational: `docs/architecture/`, an ADR directory, or a diagram exists.
* **NAV-05** — informational docstring census over public symbols. The method is stated in `detail`;
  when "public" cannot be defined for the files present the check is ``UNKNOWN``.

Deliberate limits, recorded rather than hidden. NAV-02 reads a fixed, documented set of entry-point
signals per ecosystem rather than resolving one semantically. NAV-05 is a best-effort static
approximation of "public"; it never executes or reflects. Python is parsed with the stdlib `ast`:
module-level functions and classes plus the methods of public classes (nested public classes too, never a
function inside a function), names not starting with an underscore (so no dunder method), and documented
means `ast.get_docstring` finds one. A test file (a `tests` or `test` directory in its path, or a
`test_*.py` or `*_test.py` name) is left out. A file `ast` cannot parse falls back to column-0
`def`/`class` lines with a docstring on the next code line. TypeScript/JavaScript counts exported
declarations only, preceded by a `/** */` block; class members are not counted.
"""

from __future__ import annotations

from audit.rules.checks.nav import nav_01, nav_02, nav_03, nav_04, nav_05
from audit.rules.checks.nav._shared import _outcome as _outcome, _unknown as _unknown
from audit.rules.checks.nav.nav_01 import check_nav01 as check_nav01
from audit.rules.checks.nav.nav_02 import (
    _has_exact as _has_exact,
    _NODE_INDEX_FILES as _NODE_INDEX_FILES,
    _ENTRY_NAMES as _ENTRY_NAMES,
    _node_entry as _node_entry,
    _python_entry as _python_entry,
    _grep_sources as _grep_sources,
    _jvm_entry as _jvm_entry,
    _go_entry as _go_entry,
    _rust_entry as _rust_entry,
    _DETECTORS as _DETECTORS,
    _entry_points as _entry_points,
    check_nav02 as check_nav02,
)
from audit.rules.checks.nav.nav_03 import (
    LARGE_FILE_BYTES as LARGE_FILE_BYTES,
    CATCH_ALL_FILES as CATCH_ALL_FILES,
    check_nav03 as check_nav03,
)
from audit.rules.checks.nav.nav_04 import _DIAGRAM_SUFFIXES as _DIAGRAM_SUFFIXES, check_nav04 as check_nav04
from audit.rules.checks.nav.nav_05 import (
    _PY_PUBLIC_RE as _PY_PUBLIC_RE,
    _TS_EXPORT_RE as _TS_EXPORT_RE,
    _TS_SUFFIXES as _TS_SUFFIXES,
    _PY_TEST_DIRS as _PY_TEST_DIRS,
    _language as _language,
    _next_code_line as _next_code_line,
    _python_test_file as _python_test_file,
    _python_line_census as _python_line_census,
    _python_ast_census as _python_ast_census,
    _python_census as _python_census,
    _ts_census as _ts_census,
    check_nav05 as check_nav05,
)
from audit.rules.spec import CheckSpec

#: The NAV checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    nav_01.SPEC,
    nav_02.SPEC,
    nav_03.SPEC,
    nav_04.SPEC,
    nav_05.SPEC,
)

IMPLEMENTATIONS = {
    "NAV-01": check_nav01,
    "NAV-02": check_nav02,
    "NAV-03": check_nav03,
    "NAV-04": check_nav04,
    "NAV-05": check_nav05,
}
