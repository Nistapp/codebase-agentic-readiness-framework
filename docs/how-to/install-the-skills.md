# How to install the skills from a release

> **Goal:** Use the audit and implement skills in your own project without a clone of this repository.
> **Audience:** Users of Claude Code (or any harness that reads `.claude/skills/`)
> **Status:** Live.

---

## Prerequisites

- [ ] Python 3.11 or newer on `PATH`
- [ ] `curl` (or a browser), `unzip` and `sha256sum` (on macOS: `shasum -a 256`)

The quicker path is a clone: see the quick start in the root [`README.md`](../../README.md). Use this page when you
want the skills inside another project instead.

---

## Step 1: Download the release files

Open the [releases page](https://github.com/Nistapp/codebase-agentic-readiness-framework/releases) and pick a tag,
for example `v0.3.0`. Download three files into an empty folder:

- `agentic-readiness-audit-<tag>.zip`
- `agentic-readiness-implement-<tag>.zip`
- `SHA256SUMS`

## Step 2: Check the files

```bash
sha256sum --ignore-missing -c SHA256SUMS
```

Expect `OK` for each zip. On macOS, use `shasum -a 256 --ignore-missing -c SHA256SUMS`. Do not use a zip that fails
this check.

## Step 3: Unzip into the skills folder

Unzip both into the `.claude/skills/` folder of the project where you start Claude Code:

```bash
mkdir -p /path/to/project/.claude/skills
unzip agentic-readiness-audit-<tag>.zip -d /path/to/project/.claude/skills
unzip agentic-readiness-implement-<tag>.zip -d /path/to/project/.claude/skills
```

Install the two bundles side by side. The implement skill runs the audit skill's engine. To upgrade, unzip a newer
release over the old folders.

## Step 4: Use them

Start Claude Code in that project and say, for example, "Audit /path/to/repo and write the output to /path/to/out".
Later, say "Start implementing the fixes on /path/to/repo based on /path/to/out/\<report\>.json".

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| The skill does not start | Check that `.claude/skills/agentic-readiness-audit/SKILL.md` exists in the folder where you started Claude Code. |
| A tool says Python is too old | Install Python 3.11 or newer and make sure `python3` runs it. |
| The implement skill cannot find the engine | Install the audit bundle beside it, from the same release. |
