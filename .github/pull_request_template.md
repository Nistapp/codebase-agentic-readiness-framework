<!-- The base branch is `dev`. Only the maintainer's promotion pull request from `dev` and release-please's release
     pull request target `main`. Any other pull request into `main` fails `Check source branch`.
     Do not edit CHANGELOG.md or a version: release-please writes them from the commit subjects.
     See RELEASE_PROCESS.md. -->

## Summary

<!-- What the change does and why. Link the issue, if there is one. -->

## Checklist

- [ ] The base branch is `dev`, and the head is a work branch named `<type>/<topic>` that started from `dev`
- [ ] `make check` and `make security` pass
- [ ] `make docs-lint` passes when Markdown changed; Mermaid blocks validated (`make docs-mermaid FILES=<file.md>`)
- [ ] New code has tests; a new engine check has a fixture that fails exactly that check
- [ ] Documentation and decision records updated in the same change when an interface, behaviour or decision changed
- [ ] Commits follow Conventional Commits, one logical change each, with a `Roadmap-Step:` trailer when a track applies
- [ ] No gate weakened: no skipped test, no rule turned off, no assertion relaxed
