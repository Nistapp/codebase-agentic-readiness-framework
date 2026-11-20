# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Probe output is redacted at capture time, before it reaches a ``ProbeResult`` or a report.

A Tier-C probe (``--run-gates`` plus ``--allow-probe <verb>``) runs the target's own command, and the tail of its
output is stored in the report. ``audit/probes.py`` redacts credential shapes when it captures that output, never when
it renders it. These tests feed ``redact()`` each shape in ``REDACTION_PATTERNS``, check that harmless text survives,
and run a probe whose output carries a planted key, in process, through to the JSON and Markdown reports.

Every key-shaped string is built at run time from pieces, so no secret scanner flags this file and no baseline entry
is needed.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit import cli  # noqa: E402
from audit.probes import OUTPUT_TAIL_LINES, REDACTION_PATTERNS, ProbePlan, redact, run_plan  # noqa: E402
from audit.rules.checks import con  # noqa: E402

MARK = "[REDACTED]"


def _join(*parts: str) -> str:
    return "".join(parts)


#: One sample per shape in ``REDACTION_PATTERNS``, in its order: (label, text, the secret part that must go).
SHAPES: tuple[tuple[str, str, str], ...] = (
    ("assignment", _join("API_", "KEY=", "s3cr3t-value-1"), "s3cr3t-value-1"),
    ("prefixed key", _join("sk", "-", "A1b2C3d4E5f6G7h8I9j0"), "A1b2C3d4E5f6G7h8I9j0"),
    ("GitHub token", _join("gh", "p_", "Zz9Yy8Xx7Ww6Vv5Uu4Tt"), "Zz9Yy8Xx7Ww6Vv5Uu4Tt"),
    ("AWS key id", _join("AK", "IA", "Q2W3E4R5T6Y7U8I9"), "Q2W3E4R5T6Y7U8I9"),
    ("private key header", _join("-----BEGIN ", "RSA PRIVATE", " KEY-----"), "PRIVATE KEY"),
    ("bearer token", _join("Authorization: Bear", "er ", "abcDEF123456ghiJKL789"), "abcDEF123456ghiJKL789"),
    ("Slack token", _join("xo", "xb-", "1234567890-", "AbCdEf", "GhIjKl"), "GhIjKl"),
)


class RedactShapeTests(unittest.TestCase):
    def test_every_pattern_has_a_sample(self):
        self.assertEqual(len(SHAPES), len(REDACTION_PATTERNS), "a pattern was added or removed: update SHAPES")
        for pattern, (label, text, _secret) in zip(REDACTION_PATTERNS, SHAPES, strict=True):
            with self.subTest(shape=label):
                self.assertIsNotNone(pattern.search(text), f"{label} does not exercise its own pattern")

    def test_each_shape_is_replaced_and_counted(self):
        for label, text, secret in SHAPES:
            with self.subTest(shape=label):
                clean, count = redact(f"before {text} after")
                self.assertNotIn(secret, clean)
                self.assertIn(MARK, clean)
                self.assertEqual(count, 1)
                self.assertTrue(clean.startswith("before "), clean)

    def test_assignment_words_and_separators(self):
        for word in ("api_key", "api-key", "apikey", "SECRET", "Token", "password", "passwd", "pwd"):
            for sep in ("=", ": ", " = "):
                with self.subTest(word=word, sep=sep):
                    clean, count = redact(f"{word}{sep}v4lue-{word}")
                    self.assertEqual((clean, count), (MARK, 1))

    def test_each_occurrence_is_counted(self):
        key = _join("gh", "o_", "0123456789abcdefABCD")
        clean, count = redact(f"{key}\nline two\n{key}\n")
        self.assertEqual(count, 2)
        self.assertEqual(clean, f"{MARK}\nline two\n{MARK}\n")

    def test_harmless_text_survives(self):
        for text in (
            "",
            "Ran 12 tests in 0.4s\n\nOK\n",
            "tests/test_secret_store.py::test_rotate PASSED",
            "token count: words only",
            "sk-short",
            "AKIA-not-a-key",
            "Bearer short",
            "the secret-santa list",
        ):
            with self.subTest(text=text):
                self.assertEqual(redact(text), (text, 0))


def _planted_key() -> str:
    return _join("gh", "p_", "PlantedKey0123456789xyz")


#: A target script that prints a planted key, built from pieces so the file itself holds no key-shaped literal.
_EMIT = (
    "import sys\n"
    "key = 'gh' + 'p_' + 'PlantedKey0123456789xyz'\n"
    "print('collecting tests')\n"
    "print('using ' + key)\n"
    "print('pass' + 'word=' + 'hunter2-planted', file=sys.stderr)\n"
    "print('1 passed')\n"
)


class RunPlanRedactionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        support.write(self.root, "emit.py", _EMIT)

    def test_probe_result_holds_no_planted_secret(self):
        result = run_plan(ProbePlan("test", [sys.executable, "emit.py"]), allow=("test",), cwd=self.root)
        self.assertEqual(result.exit_code, 0, result.refused_reason)
        self.assertNotIn(_planted_key(), result.output_tail)
        self.assertNotIn("hunter2-planted", result.output_tail)
        self.assertEqual(result.redactions, 2)
        self.assertIn(f"using {MARK}", result.output_tail)
        self.assertIn("1 passed", result.output_tail, "harmless output must survive redaction")

    def test_secret_before_the_tail_is_redacted_and_still_counted(self):
        script = "key = 'gh' + 'p_' + 'PlantedKey0123456789xyz'\nprint(key)\n" + "print('ok')\n" * (
            OUTPUT_TAIL_LINES + 5
        )
        support.write(self.root, "long.py", script)
        result = run_plan(ProbePlan("test", [sys.executable, "long.py"]), allow=("test",), cwd=self.root)
        self.assertNotIn(_planted_key(), result.output_tail)
        self.assertEqual(result.redactions, 1)

    def test_timed_out_probe_output_is_redacted(self):
        script = "import sys, time\nprint('gh' + 'p_' + 'PlantedKey0123456789xyz', flush=True)\ntime.sleep(30)\n"
        support.write(self.root, "slow.py", script)
        result = run_plan(ProbePlan("test", [sys.executable, "slow.py"]), allow=("test",), cwd=self.root, timeout=2)
        self.assertTrue(result.timed_out)
        self.assertNotIn(_planted_key(), result.output_tail)


class ReportRedactionTests(unittest.TestCase):
    """The full pipeline, in process: a permitted ``test`` probe prints a key; neither report holds it."""

    def test_reports_hold_the_redaction_not_the_key(self):
        self.addCleanup(con.set_emit_target, None)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            support.write(target, "emit.py", _EMIT)
            support.write(target, "package.json", json.dumps({"scripts": {"test": "python3 emit.py"}}))
            out = Path(tmp) / "out" / "report.json"
            argv = [str(target), "--format", "both", "--out", str(out), "--run-gates", "--allow-probe", "test"]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                code = cli.run(argv)
            self.assertEqual(code, 0, err.getvalue())

            raw_json = out.read_text(encoding="utf-8")
            raw_md = out.with_suffix(".md").read_text(encoding="utf-8")

        for name, raw in (("report.json", raw_json), ("report.md", raw_md)):
            with self.subTest(report=name):
                self.assertNotIn(_planted_key(), raw)
                self.assertNotIn("hunter2-planted", raw)
                self.assertIn(MARK, raw)

        probes = [p for p in json.loads(raw_json)["probes"] if p["verb"] == "test"]
        self.assertEqual(len(probes), 1)
        self.assertEqual(probes[0]["exit_code"], 0)
        self.assertEqual(probes[0]["redactions"], 2)
        self.assertIn(f"using {MARK}", probes[0]["output_tail"])


if __name__ == "__main__":
    unittest.main()
