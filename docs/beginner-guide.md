# SAC — Beginner's Guide

> **SAC = Stupid Agentic Coordinator** — a minimalist multi-agent coordinator
> written in Python 3 (stdlib only) + tmux.

---

## 1. What is SAC

SAC places multiple AI harnesses (Kimi Code, opencode…) into panes of a single
tmux session, each with a **role** (leader, dev, auditor, docs, deploy…), and
handles **one thing only**: delivering messages between them.

It is "stupid" on purpose:

- It does **not** attempt to guess when an agent finished (no screen-state heuristics).
- It does **not** orchestrate business logic or enforce workflows.
- It only guarantees **mail delivery** (a filesystem mailbox + daemon).

Workflow intelligence lives in the **contract prompts** (`prompts/*.md`) —
that is where you define, for example, that the leader must send the dev's work
to the auditor before approving.

### The Metaphor

Think of a government office with mailboxes:

| SAC Component | In the Metaphor |
|---|---|
| `.sac/sac.toml` | The org chart (who sits at which desk) |
| `prompts/*.md` | Each employee's conduct manual |
| daemon (`sac daemon`) | The courier who carries memos desk-to-desk |
| `.sac/` | The records room where everything is logged |

SAC guarantees the letters arrive; what each employee does with them is up to
their manual.

---

## 2. Installation

```bash
pipx install -e .          # recommended — isolates SAC in its own venv
# or
pip install --user -e .    # may need --break-system-packages on Ubuntu 24.04+
```

Prerequisites: Python 3 and tmux.

---

## 3. How to Configure: `.sac/sac.toml`

Everything starts from a single config file. Since v24 the default location is
`.sac/sac.toml` (inside the hidden state directory); a legacy `./sac.toml` at
the workspace root is **ignored** since v25 — resolution order is `--config`
flag → `$SAC_CONFIG` → `./.sac/sac.toml`. To migrate an old workspace:
`mkdir -p .sac && mv sac.toml .sac/`. Three sections:

### 3.1 `[session]` — the tmux session

```toml
[session]
name = "esteira"                        # tmux session name
notify_interval = 10
poke_stale_after = 120                  # seconds until re-poking a stalled task
boot_wait = 8                           # seconds to wait before injecting prompts
socket = "~/.sac-esteira/tmux.sock"     # dedicated tmux socket
```

- `socket`: each pipeline uses its own tmux socket — never the default socket.
- `width`/`height` (optional, default 220x50): session geometry, avoids SIGILL
  in narrow panes at boot.

### 3.2 `[[agents]]` — one block per agent

```toml
[[agents]]
name = "lead"
command = "kimi"                                   # harness: kimi, opencode…
args = ["--model", "kimi-code/k3", "--yolo"]       # harness flags
role = "leader"                                    # exactly ONE leader per config
prompt_file = "prompts/lead-coordinator.md"        # the "conduct manual"
boot_wait = 6                                      # optional: overrides the global
```

- `role`: `leader` (orchestrator) or `aux` (worker). **Must have exactly one
  `leader`.**
- Per-agent `boot_wait`: useful because different harnesses start at different
  speeds (opencode usually needs less waiting than kimi, for example).

### 3.3 `[windows]` — visual layout (CCB-style)

```toml
[windows]
main     = "lead"                    # single pane
trabalho = "dev-1,dev-2"             # comma = stack vertically
apoio    = "docs;auditor"            # semicolon = split side-by-side
ops      = "deployment;secops;revisor"
```

Grammar: `,` stacks vertically, `;` splits side-by-side. Every window gets a
**live sidebar** on the left (window tree → agents, inbox badges, idle time,
latest events). The `dash` window is always created. Without `[windows]`, the
legacy one-window-per-agent layout is used.

---

## 4. The Delivery System (Mailbox + Daemon)

The heart of SAC is a **filesystem mailbox** inside `.sac/`:

```
.sac/
  inbox/<agent>/    ← new messages
  claimed/<agent>/  ← task in progress
  done/<agent>/     ← history
  log.jsonl         ← event log
```

### Lifecycle of a Message

1. Someone runs `sac send dev-1 "implement X"` → a file lands in `inbox/dev-1/`.
2. The **daemon** (`sac daemon`, polling every 1s) sees the message and **injects
   the body directly into the dev-1 tmux pane** via `send-keys`. The agent does
   not need to keep asking "anything new?" — the task appears in their terminal
   with the header `SAC <id> from <sender>:` on the first line.
3. The agent works and, on completion:
   1. replies to the sender: `sac send <sender> "<result>"`;
   2. writes `SAC_DONE` on a separate line;
   3. runs `sac done <id> "<summary>"`.
4. **Replies** (the `reply_to` field is inferred on send) are special: they
   bypass the queue even when the agent is busy and are **auto-acknowledged** —
   no `sac done` needed. Only fresh tasks require explicit completion.

### Robustness

- **No daemon, nothing lost**: if the daemon goes down, `sac send` falls back to
  legacy mode ("SAC: new message — run `sac next`"). The inbox persists on disk,
  independent of the daemon or tmux.
- **Exponential backoff**: the daemon doubles the interval between pokes to the
  same stalled task (base `poke_stale_after`, cap 5 minutes) — avoids poke
  storms on long-running tasks.
- **`sac up` is idempotent**: a crash of SAC or the daemon takes nothing down.

---

## 5. Loops — removed in v26b (breaking change)

Declared loops (`[[loops]]` + the `sac run` command) were **removed in v26b**,
with no deprecation period: a config containing `[[loops]]` fails to load with
a clear error — remove the section from your `sac.toml`.

Delegation and review cycles are now the **leader contract's discipline**: the
leader decomposes the work, delegates with `sac send <aux> "<task>"`, demands
review of the auxiliaries' work (reviewing itself or delegating to a reviewer
aux), and iterates delegate → review → fix until the result converges —
escalating to the user only on real blockers. The generated leader contract
(`prompts/<leader>.md`) already carries this discipline; nothing else is
needed.

---

## 6. Deep Dive: `prompt_file` (Agent Contracts)

Each agent's `prompt_file` is the Markdown file injected into the harness at
boot (`sac up` waits `boot_wait` seconds then injects the content into the
pane). It is what turns a generic harness into "dev-1" or "auditor".
**SAC delivers messages; the contract defines behavior.**

### 6.1 Anatomy of a Contract

Every contract prompt has at least three parts:

1. **Role** — who the agent is in the pipeline. E.g.: "You are a developer on
   the SAC pipeline. Implement with TDD."
2. **SAC Contract (mandatory)** — the mechanical communication rules:
   - tasks arrive with header `SAC <id> from <sender>:`;
   - the `<sender>` for `sac send` and the `<id>` for `sac done` come from this
     header;
   - on completion: `sac send <sender> "<summary>"` → `SAC_DONE` →
     `sac done <id> "<summary>"`;
   - received replies are auto-acknowledged — do **not** run `sac done` on them;
   - if the sender is `user`, reply with `sac send user "<message>"`.
3. **Workspace rules** — your project conventions (TDD, layering, soft delete,
   commit prefixes, no unauthorized `git push`, etc.).

### 6.2 Real Example (summary of `prompts/development-specialist-1.md`)

```markdown
# Role: development-specialist (SAC)
You are a developer on the SAC pipeline. **Implement with TDD**…

## SAC Contract (mandatory)
- Tasks arrive with header `SAC <id> from <sender>:`.
- On completion:
  1. Send the result to the sender with `sac send <sender> "<summary>"`.
  2. Write `SAC_DONE`.
  3. Run `sac done <id> "<summary>"`.
- Replies you receive are auto-acknowledged — do NOT run `sac done` on them.

## Workspace Rules
- TDD mandatory: no tests = no merge.
- Soft delete: `dt_exclusao` instead of physical DELETE.
- NEVER `git push` without authorization.
```

### 6.3 The Leader Contract is Different

The leader's prompt adds **orchestration and gates** — this is where the loop
"dev → auditor → docs → deploy" is actually implemented:

- delegate implementation to devs;
- **code-auditor gate** (review; REPROVED → re-delegate, max 3 iterations);
- **information-specialist gate** (documentation);
- **secops-analyst gate** (if touching secrets/auth/personal data);
- ask the user for approval (`sac send user`);
- delegate the git cycle to the `deployment-officer`;
- request archive from the `information-specialist`.

The leader is also the **only channel to the human** — workers report to the
leader, never directly to the user.

### 6.4 Best Practices for Writing a Contract

- Be **mechanical and imperative** in the SAC part (agents must execute
  `sac send` / `sac done` without ambiguity).
- Explicitly state **who** the agent reports to and **when** to request a gate.
- Repeat critical workspace rules (the prompt is the agent's only guaranteed
  "memory" at boot).
- Agent names in the contract must match the `name` in `.sac/sac.toml` — that is
  how `sac send` routes messages.

---

## 7. Deep Dive: `sac init` (The Wizard)

`sac init` is an **interactive questionnaire** (implemented in `sac/sac/init.py`)
that generates everything a pipeline needs to start — no trip to the repository
required: every question carries a hint with a concrete example. **It requires
an interactive terminal** (TTY) — in non-interactive mode it aborts with:

```
error: interactive mode requires a terminal — use --config to point to an existing sac.toml
```

The wizard opens by announcing what will be generated and where:

```
SAC init — this wizard generates:
  .sac/sac.toml   (pipeline configuration)
  .sac/           (state: inbox/claimed/done)
  prompts/*.md    (each agent's contract — edit freely afterwards)
```

### 7.1 What the Wizard Asks

1. **Session name** (default `sac`) — validated against `[A-Za-z0-9_-]`; hint
   shows where the name appears (`sac attach`, `tmux ls`).
2. **tmux socket** (path; Enter = no dedicated socket) — hint with a concrete
   example (`~/.sac-nfi/tmux.sock`).
3. **Global boot wait** in seconds (default 10) — hint with a suggested range.
4. **Number of agents** (default 3) and, for each:
   - **Agent 1 is announced as the leader/orchestrator** (header + hint
     explaining the role) — there is **no role question**; agents 2+ are `aux`
     automatically;
   - name (same validation);
   - command — the default is the **first harness detected in PATH**
     (kimi → opencode → claude, with a "detected in your PATH" hint); when
     nothing is detected, a fixed placeholder (`kimi` for agent 1, `opencode`
     for the rest). Unknown commands trigger a warning offering to fix or
     continue;
   - **contract** (agents 2+ only): a numbered catalog — see 7.4; agent 1
     receives the leader contract with no question;
   - model (optional; if filled, generates `args = ["--model", "<model>"]`;
     for `opencode` the wizard already appends `--auto` automatically);
   - per-agent boot wait (Enter = use global).
5. **Window grouping** (optional, default no): per window — name, agents
   (space-separated, validated against the ones just created), and disposition
   (`1` side-by-side → `;`, `2` stacked → `,`), with a preview before asking
   about the next window. Agents left out of every window keep their own
   window.

### 7.2 What the Wizard Generates

| Artifact | Content |
|---|---|
| `.sac/sac.toml` | Full config, with **round-trip validation** (the generated TOML is re-parsed with `tomllib` before writing; if invalid, init aborts) |
| `prompts/<name>.md` | One per agent: the canonical contract for the chosen role (SAC messaging protocol + role discipline) plus harness-specific notes (`KIMI_NOTE` / `OPENCODE_NOTE`) |
| `.sac/` | State skeleton: `inbox/`, `claimed/`, `done/` |
| Socket directory | Created automatically if `socket` was configured |

### 7.3 Wizard Protections

- **Config already exists** (`.sac/sac.toml` or legacy `sac.toml`)? Asks
  "Overwrite? (y/N)" — default **no**.
- **`prompts/*.md` already exist?** Same question, default **no** ("prompts
  kept").
- `Ctrl+C`/`EOF` mid-questionnaire → "init cancelled by user", no side effects.

### 7.4 The Canonical Contract Catalog

The catalog (pure data in `sac/sac/contracts.py`) has 7 roles. Each contract =
the **SAC messaging protocol** (inbox / `sac next` / reply / `sac done`) + the
**role discipline**, in plain text that requires **no external plugin or CLI**:

| # | Role | Discipline |
|---|------|-----------|
| 1 | leader/orchestrator | receives from the user, decomposes, delegates, consolidates; escalates blockers |
| 2 | developer (default for aux) | TDD (test first), minimal changes, systematic debugging before proposing a fix |
| 3 | code reviewer | evidence-based verdict (runs the suite, reads the diff); blockers vs. warnings |
| 4 | documentation | docs faithful to the code; OpenSpec kept up to date |
| 5 | deploy/release | per-stage git cycle with authorization; green CI before merge |
| 6 | security | threat modeling of the diff, secrets, entry surfaces |
| 7 | generic aux | basic SAC contract (messaging + `SAC_DONE`), no extra discipline |

The disciplines are inspired by the **superpowers** skills plugin and the
**OpenSpec** workflow — SAC's canonical stack — but work without them
installed. Editing a contract later = opening `prompts/<name>.md` in your
editor; the wizard never re-edits contracts.

In other words: `init` gives you a **working skeleton with real disciplines**;
you add the project-specific business rules by editing `prompts/*.md`.

### 7.5 Starting Over: `sac uninstall`

`sac uninstall` removes SAC's configuration from the current workspace, safely:

1. **Refuses if the tmux session is up** — run `sac down` first;
2. **Lists what will be removed**: `.sac/` (config + state), `prompts/`, and
   the legacy `sac.toml` if present;
3. **Requires typing the session name** to confirm — anything else aborts
   without removing anything.

Nothing outside the workspace directory is touched, and no process is killed.

---

## 8. Day-to-Day Commands

| Command | Purpose |
|---|---|
| `sac up` | Starts the tmux session with all agents (idempotent, animated 0–100% progress bar, per-agent log) |
| `sac send <agent> "msg"` | Sends a task/message |
| `sac send user "msg"` | Talks to the human (they read via `sac log`) — works without configuring "user" as an agent |
| `sac recv <agent>` | Reads a reply (up to `SAC_DONE`) |
| `sac status` / `--mini` | Overview / one-line summary (`2● 1!`) for the tmux status bar |
| `sac status --clean [--yes]` | Lists/removes orphan inbox+claimed from agents no longer in `sac.toml` (dry-run by default) |
| `sac sidebar --toggle` | Opens/closes the sidebar in the current window (bind `prefix+e`) |
| `sac log -f` | Follows `log.jsonl` |
| `sac kill <agent>` | Restarts a stuck harness **in-place** (re-injects prompt, re-alerts claimed tasks) — no down/up cycle |
| `sac attach` | Attaches to the tmux session to look at panes |
| `sac daemon` | Runs the delivery daemon (auto-started in dash) |
| `sac doctor` | Read-only environment checkup: Python, tmux, socket, config (reports which file was used, warns on ambiguity), harnesses and the `openspec` CLI |
| `sac down` | Shuts down everything: harness panes (in order), daemon (SIGTERM→SIGKILL via pid file), and tmux session |
| `sac uninstall` | Removes `.sac/`, `prompts/` and legacy `sac.toml` — refuses with the session up, requires typing the session name |
| `sac memory <sub>` | Per-workspace long-term memory (`.sac/memory.db`): `remember`, `recall`, `revise`, `forget`, `restore`, `decay`, `export`, `pack` |

### 8.1 Long-term memory (`sac memory`)

Agents have no memory beyond the session — unless they record it. SAC keeps
per-workspace memory in `.sac/memory.db` (SQLite, stdlib only; FTS5 search
with automatic fallback to `LIKE`). Every memory has a kind — `tarefa`
(task), `lição` (lesson) or `referência` (reference) — and importance 1–5:

```bash
sac memory remember tarefa "Migrate pipeline to hidden config" -i 4
sac memory remember lição "OpenSpec archive requires original scenario names"
sac memory recall "port 9000"         # FTS5 search; without a query, most recent
sac memory revise 7 -c "updated content"   # the old one becomes superseded
sac memory forget 12                  # soft-delete (never a physical DELETE)
sac memory restore 12
sac memory decay --days 30 --dry-run  # deterministic pruning; without --dry-run, archives
sac memory export > memory.md         # Markdown grouped by kind
sac memory export --history           # audit trail of every operation
```

The leader is the **curator**: its contract gains a section between the
`<!-- SAC-MEMORY:BEGIN/END -->` markers with the active memories (~4000-char
budget: tasks → lessons → references, importance desc). `sac up` and every
`sac memory` write rewrite only that section — contracts without the markers
are never touched. Every state change is audited in the `history` table
(visible via `export --history`).

Tip: inside panes, the `SAC_ROOT` and `SAC_CONFIG` environment variables are
already set — `sac` commands work from any directory inside the session.

---

## 9. References

- Repository: `sac/` (full README at `sac/README.md`)
- Design doc: `sac/docs/2026-07-24-sac-design.md`
- Implementation plan: `sac/docs/2026-07-24-sac-implementation-plan.md`
- Wizard source: `sac/sac/init.py`
- Real contracts: `prompts/*.md`
- Inspiration: the **CCB (Claude Code Bridge)** project — SAC reimplements the
  idea in its simplest possible form, replacing screen-state detection with a
  filesystem mailbox + explicit sentinel contract (`SAC_DONE`).
