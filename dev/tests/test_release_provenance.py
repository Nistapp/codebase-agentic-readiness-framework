# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The release workflow signs build provenance for the files it publishes, from the tag it builds.

The provenance records the ref and commit that the run started from, not the commit it checked out. So
``release-please.yml`` must start ``release.yml`` from the tag, and ``release.yml`` must refuse any other ref. The
signed bundle is attached to the release, because ``gh attestation verify`` without ``--bundle`` needs a GitHub login.
How users verify: ``docs/how-to/install-the-skills.md``. The workflows are YAML; the standard library has no YAML
parser, so these tests read the text.
"""

from __future__ import annotations

import re
import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from _dev_paths import REPO

RELEASE = REPO / ".github" / "workflows" / "release.yml"
RELEASE_PLEASE = REPO / ".github" / "workflows" / "release-please.yml"
PROVENANCE_PERMISSIONS = ("contents: write", "id-token: write", "attestations: write", "artifact-metadata: write")


def job_permissions(text: str) -> list[str]:
    """The lines of the first job-level ``permissions:`` block (indented four spaces)."""
    block = re.search(r"(?m)^    permissions:\n((?:      \S.*\n)+)", text)
    return [line.strip() for line in block.group(1).splitlines()] if block else []


class ReleaseSignsProvenance(unittest.TestCase):
    def setUp(self) -> None:
        self.text = RELEASE.read_text(encoding="utf-8")

    def test_attests_the_files_in_the_checksums(self) -> None:
        self.assertRegex(self.text, r"uses: actions/attest@[0-9a-f]{40} # v\d+\.\d+\.\d+")
        self.assertIn("subject-checksums: ${{ env.RELEASE_DIR }}/SHA256SUMS", self.text)

    def test_attests_after_the_files_are_collected_and_before_the_upload(self) -> None:
        collect = self.text.index("name: Collect the release files")
        attest = self.text.index("uses: actions/attest@")
        upload = self.text.index("name: Attach the files to the release")
        self.assertLess(collect, attest)
        self.assertLess(attest, upload)

    def test_the_bundle_is_a_release_file(self) -> None:
        self.assertIn('cp "$BUNDLE" "$RELEASE_DIR/$TAG.sigstore.json"', self.text)

    def test_permissions_are_on_the_job_only(self) -> None:
        self.assertRegex(self.text, r"(?m)^permissions: \{\}$")
        self.assertEqual(sorted(job_permissions(self.text)), sorted(PROVENANCE_PERMISSIONS))

    def test_refuses_a_run_that_did_not_start_from_the_tag(self) -> None:
        self.assertIn("RUN_REF: ${{ github.ref }}", self.text)
        self.assertIn('if [[ "$RUN_REF" != "refs/tags/$TAG" ]]; then', self.text)
        guard = self.text.index("name: Require the run to start from the tag")
        self.assertLess(guard, self.text.index("name: Gates"))


class ReleasePleaseStartsFromTheTag(unittest.TestCase):
    def test_dispatch_uses_the_tag_as_the_ref(self) -> None:
        text = RELEASE_PLEASE.read_text(encoding="utf-8")
        self.assertIn('gh workflow run release.yml --repo "$GITHUB_REPOSITORY" --ref "$TAG" -f "tag=$TAG"', text)
        self.assertNotIn("--ref main", text)


if __name__ == "__main__":
    unittest.main()
