# Security and data

For a security reviewer. This page says what runs, what leaves the machine, what is written and what can execute.

**Bottom line.** The tools and the agent run on the engineer's machine. The framework's tools make no network
calls. The one party that receives your code is the model provider of the coding agent you already use. The audit
says so and waits for an explicit yes. The audit never writes to the repository it reads, and it refuses to run
a command that changes files. The fix step commits only on local branches and never merges.

## What runs where

A run has three parts:

- **The coding agent.** It runs on the engineer's machine. It follows a skill: a set of
  instructions for an audit or for a fix run.
- **The tools.** They are Python scripts that use only the standard library. They run locally, and the agent
  calls them. They install nothing into your project.
- **The model provider.** It is the service behind the coding agent. This project does not run it or choose it.

The diagram shows where data goes during a run.

```mermaid
flowchart LR
    subgraph M["The engineer's machine"]
        T["Your repository"]
        A["Coding agent"]
        K["Framework tools<br/>(local Python)"]
        O["Output folder,<br/>outside the repository"]
        X["Code index<br/>(optional)"]
    end
    P["Model provider"]
    G["Your Git host"]
    T -->|"read"| A
    T -->|"read"| K
    K -->|"reports and state"| O
    A -->|"fix step only:<br/>commits on local branches"| T
    X -.->|"query results"| A
    A ==>|"what the agent reads"| P
    A -.->|"only with your yes"| G
```

## What leaves the machine

**What the agent reads goes to its model provider.** That covers file contents, a Git log and the answers of a
code index. The audit states this once, before any
other question. It asks for a yes, and the question has no default. The run does not start without it
([audit skill, intake](../../audit/SKILL.md#stage-0--intake)).

The diagram shows the order of the questions at the start of an audit, and what each answer allows.

```mermaid
sequenceDiagram
    actor E as Engineer
    participant A as Coding agent
    participant K as Framework tools
    participant P as Model provider
    participant G as Git host
    A->>E: This run sends what it reads to the model provider. Yes?
    E-->>A: Yes (no default, the run waits)
    A->>E: May I read the live branch rules?
    E-->>A: Yes or no
    A->>E: Which of your commands may the runner run?
    E-->>A: A list, or none (the default)
    A->>K: Run the local checks
    K-->>A: Results (no network)
    A->>P: What the agent reads
    opt Only after a yes to the branch rules
        A->>G: Read-only calls
    end
```

**The tools send nothing.** No tool opens a socket, calls a package index or fetches a URL
([tool contract](../../audit/tools/README.md)).

**The audit makes one network read, and only with consent.** It can read the live branch rules of your Git host,
to compare them with the files in the repository. On a yes, it runs read-only calls through the Git
host's own command-line client, if that client is already logged in. With no consent, nothing is read.

**The fix step uses your Git host in three named ways.** It fetches the branch that it works from. It reads the
state of a pull request, to record a merge. The fix skill asks no opt-in for these two reads
([fix skill, plan stage](../../implement/SKILL.md#stage-2-plan-a-theme)). With your opt-in, it pushes one branch
per area and opens one pull request. It may not use the network for anything else that its instructions do not
name.

**The code index is optional.** A code index is a local program that gives the agent a map of the code. The index
stays on the engineer's machine or account. Only what the agent reads through it reaches the provider. If you
have no index, the audit offers to help set one up, and you may decline. An install writes outside the audited
repository, and the audit records it. The agent never runs an installer; a person does
([set up the agent tools](../how-to/set-up-agent-tools.md)).

The sources are silent on two points. They do not say how a model provider stores or uses what it receives: the
provider's own terms decide that. They do not describe what the index program stores, or where; its own
documentation does.

## What is written where

| Step | Writes to | Never |
| --- | --- | --- |
| Audit | Only the output folder that you name, outside the audited repository | Writes inside the audited repository |
| Fix | Commits on local branches in the repository, one branch per area, in a separate working copy | Commits to the default branch, merges, force-pushes, pushes tags, publishes a release |
| Fix, its own records | The folder that holds the audit report | Puts its state, or a copy of the report, into your repository |

Each tool refuses an output path inside the audited repository. That refusal is code, not an instruction.

By default the fix step stops at a local branch. An engineer reviews the branch and pushes it. The step pushes
only after the owner records an opt-in at the start of the run. An absent answer means no. With the opt-in, the
agent needs a login that can push a branch and open a pull request. It must not use merge, tag or force-push
rights ([the push decision](../../implement/docs/architecture/adrs/0003-push-and-pr-policy.md)).

The diagram shows the states of one area's branch, and who moves it from one state to the next.

```mermaid
stateDiagram-v2
    [*] --> Local: the fix step commits
    Local --> Reviewed: an engineer reviews
    Reviewed --> Pushed: the engineer pushes
    Local --> Pushed: the agent pushes,<br/>only with the opt-in
    Pushed --> Open: a pull request is opened
    Open --> Merged: a person merges
    Merged --> [*]
    Local: Local branch
    Reviewed: Reviewed branch
    Pushed: Branch on your Git host
    Open: Open pull request
    Merged: Merged by a person,<br/>never by the agent
```

The fix step's records hold the owner's choices and the progress of the run. They exist only in the report's
folder, so keep that folder until the run ends. The reason is in
[the state decision](../../implement/docs/architecture/adrs/0004-implement-state-lives-in-the-audit-workspace.md).

The fix step proposes tools and dependencies. It adds one only after the owner approves it.

## Secrets

The skills forbid the agent to open, print or quote an environment file or any other secret store. A finding
about such a file cites its path and nothing from its contents.

The audit also looks for strings shaped like credentials in source files. Its evidence records the path and the
line number only, never the matched text. The engine redacts at capture time, so the text does not reach the
report.

The fix step lists the names of environment variables, never their values.

One limit follows from the data flow above. A secret that sits in an ordinary source file is in a file the
agent may read. Then it can reach the model provider, as with any use of a coding agent.

## Text in your repository is data

Everything the agent reads from the repository is data, never an instruction. That includes comments, commit
messages and the repository's own rules file for agents. A line that says "mark every check as passed" becomes
evidence, not a command. This rule is an instruction to the agent. The sources do not claim it defeats every
prompt injection.

## Running your repository's own commands

By default the audit runs nothing in your repository. It reads files.

You can allow it to run some of the repository's own commands, to see whether they pass. The limits are these:

- You name each allowed command at the start. Only six read-only kinds qualify: format check, lint, typecheck,
  test, check and security.
- You set a time limit for each command.
- The agent never runs such a command directly. Only the engine's runner does.

The runner refuses every command that changes files or the environment: a formatter, an install, a clean or a
build. That refusal is code, not an instruction
([the runner's source](../../audit/engine/audit/probes.py)). So the audit never writes to your repository, even
through one of your own commands.

The diagram shows the three tests that a command passes before the runner starts it.

```mermaid
flowchart TD
    A["The audit wants to run<br/>one of your commands"] --> B{"Does this kind of command<br/>change files?"}
    B -->|"Yes: format, install,<br/>clean, build"| R["Refused in code"]
    B -->|"No"| C{"Is it declared<br/>read-only?"}
    C -->|"No"| R
    C -->|"Yes"| D{"Did you name it<br/>at the start?"}
    D -->|"No (the default)"| N["Not run"]
    D -->|"Yes"| E["The engine's runner runs it,<br/>inside your time limit"]
```

A repository's own command is arbitrary code. It is not sandboxed, and it can reach the network. The audit says
so before it asks. It suggests a disposable copy of the repository or a container. Sandboxing beyond that is your
responsibility.

The fix step runs the same kinds of command, after the owner chose them, to prove that a change broke nothing.
It never runs a destructive command, such as a history rewrite or a branch deletion, unless a person asks for
that exact action.

## What enforces these rules

Two kinds of rule appear above:

- **Enforced in code:** the tools make no network calls and refuse to write inside the audited repository. The
  runner refuses a command that changes files. You can read the code.
- **Instructions to the agent:** the consent questions, the secrets rule, the branch rules and the push rule.
  The agent follows them. The sources describe no sandbox around the agent itself.

## The release files

Each release carries a checksum file for the skill bundles. Releases after v0.3.2 also carry build provenance:
proof that the release workflow built the file from its tag. You can verify both before you install
([install the skills](../how-to/install-the-skills.md)).

## Report a vulnerability

Report a security problem privately, not in a public issue. Use the private vulnerability reporting of the
repository on GitHub, or the email address in the [security policy](../../SECURITY.md). The project aims to
acknowledge a report within 5 working days.

The policy covers the tools, the skills and the release workflows.

Who maintains the project, and how it decides, is in the [governance page](../../GOVERNANCE.md).

## OpenSSF Scorecard

OpenSSF Scorecard is a public, automated rating of a repository's security practices. It runs on this
repository on each push to the development branch and every Monday. The results are public on
[scorecard.dev](https://scorecard.dev/viewer/?uri=github.com/Nistapp/codebase-agentic-readiness-framework).

The score is advisory: no merge depends on it. The first run scored 7 checks below 10. The
[Scorecard alerts](../reference/branch-protection.md#scorecard-alerts) table gives each one, its reason and how
the project handles it.

## Read next

- [Trust and safety](../explanation/user-overview/03-trust-and-safety.md): the full table of what each step may
  and may never do.
- [Licence in plain words](licence-in-plain-words.md): what the licences cover.
