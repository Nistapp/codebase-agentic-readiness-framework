# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the bundle manifest and its diff (``doc_index.py manifest`` and ``manifest-diff``)."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import time
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import doc_index
from docindex import cli, manifest

AUDIT = "agentic-readiness-audit"
IMPLEMENT = "agentic-readiness-implement"


def _write(root: Path, path: str, data: bytes | str) -> None:
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    file.write_bytes(data)


def _archive(root: Path, path: str, members: dict[str, str], date_time: tuple[int, int, int, int, int, int]) -> None:
    """A zip with a shebang prefix, as ``zipapp`` writes one, whose every entry carries ``date_time``."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=date_time), text)
    _write(root, path, b"#!/usr/bin/env python3\n" + buffer.getvalue())


def _bundles(root: Path, changes: dict[str, str | None] | None = None) -> None:
    """Two small bundles; ``changes`` overrides a file (``AUDIT/LICENSE``-style keys), ``None`` drops it."""
    files: dict[str, str | None] = {
        f"{AUDIT}/LICENSE": "licence\n",
        f"{AUDIT}/SKILL.md": "# Audit\n",
        f"{AUDIT}/references/checks/one.md": "# One\n",
        f"{IMPLEMENT}/SKILL.md": "# Implement\n",
        f"{IMPLEMENT}/scripts/tools/progress.py": "print('progress')\n",
    }
    files.update(changes or {})
    for path, text in files.items():
        if text is not None:
            _write(root, path, text)


class _Temp(unittest.TestCase):
    def _folder(self) -> Path:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Path(folder.name)


class ManifestTest(_Temp):
    def test_lists_each_bundle_file_with_its_path_size_and_sha256(self) -> None:
        root = self._folder()
        _bundles(root)
        data = manifest.manifest(root)
        self.assertEqual(data["format"], manifest.MANIFEST_FORMAT)
        self.assertEqual(list(data["bundles"]), [AUDIT, IMPLEMENT])
        audit = data["bundles"][AUDIT]
        self.assertEqual([entry["path"] for entry in audit], ["LICENSE", "SKILL.md", "references/checks/one.md"])
        self.assertEqual(
            audit[2], {"path": "references/checks/one.md", "size": 6, "sha256": hashlib.sha256(b"# One\n").hexdigest()}
        )

    def test_the_json_is_the_same_for_the_same_content_in_any_folder_or_order(self) -> None:
        first, second = self._folder(), self._folder()
        _bundles(first)
        for path in sorted((p.relative_to(first) for p in first.rglob("*") if p.is_file()), reverse=True):
            _write(second, path.as_posix(), (first / path).read_bytes())
        text = manifest.to_json(manifest.manifest(first))
        self.assertEqual(text, manifest.to_json(manifest.manifest(second)))
        self.assertEqual(text, manifest.to_json(manifest.manifest(first)))
        self.assertNotIn(str(first), text)
        self.assertTrue(text.endswith("}\n"))

    def test_a_file_outside_every_bundle_is_refused(self) -> None:
        root = self._folder()
        _bundles(root)
        _write(root, "stray.txt", "x")
        with self.assertRaisesRegex(manifest.ManifestError, "stray.txt"):
            manifest.manifest(root)

    def test_an_empty_folder_has_no_bundles(self) -> None:
        self.assertEqual(manifest.manifest(self._folder())["bundles"], {})


class ArchiveTest(_Temp):
    MEMBERS = {"audit/__init__.py": "", "__main__.py": "entry()\n"}

    def _entry(self, root: Path) -> dict[str, Any]:
        entries = manifest.manifest(root)["bundles"][AUDIT]
        return next(entry for entry in entries if entry["path"] == "scripts/audit.pyz")

    def test_audit_pyz_gets_a_members_digest_in_place_of_sha256(self) -> None:
        root = self._folder()
        _archive(root, f"{AUDIT}/scripts/audit.pyz", self.MEMBERS, (2026, 1, 1, 0, 0, 0))
        entry = self._entry(root)
        self.assertNotIn("sha256", entry)
        self.assertEqual(set(entry), {"path", "size", "members_sha256"})

    def test_entry_times_do_not_change_the_digest_or_the_diff(self) -> None:
        old, new = self._folder(), self._folder()
        _archive(old, f"{AUDIT}/scripts/audit.pyz", self.MEMBERS, (2026, 1, 1, 0, 0, 0))
        _archive(new, f"{AUDIT}/scripts/audit.pyz", self.MEMBERS, (2026, 6, 2, 12, 30, 0))
        pyz = f"{AUDIT}/scripts/audit.pyz"
        self.assertNotEqual((old / pyz).read_bytes(), (new / pyz).read_bytes())
        self.assertEqual(self._entry(old), self._entry(new))
        self.assertEqual(manifest.compare(manifest.manifest(old), manifest.manifest(new)), ())

    def test_a_changed_member_changes_the_digest_and_shows_in_the_diff(self) -> None:
        old, new = self._folder(), self._folder()
        _archive(old, f"{AUDIT}/scripts/audit.pyz", self.MEMBERS, (2026, 1, 1, 0, 0, 0))
        edited = {**self.MEMBERS, "__main__.py": "entry(1)\n"}
        _archive(new, f"{AUDIT}/scripts/audit.pyz", edited, (2026, 1, 1, 0, 0, 0))
        self.assertNotEqual(self._entry(old)["members_sha256"], self._entry(new)["members_sha256"])
        changes = manifest.compare(manifest.manifest(old), manifest.manifest(new))
        self.assertEqual(changes, (manifest.BundleChange(AUDIT, (), (), ("scripts/audit.pyz",)),))

    def test_an_archive_that_is_not_a_zip_is_refused(self) -> None:
        root = self._folder()
        _write(root, f"{AUDIT}/scripts/audit.pyz", "not a zip")
        with self.assertRaisesRegex(manifest.ManifestError, "audit.pyz"):
            manifest.manifest(root)

    def test_the_archive_names_are_a_parameter(self) -> None:
        root = self._folder()
        _write(root, f"{AUDIT}/scripts/audit.pyz", "not a zip")
        entry = self._entry_with(root, ())
        self.assertEqual(entry["sha256"], hashlib.sha256(b"not a zip").hexdigest())

    def _entry_with(self, root: Path, archives: tuple[str, ...]) -> dict[str, Any]:
        entries = manifest.manifest(root, archives)["bundles"][AUDIT]
        return next(entry for entry in entries if entry["path"] == "scripts/audit.pyz")


class CompareTest(_Temp):
    def _pair(self, changes: dict[str, str | None]) -> tuple[dict[str, Any], dict[str, Any]]:
        old, new = self._folder(), self._folder()
        _bundles(old)
        _bundles(new, changes)
        return manifest.manifest(old), manifest.manifest(new)

    def test_unchanged_bundles_give_no_change(self) -> None:
        old, new = self._pair({})
        self.assertEqual(manifest.compare(old, new), ())
        self.assertEqual(manifest.to_text(()), "no bundle file changed\n")

    def test_added_removed_and_changed_files_are_listed_per_bundle_and_sorted(self) -> None:
        old, new = self._pair(
            {
                f"{AUDIT}/references/checks/zeta.md": "# Zeta\n",
                f"{AUDIT}/references/checks/alpha.md": "# Alpha\n",
                f"{AUDIT}/LICENSE": None,
                f"{AUDIT}/SKILL.md": "# Audit, edited\n",
                f"{IMPLEMENT}/scripts/tools/progress.py": "print('PROGRESS')\n",
            }
        )
        changes = manifest.compare(old, new)
        self.assertEqual(
            changes,
            (
                manifest.BundleChange(
                    AUDIT, ("references/checks/alpha.md", "references/checks/zeta.md"), ("LICENSE",), ("SKILL.md",)
                ),
                manifest.BundleChange(IMPLEMENT, (), (), ("scripts/tools/progress.py",)),
            ),
        )
        self.assertEqual(
            manifest.to_text(changes),
            f"bundle {AUDIT}: 2 added, 1 removed, 1 changed\n"
            "  added   references/checks/alpha.md\n"
            "  added   references/checks/zeta.md\n"
            "  removed LICENSE\n"
            "  changed SKILL.md\n"
            f"bundle {IMPLEMENT}: 0 added, 0 removed, 1 changed\n"
            "  changed scripts/tools/progress.py\n",
        )
        self.assertEqual(
            json.loads(manifest.diff_to_json(changes))["bundles"][AUDIT],
            {
                "added": ["references/checks/alpha.md", "references/checks/zeta.md"],
                "removed": ["LICENSE"],
                "changed": ["SKILL.md"],
            },
        )

    def test_a_bundle_on_one_side_only_has_all_its_files_added_or_removed(self) -> None:
        old, new = self._pair({})
        gone = {"format": manifest.MANIFEST_FORMAT, "bundles": {AUDIT: old["bundles"][AUDIT]}}
        self.assertEqual(
            manifest.compare(gone, new),
            (manifest.BundleChange(IMPLEMENT, ("SKILL.md", "scripts/tools/progress.py"), (), ()),),
        )
        self.assertEqual(
            manifest.compare(new, gone),
            (manifest.BundleChange(IMPLEMENT, (), ("SKILL.md", "scripts/tools/progress.py"), ()),),
        )

    def test_a_round_trip_through_json_keeps_the_comparison(self) -> None:
        old, new = self._pair({f"{AUDIT}/SKILL.md": "# Changed\n"})
        loaded = json.loads(manifest.to_json(new))
        self.assertEqual(manifest.compare(old, loaded), manifest.compare(old, new))

    def test_a_wrong_manifest_is_refused(self) -> None:
        good, _ = self._pair({})
        for bad in (
            [],
            {"format": "other", "bundles": {}},
            {"format": manifest.MANIFEST_FORMAT},
            {"format": manifest.MANIFEST_FORMAT, "bundles": {AUDIT: {}}},
            {"format": manifest.MANIFEST_FORMAT, "bundles": {AUDIT: [{"path": "a"}]}},
            {"format": manifest.MANIFEST_FORMAT, "bundles": {AUDIT: [{"path": "a", "size": 1}]}},
            {"format": manifest.MANIFEST_FORMAT, "bundles": {AUDIT: [{"path": "a", "size": 1, "sha256": "x"}] * 2}},
        ):
            with self.subTest(bad=bad), self.assertRaises(manifest.ManifestError):
                manifest.compare(good, bad)


def _run(argv: list[str], **kwargs: Any) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv, {}, **kwargs)
    return code, out.getvalue(), err.getvalue()


class ManifestCommandTest(_Temp):
    def _stub(self, seen: list[Path]) -> Callable[[Path], None]:
        def build(out_dir: Path) -> None:
            seen.append(out_dir)
            self.assertEqual(list(out_dir.iterdir()), [])
            _bundles(out_dir)

        return build

    def test_builds_into_a_fresh_temporary_folder_and_writes_the_manifest_to_stdout(self) -> None:
        seen: list[Path] = []
        code, out, err = _run(["manifest"], build_bundles=self._stub(seen))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())
        self.assertNotIn(doc_index.DEV / "dist", seen[0].resolve().parents)
        self.assertEqual(list(json.loads(out)["bundles"]), [AUDIT, IMPLEMENT])
        self.assertNotIn(str(seen[0]), out)

    def test_out_writes_the_same_manifest_to_a_file(self) -> None:
        target = self._folder() / "manifest.json"
        code, out, _ = _run(["manifest", "--out", str(target)], build_bundles=self._stub([]))
        self.assertEqual((code, out), (0, ""))
        _, again, _ = _run(["manifest"], build_bundles=self._stub([]))
        self.assertEqual(target.read_text(encoding="utf-8"), again)

    def test_a_failed_build_exits_1(self) -> None:
        def fail(out_dir: Path) -> None:
            raise manifest.BuildError("the engine build failed")

        code, out, err = _run(["manifest"], build_bundles=fail)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("doc_index.py manifest: the engine build failed", err)

    def test_without_a_build_the_core_says_so_and_exits_1(self) -> None:
        code, _, err = _run(["manifest"])
        self.assertEqual(code, 1)
        self.assertIn("dev/doc_index.py", err)

    def test_the_entry_point_refuses_the_projects_own_bundle_folder(self) -> None:
        config = doc_index.load_config()
        module = doc_index._bundle_module(config)
        assert module is not None
        with self.assertRaisesRegex(manifest.BuildError, "own bundle folder"):
            doc_index.build_bundles(config, Path(module.DEFAULT_OUT_DIR))

    def test_the_entry_point_builds_both_real_bundles(self) -> None:
        target = self._folder() / "manifest.json"
        dist = doc_index.DEV / "dist" / "skills"
        before = sorted(dist.rglob("*")) if dist.exists() else []
        start = time.monotonic()
        code = doc_index.main(["manifest", "--out", str(target)])
        elapsed = time.monotonic() - start
        self.assertEqual(code, 0)
        self.assertLess(elapsed, 30)
        self.assertEqual(sorted(dist.rglob("*")) if dist.exists() else [], before)
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(list(data["bundles"]), [AUDIT, IMPLEMENT])
        pyz = [entry for entry in data["bundles"][AUDIT] if entry["path"] == "scripts/audit.pyz"]
        self.assertEqual(len(pyz), 1)
        self.assertIn("members_sha256", pyz[0])
        self.assertIn("SKILL.md", [entry["path"] for entry in data["bundles"][IMPLEMENT]])


class ManifestDiffCommandTest(_Temp):
    def _files(self, changes: dict[str, str | None]) -> tuple[str, str]:
        folder = self._folder()
        old, new = folder / "old", folder / "new"
        _bundles(old)
        _bundles(new, changes)
        old_json, new_json = folder / "old.json", folder / "new.json"
        old_json.write_text(manifest.to_json(manifest.manifest(old)), encoding="utf-8")
        new_json.write_text(manifest.to_json(manifest.manifest(new)), encoding="utf-8")
        return str(old_json), str(new_json)

    def test_text_and_json_reports(self) -> None:
        old, new = self._files({f"{IMPLEMENT}/SKILL.md": None})
        code, out, err = _run(["manifest-diff", old, new])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, f"bundle {IMPLEMENT}: 0 added, 1 removed, 0 changed\n  removed SKILL.md\n")
        code, out, _ = _run(["manifest-diff", old, new, "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(out),
            {
                "format": manifest.DIFF_FORMAT,
                "bundles": {IMPLEMENT: {"added": [], "removed": ["SKILL.md"], "changed": []}},
            },
        )

    def test_no_change_still_exits_0(self) -> None:
        old, new = self._files({})
        self.assertEqual(_run(["manifest-diff", old, new]), (0, "no bundle file changed\n", ""))

    def test_an_unreadable_manifest_exits_1(self) -> None:
        old, _ = self._files({})
        missing = str(Path(old).parent / "missing.json")
        code, out, err = _run(["manifest-diff", old, missing])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("doc_index.py manifest-diff: cannot read", err)
        Path(missing).write_text("{", encoding="utf-8")
        self.assertEqual(_run(["manifest-diff", old, missing])[0], 1)


if __name__ == "__main__":
    unittest.main()
