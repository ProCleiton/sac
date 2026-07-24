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


def _daemon_active(store: Store) -> bool:
    pid_path = store.root / "daemon.pid"
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError):
        pid_path.unlink(missing_ok=True)
        return False
    except PermissionError:
        return True


def cmd_send(cfg: Config, store: Store, tmux: Tmux, to: str, body: str, sender: str = "user") -> str:
    if to != "user":
        cfg.agent(to)
    mid = store.send(sender, to, body)
    if to == "user":
        return mid
    if _daemon_active(store):
        return mid
    if tmux.has_session():
        pid = tmux.find_pane_id(to)
        if pid:
            tmux.send_keys(pid, POKE_TEXT)
        else:
            print(f"aviso: pane do agente '{to}' não encontrado; mensagem persistida na inbox", file=sys.stderr)
    return mid


def _require_agent(env: Mapping[str, str]) -> str | None:
    return env.get("SAC_AGENT")


def cmd_next(store: Store, env: Mapping[str, str]) -> int:
    agent = _require_agent(env)
    if not agent:
        print("erro: SAC_AGENT não definido (rode dentro de um pane de agente)", file=sys.stderr)
        return 2
    if _daemon_active(store):
        msg = store.ack(agent)
    else:
        msg = store.next(agent)
        if msg and msg.reply_to:
            store.finish_reply(agent, msg.id)
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


def cmd_kill(cfg: Config, store: Store, tmux: Tmux, project_root: Path | None,
             agent_name: str, boot_wait: float | None = None) -> int:
    cfg.agent(agent_name)
    if not tmux.has_session():
        print("erro: nenhuma sessão ativa", file=sys.stderr)
        return 1
    pid = tmux.find_pane_id(agent_name)
    if not pid:
        print(f"erro: pane do agente '{agent_name}' não encontrado", file=sys.stderr)
        return 1
    sidebar_id = tmux.find_pane_by_command("sac sidebar", window=agent_name)
    if not sidebar_id:
        print(f"erro: sidebar não encontrada na janela do agente '{agent_name}'", file=sys.stderr)
        return 1
    tmux.kill_pane(pid)
    agent = cfg.agent(agent_name)
    harness_id = tmux.split_window(sidebar_id, [agent.command, *agent.args],
                                    env={"SAC_AGENT": agent.name})
    tmux.resize_pane(sidebar_id, SIDEBAR_WIDTH)
    tmux.set_pane_title(harness_id, agent.name)
    _boot = boot_wait if boot_wait is not None else cfg.boot_wait
    if _boot > 0:
        time.sleep(_boot)
    if project_root:
        _inject_prompt(tmux, agent, project_root, pane_id=harness_id)
    claimed = store.claimed(agent_name)
    if claimed:
        time.sleep(0.5)
        tmux.paste(harness_id, f"SAC: tarefa {claimed[0]} pendente — rode `sac done {claimed[0]}`")
        tmux.press_enter(harness_id)
    store.log("kill", agent=agent_name)
    print(f"ok: harness do '{agent_name}' reiniciado")
    return 0


SIDEBAR_CMD = ["sh", "-c", "while true; do clear; sac sidebar; sleep 5; done"]
SIDEBAR_WIDTH = 30
DASH_LOG_CMD = ["sac", "log", "-f"]
DASH_NOTIFY_CMD = ["sac", "daemon"]


def cmd_sidebar(cfg: Config, store: Store, tmux: Tmux) -> int:
    out_lines = ["SAC", ""]
    # Mapeia índice da janela para cada agente e dash
    cmd_raw = tmux._run("list-windows", "-t", tmux.session, "-F",
                        "#{window_index} #{window_name}").stdout
    win_map: dict[str, str] = {}  # window_name → index
    for line in cmd_raw.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            win_map[parts[1]] = parts[0]
    # Agentes agrupados por role
    agents = sorted(cfg.agents, key=lambda a: a.role != "leader")
    for a in agents:
        inbox = len(store.pending(a.name))
        claimed = len(store.claimed(a.name))
        if claimed > 0:
            marker = "\u2699"
        elif inbox > 0:
            marker = "\U0001f4e8"
        else:
            marker = "\u00b7"
        wid = win_map.get(a.name, "\u2014")
        out_lines.append(f"{a.name:<8} {marker} in={inbox} cl={claimed} [{wid}]")
    out_lines.append("")
    # Loops
    if cfg.loops:
        out_lines.append("loops")
        for l in cfg.loops:
            seq = "\u2192".join(l.sequence)
            out_lines.append(f"  {l.name}: {seq}")
        out_lines.append("")
    # Atalhos
    out_lines.append("atalhos")
    for a in agents:
        wid = win_map.get(a.name)
        if wid:
            out_lines.append(f"C-b {wid} {a.name}")
    dash_w = win_map.get("dash")
    if dash_w:
        out_lines.append(f"C-b {dash_w} dash")
    out_lines.append("C-b d detach")
    print("\n".join(out_lines))
    return 0


def cmd_up(cfg: Config, store: Store, tmux: Tmux, project_root: Path,
           boot_wait: float | None = None) -> int:
    if tmux.has_session():
        print(f" sessão '{tmux.session}' já existe — use `sac attach`")
        return 0
    agents = sorted(cfg.agents, key=lambda a: a.role != "leader")
    harness_ids = {}
    first = True
    for agent in agents:
        if first:
            sidebar_id = tmux.new_session(agent.name, SIDEBAR_CMD)
            first = False
        else:
            sidebar_id = tmux.new_window(agent.name, SIDEBAR_CMD)
        harness_id = tmux.split_window(sidebar_id, [agent.command, *agent.args],
                                        env={"SAC_AGENT": agent.name})
        tmux.resize_pane(sidebar_id, SIDEBAR_WIDTH)
        tmux.set_pane_title(harness_id, agent.name)
        harness_ids[agent.name] = harness_id
    # janela dashboard (sidebar + log + notify)
    d_side = tmux.new_window("dash", SIDEBAR_CMD)
    d_log = tmux.split_window(d_side, DASH_LOG_CMD)
    tmux.split_window(d_log, DASH_NOTIFY_CMD, vertical=True)
    tmux.resize_pane(d_side, SIDEBAR_WIDTH)
    # aterrissar no leader
    leader_name = agents[0].name
    tmux.select_window(leader_name)
    tmux.select_pane(harness_ids[leader_name])
    # boot wait + prompts (per-agent)
    for agent in agents:
        _boot = boot_wait if boot_wait is not None else (agent.boot_wait if agent.boot_wait is not None else cfg.boot_wait)
        if _boot > 0:
            time.sleep(_boot)
        pid = harness_ids.get(agent.name)
        if pid:
            _inject_prompt(tmux, agent, project_root, pane_id=pid)
    agent_names = " ".join(a.name for a in cfg.agents)
    tmux_bin = f"tmux -S {cfg.socket}" if cfg.socket else "tmux"
    hook_cmd = (
        f"run-shell 'for w in {agent_names}; do "
        f"id=$({tmux_bin} list-panes -t {tmux.session}:$w "
        f"-F \"##{{pane_id}} ##{{pane_start_command}}\" | grep \"sac sidebar\" | cut -d\" \" -f1); "
        f"[ -n \"$id\" ] && {tmux_bin} resize-pane -t \"$id\" -x {SIDEBAR_WIDTH}; "
        f"done; true'")
    tmux._run("set-hook", "-t", tmux.session, "client-resized", hook_cmd)
    print(f"sessão '{tmux.session}' no ar com {len(cfg.agents)} agentes + dashboard")
    if sys.stdin.isatty():
        _cmd = ["tmux"]
        if cfg.socket:
            _cmd += ["-S", cfg.socket]
        _cmd += ["attach", "-t", cfg.session_name]
        os.execvp("tmux", _cmd)
    return 0


def _inject_prompt(tmux: Tmux, agent, project_root: Path, pane_id: str | None = None) -> None:
    if not agent.prompt_file or not pane_id:
        return
    p = project_root / agent.prompt_file
    if p.is_file():
        tmux.paste(pane_id, p.read_text(encoding="utf-8"))
        tmux.press_enter(pane_id)


def cmd_inject(cfg: Config, tmux: Tmux, project_root: Path, agent_name: str) -> int:
    try:
        a = cfg.agent(agent_name)
    except ConfigError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    if not a.prompt_file:
        print(f"aviso: {agent_name} não tem prompt_file configurado", file=sys.stderr)
        return 1
    pid = tmux.find_pane_id(agent_name)
    if not pid:
        print(f"aviso: pane do agente '{agent_name}' não encontrado na sessão", file=sys.stderr)
        return 1
    _inject_prompt(tmux, a, project_root, pane_id=pid)
    return 0


def cmd_down(cfg: Config, tmux: Tmux) -> int:
    if tmux.has_session():
        tmux.kill_session()
        print(f"sessão '{tmux.session}' encerrada (.sac/ preservado)")
    else:
        print("nenhuma sessão ativa")
    return 0


def cmd_status(cfg: Config, store: Store, tmux: Tmux, clean: bool = False, yes: bool = False) -> int:
    if clean:
        names = [a.name for a in cfg.agents]
        if yes:
            stats = store.clean_orphans(names, dry_run=False)
            print(f"limpeza: {stats['inbox_files']} inbox, {stats['claimed_files']} claimed removidos "
                  f"({len(stats['agents_removed'])} agentes)")
        else:
            stats = store.clean_orphans(names, dry_run=True)
            agents = ", ".join(stats["agents_removed"]) or "nenhum"
            print(f"simulação: {stats['inbox_files']} inbox, {stats['claimed_files']} claimed — "
                  f"agentes órfãos: {agents} (use --yes para executar)")
    up = tmux.has_session()
    print(f"sessão '{tmux.session}': {'ativa' if up else 'inativa'}")
    for a in cfg.agents:
        win = up and tmux.has_pane(a.name)
        inbox = len(store.pending(a.name))
        claimed = len(store.claimed(a.name))
        print(f"  {a.name:<12} {a.role:<7} janela={'sim' if win else 'não'}  inbox={inbox} claimed={claimed}")
    return 0


def cmd_recv(cfg: Config, tmux: Tmux, agent: str, lines: int = 200) -> int:
    cfg.agent(agent)
    pid = tmux.find_pane_id(agent)
    if not pid:
        print(f"erro: pane do agente '{agent}' não encontrado na sessão", file=sys.stderr)
        return 1
    done, text = extract_reply(tmux.capture_pane(pid, lines))
    if not done:
        print("⏳ ainda processando (sem SAC_DONE)")
        print(text[-500:])
        return 1
    print(text)
    return 0


def notify_sweep(cfg: Config, store: Store, tmux: Tmux, poke_state: dict | None = None) -> dict[str, int]:
    pokes = {}
    for a in cfg.agents:
        stale = store.stale(a.name, cfg.poke_stale_after)
        if not stale:
            continue
        ids_pending = set(store.pending(a.name) + store.claimed(a.name))
        stale = [m for m in stale if m in ids_pending]
        if not stale:
            continue
        stale = [m for m in stale if _should_poke(m, poke_state, cfg)]
        if not stale:
            continue
        pid = tmux.find_pane_id(a.name)
        if pid:
            tmux.send_keys(pid, f"SAC: {len(stale)} mensagem(ns) aguardando — rode `sac next`")
            store.log("poke", agent=a.name, count=len(stale))
            if poke_state is not None:
                for m in stale:
                    poke_state.setdefault(a.name, {})[m] = time.monotonic()
            pokes[a.name] = len(stale)
    return pokes


def _should_poke(msg_id: str, poke_state: dict | None, cfg: Config) -> bool:
    if poke_state is None:
        return True
    for agent_state in poke_state.values():
        if msg_id in agent_state:
            last = agent_state[msg_id]
            n = sum(1 for v in agent_state.values() if v <= last)
            interval = min(cfg.poke_stale_after * (2 ** n), 600)
            if time.monotonic() - last < interval:
                return False
    return True


def cmd_notify(cfg: Config, store: Store, tmux: Tmux, once: bool = False) -> int:
    poke_state: dict[str, dict[str, float]] = {}
    if once:
        try:
            notify_sweep(cfg, store, tmux, poke_state=poke_state)
        except Exception as exc:
            store.log("loop_error", error=str(exc))
        return 0
    print(f"notify ativo (intervalo {cfg.notify_interval}s, stale após {cfg.poke_stale_after}s) — Ctrl-C para sair")
    try:
        while True:
            try:
                notify_sweep(cfg, store, tmux, poke_state=poke_state)
            except Exception as exc:
                store.log("loop_error", error=str(exc))
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
        if follow:
            while not path.is_file():
                time.sleep(0.5)
        else:
            print("log vazio")
            return 0
    with path.open(encoding="utf-8") as f:
        while True:
            try:
                line = f.readline()
            except OSError as exc:
                store.log("loop_error", error=str(exc))
                time.sleep(1)
                continue
            if line:
                print(line, end="")
            elif follow:
                time.sleep(1)
            else:
                break
    return 0
