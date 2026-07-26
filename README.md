# SAC — Stupid Agentic Coordinator

<p align="center">
  <img src="assets/logo-sac.png" alt="SAC — Stupid Agentic Coordinator" width="360">
</p>

A lightweight multi-agent coordinator built on tmux. An optional polling daemon
watches each agent's inbox and **injects tasks directly into the harness pane**
— no need for agents to periodically check for new messages.

Design doc: `docs/2026-07-24-sac-design.md`.

## Install

```bash
pipx install -e .          # recommended — isolates SAC in its own venv
# or
pip install --user -e .    # may need --break-system-packages on Ubuntu 24.04+
```

## Quickstart

```bash
python3 -m unittest discover -s tests -v   # test suite
sac init                                    # interactive wizard: creates .sac/sac.toml + prompts/ + .sac/
sac doctor                                  # environment checkup (Python, tmux, config, harnesses, openspec)
sac up                                      # start the tmux session with agents
sac status                                  # overview
sac status --mini                           # one-line summary (2● 1!) for the tmux status bar
sac status --clean                          # dry-run: list orphan inbox/claimed
sac status --clean --yes                    # execute removal of orphan data
sac sidebar --toggle                        # toggle the sidebar pane in the current window
sac sidebar --watch                         # in-place live sidebar (used by the sidebar panes)
sac send leader "implement X"               # task the leader
sac send user "report"                      # message the human (read via sac log)
sac recv dev-1                              # read a reply (up to SAC_DONE)
sac daemon                                  # run the delivery daemon (auto-started on dash)
sac kill <agent>                            # restart a stuck harness (re-injects prompt, re-alerts claimed tasks)
sac notify --once                           # single re-poke sweep (legacy)
sac log -f                                  # follow log.jsonl
sac attach                                  # attach to the tmux session
sac down                                    # stop everything: harnesses, daemon and tmux session
sac uninstall                               # remove .sac/, prompts/ and legacy sac.toml (asks for the session name)
```

## Beginner's Guide

New to SAC? A detailed step-by-step walkthrough covers installation,
configuration, the daemon and mailbox system, agent contract
prompts, the `sac init` wizard, and every-day commands.

→ [docs/beginner-guide.md](docs/beginner-guide.md)

## Concepts

- **CCB-style layout (`[windows]`)**: group agents into named tmux windows with
  a simple grammar — `,` stacks vertically, `;` splits side-by-side
  (`trabalho = "dev-1,auditor"`). Every window gets a left sidebar; the dash
  window is always created. Without `[windows]`, the legacy
  one-window-per-agent layout is preserved.
- **Sidebar**: live tree of windows → agents with `├─`/`└─` connectors,
  inbox badge `(N)`, idle time (`· 5m`), state markers (`●` claimed,
  `!` escalated, `◐` inbox, `·` idle, `*` focused), harness command name
  in gray (e.g. `kimi`), plus the last 5 comms events and tmux tips.
  The sidebar is 18% of the window width (min 28 cols). `sac sidebar --watch`
  redraws in place; `sac sidebar --toggle` (bind `prefix+e`) opens/closes it
  in any window.
- **Status bar**: Catppuccin Mocha palette with powerline separators (U+E0B0/U+E0B2).
  Left: mode (`KEY`/`COPY`/`INPUT`) with dynamic background via conditional tmux
  format (pink/red/peach) → U+E0B0 → workspace name (basename of project root)
  centred in gray — no session name or mauve block. Right: agent (`#{@agent}`,
  red) → U+E0B2 → live version (`#(sac --version 2>/dev/null)`, mauve) →
  U+E0B2 → summary (`#(sac status --mini)`, blue) → U+E0B2 → date
  (`dd/MM dow HH:MM`, peach). `status-style bg=#1e1e2e,fg=#cdd6f4`,
  `status-left-length=80`, `status-right-length=120`.
- **Stable agent identity**: harness panes are tagged with the `@agent` pane
  option at boot — sidebar, status bar, and pane borders never rely on
  `pane_title`, which harnesses overwrite seconds after boot (kimi → "Kimi Code").
  Each pane's top border (`pane-border-format`) displays the agent name in a
  stable color derived from a hash of the name; the active pane is highlighted
  via an `after-select-pane` hook.
- **Full shutdown**: `sac down` kills every harness pane (in config order),
  terminates the daemon via pid file (SIGTERM → SIGKILL, even detached) and
  only then kills the tmux session.
- **Boot progress bar**: `sac up` shows an animated 0–100% progress bar on
  TTYs (falls back to plain log lines when piped).
- **Daemon coordinator**: a lightweight polling daemon (`sac daemon`) monitors
  every agent's inbox (POLL_INTERVAL=1s). When a new message arrives, it injects
  the **body directly** into the agent's tmux pane via `send-keys` — no
  intermediate "run `sac next`" prompt. The daemon also re-pokes stale claimed
  tasks and writes `daemon.pid` for inter-process coordination.
- **Reply semantics**: responses are automatically recognized (`reply_to` field
  inferred at send time). The daemon delivers replies even while the agent is
  busy with a task (they skip the queue) and auto-acknowledges them — no
  `sac done` required. Only fresh tasks need explicit completion. In legacy
  mode, reading a reply via `sac next` also auto-acks it.
- **User route**: `sac send user "<msg>"` works without configuring "user" as
  an agent — messages land in `inbox/user/` for you to read via `sac log`.
  Agents can report directly to the user without going through the leader.
- **Exponential backoff on stale pokes**: the daemon doubles the interval
  between pokes to the same message (base `poke_stale_after`, cap 5 min).
  The legacy `sac notify` applies the same backoff. Prevents poke storms
  during long-running tasks.
- **Session environment**: every pane (harness, sidebar, dash) receives
  `SAC_ROOT=<raiz do store>` and `SAC_CONFIG=<caminho absoluto do sac.toml>`.
  Config resolution order: `--config` flag → `$SAC_CONFIG` → `./.sac/sac.toml`
  (legacy `./sac.toml` is **ignored** since v25 — migrate with
  `mkdir -p .sac && mv sac.toml .sac/`). `sac` commands inside panes always
  resolve the correct session regardless of cwd.
- **Boot progress & fail-fast**: `sac up` shows per-agent progress
  (`[3/8] agent: creating window... waiting 12s for prompt...`) with
  elapsed-time-aware waiting. Socket directory is auto-created. Critical
  tmux failures abort immediately with a clear error message instead of
  silently pretending success.
- **`sac init` wizard**: interactive questionnaire that generates a complete
  `.sac/sac.toml`, `prompts/*.md` with a canonical role contract per agent,
  `.sac/` skeleton, and socket directory. Every question has a hint with a
  concrete example. Agent 1 is announced as the leader/orchestrator (no role
  question); agents 2+ are `aux` and pick a contract from a numbered catalog
  (leader, developer, reviewer, docs, deploy/release, security, generic aux —
  default: developer). The harness command defaults to the first one detected
  in PATH (kimi → opencode → claude). Optional window grouping writes
  `[windows]` for you. Name validation (`[A-Za-z0-9_-]`), round-trip TOML
  validation, overwrite confirmation. Non-TTY: error guiding to `--config`.
- **Explicit completion contract**: agents signal completion by writing
  `SAC_DONE` and running `sac done <id>` — the daemon does **not** attempt
  turn-detection heuristics (avoids false positives). With the daemon online,
  only daemon-delivered tasks require this; manually read messages are auto-acked.
- **No dependency on the daemon**: if the daemon is down, `sac send` falls back
  to the legacy poke ("SAC: mensagem nova — rode `sac next`"). Messages are
  never lost — the filesystem inbox persists independently.
- **Filesystem state**: everything lives in `.sac/` (inbox/claimed/done +
  log.jsonl) plus the tmux session. Crash of SAC or the daemon takes nothing
  down; `sac up` is idempotent.
- **Long-term memory**: `sac memory` keeps per-workspace memory in
  `.sac/memory.db` (SQLite stdlib + FTS5, degraded to `LIKE` when FTS5 is
  unavailable). Kinds are `tarefa`, `lição` and `referência`, with importance
  1–5. Subcommands: `remember`, `recall` (FTS5-ranked or chronological),
  `revise` (supersedes), `forget`/`restore` (soft-delete — never a physical
  DELETE), `decay` (deterministic pruning), `export` (Markdown, `--history`
  for the audit trail) and `pack` (budgeted injection block). The active
  memories are injected into the leader contract between
  `<!-- SAC-MEMORY:BEGIN/END -->` markers — rewritten idempotently by
  `sac up` and after every memory write; contracts without markers are never
  touched. The leader is the curator: register with `remember`, consult with
  `recall` before deciding, prune with `forget`/`revise`/`decay`; every
  state change is audited in the `history` table.
- **Configuration**: `.sac/sac.toml` declares exactly one leader and the
  auxiliaries (legacy `./sac.toml` is ignored since v25).
  The session-level `boot_wait` (default 8s) controls how long
  `sac up` waits before injecting prompts — individual agents can override it
  with `[[agents]] boot_wait = N`. Session geometry is set via `[session]
  width`/`height` (default 220x50) — avoids SIGILL in narrow panes at boot.
  The workflow lives in each agent's contract prompt (`prompts/`).
  **Breaking change (v26b)**: declared loops (`[[loops]]`) and the `sac run`
  command were removed — a config containing `[[loops]]` fails to load with a
  clear error (remove the section). Delegation and review cycles are now the
  leader contract's discipline (delegate with `sac send`, demand review,
  iterate until convergence).
- **Harness recovery**: `sac kill <agent>` restarts a stuck harness in-place —
  kills the process, recreates the pane from the sidebar, re-injects the prompt
  file, and re-alerts any pending claimed tasks. If the pane is already dead
  (process gone), `sac kill` revives it from scratch — no need for a full
  `down`/`up` cycle.
- **Orphan cleanup**: `sac status --clean` runs a dry-run by default (lists
  orphans without removing). Add `--yes` to execute: removes inbox and claimed
  directories for agents no longer declared in `sac.toml` (preserves `done/`
  history). The event is logged to `log.jsonl`.
- **Reply-to-sender**: upon completing a task, auxiliaries send the result back to
  the original sender via `sac send <sender> "<result>"` before writing `SAC_DONE`
  and running `sac done <id>`.

## SAC and your harness

SAC does not configure your harness — it launches the same binary you already
use, in a tmux pane, and delivers messages to it. Everything the harness knows
how to do keeps working, untouched.

- **Plugins and skills work with zero extra config**: global plugins/skills
  (`~/.kimi/plugins`, `~/.claude/skills`, `~/.config/opencode`) and project-level
  ones (`.claude/skills`, `AGENTS.md`) are loaded by the harness itself — SAC
  neither replaces nor disables anything. The `prompt_file` is **not**
  configuration: it is a message injected into the first turn, nothing more.
- **What lives where**:

  | Concern | Owner | Where |
  |---------|-------|-------|
  | Plugins, skills, login, model, harness flags | you | the harness's own config files |
  | Agents, roles, layout, socket | SAC | `.sac/sac.toml` |
  | Agent behavior (contracts, workflow) | you | `prompts/*.md` |

- **Pre-warm before the first `sac up`**: run the harness once in the workspace
  directory (e.g. `kimi .`) to approve logins, plugins and interactive consents.
  SAC does not — and should not — answer harness dialogs.
- **Long-term memory lives in SAC**: pipeline memory (tasks, lessons,
  references) lives in `.sac/memory.db` — managed via `sac memory` and curated
  by the leader. `AGENTS.md`/`CLAUDE.md` still matter, but only when you run
  the harness WITHOUT SAC (direct sessions); the canonical contracts never
  tell agents to manage those files. Harness memory plugins are per-harness
  and per-process; they don't share across agents. The discipline of reading
  and recording lives in the prompt contracts (SAC delivers letters; behavior
  is in the manuals).
- **Stupid on purpose**: SAC doesn't configure the harness, doesn't orchestrate
  your workflow, doesn't impose anything — it just delivers messages. All the
  intelligence lives in the contracts and in each layer's own config.

## Canonical stack: superpowers + OpenSpec

SAC's canonical workflow stack is the **superpowers** skills plugin (TDD,
systematic debugging, evidence-based review) plus the **OpenSpec** CLI
(spec-driven changes). They are conventions, not requirements:

- The **canonical contracts** generated by `sac init` (`sac/contracts.py`)
  translate those disciplines into plain text — TDD, systematic debugging,
  evidence-based verdicts, per-stage git cycle — so agents follow them **with
  nothing installed**. If the harness has the superpowers plugin, the agent
  simply recognizes the practices by their skill names.
- **OpenSpec** tracks what changes and why (`openspec/`); SAC tracks who does
  it and when. `sac doctor` warns when the `openspec` CLI is not in PATH and
  prints the install hint — installing it (and the superpowers plugin) is
  always the user's call.
- Editing a contract after `sac init` = opening `prompts/<name>.md` in your
  editor. The wizard never re-edits contracts.

## Credits

- Inspired by the **CCB (Claude Code Bridge)** project, whose multi-agent tmux
  orchestration proved the concept — SAC reimplements the idea in its simplest
  possible form, replacing CCB's daemon and screen-state completion detection
  with a filesystem mailbox and an explicit sentinel contract.
- Built with **Python 3** (standard library only) and **tmux**.
- Designed to orchestrate AI harnesses such as **Kimi Code** (Moonshot AI) and
  **opencode**.

## License

MIT — see `LICENSE`.
