"""Lógica dos comandos do SAC. Funções puras com dependências injetadas."""
from __future__ import annotations

import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path

from .config import Config, ConfigError
from .store import Store, StoreError
from .tmux import Tmux

POKE_TEXT = "SAC: mensagem nova na inbox — rode `sac next`"
SENTINEL = "SAC_DONE"


def cmd_send(cfg: Config, store: Store, tmux: Tmux, to: str, body: str, sender: str = "user") -> str:
    cfg.agent(to)
    mid = store.send(sender, to, body)
    if tmux.has_session() and tmux.has_window(to):
        tmux.send_keys(to, POKE_TEXT)
    else:
        print(f"aviso: janela '{to}' não encontrada; mensagem persistida na inbox", file=sys.stderr)
    return mid


def _require_agent(env: Mapping[str, str]) -> str | None:
    return env.get("SAC_AGENT")


def cmd_next(store: Store, env: Mapping[str, str]) -> int:
    agent = _require_agent(env)
    if not agent:
        print("erro: SAC_AGENT não definido (rode dentro de um pane de agente)", file=sys.stderr)
        return 2
    msg = store.next(agent)
    if msg is None:
        print("inbox vazia")
        return 0
    print(f"=== mensagem {msg.id} (de {msg.sender}) ===")
    print(msg.body)
    return 0


def cmd_done(store: Store, env: Mapping[str, str], msg_id: str, summary: str) -> int:
    agent = _require_agent(env)
    if not agent:
        print("erro: SAC_AGENT não definido", file=sys.stderr)
        return 2
    try:
        store.done(agent, msg_id, summary)
    except StoreError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    print(f"ok: {msg_id} concluída")
    return 0


def extract_reply(pane_text: str) -> tuple[bool, str]:
    idx = pane_text.rfind(SENTINEL)
    if idx == -1:
        return False, pane_text
    end = pane_text.find("\n", idx)
    if end == -1:
        end = len(pane_text)
    return True, pane_text[:idx].rstrip("\n")


def cmd_up(cfg: Config, store: Store, tmux: Tmux, project_root: Path) -> int:
    if tmux.has_session():
        print(f" sessão '{tmux.session}' já existe — use `sac attach`")
        return 0
    leader = cfg.leader
    tmux.new_session(leader.name, [leader.command, *leader.args], env={"SAC_AGENT": leader.name})
    _inject_prompt(tmux, leader, project_root)
    for agent in cfg.agents:
        if agent.name == leader.name:
            continue
        tmux.new_window(agent.name, [agent.command, *agent.args], env={"SAC_AGENT": agent.name})
        _inject_prompt(tmux, agent, project_root)
    print(f"sessão '{tmux.session}' no ar com {len(cfg.agents)} agentes")
    return 0


def _inject_prompt(tmux: Tmux, agent, project_root: Path) -> None:
    if not agent.prompt_file:
        return
    p = project_root / agent.prompt_file
    if p.is_file():
        tmux.paste(agent.name, p.read_text(encoding="utf-8"))


def cmd_down(cfg: Config, tmux: Tmux) -> int:
    if tmux.has_session():
        tmux.kill_session()
        print(f"sessão '{tmux.session}' encerrada (.sac/ preservado)")
    else:
        print("nenhuma sessão ativa")
    return 0


def cmd_status(cfg: Config, store: Store, tmux: Tmux) -> int:
    up = tmux.has_session()
    print(f"sessão '{tmux.session}': {'ativa' if up else 'inativa'}")
    for a in cfg.agents:
        win = up and tmux.has_window(a.name)
        inbox = len(store.pending(a.name))
        claimed = len(store.claimed(a.name))
        print(f"  {a.name:<12} {a.role:<7} janela={'sim' if win else 'não'}  inbox={inbox} claimed={claimed}")
    return 0


def cmd_recv(cfg: Config, tmux: Tmux, agent: str, lines: int = 200) -> int:
    cfg.agent(agent)
    done, text = extract_reply(tmux.capture_pane(agent, lines))
    if not done:
        print("⏳ ainda processando (sem SAC_DONE)")
        print(text[-500:])
        return 1
    print(text)
    return 0


def notify_sweep(cfg: Config, store: Store, tmux: Tmux) -> dict[str, int]:
    pokes = {}
    for a in cfg.agents:
        stale = store.stale(a.name, cfg.poke_stale_after)
        if stale:
            tmux.send_keys(a.name, f"SAC: {len(stale)} mensagem(ns) aguardando — rode `sac next`")
            store.log("poke", agent=a.name, count=len(stale))
            pokes[a.name] = len(stale)
    return pokes


def cmd_notify(cfg: Config, store: Store, tmux: Tmux, once: bool = False) -> int:
    if once:
        notify_sweep(cfg, store, tmux)
        return 0
    print(f"notify ativo (intervalo {cfg.notify_interval}s, stale após {cfg.poke_stale_after}s) — Ctrl-C para sair")
    try:
        while True:
            notify_sweep(cfg, store, tmux)
            time.sleep(cfg.notify_interval)
    except KeyboardInterrupt:
        return 0


def cmd_run(cfg: Config, store: Store, tmux: Tmux, loop_name: str, task: str) -> str:
    loop = next((l for l in cfg.loops if l.name == loop_name), None)
    if loop is None:
        raise ConfigError(f"loop desconhecido: {loop_name}")
    return cmd_send(cfg, store, tmux, loop.sequence[0], f"[loop {loop_name}] {task}", sender="user")


def cmd_log(store: Store, follow: bool = False) -> int:
    path = store.root / "log.jsonl"
    if not path.is_file():
        print("log vazio")
        return 0
    with path.open(encoding="utf-8") as f:
        while True:
            line = f.readline()
            if line:
                print(line, end="")
            elif follow:
                time.sleep(1)
            else:
                break
    return 0
