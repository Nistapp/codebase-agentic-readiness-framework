# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The Makefile reader (``audit.stack.parse_makefile``) and what a Makefile target runs.

R-04 found the engine reading a Makefile only for single-line recipes. These tests pin what it reads now: a colon
escaped in a target name, prerequisites in order, continuation lines, and the one thing GNU Make refuses that the
engine's own fixture did, an unescaped ``format:check:``.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import (  # noqa: E402
    MakeError,
    MakeRule,
    _logical_lines,
    _trailing_backslashes,
    _unescaped,
    canonical_verb,
    parse_makefile,
    parse_makefile_targets,
)


def read(text: str | None):
    """``(parse_makefile, parse_makefile_targets)`` of a directory whose Makefile holds ``text``."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        if text is not None:
            support.write(root, "Makefile", text)
        inventory = build_inventory(root)
        return parse_makefile(inventory), parse_makefile_targets(inventory)


class RuleTests(unittest.TestCase):
    def test_a_colon_escaped_in_a_target_name_is_part_of_the_name(self):
        parsed, _ = read("format\\:check:\n\tprettier --check .\n")
        self.assertEqual(parsed.errors, ())
        self.assertEqual(parsed.rules, {"format:check": MakeRule((), ("prettier --check .",), 1)})

    def test_prerequisites_keep_their_order_and_read_an_escaped_colon(self):
        parsed, _ = read("check: format\\:check typecheck test\n")
        self.assertEqual(parsed.rules["check"].prerequisites, ("format:check", "typecheck", "test"))

    def test_prerequisites_of_more_than_one_rule_line_add_up_without_repeats(self):
        parsed, _ = read("check: a b\ncheck: b c\n")
        self.assertEqual(parsed.rules["check"].prerequisites, ("a", "b", "c"))

    def test_one_rule_for_several_targets_gives_each_its_own_copy(self):
        parsed, _ = read("a b: c\n\tdo it\n")
        self.assertEqual(parsed.rules["a"], MakeRule(("c",), ("do it",), 1))
        self.assertEqual(parsed.rules["b"], MakeRule(("c",), ("do it",), 1))

    def test_a_recipe_after_a_semicolon_belongs_to_the_rule(self):
        parsed, _ = read("lint: ; ruff check .\n")
        self.assertEqual(parsed.rules["lint"], MakeRule((), ("ruff check .",), 1))

    def test_a_trailing_backslash_joins_the_next_line(self):
        parsed, _ = read("check: a \\\n   b \\\n   c\n\ttest -f x\n")
        self.assertEqual(parsed.rules["check"], MakeRule(("a", "b", "c"), ("test -f x",), 1))

    def test_a_continued_recipe_is_one_step(self):
        parsed, _ = read("test:\n\tpython -m unittest \\\n\t\tdiscover\n")
        self.assertEqual(parsed.rules["test"].recipe, ("python -m unittest discover",))

    def test_two_backslashes_at_the_end_do_not_continue_the_line(self):
        parsed, _ = read("a:\n\techo \\\\\nb:\n")
        self.assertEqual(sorted(parsed.rules), ["a", "b"])

    def test_blank_and_comment_lines_between_recipe_lines_keep_the_recipe_together(self):
        parsed, _ = read("test:\n\tone\n\n# a comment\n\ttwo\n\t# not a step\n")
        self.assertEqual(parsed.rules["test"].recipe, ("one", "two"))

    def test_a_double_colon_rule_is_a_rule(self):
        parsed, _ = read("a:: b\n\tdo it\n")
        self.assertEqual(parsed.rules["a"], MakeRule(("b",), ("do it",), 1))

    def test_order_only_prerequisites_are_prerequisites(self):
        parsed, _ = read("a: b | c\n")
        self.assertEqual(parsed.rules["a"].prerequisites, ("b", "c"))

    def test_a_target_specific_variable_is_not_a_prerequisite(self):
        parsed, _ = read("check: X=1 other\n")
        self.assertEqual(parsed.rules["check"].prerequisites, ("other",))

    def test_a_name_that_holds_a_variable_or_a_pattern_is_left_out(self):
        parsed, _ = read("$(NAME): x\n\ty\n%.o: %.c\n\tcc\nall: $(DEPS) b\n")
        self.assertEqual(parsed.rules, {"all": MakeRule(("b",), (), 5)})

    def test_assignments_are_not_rules(self):
        parsed, _ = read("A := b:c\nB = d:e\nC ?= f\nexport G := h:i\n")
        self.assertEqual((parsed.rules, parsed.errors), ({}, ()))

    def test_a_define_block_is_not_read(self):
        parsed, _ = read("define BLOCK\nlint:\n\tbad\nendef\ntest:\n\tgood\n")
        self.assertEqual(sorted(parsed.rules), ["test"])

    def test_a_special_target_is_not_a_verb(self):
        parsed, _ = read(".PHONY: a b\n.DEFAULT: x\n")
        self.assertEqual(parsed.rules, {})

    def test_a_rule_records_the_line_it_starts_on(self):
        parsed, _ = read("# header\n\nlint:\n\teslint .\n")
        self.assertEqual(parsed.rules["lint"].line, 3)


class RuleEdgeTests(unittest.TestCase):
    def test_a_name_with_an_x_in_it_is_a_name(self):
        parsed, _ = read("fix: matrix\n")
        self.assertEqual(parsed.rules["fix"].prerequisites, ("matrix",))

    def test_a_prerequisite_may_follow_the_colon_with_no_space(self):
        parsed, _ = read("a:b\n")
        self.assertEqual(parsed.rules["a"].prerequisites, ("b",))

    def test_a_double_colon_may_be_followed_by_a_name_with_no_space(self):
        parsed, _ = read("a::b\n")
        self.assertEqual(parsed.rules["a"].prerequisites, ("b",))

    def test_a_recipe_after_a_semicolon_may_follow_it_with_no_space(self):
        parsed, _ = read("lint:;ruff check .\n")
        self.assertEqual(parsed.rules["lint"].recipe, ("ruff check .",))

    def test_the_posix_assignments_with_more_than_one_colon_are_assignments(self):
        parsed, _ = read("A ::= b:c\nD :::= e\n")
        self.assertEqual((parsed.rules, parsed.errors), ({}, ()))

    def test_a_target_named_like_a_directive_is_a_rule(self):
        parsed, _ = read("export: build\n\tzip out.zip .\ninclude:\n\tcat x\n")
        self.assertEqual(sorted(parsed.rules), ["export", "include"])

    def test_a_directive_ends_the_rule_before_it(self):
        parsed, _ = read("a:\ninclude other.mk\n\tnot a recipe\n")
        self.assertEqual(parsed.rules["a"].recipe, ())

    def test_every_line_of_a_define_block_is_skipped_until_endef(self):
        parsed, _ = read("define BLOCK\nx:\ny:\nendef\nz:\n")
        self.assertEqual(sorted(parsed.rules), ["z"])

    def test_endef_may_carry_a_comment(self):
        parsed, _ = read("define BLOCK\nx:\nendef # done\nz:\n")
        self.assertEqual(sorted(parsed.rules), ["z"])

    def test_a_backslash_with_no_space_before_it_joins_with_one_space(self):
        parsed, _ = read("check: a\\\nb\n")
        self.assertEqual(parsed.rules["check"].prerequisites, ("a", "b"))


class ScanTests(unittest.TestCase):
    def test_trailing_backslashes_are_counted_exactly(self):
        self.assertEqual(_trailing_backslashes(""), 0)
        self.assertEqual(_trailing_backslashes("a"), 0)
        self.assertEqual(_trailing_backslashes("a\\"), 1)
        self.assertEqual(_trailing_backslashes("a\\\\\\"), 3)
        self.assertEqual(_trailing_backslashes("\\a\\"), 1)

    def test_an_odd_run_of_backslashes_continues_the_line_and_an_even_run_does_not(self):
        self.assertEqual(_logical_lines("a \\\nb"), [(1, "a b")])
        self.assertEqual(_logical_lines("a \\\\\nb"), [(1, "a \\\\"), (2, "b")])
        self.assertEqual(_logical_lines("a \\\\\\\nb"), [(1, "a \\\\ b")])

    def test_the_line_numbers_are_those_of_the_first_physical_line(self):
        self.assertEqual(_logical_lines("a\nb \\\nc \\\nd\ne"), [(1, "a"), (2, "b c d"), (5, "e")])

    def test_a_last_line_that_ends_in_a_backslash_is_kept(self):
        self.assertEqual(_logical_lines("a \\"), [(1, "a")])

    def test_a_colon_at_the_start_is_found(self):
        self.assertEqual(_unescaped(":a", ":"), [0])

    def test_an_escaped_character_is_skipped_with_what_it_escapes_and_no_more(self):
        self.assertEqual(_unescaped("\\::", ":"), [2])
        self.assertEqual(_unescaped("\\:x:", ":"), [3])

    def test_a_dollar_that_does_not_open_a_reference_opens_nothing(self):
        self.assertEqual(_unescaped("a(:", ":"), [2])
        self.assertEqual(_unescaped("$a:", ":"), [2])

    def test_a_reference_in_braces_or_parentheses_hides_what_is_inside(self):
        self.assertEqual(_unescaped("${A:b}:", ":"), [6])
        self.assertEqual(_unescaped("$(A:b):", ":"), [6])

    def test_a_reference_is_closed_by_its_own_bracket_and_the_next_text_is_seen_again(self):
        self.assertEqual(_unescaped("$(A):", ":"), [4])
        self.assertEqual(_unescaped("$():", ":"), [3])
        self.assertEqual(_unescaped("$(x:y):", ":"), [6])

    def test_nested_references_close_one_at_a_time(self):
        self.assertEqual(_unescaped("$(a $(b):c):", ":"), [11])


class ParseErrorTests(unittest.TestCase):
    def test_an_unescaped_colon_in_a_name_is_the_error_make_reports(self):
        parsed, targets = read("format:\n\tprettier --write .\n\nformat:check:\n\tprettier --check .\n")
        self.assertEqual(parsed.errors, (MakeError(4, "format:check:", "target pattern contains no '%'"),))
        self.assertEqual(targets, {}, "a Makefile that Make refuses has no target that can run")

    def test_the_error_names_the_first_physical_line_of_a_continued_rule(self):
        parsed, _ = read("a:\n\tx\nformat:check: \\\n\tprettier\n")
        self.assertEqual([error.line for error in parsed.errors], [3])

    def test_a_static_pattern_rule_with_a_percent_is_valid(self):
        parsed, _ = read("OBJS = a.o\n$(OBJS): %.o: %.c\n\tcc -c $<\n")
        self.assertEqual((parsed.rules, parsed.errors), ({}, ()))

    def test_a_pattern_that_holds_a_variable_is_not_judged(self):
        parsed, _ = read("a b: $(PAT): c\n")
        self.assertEqual(parsed.errors, ())

    def test_a_colon_inside_a_variable_reference_is_not_a_second_colon(self):
        parsed, _ = read("all: $(SRCS:.c=.o) b\n")
        self.assertEqual((parsed.errors, parsed.rules["all"].prerequisites), ((), ("b",)))

    def test_the_text_of_a_long_line_is_cut_to_two_hundred_characters(self):
        parsed, _ = read("a:" + "b" * 300 + ":\n")
        self.assertEqual(len(parsed.errors[0].text), 200)


class TargetCommandTests(unittest.TestCase):
    def test_a_target_runs_its_prerequisites_that_are_targets_then_its_recipe(self):
        _, targets = read("lint:\n\truff check .\ntest:\n\tpytest\ncheck: lint test\n\techo done\n")
        self.assertEqual(targets["check"], "make lint && make test && echo done")

    def test_a_prerequisite_that_is_not_a_target_is_a_file_and_is_not_run(self):
        _, targets = read("test: src/x.py\n\tpytest\n")
        self.assertEqual(targets["test"], "pytest")

    def test_the_recipe_lines_of_a_target_are_joined_with_and(self):
        _, targets = read("check:\n\tone\n\ttwo\n")
        self.assertEqual(targets["check"], "one && two")

    def test_a_target_with_nothing_to_run_is_listed_with_an_empty_command(self):
        _, targets = read("setup:\n")
        self.assertEqual(targets, {"setup": ""})

    def test_an_escaped_colon_in_a_prerequisite_is_a_target_name(self):
        _, targets = read("format\\:check:\n\tprettier --check .\ncheck: format\\:check\n")
        self.assertEqual(targets["check"], "make format:check")

    def test_no_makefile_has_no_targets(self):
        parsed, targets = read(None)
        self.assertEqual((parsed.rules, parsed.errors, targets), ({}, (), {}))


class CanonicalVerbTests(unittest.TestCase):
    def test_the_escaped_and_the_aliased_spelling_are_the_verb(self):
        self.assertEqual(canonical_verb("format\\:check"), "format:check")
        self.assertEqual(canonical_verb("format-check"), "format:check")
        self.assertEqual(canonical_verb("format:check"), "format:check")

    def test_any_other_name_is_itself(self):
        self.assertEqual(canonical_verb("typecheck"), "typecheck")
        self.assertEqual(canonical_verb("format"), "format")
        self.assertEqual(canonical_verb("lint-all"), "lint-all")


if __name__ == "__main__":
    unittest.main()
