# Tool choice

Two procedures of the [implement recipe](SKILL.md) for the tools a step needs: one for a tool the repository
does not have, one for a tool that is older than the repository's pin. Every stage that needs a tool follows them.

## When a needed tool is missing

A step needs a tool the repository does not have: a Markdown linter for a README, a formatter, a scanner. This
happens most often before the theme that owns the tool has run. Never pick the tool yourself. A stack profile's
recommendation or a playbook's recommendation is not the owner's pick.

1. **Read the preference first.** Use the owning playbook's key when one exists (`docs.lint_tools`, `format.*`,
   `lint.*`, `scanner.*`). Otherwise use `tool.<concern>`, for example `tool.markdown-lint`. A recorded answer
   stands: never ask it again.
2. **Stop and ask.** Send a [decision request](../audit/prompts/talking-to-the-user.md#decision-requests).
   Offer two to four current, maintained options from the owning playbook's "Inputs to ask" or the stack profile.
   Add a last option: none. Name the step that waits for the answer.
3. **Ask the scope too.**
   - One-off: run the tool once, outside the target (for example through `npx` or `uvx` at a pinned version).
     Nothing is added to the repository.
   - Adopt: add the tool, pinned, with its config, as a change in this theme's change list.

   When a later theme's playbook owns the tool, recommend one-off now and adoption in that theme. A one-off pick
   does not answer that playbook's adoption question; it still asks, and offers the one-off tool first.
4. **Discuss until the owner names one.** The owner may ask questions, compare options or name another tool.
   Answer with evidence: the latest release and its date, and the maintenance status. Install and run nothing
   until the owner names a tool and a scope.
5. **A blanket go-ahead is not a choice.** "Install whatever is needed" lets you ask; it picks no tool. Ask
   several tools' questions in one numbered message if you like, but each tool needs its own answer.
6. **Record at once.** `progress.py pref set <key> <tool> --reason "<owner's words>; scope <one-off|adopt>" --by
   owner --phase <phase>`.
7. **When the owner picks none.** Record `none` with the owner's words, so the question is not asked again. Then:
   - Say plainly which check cannot run, and what that leaves unchecked.
   - The item's own Verification needs the tool: the item is not `done`. End it `blocked` with the reason "owner
     chose no `<concern>` tool".
   - The check was only a side step, such as a README the item changed: end the item as usual. Add a `--note`
     that names the check not run.
   - List every check not run in each status report, and under "What was not done" in the pull request body and
     the close-out summary.

## When a found tool is older than needed

A tool on the machine can be older than the version the target pins: gitleaks 8.21.2 locally while CI pins
8.30.1. Results then differ between the machine and CI. Check the version every time; never assume it.

1. **Check before the first run.** Before a step first runs a tool in a session, run its version command (`gitleaks
   version`, `ruff --version`). Note which binary ran (`command -v <tool>`); a stale copy earlier on `PATH` can
   hide a newer one.
2. **Find the reference.** Use the version the target pins: in CI, a lockfile, a hook config or a tool manifest.
   When the target pins none, use the version the owning playbook cites. With no reference at all, record the
   local version and carry on.
3. **Sort the gap into one of three bands.**
   - **Same or newer:** carry on.
   - **Older but usable:** same major version, and the tool accepts the config and the flags the step uses. Warn
     in one line, record it (step 5) and carry on. Do not ask.
   - **Unacceptable:** another major version, or the tool rejects the config or a flag the step needs. Stop and
     ask (step 4).
4. **Ask, and respect the answer.** Send a
   [decision request](../audit/prompts/talking-to-the-user.md#decision-requests) with three options:
   - Upgrade on the machine. The owner does it, or approves the command you show them.
   - Run the pinned version once, outside the target (`npx`, `uvx`, or a checksum-verified download into a
     scratch folder). Nothing is installed on the machine or added to the repository.
   - Carry on with the local version.

   Name the step that waits. Upgrade nothing without the owner's yes. "Carry on" is a valid answer: take it.
5. **Record it.**
   - An owner's choice: `progress.py pref set tool.<tool>.version "<local> vs <reference>; <choice>" --reason
     "<owner's words>" --by owner --phase <phase>`. Do not ask again while both versions stay the same.
   - A usable gap: add a `--note "<tool> <local> vs <reference>, usable"` when you end the item that ran it.
6. **Report it.** Name each open gap under "What was not done" in status reports and the pull request body. Give
   the tool, both versions, and the warning that local results may differ from CI.
7. **When CI disagrees with a local run**, name the version gap first as a likely cause.
