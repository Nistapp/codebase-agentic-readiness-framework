# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC-04` tells a shell's own variables and optional inputs from required ones (issue #13).

A CI script used `${SECONDS}` as a timer, and `EXEC-04` reported the bash builtin as an undeclared environment
variable. Variables the shell sets itself are now on the allow-list. A reference with a fallback (`${VAR:-default}`,
`${VAR-x}`, `${VAR:=x}`, `${VAR:+x}`) runs without the variable: it is reported apart, as optional, and never fails
the check. `${VAR:?message}` stops the script without the variable, so it is required, as a bare `${VAR}` is. The
check runs in-process here, so coverage traces it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.execution import check_exec04  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402


def _exec04(files: dict[str, str]):
    """The `EXEC-04` outcome of a repository built from ``files``."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        inventory = build_inventory(root)
        return check_exec04(
            spec=REGISTRY_BY_ID["EXEC-04"],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=None,
            session=None,
        )


class Exec04ShellFormTests(unittest.TestCase):
    def test_shell_builtins_are_not_environment_inputs(self):
        script = 'start=${SECONDS}\necho "${RANDOM} ${LINENO} ${BASH_SOURCE} ${OLDPWD} ${HOSTNAME} ${UID}"\n'
        outcome = _exec04({"ci/build.sh": script})
        self.assertEqual((outcome.verdict.value, outcome.data.missing), ("PASS", ()))

    def test_a_reference_with_a_fallback_is_optional_and_does_not_fail(self):
        script = 'tar -cf "${IMAGE_TAR:-image.tar}" .\nmkdir -p "${CACHE_DIR-/tmp/cache}"\n'
        outcome = _exec04({"ci/build.sh": script})
        self.assertEqual(outcome.verdict.value, "PASS")
        self.assertEqual((outcome.data.missing, outcome.data.optional), ((), ("CACHE_DIR", "IMAGE_TAR")))
        self.assertEqual(
            outcome.summary,
            "no required environment key referenced; 2 optional key(s) with a fallback, not in an example file: "
            "CACHE_DIR, IMAGE_TAR",
        )

    def test_every_fallback_operator_is_optional(self):
        script = "".join(f"echo ${{K{n}{op}x}}\n" for n, op in enumerate((":-", "-", ":=", "=", ":+", "+")))
        outcome = _exec04({"run.sh": script})
        self.assertEqual(outcome.data.optional, tuple(f"K{n}" for n in range(6)))

    def test_a_required_form_fails_beside_the_optional_note(self):
        script = 'echo "${API_TOKEN:?set API_TOKEN}" "${REGION}" "${CACHE_DIR:-/tmp}"\n'
        outcome = _exec04({"deploy.sh": script})
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual(outcome.data.missing, ("API_TOKEN", "REGION"))
        self.assertEqual(
            outcome.summary,
            "2 referenced key(s) are absent from any committed example file: API_TOKEN, REGION; "
            "1 optional key(s) with a fallback, not in an example file: CACHE_DIR",
        )

    def test_one_required_reference_makes_a_key_required(self):
        outcome = _exec04({"a.sh": 'echo "${REGION:-eu}"\n', "b.sh": 'echo "${REGION}"\n'})
        self.assertEqual((outcome.data.missing, outcome.data.optional), (("REGION",), ()))

    def test_an_optional_key_in_the_example_file_is_not_listed(self):
        outcome = _exec04({"a.sh": 'echo "${REGION:-eu}"\n', ".env.example": "REGION=\n"})
        self.assertEqual((outcome.verdict.value, outcome.data.optional), ("PASS", ()))
        self.assertEqual(outcome.summary, "no required environment key referenced")


if __name__ == "__main__":
    unittest.main()
