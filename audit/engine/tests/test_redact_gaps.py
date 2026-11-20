# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Credential shapes the probe runner's ``redact()`` used to let through, and prose it must leave alone.

Every key-shaped value is built at run time from parts, so the secrets scan does not read this file as holding one.
Each case checks the value is gone, that one secret counts once, and that the text around it survives.
"""

from __future__ import annotations

import unittest

from audit.probes import redact
from audit.rules.checks.sec import _line_is_secret


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


class QuotedValue(unittest.TestCase):
    """A quoted value is redacted up to its closing quote, spaces and all."""

    def test_a_quoted_value_with_spaces_is_redacted_whole(self) -> None:
        for quote in ('"', "'"):
            for name, sep in (("password", " = "), ("DB_PASSWORD", "="), ('"secret"', ": ")):
                with self.subTest(quote=quote, name=name):
                    value = _join("x", "y ", "z", "w")
                    clean, count = redact(f"{name}{sep}{quote}{value}{quote}, next")
                    self.assertEqual(count, 1)
                    self.assertNotIn("y z", clean)
                    self.assertNotIn("zw", clean)
                    self.assertTrue(clean.endswith("[REDACTED], next"))

    def test_an_unclosed_quote_is_redacted_to_the_end_of_its_line(self) -> None:
        clean, count = redact('password = "' + _join("open ", "ended") + "\nnext line")
        self.assertEqual((clean, count), ("[REDACTED]\nnext line", 1))

    def test_a_bearer_value_is_redacted_with_its_token(self) -> None:
        body = _join("abc", "defghij", "klmnop")
        clean, count = redact(f"token: Bearer {body}")
        self.assertEqual((clean, count), ("[REDACTED]", 1))


_BEGIN = _join("-----BEGIN RSA PRIV", "ATE KEY-----")
_END = _join("-----END RSA PRIV", "ATE KEY-----")
_BODY = ("MIIEow" + "IBAAKCAQEA" * 6, "q3Rk" + "Zm9vYmFy" * 8, "dGVzdA" + "==")


class PemPrivateKey(unittest.TestCase):
    """A PEM private key is redacted whole: the BEGIN line, the base64 body and the END line."""

    def test_a_whole_block_is_one_redaction(self) -> None:
        text = "\n".join(("loading key", _BEGIN, *_BODY, _END, "done"))
        clean, count = redact(text)
        self.assertEqual(count, 1)
        for line in (*_BODY, "BEGIN", "END RSA"):
            self.assertNotIn(line, clean)
        self.assertTrue(clean.startswith("loading key\n"))
        self.assertTrue(clean.endswith("\ndone"))

    def test_a_block_cut_off_before_its_end_is_redacted_to_the_end(self) -> None:
        text = "\n".join(("loading key", _BEGIN, *_BODY[:2]))
        clean, count = redact(text)
        self.assertEqual((clean, count), ("loading key\n[REDACTED]", 1))

    def test_two_blocks_are_two_redactions_and_the_text_between_stays(self) -> None:
        block = "\n".join((_BEGIN, *_BODY, _END))
        clean, count = redact("\n".join((block, "between", block)))
        self.assertEqual((clean, count), ("[REDACTED]\nbetween\n[REDACTED]", 2))

    def test_a_keyword_before_the_block_does_not_leave_the_body(self) -> None:
        clean, count = redact("\n".join(("secret: " + _BEGIN, *_BODY, _END)))
        self.assertEqual(count, 1)
        for line in _BODY:
            self.assertNotIn(line, clean)

    def test_an_end_line_alone_is_left_alone(self) -> None:
        self.assertEqual(redact(_END), (_END, 0))


class SlackToken(unittest.TestCase):
    """A Slack token has a shape of its own: ``xoxb-``, ``xoxp-``, ``xapp-`` and the other ``xox`` kinds."""

    def tokens(self) -> list[str]:
        tail = _join("1234567890", "-", "0987654321", "-", "AbCdEfGhIjKlMnOp")
        return [_join("xo", "xb-", tail), _join("xo", "xp-", tail), _join("xa", "pp-1-", tail)]

    def test_each_kind_is_one_redaction(self) -> None:
        for token in self.tokens():
            with self.subTest(token=token[:4]):
                clean, count = redact(f"posting with {token} now")
                self.assertEqual((clean, count), ("posting with [REDACTED] now", 1))

    def test_a_slack_token_in_a_keyword_assignment_counts_once(self) -> None:
        token = self.tokens()[0]
        self.assertEqual(redact(f"SLACK_BOT_TOKEN={token}"), ("[REDACTED]", 1))

    def test_sec_02_reads_a_tracked_slack_token_as_a_credential(self) -> None:
        for token in self.tokens():
            with self.subTest(token=token[:4]):
                self.assertTrue(_line_is_secret(f'client = WebClient("{token}")', in_code=True))

    def test_words_that_only_start_alike_are_left_alone(self) -> None:
        for text in ("xoxb-short", "the xapp- prefix", "toxoxb-1234567890abc"):
            with self.subTest(text=text):
                self.assertEqual(redact(text), (text, 0))


if __name__ == "__main__":
    unittest.main()
