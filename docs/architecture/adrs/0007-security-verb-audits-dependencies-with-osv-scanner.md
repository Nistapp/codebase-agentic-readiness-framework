# 0007. The Security Verb Audits the Dev Tools' Dependencies with osv-scanner

## Context

A security verb that runs only a secrets scan leaves `TOOL-04` at PARTIAL in the repository's own audit: the verb
exists, but it runs no dependency audit. The engine and the tools have no third-party dependencies. The dev tools
do: about 500 packages across `dev/tools/uv.lock`, `dev/tools/package-lock.json` and their own dependencies
([ADR 0003](0003-dependabot-security-pull-requests-only.md)).

The engine's `TOOL-04` reads only the seven framework verbs. It reads the recipe text: it does not expand Make
variables or follow a prerequisite target. A separate `make deps-audit` target would leave `TOOL-04` at PARTIAL.

The owner wants the most effective tool. Contributors may install a toolchain; users may not, and users never run
`make security`: they run the standard-library `audit.pyz` and the skill bundles.

## Decision

1. **osv-scanner runs inside `make security`.** After the secrets scan, the
   [`Makefile`](../../../Makefile) runs osv-scanner on every dev-tool lockfile: `dev/tools/uv.lock`,
   `dev/tools/package-lock.json` and the Go tool modules (`dev/tools/osv/go.mod`, `dev/tools/actionlint/go.mod`).
   The tool name is written in the recipe, so `TOOL-04`
   sees it.
2. **osv-scanner is a Go `tool` requirement.** [`dev/tools/osv/go.mod`](../../../dev/tools/osv/go.mod) pins a
   tagged release; `go.sum` holds the checksums. `go -C dev/tools/osv tool osv-scanner` builds and runs it. The
   version is written once, and Dependabot's `gomod` entry sees it, under the policy of ADR 0003.
3. **A known vulnerability fails the gate.** osv-scanner exits non-zero, so `make security` and `CI Gate` fail.
4. **Exceptions are reviewed and expire.** An `osv-scanner.toml` next to the lockfiles it covers
   ([`dev/tools/osv-scanner.toml`](../../../dev/tools/osv-scanner.toml), `dev/tools/osv/osv-scanner.toml`) lists each
   accepted vulnerability with an `id`, a `reason` and an `ignoreUntil` date at most six months ahead.
   [`test_tool_pins.py`](../../../dev/tests/test_tool_pins.py) checks the format and the six-month limit. When the
   date passes, the scan fails again. `make security` passes no `--config`, so osv-scanner reads these files the way
   OpenSSF Scorecard does.
5. **No offline switch.** `make security` needs the network (osv.dev). CI has it; a contributor without it cannot
   run the gate.
6. **Contributors need Go 1.27 or newer.** `make setup` checks for it. actionlint is a Go tool
   too (`make check`). CI installs it with `actions/setup-go` from
   `go.mod`; the release job does so without a cache.

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| pip-audit plus `npm audit --package-lock-only` | Two tools and a `uv export` step. Two advisory sources instead of OSV, which aggregates GitHub advisories, PyPA and the Go database. osv-scanner reads `uv.lock` directly. |
| A separate `make deps-audit`; `security` stays offline | `TOOL-04` stays PARTIAL. Changing the engine to accept it would bend a check to suit this repository. |
| An `OFFLINE=1` switch that skips the audit | A skip switch on a gate. CI would never set it, but it invites use. |
| osv-scanner binary on `PATH`, version in a pin file | Dependabot cannot see a pin file. Every contributor installs it by hand, at any version. |
| `google/osv-scanner-action` in CI only | CI would run something other than `make security`. Local and CI results could differ. |
| Report only, exit 0 | `TOOL-04` would pass on a check that never blocks. |
| actionlint through its PyPI wrapper | The wrapper downloads the binary from GitHub releases on each install, so a GitHub outage fails CI. |
| Scan only the Python and Node lockfiles | The Go modules of osv-scanner itself would raise Dependabot alerts that no gate checks. |

## Consequences

### Positive

* `TOOL-04` passes. A known vulnerability in any dev tool blocks a merge.
* One advisory source (OSV) and one tool for Python, Node and Go. The same tool fits target repositories of any stack.
* Each accepted vulnerability has a written reason and an end date.

### Negative / Trade-offs

* `make security` needs the network and Go. The first run builds osv-scanner (about 30 seconds); later runs use
  the Go build cache.
* A new advisory turns every pull request red until someone fixes or accepts it. That is intended.
* `go.mod` and `go.sum` add about 700 lines. A raised indirect Go dependency differs from the set that upstream
  osv-scanner tested.
