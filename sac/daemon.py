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
        self._poke_state: dict[str, dict[str, float]] = {}
        self._poke_count: dict[str, dict[str, int]] = {}

    def _poke_interval(self, msg_id: str) -> float:
        for agent_name, msgs in self._poke_state.items():
            if msg_id in msgs:
                n = self._poke_count.get(agent_name, {}).get(msg_id, 0)
                return min(self.cfg.poke_stale_after * (2 ** n), 600)
        return 0.0

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
                sid = stale_ids[0]
                interval = self._poke_interval(sid)
                last = self._poke_state.get(name, {}).get(sid, 0.0)
                if not (time.monotonic() - last < interval):
                    pid = self.tmux.find_pane_id(name)
                    if pid:
                        self.tmux.send_keys(
                            pid,
                            f"SAC: tarefa {sid} pendente — rode `sac done {sid}`"
                        )
                        self.store.log("poke", agent=name, id=sid)
                        self._poke_state.setdefault(name, {})[sid] = time.monotonic()
                        self._poke_count.setdefault(name, {})[sid] = self._poke_count.get(name, {}).get(sid, 0) + 1
            peek = self.store.peek_next(name)
            if peek and peek[1]:
                self._deliver_next(name)
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
        if msg.reply_to:
            self.store.finish_reply(name, msg.id)


def run_daemon(cfg: Config, store: Store, tmux: Tmux) -> int:
    Daemon(cfg, store, tmux).run()
    return 0
