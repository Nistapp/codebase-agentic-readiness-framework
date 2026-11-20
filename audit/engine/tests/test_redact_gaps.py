# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Credential shapes the probe runner's ``redact()`` used to let through, and prose it must leave alone.

Every key-shaped value is built at run time from parts, so the secrets scan does not read this file as holding one.
Each case checks the value is gone, that one secret counts once, and that the text around it survives.
"""

from __future__ import annotations

import unittest

from audit.probes import redact


def _join(*parts: str) -> str:
    return "".join(parts)


class KeywordInACompoundName(unittest.TestCase):
    """A keyword joined to other words by ``_`` or ``-`` is still a keyword (``GITHUB_TOKEN``, ``DB_PASSWORD``)."""

    def test_a_prefixed_or_suffixed_name_is_redacted_once(self) -> None:
        cases = {
            "GITHUB_TOKEN": _join("abc", "123def"),
            "DB_PASSWORD": _join("hun", "ter2"),
            "AWS_SECRET_ACCESS_KEY": _join("wJal", "rXUt"),
            "client_secret": _join("ab", "c"),
            "x-api-key": _join("k3y", "value"),
            "SECRET_KEY": _join("s3", "cr3t"),
        }
        for name, value in cases.items():
            for sep in ("=", ": ", " = "):
                with self.subTest(name=name, sep=sep):
                    clean, count = redact(f"before\n{name}{sep}{value}\nafter")
                    self.assertNotIn(value, clean)
                    self.assertEqual(count, 1)
                    self.assertIn("before", clean)
                    self.assertIn("after", clean)

    def test_a_bare_keyword_is_still_redacted(self) -> None:
        for name in ("API_KEY", "SECRET", "token", "password", "--password"):
            with self.subTest(name=name):
                value = _join("v4l", "ue9")
                clean, count = redact(f"{name}={value}")
                self.assertNotIn(value, clean)
                self.assertEqual(count, 1)

    def test_a_json_key_is_redacted(self) -> None:
        value = _join("abcd", "1234")
        clean, count = redact('{"access_token": "' + value + '"}')
        self.assertNotIn(value, clean)
        self.assertEqual(count, 1)

    def test_prose_and_counters_are_left_alone(self) -> None:
        for text in (
            "passwords must be rotated every 90 days",
            "token count: 5",
            "tokens: 5",
            "max_tokens: 4096",
            "OLDPWD=/home/user",
            "the secretary said: yes",
        ):
            with self.subTest(text=text):
                self.assertEqual(redact(text), (text, 0))

    def test_an_empty_assignment_does_not_swallow_the_next_line(self) -> None:
        text = "password=\nnext line"
        self.assertEqual(redact(text), (text, 0))


if __name__ == "__main__":
    unittest.main()
