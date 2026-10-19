# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Every fixture Makefile parses under the real ``make``, except the one that is meant not to.

R-04 found the engine's own "known good" Makefile fixture unreadable to GNU Make (``format:check:`` is a static
pattern rule), so the PASS it earned was a PASS for a file that no runner could run. A fixture is the engine's idea
of a correct repository; it has to be correct for the runner it names. The project controls these fixtures, so
``make -n -f <fixture>/Makefile check`` is safe: ``-n`` prints the recipes and runs none of them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

#: Fixtures whose Makefile is wrong on purpose, each with the line Make reports.
REFUSED_ON_PURPOSE = {"cmd-01-make-parse-error": "Makefile:4: *** target pattern contains no '%'.  Stop."}

#: What Make says is the same in every language only under the C locale.
ENV = {**os.environ, "LC_ALL": "C", "MAKEFLAGS": "", "MFLAGS": ""}

MAKE = shutil.which("make")


def _normalize_make_quotes(text: str) -> str:
    """GNU Make's own quoting of a name in a message is version-dependent, not content:
    older builds (seen on macOS CI) wrap it ```like this'``, newer ones ``'like this'``. Both
    quote the same word, so a straight apostrophe on both sides is the canonical form compared
    against; everything else about the message is still checked byte for byte.
    """
    return text.replace("`", "'")


def makefile_fixtures() -> list[str]:
    return sorted(p.name for p in support.FIXTURES_DIR.iterdir() if (p / "Makefile").is_file())


def dry_run(name: str) -> subprocess.CompletedProcess:
    fixture = support.fixture(name)
    return subprocess.run(
        [MAKE or "make", "-n", "-f", str(fixture / "Makefile"), "check"],
        cwd=str(fixture),
        env=ENV,
        text=True,
        capture_output=True,
    )


@unittest.skipUnless(MAKE, "make is not installed, so a Makefile fixture cannot be held to its real runner")
class MakeFixtureTests(unittest.TestCase):
    def test_the_fixtures_this_covers_include_every_make_positive_fixture(self):
        names = makefile_fixtures()
        for expected in ("cmd-ok-make", "cmd-ok-make-prereqs", "cmd-ok-make-alias", "cmd-03-divergent"):
            self.assertIn(expected, names)

    def test_every_makefile_fixture_runs_check_under_make_except_the_one_that_is_refused_on_purpose(self):
        for name in makefile_fixtures():
            if name in REFUSED_ON_PURPOSE:
                continue
            with self.subTest(fixture=name):
                done = dry_run(name)
                self.assertEqual((done.returncode, done.stderr), (0, ""), f"{name}: make refused the Makefile")

    def test_the_fixture_that_is_refused_on_purpose_is_refused_with_the_message_the_engine_reports(self):
        for name, message in REFUSED_ON_PURPOSE.items():
            with self.subTest(fixture=name):
                done = dry_run(name)
                self.assertNotEqual(done.returncode, 0)
                actual = done.stderr.strip().replace(str(support.fixture(name)) + "/", "")
                self.assertEqual(_normalize_make_quotes(actual), _normalize_make_quotes(message))

    def test_the_only_fixtures_that_are_refused_are_the_ones_named_here(self):
        self.assertEqual(set(REFUSED_ON_PURPOSE) - set(makefile_fixtures()), set())


if __name__ == "__main__":
    unittest.main()
