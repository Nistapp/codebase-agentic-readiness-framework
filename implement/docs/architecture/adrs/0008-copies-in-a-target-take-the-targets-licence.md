# 0008. Text and Code Placed in a Target Take the Target's Own Licence

## Context

An implement run writes into a repository this project does not own. Some of that text is generated for the target.
Some is copied or adapted from [`greenfield/templates/`](../../../../greenfield/templates/), which is MIT-0. Some is
code copied from [`playbooks/templates/`](../../../playbooks/templates/), which is AGPL-3.0-or-later here and carries
a copyright line. [Licensing](../../../../docs/reference/licensing.md) says which licence covers which path.

A target can be under any licence, open or proprietary. An agent that copies a file tends to keep its licence line,
or to offer the owner a short list of licences. Both give the target a file whose licence differs from the rest of
its tree.

The project's copyright holder decided the policy below. Why this policy and not another: Rationale not recorded;
owner to fill in.

## Decision

1. **The target's licence applies.** Text and code that the implement step generates, or copies into a target, take
   the target's own licence. This holds even for a word-for-word copy.
2. **The project grants the relicensing.** The copyright holder licenses that text and code so that the target may
   relicense its copy under its own licence. The grant is stated in
   [licensing](../../../../docs/reference/licensing.md#what-an-implement-run-puts-into-your-repository). The file in
   this repository keeps its own licence.
3. **Greenfield templates need no step.** MIT-0 ([`LICENSE-TEMPLATES`](../../../../LICENSE-TEMPLATES)) already
   allows the copy to take another licence, with no notice.
4. **A code template's copy names the target's licence.** The playbook replaces the template's SPDX line with the
   target's licence and keeps the copyright line. It never leaves this repository's licence line on the copy.
5. **The licence is read, then asked.** The playbook reads the target's root licence file and its manifest. It asks
   the owner when no licence file exists or the licence is unclear. It records the answer as a preference
   (`docs.prose_check_licence` in [`establish-docs-contract`](../../../playbooks/establish-docs-contract.md)). It
   never guesses, and never offers a list of licences to pick from.
6. **The sources stay narrow.** A playbook copies text only from `greenfield/templates/` and code only from
   `playbooks/templates/` ([rules for every playbook](../../../playbooks/README.md#anatomy)).
7. **A change to a code template needs the same grant.** Only the copyright holder changes code in
   `playbooks/templates/`, or a contributor who agrees in writing to the relicensing
   ([`implement/AGENTS.md`](../../../AGENTS.md#rules)).

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| The owner picks `MIT`, `Apache-2.0` or `BSD-3-Clause` for a copied code template | A target under any other licence had to skip the template, or hold one file under a licence that is not its own. |
| Keep this repository's licence on the copy | The copy would carry AGPL-3.0-or-later into a target that is not under it. |
| Copy text from this repository's `docs/` as well | Those pages are GFDL 1.3 and are not written to be copied; the templates are. |
| A tool detects the licence | The licence file of a target is free text; the agent reads it and the owner confirms. A tool can follow when a second code template needs it. |

## Consequences

### Positive

- A target's tree stays under one licence after an implement run.
- The owner is not asked to choose a licence when the repository already states one.

### Negative / Trade-offs

- The rule lives in the recipe. No tool checks the licence line of a copy on a real run; only the paid implement
  eval does (its assertion A11).
- A target with no licence file needs one more answer from its owner.
- The grant is a policy statement of the copyright holder. A target that needs certainty has its counsel review it.
