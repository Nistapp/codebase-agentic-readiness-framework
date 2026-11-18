# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the completeness sweep: triggers, units, kinds, scope, ``--at`` and the output forms."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable, Sequence

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import doc_index
from docindex import cli, sweep
from docindex.gitread import GitError, RefTree, WorkTree
from docindex.markdown import parse

PATH = "docs/page.md"
CONFIG = doc_index.load_config()
ALL = sweep.select_triggers(CONFIG, "all")
GROUP1 = sweep.select_triggers(CONFIG, "group1")

GROUP1_WORDS = (
    *("must", "never", "always", "only", "do not", "may not", "required", "stop", "refuse", "before", "after"),
    *("at most", "at least"),
)
GROUP2_WORDS = ("requires", "needs", "first", "each", "every", "except", "nothing")

#: One sentence per trigger word that holds that trigger and no other trigger.
TRIGGER_SENTENCES = {
    "must": "You must sign the form.",
    "never": "Never sign the form.",
    "always": "Always sign the form.",
    "only": "Sign the form only.",
    "do not": "Do not sign the form.",
    "may not": "You may not sign the form.",
    "required": "A signature is required.",
    "stop": "Stop when the form is signed.",
    "refuse": "Refuse an unsigned form.",
    "before": "Sign the form before lunch.",
    "after": "Sign the form after lunch.",
    "at most": "Sign at most two forms.",
    "at least": "Sign at least two forms.",
    "requires": "The form requires a signature.",
    "needs": "The form needs a signature.",
    "first": "Sign the form first.",
    "each": "Sign each form.",
    "every": "Sign every form.",
    "except": "Sign all forms except this one.",
    "nothing": "Nothing is signed here.",
}


def _items(text: str, triggers: Sequence[str] = ALL, path: str = PATH) -> list[sweep.Item]:
    return sweep.items_of(parse(path, text), triggers)


def _texts(text: str, triggers: Sequence[str] = ALL) -> list[str]:
    return [item.text for item in _items(text, triggers)]


def _one(test: unittest.TestCase, text: str) -> sweep.Item:
    items = _items(text)
    test.assertEqual(len(items), 1, [item.text for item in items])
    return items[0]


# --- Triggers -------------------------------------------------------------------------------------------------------


class TriggerTest(unittest.TestCase):
    """One generated test per trigger word (``test_trigger_<word>``), plus the group rules."""

    def test_the_config_holds_both_groups(self) -> None:
        self.assertEqual(GROUP1, GROUP1_WORDS)
        self.assertEqual(ALL, GROUP1_WORDS + GROUP2_WORDS)
        self.assertEqual(set(TRIGGER_SENTENCES), set(ALL))

    def test_triggers_are_whole_words(self) -> None:
        self.assertEqual(_texts("Mustard for everyone, the first-run offer and a stopwatch."), [])

    def test_triggers_ignore_case(self) -> None:
        self.assertEqual(_one(self, "NEVER sign the form.").triggers, ("never",))

    def test_a_two_word_trigger_matches_across_a_line_break(self) -> None:
        self.assertEqual(_one(self, "You do\nnot sign the form.").triggers, ("do not",))

    def test_group1_misses_what_all_flags(self) -> None:
        line = "Every public method requires positive and negative tests."
        self.assertEqual(_texts(line, GROUP1), [])
        item = _one(self, line)
        self.assertEqual(item.triggers, ("every", "requires"))
        self.assertEqual(item.text, line)

    def test_an_unknown_selection_or_a_missing_group_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            sweep.select_triggers(CONFIG, "group2")
        with self.assertRaises(ValueError):
            sweep.select_triggers({"sweep": {"triggers": {"group1": ["must"]}}}, "all")


def _trigger_test(word: str, sentence: str) -> Callable[[TriggerTest], None]:
    def test(self: TriggerTest) -> None:
        self.assertEqual(_one(self, sentence).triggers, (word,))
        self.assertEqual(len(_items(sentence, GROUP1)), 1 if word in GROUP1_WORDS else 0)

    return test


for _word, _sentence in TRIGGER_SENTENCES.items():
    setattr(TriggerTest, f"test_trigger_{_word.replace(' ', '_')}", _trigger_test(_word, _sentence))


class PatternTriggerTest(unittest.TestCase):
    def test_a_number_with_a_unit_or_a_limit(self) -> None:
        for text in ("Keep a page under 500 lines.", "A name has 25 characters.", "Coverage is 90%.", "Use up to 3."):
            with self.subTest(text=text):
                self.assertEqual(_one(self, text).triggers, ("limit",))
        self.assertEqual(_texts("Python 3.11 or newer, as ADR 0011 says."), [])

    def test_an_exit_code(self) -> None:
        for text in ("The tool exits 2 on a bad report.", "A bug gives exit 3.", "It ends with exit code 1."):
            with self.subTest(text=text):
                self.assertEqual(_one(self, text).triggers, ("exit-code",))

    def test_a_path_that_is_written(self) -> None:
        self.assertEqual(_one(self, "The build writes `dev/dist/skills/`.").triggers, ("path-write",))
        self.assertEqual(_one(self, "Agents edit docs/how-to/page.md here.").triggers, ("path-write",))
        self.assertEqual(_texts("The build writes. See `dev/dist/` for the bundle."), [])


# --- Units ----------------------------------------------------------------------------------------------------------


class UnitTest(unittest.TestCase):
    def test_wrapped_lines_are_joined_and_whitespace_normalised(self) -> None:
        text = "You   must sign\n   the form\tnow.\n\nA plain line.\n"
        self.assertEqual(_texts(text), ["You must sign the form now."])

    def test_list_items_lose_their_markers_and_nested_numbers(self) -> None:
        text = "- You must sign.\n  It is late.\n- [x] Never wait.\n\n1. 4.2 Always ask.\n   1) Do not run.\n"
        self.assertEqual(_texts(text), ["You must sign. It is late.", "Never wait.", "Always ask.", "Do not run."])

    def test_a_block_quote_loses_its_marker(self) -> None:
        self.assertEqual(_texts("> You must sign\n> the form.\n"), ["You must sign the form."])

    def test_a_fenced_command_block_is_one_item(self) -> None:
        text = "# Commands\n\n```bash\nmake setup   # check\nmake  check\n```\n"
        item = _one(self, text)
        self.assertEqual((item.kind, item.triggers, item.text), ("command", (), "make setup # check\nmake check"))
        self.assertEqual(item.address, f"{PATH}#commands")
        self.assertEqual(item.lines, (3, 4, 5, 6))

    def test_an_untagged_fence_of_commands_is_a_command_block(self) -> None:
        for body in ("$ ls\n", "python3 dev/doc_index.py sweep\n", "git status\n"):
            with self.subTest(body=body):
                self.assertEqual(_one(self, f"```\n{body}```\n").kind, "command")

    def test_other_fences_are_not_prose(self) -> None:
        text = "```python\n# You must never do this.\nmakefile = 1\n```\n\n~~~\nEvery line must stop.\n~~~\n"
        self.assertEqual(_texts(text), [])

    def test_a_heading_in_a_fence_is_ignored(self) -> None:
        text = "# Real\n\n```markdown\n# Not a heading\n```\n\nYou must sign.\n"
        self.assertEqual(_one(self, text).address, f"{PATH}#real")

    def test_a_table_row_is_an_item(self) -> None:
        text = "| Rule | Why |\n|---|---|\n| You must sign | the law |\n| Lunch | food |\n"
        item = _one(self, text)
        self.assertEqual(item.text, "You must sign | the law")
        self.assertEqual(item.triggers, ("must",))

    def test_every_row_of_a_tool_table_is_an_item(self) -> None:
        text = "| Tool | What it does |\n|---|---|\n| `engine.py` | reads a repo |\n| `facts.py` | lists facts |\n"
        items = _items(text)
        self.assertEqual([item.text for item in items], ["`engine.py` | reads a repo", "`facts.py` | lists facts"])
        self.assertEqual({item.kind for item in items}, {"tool-contract"})

    def test_headings_comments_and_frontmatter_are_not_items(self) -> None:
        text = "---\nnote: you must\n---\n# You must\n\n<!-- You must sign. -->\n\n---\n"
        self.assertEqual(_texts(text), [])


# --- Kinds ----------------------------------------------------------------------------------------------------------


class KindTest(unittest.TestCase):
    CASES = {
        "prohibition": "Never push.",
        "required-step": "You must run the gate.",
        "ordering": "Read the plan before you edit.",
        "stop-condition": "Stop when the gate fails.",
        "threshold": "Lines hold at most 100 characters.",
        "output-format": "The report is JSON, except in text mode.",
        "command": "```sh\nmake check\n```\n",
        "tool-contract": "The tool exits 2 on a bad report.",
        "question": "Except for a typo fix, ask the user.",
        "default": "Except when set, the default is text.",
    }

    def test_each_kind_has_a_case(self) -> None:
        self.assertEqual(tuple(self.CASES), sweep.KINDS)

    def test_the_kind_of_each_rule(self) -> None:
        for kind, text in self.CASES.items():
            with self.subTest(kind=kind):
                self.assertEqual(_one(self, text).kind, kind)

    def test_the_first_kind_in_list_order_wins(self) -> None:
        self.assertEqual(_one(self, "You must never push before the gate.").kind, "prohibition")
        self.assertEqual(_one(self, "Run the gate first, then stop.").kind, "ordering")

    def test_an_item_that_no_rule_fits_is_a_required_step(self) -> None:
        self.assertEqual(_one(self, "Sign all forms except this one.").kind, "required-step")


# --- Scope ----------------------------------------------------------------------------------------------------------


class ScopeTest(unittest.TestCase):
    FILES = (
        "README.md",
        "RULES.md",
        "artefacts/RULES.md",
        "bundle/SKILL.md",
        "bundle/checks/a.md",
        "bundle/checks/tool.py",
        "docs/other.md",
        "fixtures/RULES.md",
        "templates/deep/page.md",
    )
    CONFIG: dict[str, Any] = {
        "exclude": {"list_only": ["fixtures/"], "skip": ["artefacts/"]},
        "file_kinds": {".md": "markdown", ".py": "python"},
        "sweep": {"file_names": ["RULES.md"], "paths": ["templates/"]},
    }

    def test_sources_paths_and_names_outside_the_exclusions(self) -> None:
        self.assertEqual(
            sweep.scope(self.FILES, self.CONFIG, ["bundle/checks", "bundle/SKILL.md", "gone/"]),
            ["RULES.md", "bundle/SKILL.md", "bundle/checks/a.md", "templates/deep/page.md"],
        )

    def test_the_repository_scope_comes_from_the_bundle_module(self) -> None:
        sources = doc_index.bundle_sources(CONFIG)
        self.assertIn("audit/SKILL.md", sources)
        self.assertIn("implement/SKILL.md", sources)
        self.assertIn("audit/checks", sources)
        paths = sweep.scope(WorkTree(doc_index.REPO).files(), CONFIG, sources)
        self.assertIn("AGENTS.md", paths)
        self.assertIn("implement/playbooks/register-index.md", paths)
        self.assertTrue(any(path.startswith("greenfield/templates/") for path in paths))
        self.assertFalse(any(path.startswith("audit/engine/tests/fixtures/") for path in paths))


# --- --at and the command line --------------------------------------------------------------------------------------

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Sweep Test",
    "GIT_AUTHOR_EMAIL": "sweep@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Sweep Test",
    "GIT_COMMITTER_EMAIL": "sweep@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

#: The temporary repository's config: no fixture file is named like the repository's own instruction files.
_REPO_CONFIG: dict[str, Any] = {
    "exclude": {"list_only": [], "skip": []},
    "file_kinds": {".md": "markdown"},
    "sweep": {"file_names": ["RULES.md"], "paths": ["templates/"], "triggers": CONFIG["sweep"]["triggers"]},
}


class GitRepoTest(unittest.TestCase):
    """A two-commit repository built in a temporary folder: the first commit is ``HEAD~1``."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self._git("init", "-q")
        self._write("RULES.md", "# Rules\n\nYou must sign.\n")
        self._write("bundle/guide.md", "# Guide\n\nNever push.\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "first")
        self._write("RULES.md", "# Rules\n\nYou must sign.\n\nAlways ask.\n")
        self._write("templates/new.md", "# New\n\nStop here.\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "second")

    def _git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True)

    def _write(self, path: str, text: str) -> None:
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv, _REPO_CONFIG, root=self.root, bundle_sources=lambda: ["bundle"])
        return code, out.getvalue(), err.getvalue()

    def test_at_reads_the_files_at_the_ref(self) -> None:
        tree = RefTree(self.root, "HEAD~1")
        self.assertEqual(tree.files(), ["RULES.md", "bundle/guide.md"])
        self.assertEqual(tree.read("RULES.md"), "# Rules\n\nYou must sign.\n")
        self.assertIsNone(tree.read("templates/new.md"))

    def test_at_resolves_the_scope_at_the_ref(self) -> None:
        code, out, err = self._run(["sweep", "--at", "HEAD~1", "--format", "json"])
        self.assertEqual((code, err), (0, ""))
        data = json.loads(out)
        self.assertEqual(data["at"], "HEAD~1")
        self.assertEqual(data["counts"], {"RULES.md": 1, "bundle/guide.md": 1})
        self.assertEqual([item["text"] for item in data["items"]], ["You must sign.", "Never push."])

    def test_without_at_the_working_tree_is_swept(self) -> None:
        self._write("RULES.md", "# Rules\n\nRefuse a stale report.\n")
        code, out, _err = self._run(["sweep", "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["counts"], {"RULES.md": 1, "bundle/guide.md": 1, "templates/new.md": 1})
        self.assertEqual(data["items"][0]["text"], "Refuse a stale report.")

    def test_a_bad_ref_exits_1(self) -> None:
        for ref in ("no-such-ref", "--output=x"):
            with self.subTest(ref=ref):
                code, out, err = self._run(["sweep", f"--at={ref}"])
                self.assertEqual((code, out), (1, ""))
                self.assertIn("does not name a commit" if ref[0] != "-" else "not a git ref", err)
        with self.assertRaises(GitError):
            WorkTree(self.root / "missing").files()

    def test_the_json_is_byte_identical_over_two_runs(self) -> None:
        first = self._run(["sweep", "--format", "json"])
        second = self._run(["sweep", "--format", "json"])
        self.assertEqual(first[1].encode("utf-8"), second[1].encode("utf-8"))
        self.assertNotIn(str(self.root), first[1])

    def test_the_json_form(self) -> None:
        code, out, _err = self._run(["sweep", "--at", "HEAD", "--format", "json", "--triggers", "group1"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(sorted(data), ["at", "counts", "format", "items", "triggers"])
        self.assertEqual(data["triggers"], "group1")
        first = {"address": "RULES.md#rules", "kind": "required-step", "path": "RULES.md", "text": "You must sign."}
        self.assertEqual(data["items"][0], {**first, "triggers": ["must"]})
        self.assertEqual(out, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        self.assertEqual([item["path"] for item in data["items"]], sorted(item["path"] for item in data["items"]))

    def test_the_text_form_has_one_block_per_item_and_counts_on_stderr(self) -> None:
        code, out, err = self._run(["sweep", "--at", "HEAD"])
        self.assertEqual(code, 0)
        blocks = out.split("\n\n")
        self.assertEqual(len(blocks), 4)
        self.assertEqual(blocks[0], "RULES.md#rules\n  kind: required-step\n  triggers: must\n  You must sign.")
        self.assertIn("     2  RULES.md\n", err)
        self.assertIn("4  items in 3 files", err)

    def test_a_usage_error_exits_2(self) -> None:
        for argv in (["sweep", "--triggers", "group2"], ["sweep", "--format", "yaml"], ["sweep", "--at"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                cli.main(argv, _REPO_CONFIG, root=self.root)
            self.assertEqual(raised.exception.code, 2)


class RepositorySweepTest(unittest.TestCase):
    def test_the_repository_sweep_is_deterministic(self) -> None:
        runs: list[str] = []
        for _ in range(2):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(doc_index.main(["sweep", "--format", "json"]), 0)
            runs.append(out.getvalue())
        self.assertEqual(runs[0].encode("utf-8"), runs[1].encode("utf-8"))
        self.assertNotIn(str(doc_index.REPO), runs[0])
        data = json.loads(runs[0])
        self.assertGreater(data["counts"]["AGENTS.md"], 0)
        self.assertLessEqual({item["kind"] for item in data["items"]}, set(sweep.KINDS))


if __name__ == "__main__":
    unittest.main()
