"""Daemon do SAC — monitora inbox e entrega mensagens direto ao harness.

Sem overhead de instrução: o daemon injeta o corpo da tarefa diretamente
no pane do agente via paste (bracketed paste), sem texto "SAC: mensagem nova...".

O agente ainda precisa rodar `sac done <id>` (shell command, custo
desprezível). O daemon só gerencia entrega e re-cutucada de tarefas
stale — sem detecção automática de SAC_DONE para evitar falso-positivos."""
from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from .config import Config
from .store import Message, Store
from .tmux import Tmux

POLL_INTERVAL = 1.0


class Daemon:
    def __init__(self, cfg: Config, store: Store, tmux: Tmux):
        self.cfg = cfg
        self.store = store
        self.tmux = tmux
        self._running = True
        self._last_poke: dict[str, float] = {}

    def _pid_path(self) -> Path:
        return self.store.root / "daemon.pid"

    def _write_pid(self):
        self._pid_path().parent.mkdir(parents=True, exist_ok=True)
        self._pid_path().write_text(str(os.getpid()), encoding="utf-8")

    def _remove_pid(self):
        p = self._pid_path()
        if p.exists():
            p.unlink()

    def run(self):
        self._write_pid()
        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, '_running', False))
        signal.signal(signal.SIGINT, lambda s, f: setattr(self, '_running', False))
        try:
            self._loop()
        finally:
            self._remove_pid()

    def _loop(self):
        while self._running:
            for agent in self.cfg.agents:
                try:
                    self._process_agent(agent.name)
                except Exception as exc:
                    self.store.log("loop_error", agent=agent.name, error=str(exc))
            time.sleep(POLL_INTERVAL)

    def _process_agent(self, name: str):
        claimed = self.store.claimed(name)

        if claimed:
            stale = self.store.stale(name, self.cfg.poke_stale_after)
            stale_ids = [m for m in claimed if m in stale]
            if stale_ids:
                last = self._last_poke.get(name, 0.0)
                if time.monotonic() - last < self.cfg.notify_interval:
                    return
                pid = self.tmux.find_pane_id(name)
                if pid:
                    self.tmux.send_keys(
                        pid,
                        f"SAC: tarefa {stale_ids[0]} pendente — rode `sac done {stale_ids[0]}`"
                    )
                    self.store.log("poke", agent=name, id=stale_ids[0])
                    self._last_poke[name] = time.monotonic()
            return

        if self.store.pending(name):
            self._deliver_next(name)

    def _deliver_next(self, name: str):
        pid = self.tmux.find_pane_id(name)
        if not pid:
            return
        msg = self.store.next(name)
        if msg is None:
            return
        content = f"SAC {msg.id} de {msg.sender}:\n{msg.body}"
        self.tmux.paste(pid, content)
        self.tmux.press_enter(pid)
        self.store.log("deliver", agent=name, id=msg.id, sender=msg.sender)


def run_daemon(cfg: Config, store: Store, tmux: Tmux) -> int:
    Daemon(cfg, store, tmux).run()
    return 0
