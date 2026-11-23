# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Create every file a new engine check needs, as stubs, and print what a person must still write.

    new_check.py --id PACK-NN --title "..." [--date YYYY-MM-DD]   (``make new-check ID=PACK-NN TITLE="..."``)

It writes, in this checkout:

- the check module ``audit/engine/audit/rules/checks/<family>/<pack>_NN.py``, with its ``SPEC``, a check function
  that reports ``UNKNOWN`` and an empty ``reads()``, wired into the family's ``SPECS`` and ``IMPLEMENTATIONS``;
- a fixture folder ``audit/engine/tests/fixtures/<pack>-NN-stub``, a copy of ``governed-minimal``, and its row in the
  family's fixture matrix table (``audit/engine/tests/packs/<family>/matrix.py``), expecting ``FAIL``;
- a rubric section stub at the end of the family's last file in ``audit/checks/``;
- the check's entry in ``audit/catalogue-overlay.json``, and ``audit/catalogue.json`` regenerated from it;
- a row stub at the top of the ruleset changelog, ``audit/engine/docs/reference/changelog.md``.

Every stub carries the marker :data:`MARKER` (the overlay entry names the playbook :data:`STUB_PLAYBOOK`), so
:func:`stubs_left` and the test that calls it name each file a person has not finished. The fixture matrix test
fails too, since the stub check reports ``UNKNOWN`` where the row expects ``FAIL``, and the catalogue test fails
until the requirement and the traceability row exist.

It refuses, and writes nothing, when the ID is malformed or taken, when its number is not above every number its
family uses (agent-only checks included), when the family has no engine package, and when the family is still one
module (a ``<family>.py`` file; no family is today): add such a check by hand, as the engine page ``02-check-catalogue.md``
§ 15 says. It never bumps ``__ruleset_revision__``. Exit 1 for bad input, 2 for a refusal, 0 when the stubs are
written. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
MARKER = "NEW-CHECK-STUB"
STUB_PLAYBOOK = "new-check-stub"

CHECKS_PKG = Path("audit/engine/audit/rules/checks")
FIXTURES = Path("audit/engine/tests/fixtures")
PACK_TESTS = Path("audit/engine/tests/packs")
RUBRICS = Path("audit/checks")
OVERLAY = Path("audit/catalogue-overlay.json")
CATALOGUE = Path("audit/catalogue.json")
CHANGELOG = Path("audit/engine/docs/reference/changelog.md")
TEMPLATE_FIXTURE = "governed-minimal"

CHECK_ID = re.compile(r"^([A-Z]{2,5})-([0-9]{2})$")
#: A family whose engine package or test package name is not its code in lower case.
ENGINE_PACKAGE = {"EXEC": "execution"}
TEST_PACKAGE = {"DOC": "doc_nav", "NAV": "doc_nav"}
#: The files and folders :func:`stubs_left` reads, relative to the root. In the fixtures it reads file names only.
STUB_PLACES = (CHECKS_PKG, FIXTURES, PACK_TESTS, RUBRICS, OVERLAY, CHANGELOG)


class UsageError(Exception):
    """The command line is malformed (exit 1)."""


class Refused(Exception):
    """The check cannot be scaffolded here; nothing was written (exit 2)."""


@dataclass(frozen=True)
class NewCheck:
    check_id: str
    title: str
    family: str
    number: str

    @property
    def module(self) -> str:
        return f"{self.family.lower()}_{self.number}"

    @property
    def function(self) -> str:
        return f"check_{self.family.lower()}{self.number}"

    @property
    def fixture(self) -> str:
        return f"{self.family.lower()}-{self.number}-stub"


def parse_id(check_id: str, title: str) -> NewCheck:
    match = CHECK_ID.match(check_id)
    if not match:
        raise UsageError(f"--id must be a family code, a hyphen and two digits (PACK-NN), not {check_id!r}")
    if not title.strip() or "\n" in title or '"' in title or "|" in title:
        raise UsageError("--title must be one line, without a double quote or a pipe")
    return NewCheck(check_id, title.strip(), match.group(1), match.group(2))


def _append_item(text: str, opener: str, closer: str, line: str, where: Path) -> str:
    """``text`` with ``line`` added as the last item of the block from ``opener`` to the line ``closer``."""
    if text.count(opener) != 1:
        raise Refused(f"{where}: expected one '{opener.strip()}', found {text.count(opener)}")
    start = text.index(opener) + len(opener)
    end = text.find(f"\n{closer}\n", start - 1)
    if end < 0:
        raise Refused(f"{where}: no line '{closer}' after '{opener.strip()}'")
    return text[: end + 1] + line + text[end + 1 :]


def _module_text(new: NewCheck) -> str:
    return f'''# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""{new.check_id}: {new.title}."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare

# {MARKER}: set the tier (A, B or C), the severity and the falsifiable evidence rule (rule=...).
SPEC = declare("{new.check_id}", "{new.title}", "B", Severity.DEGRADER)


def {new.function}(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    # {MARKER}: write the check; it reports UNKNOWN until then.
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        Verdict.UNKNOWN,
        spec.status,
        summary="{MARKER}: this check is not written yet",
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import Reads, What

    # {MARKER}: declare the places, the text and the binding (02-check-catalogue.md, § 15, step 6).
    return Reads(where=(), what=What("exists"), binding="file", note="{MARKER}: not declared yet")
'''


def _rubric_text(new: NewCheck) -> str:
    return f"""
## {new.check_id} — {new.title}

Why it matters   {MARKER}: one sentence, with a link to the framework section this check anchors.
Severity         DEGRADER
Engine           `{new.check_id}`. {MARKER}: what it reads, when its verdict can be wrong, how to verify it.
Method           automated
Look for         {MARKER}: the evidence to gather, and where to look first.
Rubric           PASS: {MARKER}.
                 PARTIAL: {MARKER}.
                 FAIL: {MARKER}.
                 NOT_APPLICABLE: {MARKER}.
                 UNKNOWN when: {MARKER}.
Evidence to cite {MARKER}: exactly what must appear in evidence[].
Absence proof    {MARKER}: the searches[] entries a FAIL must record.
Remediation      {MARKER}: the playbook id(s) the overlay names.
Pitfalls         {MARKER}: known false positives and false negatives.
"""


def _fixture_note(new: NewCheck) -> str:
    return (
        f"# {MARKER}\n\n"
        f"This fixture is a copy of `{TEMPLATE_FIXTURE}`. Change it so that it fails exactly `{new.check_id}` and "
        "nothing else.\nThen give the folder a name that says its defect, rename its matrix row, and delete this "
        "file.\n"
    )


def _rubric_file(root: Path, family: str) -> Path:
    heading = re.compile(rf"^# .+ \(`{family}`\)", re.MULTILINE)
    files = [p for p in sorted((root / RUBRICS).glob("[0-9][0-9]-*.md")) if heading.search(p.read_text("utf-8"))]
    if not files:
        raise Refused(f"no file in {RUBRICS} has the heading '# <name> (`{family}`)'")
    return files[-1]


def _used_numbers(root: Path, family: str) -> list[int]:
    catalogue: dict[str, Any] = json.loads((root / CATALOGUE).read_text(encoding="utf-8"))
    return [int(c["id"].split("-")[1]) for c in catalogue["checks"] if c["family"] == family]


def plan(root: Path, new: NewCheck, today: str) -> dict[Path, str]:
    """Every file to write, with its new text, or :class:`Refused`. Reads only; writes nothing."""
    package = root / CHECKS_PKG / ENGINE_PACKAGE.get(new.family, new.family.lower())
    if (root / CHECKS_PKG / f"{new.family.lower()}.py").is_file():
        raise Refused(
            f"the {new.family} family is still one module ({CHECKS_PKG / (new.family.lower() + '.py')}); "
            "add the check by hand (02-check-catalogue.md, § 15) or split the family into a package first"
        )
    if not (package / "__init__.py").is_file():
        raise Refused(f"the {new.family} family has no engine package at {package.relative_to(root)}")
    used = _used_numbers(root, new.family)
    if not used:
        raise Refused(f"the catalogue has no {new.family} check; a new family needs more than this scaffold")
    if int(new.number) in used:
        raise Refused(f"{new.check_id} is taken in {CATALOGUE}")
    if int(new.number) <= max(used):
        raise Refused(f"{new.check_id}: take the next free number in {new.family}, above {max(used):02d}")
    overlay: dict[str, Any] = json.loads((root / OVERLAY).read_text(encoding="utf-8"))
    if new.check_id in overlay["checks"]:
        raise Refused(f"{new.check_id} already has an entry in {OVERLAY}")
    module = package / f"{new.module}.py"
    fixture = root / FIXTURES / new.fixture
    matrix = root / PACK_TESTS / TEST_PACKAGE.get(new.family, new.family.lower()) / "matrix.py"
    for path in (module, fixture):
        if path.exists():
            raise Refused(f"{path.relative_to(root)} exists")
    if not matrix.is_file():
        raise Refused(f"no fixture matrix table at {matrix.relative_to(root)}")

    files: dict[Path, str] = {module: _module_text(new)}

    init = package / "__init__.py"
    text = init.read_text(encoding="utf-8")
    anchor = "from audit.rules.spec import CheckSpec\n"
    if text.count(anchor) != 1:
        raise Refused(f"{init.relative_to(root)}: expected one '{anchor.strip()}'")
    dotted = f"audit.rules.checks.{package.name}"
    text = text.replace(
        anchor,
        f"from {dotted} import {new.module}\nfrom {dotted}.{new.module} import {new.function} as {new.function}\n"
        + anchor,
    )
    text = _append_item(text, "SPECS: tuple[CheckSpec, ...] = (\n", ")", f"    {new.module}.SPEC,\n", init)
    files[init] = _append_item(text, "IMPLEMENTATIONS = {\n", "}", f'    "{new.check_id}": {new.function},\n', init)

    row = f'    "{new.fixture}": {{"{new.check_id}": "FAIL"}},  # {MARKER}: the fixture fails exactly this check\n'
    opener = "ROWS: dict[str, dict[str, str]] = {\n"
    files[matrix] = _append_item(matrix.read_text(encoding="utf-8"), opener, "}", row, matrix)

    rubric = _rubric_file(root, new.family)
    files[rubric] = rubric.read_text(encoding="utf-8").rstrip("\n") + "\n" + _rubric_text(new)

    entries: dict[str, Any] = {}
    family_entries = [check_id for check_id in overlay["checks"] if check_id.split("-")[0] == new.family]
    for check_id, entry in overlay["checks"].items():
        entries[check_id] = entry
        if check_id == family_entries[-1]:
            entries[new.check_id] = {"req_ids": [], "playbooks": [STUB_PLAYBOOK]}
    overlay["checks"] = entries
    files[root / OVERLAY] = json.dumps(overlay, indent=2, ensure_ascii=False) + "\n"

    changelog = root / CHANGELOG
    log = changelog.read_text(encoding="utf-8")
    header = "| Revision | Date | Scoreable checks | What it is |\n|---|---|---|---|\n"
    if log.count(header) != 1:
        raise Refused(f"{CHANGELOG}: expected one revision table")
    stub_row = (
        f"| `{MARKER}` | {today} | {MARKER} | `{new.check_id}` ({new.title}) added. {MARKER}: take the next "
        "ruleset revision, set it here and in `__ruleset_revision__`, and say which verdicts move |\n"
    )
    files[changelog] = log.replace(header, header + stub_row)
    return files


def write(root: Path, new: NewCheck, files: dict[Path, str]) -> None:
    shutil.copytree(root / FIXTURES / TEMPLATE_FIXTURE, root / FIXTURES / new.fixture)
    (root / FIXTURES / new.fixture / f"{MARKER}.md").write_text(_fixture_note(new), encoding="utf-8")
    for path, text in files.items():
        path.write_text(text, encoding="utf-8")


def stubs_left(root: Path) -> list[str]:
    """Each file under :data:`STUB_PLACES` that still holds a scaffold stub, as a path from ``root``."""
    found: list[str] = []
    for place in STUB_PLACES:
        path = root / place
        candidates = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
        for candidate in candidates:
            if "__pycache__" in candidate.parts:
                continue
            if candidate.name == f"{MARKER}.md":
                found.append(candidate.relative_to(root).as_posix())
                continue
            if place == FIXTURES:  # a fixture is data, and may hold a secret-shaped file: only its names are read
                continue
            try:
                text = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if MARKER in text or f'"{STUB_PLAYBOOK}"' in text:
                found.append(candidate.relative_to(root).as_posix())
    return found


def todo(new: NewCheck) -> list[str]:
    return [
        f"Write {new.check_id} in {CHECKS_PKG}/{ENGINE_PACKAGE.get(new.family, new.family.lower())}/{new.module}.py: "
        "tier, severity and evidence rule in SPEC, "
        "the check function, and reads().",
        f"Make {FIXTURES}/{new.fixture} fail exactly {new.check_id}, rename it after its defect, rename its matrix "
        f"row, and delete its {MARKER}.md.",
        f"Fill the {new.check_id} section at the end of the family's file in {RUBRICS}/.",
        f"In {OVERLAY}: the req_ids, the playbooks (not {STUB_PLAYBOOK}) and since_ruleset. Then add "
        f"{new.check_id} to the requirement's Checks field (spec/readiness-requirements.md) and to "
        "spec/traceability.md.",
        f"Take the next ruleset revision: the row stub in {CHANGELOG} and __ruleset_revision__.",
        "Add the row to the engine page 02-check-catalogue.md and the failure mode to Why These Checks.",
        "Run make update-catalogue, make update-masters and python3 dev/consistency_map_reads.py --write, "
        "then make check: its tests name each stub left.",
    ]


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--id", required=True, help="the new check's ID, PACK-NN")
    parser.add_argument("--title", required=True, help="the new check's title, one line")
    parser.add_argument("--date", default=None, help="the changelog row's date (default: today)")
    args = parser.parse_args(argv)
    try:
        new = parse_id(args.id, args.title)
        today = args.date or datetime.date.today().isoformat()
        files = plan(root, new, today)
    except UsageError as exc:
        print(f"new_check: {exc}", file=sys.stderr)
        return 1
    except (Refused, OSError, KeyError, ValueError) as exc:
        print(f"new_check: refused, nothing written: {exc}", file=sys.stderr)
        return 2
    write(root, new, files)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_catalogue

    if build_catalogue.main(["--write"], root=root) != 0:
        print(f"new_check: the stubs are written, but {CATALOGUE} could not be regenerated", file=sys.stderr)
        return 2
    print(f"new_check: wrote the stubs of {new.check_id}. Still to write:")
    for number, item in enumerate(todo(new), start=1):
        print(f"  {number}. {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
