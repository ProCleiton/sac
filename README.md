# SAC — Stupid Agentic Coordinator

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
sac init                                    # interactive wizard: creates sac.toml + prompts/ + .sac/
sac up                                      # start the tmux session with agents
sac status                                  # overview
sac status --clean                          # dry-run: list orphan inbox/claimed
sac status --clean --yes                    # execute removal of orphan data
sac send leader "implement X"               # task the leader
sac send user "report"                      # message the human (read via sac log)
sac run dev-review "feature Y"              # kick off a declared loop
sac recv dev-1                              # read a reply (up to SAC_DONE)
sac daemon                                  # run the delivery daemon (auto-started on dash)
sac kill <agent>                            # restart a stuck harness (re-injects prompt, re-alerts claimed tasks)
sac notify --once                           # single re-poke sweep (legacy)
sac log -f                                  # follow log.jsonl
sac attach                                  # attach to the tmux session
sac down                                    # stop the session
```

## Concepts

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
- **Boot progress & fail-fast**: `sac up` shows per-agent progress
  (`[3/8] agent: creating window... waiting 12s for prompt...`) with
  elapsed-time-aware waiting. Socket directory is auto-created. Critical
  tmux failures abort immediately with a clear error message instead of
  silently pretending success.
- **`sac init` wizard**: interactive questionnaire that generates a complete
  `sac.toml`, `prompts/*.md` with the basic SAC contract, `.sac/` skeleton,
  and socket directory. Name validation (`[A-Za-z0-9_-]`), round-trip TOML
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
- **Configuration**: `sac.toml` declares exactly one leader, the auxiliaries and
  named loops. The session-level `boot_wait` (default 8s) controls how long
  `sac up` waits before injecting prompts — individual agents can override it
  with `[[agents]] boot_wait = N`. Loops are not enforced — the workflow lives
  in each agent's contract prompt (`prompts/`).
- **Harness recovery**: `sac kill <agent>` restarts a stuck harness in-place —
  kills the process, recreates the pane from the sidebar, re-injects the prompt
  file, and re-alerts any pending claimed tasks.
- **Orphan cleanup**: `sac status --clean` runs a dry-run by default (lists
  orphans without removing). Add `--yes` to execute: removes inbox and claimed
  directories for agents no longer declared in `sac.toml` (preserves `done/`
  history). The event is logged to `log.jsonl`.
- **Reply-to-sender**: upon completing a task, auxiliaries send the result back to
  the original sender via `sac send <sender> "<result>"` before writing `SAC_DONE`
  and running `sac done <id>`.

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
