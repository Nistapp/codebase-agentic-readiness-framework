## Summary

<!-- What the change does and why. Link the issue, if there is one. -->

## Checklist

- [ ] `make check` and `make security` pass
- [ ] `make docs-lint` passes when Markdown changed; Mermaid blocks validated (`make docs-mermaid FILES=<file.md>`)
- [ ] New code has tests; a new engine check has a fixture that fails exactly that check
- [ ] Documentation and decision records updated in the same change when an interface, behaviour or decision changed
- [ ] Commits follow Conventional Commits, one logical change each, with a `Roadmap-Step:` trailer when a track applies
- [ ] No gate weakened: no skipped test, no rule turned off, no assertion relaxed
