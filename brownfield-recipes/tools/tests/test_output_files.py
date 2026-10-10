# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Output file names carry the repository's name, and no tool replaces a file.

The contract is "Output files" in `brownfield-recipes/schema/SCHEMA.md`. These tests pin the label rule, the
stamp, the name, and the exclusive create with its `-2`, `-3` suffixes.
"""

from __future__ import annotations

import re
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import _paths
import _common

NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}\.[a-z]+(-[a-z]+)*\.[0-9]{8}T[0-9]{6}Z(-[0-9]+)?\.[a-z]+$")
STAMP = "20261010T094207Z"


class ImportTests(unittest.TestCase):
    def test_the_helpers_come_from_the_tools_folder(self) -> None:
        self.assertEqual(Path(_common.__file__).resolve().parent, _paths.TOOLS)


class DeriveLabelTests(unittest.TestCase):
    def test_the_roadmap_example_is_cut_to_24_characters(self) -> None:
        self.assertEqual(_common.derive_label("Digital_Assistant_microServices"), "digital-assistant-micros")

    def test_the_schema_example(self) -> None:
        self.assertEqual(_common.derive_label("Digital-Assistant-SDK"), "digital-assistant-sdk")

    def test_a_clean_name_is_unchanged(self) -> None:
        self.assertEqual(_common.derive_label("agentic-tdd"), "agentic-tdd")

    def test_upper_case_becomes_lower_case(self) -> None:
        self.assertEqual(_common.derive_label("MyRepo"), "myrepo")

    def test_a_run_of_other_characters_becomes_one_hyphen(self) -> None:
        self.assertEqual(_common.derive_label("my___repo...v2 (copy)"), "my-repo-v2-copy")

    def test_leading_and_trailing_hyphens_are_dropped(self) -> None:
        self.assertEqual(_common.derive_label("--_my repo_--"), "my-repo")

    def test_a_trailing_hyphen_left_by_the_cut_is_dropped(self) -> None:
        name = "a" * 23 + "-bbb"
        self.assertEqual(_common.derive_label(name), "a" * 23)

    def test_exactly_24_characters_are_kept(self) -> None:
        self.assertEqual(_common.derive_label("a" * 30), "a" * 24)

    def test_a_letter_outside_a_to_z_is_replaced(self) -> None:
        self.assertEqual(_common.derive_label("Diátaxis"), "di-taxis")

    def test_nothing_left_gives_repo(self) -> None:
        for name in ("", "...", "---", "ÄÖÜ"):
            with self.subTest(name=name):
                self.assertEqual(_common.derive_label(name), "repo")

    def test_every_derived_label_is_a_valid_explicit_label(self) -> None:
        for name in (
            "Digital_Assistant_microServices",
            "x",
            "9",
            "a.b_c-d",
            "UPPER CASE NAME THAT IS VERY LONG INDEED",
        ):
            with self.subTest(name=name):
                self.assertRegex(_common.derive_label(name), _common.EXPLICIT_LABEL)


class RepoLabelTests(unittest.TestCase):
    def test_an_explicit_label_wins(self) -> None:
        self.assertEqual(_common.repo_label("/some/Digital_Assistant_microServices", "da-micro"), "da-micro")

    def test_an_explicit_label_may_hold_dot_underscore_and_hyphen(self) -> None:
        self.assertEqual(_common.repo_label("/x", "my_repo.v2-a"), "my_repo.v2-a")

    def test_an_explicit_label_of_32_characters_is_allowed_and_33_is_not(self) -> None:
        self.assertEqual(_common.repo_label("/x", "a" * 32), "a" * 32)
        with self.assertRaises(_common.UsageError):
            _common.repo_label("/x", "a" * 33)

    def test_an_explicit_label_that_breaks_the_pattern_is_a_usage_error(self) -> None:
        for bad in ("", "Upper", "has space", "-leading", ".hidden", "a/b", "../x", "naïve"):
            with self.subTest(label=bad):
                with self.assertRaises(_common.UsageError):
                    _common.repo_label("/x", bad)

    def test_the_label_comes_from_the_name_of_the_resolved_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "My Repo!!"
            repo.mkdir()
            self.assertEqual(_common.repo_label(repo), "my-repo")
            self.assertEqual(_common.repo_label(repo / "." / "..", None), _common.derive_label(Path(tmp).name))

    def test_a_dot_is_resolved_before_its_name_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "agentic-tdd"
            repo.mkdir()
            with mock.patch("pathlib.Path.cwd", return_value=repo):
                self.assertEqual(_common.repo_label(repo / "."), "agentic-tdd")

    def test_the_filesystem_root_gives_repo(self) -> None:
        self.assertEqual(_common.repo_label(Path(Path.cwd().anchor)), "repo")


class StampTests(unittest.TestCase):
    def test_a_utc_time_is_formatted(self) -> None:
        moment = datetime(2026, 10, 10, 9, 42, 7, tzinfo=timezone.utc)
        self.assertEqual(_common.utc_stamp(moment), STAMP)

    def test_another_timezone_is_converted_to_utc(self) -> None:
        moment = datetime(2026, 10, 10, 11, 42, 7, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(_common.utc_stamp(moment), STAMP)

    def test_a_time_without_a_timezone_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            _common.utc_stamp(datetime(2026, 10, 10, 9, 42, 7))

    def test_now_has_the_format(self) -> None:
        self.assertRegex(_common.utc_stamp(), r"^[0-9]{8}T[0-9]{6}Z$")

    def test_microseconds_are_dropped(self) -> None:
        moment = datetime(2026, 10, 10, 9, 42, 7, 999999, tzinfo=timezone.utc)
        self.assertEqual(_common.utc_stamp(moment), STAMP)


class OutputNameTests(unittest.TestCase):
    def test_the_format_is_label_kind_stamp_extension(self) -> None:
        self.assertEqual(
            _common.output_name("digital-assistant-sdk", "engine-report", STAMP, "json"),
            "digital-assistant-sdk.engine-report.20261010T094207Z.json",
        )

    def test_the_second_and_third_attempts_add_a_suffix_after_the_stamp(self) -> None:
        self.assertEqual(
            _common.output_name("r", "audit-draft", STAMP, "json", 2), "r.audit-draft.20261010T094207Z-2.json"
        )
        self.assertEqual(
            _common.output_name("r", "audit-draft", STAMP, "json", 3), "r.audit-draft.20261010T094207Z-3.json"
        )

    def test_every_name_matches_the_documented_shape(self) -> None:
        for attempt in (1, 2, 17):
            with self.subTest(attempt=attempt):
                self.assertRegex(_common.output_name("a.b_c-d", "audit-report", STAMP, "md", attempt), NAME)

    def test_a_label_kind_stamp_or_extension_that_could_change_the_directory_is_refused(self) -> None:
        bad = [
            ("../x", "engine-report", STAMP, "json"),
            ("r", "engine/report", STAMP, "json"),
            ("r", "engine-report", "2026-10-10", "json"),
            ("r", "engine-report", STAMP, "j/son"),
            ("r", "engine-report", STAMP, ""),
            ("r", "", STAMP, "json"),
        ]
        for label, kind, stamp, ext in bad:
            with self.subTest(label=label, kind=kind, stamp=stamp, ext=ext):
                with self.assertRaises(ValueError):
                    _common.output_name(label, kind, stamp, ext)


class CreateNewTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def names(self) -> list[str]:
        return sorted(p.name for p in self.dir.iterdir())

    def test_a_file_is_created_with_the_name_and_the_text(self) -> None:
        path = _common.create_new(self.dir, "repo", "audit-report", STAMP, "json", '{"a": 1}\n')
        self.assertEqual(path, self.dir / "repo.audit-report.20261010T094207Z.json")
        self.assertEqual(path.read_text(encoding="utf-8"), '{"a": 1}\n')

    def test_bytes_are_written_as_they_are(self) -> None:
        path = _common.create_new(self.dir, "repo", "audit-report", STAMP, "md", b"\xc3\xa9\r\n")
        self.assertEqual(path.read_bytes(), b"\xc3\xa9\r\n")

    def test_two_creations_of_one_name_give_two_files_and_the_first_is_untouched(self) -> None:
        first = _common.create_new(self.dir, "repo", "audit-draft", STAMP, "json", "first run\n")
        before = first.read_bytes()
        second = _common.create_new(self.dir, "repo", "audit-draft", STAMP, "json", "second run, longer text\n")
        self.assertNotEqual(first, second)
        self.assertEqual(first.name, "repo.audit-draft.20261010T094207Z.json")
        self.assertEqual(second.name, "repo.audit-draft.20261010T094207Z-2.json")
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(second.read_text(encoding="utf-8"), "second run, longer text\n")

    def test_a_third_creation_is_numbered_3(self) -> None:
        for _ in range(3):
            last = _common.create_new(self.dir, "repo", "audit-draft", STAMP, "json", "x")
        self.assertEqual(last.name, "repo.audit-draft.20261010T094207Z-3.json")
        self.assertEqual(len(self.names()), 3)

    def test_a_file_that_was_there_before_is_never_replaced(self) -> None:
        old = self.dir / "repo.engine-report.20261010T094207Z.json"
        old.write_text("somebody else's report", encoding="utf-8")
        new = _common.create_new(self.dir, "repo", "engine-report", STAMP, "json", "mine")
        self.assertEqual(old.read_text(encoding="utf-8"), "somebody else's report")
        self.assertEqual(new.name, "repo.engine-report.20261010T094207Z-2.json")

    def test_a_dangling_symlink_holds_its_name_and_is_not_written_through(self) -> None:
        link = self.dir / "repo.engine-report.20261010T094207Z.json"
        elsewhere = self.dir / "elsewhere.txt"
        try:
            link.symlink_to(elsewhere)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        new = _common.create_new(self.dir, "repo", "engine-report", STAMP, "json", "mine")
        self.assertFalse(elsewhere.exists())
        self.assertEqual(new.name, "repo.engine-report.20261010T094207Z-2.json")

    def test_a_failed_write_removes_only_its_own_partial_file(self) -> None:
        old = _common.create_new(self.dir, "repo", "audit-draft", STAMP, "json", "kept")
        with mock.patch("os.fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                _common.create_new(self.dir, "repo", "audit-draft", STAMP, "json", "lost")
        self.assertEqual(self.names(), [old.name])
        self.assertEqual(old.read_text(encoding="utf-8"), "kept")

    def test_every_created_name_matches_the_documented_shape(self) -> None:
        for _ in range(3):
            path = _common.create_new(self.dir, "digital-assistant-micros", "audit-report", STAMP, "json", "x")
            self.assertRegex(path.name, NAME)

    def test_running_out_of_names_is_a_usage_error(self) -> None:
        with mock.patch.object(_common, "MAX_NAME_ATTEMPTS", 3):
            for _ in range(3):
                _common.create_new(self.dir, "repo", "audit-draft", STAMP, "json", "x")
            with self.assertRaises(_common.UsageError):
                _common.create_new(self.dir, "repo", "audit-draft", STAMP, "json", "x")
        self.assertEqual(len(self.names()), 3)

    def test_racing_writers_each_get_their_own_file(self) -> None:
        count = 8
        paths: list[Path] = []
        start = threading.Barrier(count)

        def writer(n: int) -> None:
            start.wait()
            paths.append(_common.create_new(self.dir, "repo", "audit-draft", STAMP, "json", f"writer {n}\n"))

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(set(paths)), count)
        self.assertEqual(
            sorted(p.read_text(encoding="utf-8") for p in paths), sorted(f"writer {n}\n" for n in range(count))
        )


class FreeNameTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_the_plain_name_when_nothing_is_there(self) -> None:
        path = _common.free_name(self.dir, "repo", "engine-report", STAMP, "json")
        self.assertEqual(path, self.dir / "repo.engine-report.20261010T094207Z.json")
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_a_taken_name_gives_the_next_one_and_nothing_is_created(self) -> None:
        (self.dir / "repo.engine-report.20261010T094207Z.json").write_text("x", encoding="utf-8")
        (self.dir / "repo.engine-report.20261010T094207Z-2.json").write_text("x", encoding="utf-8")
        path = _common.free_name(self.dir, "repo", "engine-report", STAMP, "json")
        self.assertEqual(path.name, "repo.engine-report.20261010T094207Z-3.json")
        self.assertEqual(len(list(self.dir.iterdir())), 2)

    def test_a_dangling_symlink_holds_its_name(self) -> None:
        link = self.dir / "repo.engine-report.20261010T094207Z.json"
        try:
            link.symlink_to(self.dir / "nowhere")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        self.assertEqual(
            _common.free_name(self.dir, "repo", "engine-report", STAMP, "json").name,
            "repo.engine-report.20261010T094207Z-2.json",
        )


if __name__ == "__main__":
    unittest.main()
