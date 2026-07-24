# SAC — Stupid Agentic Coordinator

![SAC mascot](docs/sac-mascot.png)

A daemonless multi-agent coordinator built on tmux. The "switchboard" is a
directory (`.sac/`), not a process. Design doc: `docs/2026-07-24-sac-design.md`.

SAC manages AI harnesses (Kimi Code, opencode, or any interactive CLI) in tmux
windows and lets them exchange messages through the filesystem — no daemon, no
database, no screen-scraping heuristics. Completion is explicit: agents end
their replies with a `SAC_DONE` sentinel line and run `sac done <id>`.

## Install

```bash
pipx install -e .          # recommended — isolates SAC in its own venv
# or
pip install --user -e .    # may need --break-system-packages on Ubuntu 24.04+
```

## Quickstart

```bash
python3 -m unittest discover -s tests -v   # test suite
sac up                                      # start the tmux session with agents
sac status                                  # overview
sac send leader "implement X"               # task the leader
sac run dev-review "feature Y"              # kick off a declared loop
sac recv dev-1                              # read a reply (up to SAC_DONE)
sac notify --once                           # single re-poke sweep
sac notify                                  # continuous watcher (Ctrl-C exits)
sac log -f                                  # follow log.jsonl
sac attach                                  # attach to the tmux session
sac down                                    # stop the session
```

## Concepts

- **No daemon**: state is `.sac/` (inbox/claimed/done + log.jsonl) plus the tmux
  session. Crash of SAC takes nothing down; `sac up` is idempotent.
- **Explicit completion contract**: agents finish replies with `SAC_DONE` and run
  `sac done <id>` — no fragile turn-detection heuristics.
- **Reply-to-sender**: upon completing a task, auxiliaries send the result back to
  the original sender via `sac send <sender> "<result>"` before writing `SAC_DONE`
  and running `sac done <id>`.
- **Configuration**: `sac.toml` declares exactly one leader, the auxiliaries and
  named loops. Loops are not enforced — the workflow lives in each agent's
  contract prompt (`prompts/`).

## Credits

- Inspired by the **CCB (Claude Code Bridge)** project, whose multi-agent tmux
  orchestration proved the concept — SAC reimplements the idea in its simplest
  possible form, replacing CCB's daemon and screen-state completion detection
  with a filesystem mailbox and an explicit sentinel contract.
- Built with **Python 3** (standard library only) and **tmux**.
- Designed to orchestrate AI harnesses such as **Kimi Code** (Moonshot AI) and
  **opencode**.
- Mascot generated via Pollinations.ai (image generation API).

## License

MIT — see `LICENSE`.
