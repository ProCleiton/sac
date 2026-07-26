"""Lógica dos comandos do SAC. Funções puras com dependências injetadas."""
from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from .config import Config, ConfigError
from .store import Store, StoreError
from .tmux import Tmux

POKE_TEXT = "SAC: mensagem — rode `sac next`"
SENTINEL = "SAC_DONE"

ESCALATION_CONTRACT = (
    "[SAC — CONTRATO DE ESCALAÇÃO]\n"
    "Você NUNCA fala diretamente com o humano. Dúvida, erro, bloqueio ou falta de "
    "permissão: reporte IMEDIATAMENTE ao líder com `sac send {leader} \"...\"`, "
    "substituindo `...` pela descrição real da situação (NUNCA envie placeholders "
    "literais como `<situação>`), e aguarde a resposta dele. Sem situação real a "
    "reportar, não envie mensagem. O líder é o único canal com o humano.\n\n"
)
ESCALATION_CONTRACT_LEADER = (
    "[SAC — CONTRATO DE ESCALAÇÃO]\n"
    "Você é o ÚNICO canal com o humano (`sac send user`). Os workers se reportam a "
    "você — nunca ao humano; a triagem dos problemas deles é sua responsabilidade.\n\n"
)


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
            tmux.poke_with_enter(pid, POKE_TEXT)
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
        ok = store.done(agent, msg_id, summary)
    except StoreError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    if not ok:
        print(f"erro: falha ao mover {msg_id} para done/ (detalhes no log.jsonl)", file=sys.stderr)
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


def _agent_window(cfg: Config, agent_name: str) -> str:
    """Janela onde o agente vive: legado = nome do agente; grid = janela da gramática [windows]."""
    if not cfg.windows:
        return agent_name
    from .layout import build_plan
    for wplan in build_plan(cfg.windows):
        if any(op.agent == agent_name for op in wplan.ops):
            return wplan.name
    return agent_name


def _session_env(store: Store, config_path: Path | None, agent: str | None = None) -> dict[str, str]:
    """Env de sessão exportada aos panes: comandos `sac` resolvem a sessão certa de qualquer cwd."""
    env = {}
    if agent:
        env["SAC_AGENT"] = agent
    env["SAC_ROOT"] = str(store.root.parent)
    if config_path:
        env["SAC_CONFIG"] = str(config_path)
    return env


def _default_config_path(project_root: Path | None) -> Path | None:
    """Config efetivo do workspace: sempre `.sac/sac.toml` (legado ignorado desde a v25)."""
    if project_root is None:
        return None
    return project_root / ".sac" / "sac.toml"


def cmd_kill(cfg: Config, store: Store, tmux: Tmux, project_root: Path | None,
             agent_name: str, boot_wait: float | None = None,
             config_path: Path | None = None) -> int:
    cfg.agent(agent_name)
    if not tmux.has_session():
        print("erro: nenhuma sessão ativa", file=sys.stderr)
        return 1
    pid = tmux.find_pane_id(agent_name)
    window = _agent_window(cfg, agent_name)
    sidebar_id = tmux.find_pane_by_command("sac sidebar", window=window)
    if not sidebar_id:
        print(f"erro: sidebar não encontrada na janela '{window}' do agente '{agent_name}'", file=sys.stderr)
        return 1
    revive = pid is None
    if pid:
        tmux.kill_pane(pid)
    agent = cfg.agent(agent_name)
    _cfg_path = config_path or _default_config_path(project_root)
    harness_id = tmux.split_window(sidebar_id, [agent.command, *agent.args],
                                    env=_session_env(store, _cfg_path, agent.name), full=revive)
    tmux.resize_pane(sidebar_id, SIDEBAR_WIDTH)
    tmux.set_pane_title(harness_id, agent.name)
    tmux.set_pane_option(harness_id, "@agent", agent.name)
    _boot = boot_wait if boot_wait is not None else cfg.boot_wait
    if _boot > 0:
        time.sleep(_boot)
    if project_root:
        _inject_prompt(tmux, cfg, agent, project_root, pane_id=harness_id)
    claimed = store.claimed(agent_name)
    if claimed:
        time.sleep(0.5)
        tmux.paste(harness_id, f"SAC: tarefa {claimed[0]} pendente — rode `sac done {claimed[0]}`")
        tmux.press_enter(harness_id)
    store.log("kill", agent=agent_name, revive=revive)
    print(f"ok: harness do '{agent_name}' {'revivido' if revive else 'reiniciado'}")
    return 0


SIDEBAR_CMD = ["sac", "sidebar", "--watch"]
SIDEBAR_WIDTH = 30
DASH_LOG_CMD = ["sac", "log", "-f"]
DASH_NOTIFY_CMD = ["sac", "daemon"]


class _Progress:
    """Barra de progresso animada (0-100%, verde) que reescreve a mesma linha."""

    CELLS = 20

    def __init__(self, total: int, enabled: bool = True):
        self.total = max(1, total)
        self.done = 0
        self.enabled = enabled

    def _line(self, frac_done: float, label: str) -> str:
        pct = min(100, int(frac_done / self.total * 100))
        filled = pct * self.CELLS // 100
        bar = "█" * filled + "░" * (self.CELLS - filled)
        return f"\r\033[32m{bar}\033[0m {pct:3d}% {label:<44.44}"

    def render(self, frac_done: float, label: str) -> None:
        if not self.enabled:
            return
        sys.stdout.write(self._line(frac_done, label))
        sys.stdout.flush()

    def step(self, label: str) -> None:
        self.done += 1
        self.render(self.done, label)

    def wait(self, seconds: float, label: str) -> None:
        end = time.monotonic() + seconds
        while True:
            left = end - time.monotonic()
            if left <= 0:
                break
            frac = self.done + (seconds - left) / seconds if seconds > 0 else self.done + 1
            self.render(frac, label)
            time.sleep(min(0.1, left))

    def finish(self) -> None:
        if self.enabled:
            sys.stdout.write("\n")
            sys.stdout.flush()


TIPS_LINES = [
    "  C-b e sidebar",
    "  C-b o next",
    "  C-b h/j/k/l pane",
    "  C-b z zoom",
    "  C-b H/J/K/L resize",
    "  C-b w tree",
    "  C-b [ copy",
    "  C-b ] paste",
    "  C-b d detach",
]


def _escalated_agents(store: Store) -> set[str]:
    path = store.root / "log.jsonl"
    if not path.is_file():
        return set()
    esc: dict[str, int] = {}
    done: dict[str, int] = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("event") == "escalate":
            esc[ev.get("agent", "")] = i
        elif ev.get("event") == "done":
            done[ev.get("agent", "")] = i
    return {a for a, idx in esc.items() if idx > done.get(a, -1)}


_ANSI = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "orange": "\033[38;5;208m", "green": "\033[38;5;114m",
    "yellow": "\033[38;5;215m", "red": "\033[38;5;203m",
    "gray": "\033[38;5;245m", "white": "\033[38;5;255m",
}


def _section(title: str) -> str:
    pad = "─" * max(2, 23 - len(title))
    return f"{_ANSI['orange']}╭─ {title} {pad}╮{_ANSI['reset']}"


def _colored_marker(marker: str) -> str:
    cor = {"\u25cf": "green", "!": "red", "\u25d0": "yellow"}.get(marker, "dim")
    return f"{_ANSI[cor]}{_ANSI['bold']}{marker}{_ANSI['reset']}"


def _sidebar_marker(store: Store, agent: str, escalated: set[str]) -> str:
    if store.claimed(agent):
        return "\u25cf"
    if agent in escalated:
        return "!"
    if store.pending(agent):
        return "\u25d0"
    return "\u00b7"


def _agent_model(agent) -> str:
    """Basename do comando do harness."""
    return agent.command.rsplit("/", 1)[-1]


_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _truncate_ansi(line: str, width: int) -> str:
    """Trunca pela largura visível preservando os códigos ANSI (reset ao cortar)."""
    if width <= 0 or len(_ANSI_RE.sub("", line)) <= width:
        return line
    out, visible, i = [], 0, 0
    for m in _ANSI_RE.finditer(line):
        chunk = line[i:m.start()]
        room = width - visible
        out.append(chunk[:room])
        visible += min(len(chunk), room)
        out.append(m.group(0))
        i = m.end()
        if visible >= width:
            break
    if visible < width:
        out.append(line[i:i + (width - visible)])
    out.append(_ANSI["reset"])
    return "".join(out)


def _fmt_age(seconds: float) -> str:
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def _comms_lines(store: Store, limit: int = 5) -> list[str]:
    path = store.root / "log.jsonl"
    if not path.is_file():
        return [f"  {_ANSI['dim']}(vazio){_ANSI['reset']}"]
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    out = []
    for ev in events[-limit:]:
        hhmm = str(ev.get("ts", ""))[11:16]
        who = ev.get("sender") or ev.get("agent") or "?"
        arrow = f"\u2192{ev['to']}" if ev.get("to") else ""
        event = ev.get("event", "?")
        cor = {"done": "green", "escalate": "red", "loop_error": "red"}.get(event, "white")
        out.append(f"  {_ANSI['dim']}{hhmm}{_ANSI['reset']} {who}{arrow} "
                   f"{_ANSI[cor]}{event}{_ANSI['reset']}")
    return out or [f"  {_ANSI['dim']}(vazio){_ANSI['reset']}"]


def _render_sidebar(cfg: Config, store: Store, tmux: Tmux,
                    cursor: int | None = None) -> tuple[str, dict[int, tuple]]:
    agents = {a.name: a for a in cfg.agents}
    escalated = _escalated_agents(store)
    rows: list[tuple[str, tuple | None]] = []
    wins_raw = tmux._run("list-windows", "-t", tmux.session, "-F",
                         "#{window_name}|#{window_active}").stdout
    panes_raw = tmux._run("list-panes", "-s", "-t", tmux.session, "-F",
                          "#{window_name}|#{@agent}|#{pane_active}|#{pane_id}").stdout
    panes_by_win: dict[str, list[tuple[str, bool, str]]] = {}
    for line in panes_raw.splitlines():
        parts = line.split("|")
        if len(parts) != 4:
            continue
        wname, title, active, pid = parts
        if title in agents:
            panes_by_win.setdefault(wname, []).append((title, active == "1", pid))
    for line in wins_raw.splitlines():
        parts = line.split("|")
        if len(parts) != 2:
            continue
        wname, wactive = parts
        if wactive == "1":
            rows.append((f"{_ANSI['bold']}> {wname}{_ANSI['reset']}", ("window", wname)))
        else:
            rows.append((f"{_ANSI['dim']}  {wname}{_ANSI['reset']}", ("window", wname)))
        panes = panes_by_win.get(wname, [])
        for i, (title, focused, pid) in enumerate(panes):
            connector = "└─" if i == len(panes) - 1 else "├─"
            marker = _colored_marker(_sidebar_marker(store, title, escalated))
            model = _agent_model(agents[title])
            n = store.inbox_count(title)
            badge = f" ({n})" if n else ""
            age = store.last_event_age(title)
            age_s = f"{_ANSI['dim']} · {_fmt_age(age)}{_ANSI['reset']}" if age is not None else ""
            star = "* " if focused and wactive == "1" else ""
            linha = (f"  {connector} {_ANSI['bold'] if star else ''}{star}{title}"
                     f"{_ANSI['reset'] if star else ''} {marker} "
                     f"{_ANSI['gray']}{model}{_ANSI['reset']}{badge}{age_s}")
            rows.append((linha, ("agent", wname, pid)))
    rows.append(("", None))
    rows.append((_section("comms"), None))
    rows += [(l, None) for l in _comms_lines(store)]
    rows.append(("", None))
    rows.append((_section("tips"), None))
    tips = [f"{_ANSI['green']}{l}{_ANSI['reset']}" for l in TIPS_LINES]
    rows += [(l, None) for l in tips]
    hits = {i: a for i, (_, a) in enumerate(rows) if a}
    import shutil
    width = shutil.get_terminal_size().columns
    text_lines = []
    for i, (line, action) in enumerate(rows):
        line = _truncate_ansi(line, width)
        if cursor is not None and action and i == cursor:
            text_lines.append(f"\033[7m{line}\033[0m")
        else:
            text_lines.append(line)
    return "\n".join(text_lines), hits


def _activate(tmux: Tmux, action: tuple) -> None:
    if action[0] == "window":
        tmux.select_window(action[1])
    elif action[0] == "agent":
        tmux.select_window(action[1])
        tmux.select_pane(action[2])


def _move_cursor(hits: dict[int, tuple], cursor: int, delta: int) -> int:
    ordered = sorted(hits)
    if not ordered:
        return cursor
    if cursor not in hits:
        return ordered[0] if delta > 0 else ordered[-1]
    idx = (ordered.index(cursor) + delta) % len(ordered)
    return ordered[idx]


def _handle_input(data: str, hits: dict[int, tuple], cursor: int, tmux: Tmux) -> int:
    for m in re.finditer(r"\033\[<(\d+);(\d+);(\d+)([Mm])", data):
        botao, _x, y, tipo = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
        if tipo == "M" and botao == 0:  # clique esquerdo (press)
            action = hits.get(y - 1)
            if action:
                _activate(tmux, action)
                return y - 1
    if "j" in data or "\033[B" in data:
        return _move_cursor(hits, cursor, 1)
    if "k" in data or "\033[A" in data:
        return _move_cursor(hits, cursor, -1)
    if "\r" in data or "\n" in data:
        action = hits.get(cursor)
        if action:
            _activate(tmux, action)
    return cursor


def _frame(text: str) -> str:
    """Frame de redraw in-place: home, cada linha limpa até o fim, limpa o resto."""
    linhas = "\n".join(l + "\033[K" for l in text.split("\n"))
    return "\033[H" + linhas + "\033[J"


def _interactive_sidebar(cfg: Config, store: Store, tmux: Tmux, interval: float) -> None:
    import select as _select
    import termios
    import tty
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        old = None
    cursor = 0
    try:
        if old:
            tty.setcbreak(fd)
        sys.stdout.write("\033[?1000h\033[?1006h\033[?25l")  # mouse SGR + esconde cursor
        sys.stdout.flush()
        while True:
            text, hits = _render_sidebar(cfg, store, tmux, cursor=cursor)
            sys.stdout.write(_frame(text))
            sys.stdout.flush()
            pronto, _, _ = _select.select([sys.stdin], [], [], interval)
            if pronto:
                data = os.read(fd, 128).decode("utf-8", errors="ignore")
                cursor = _handle_input(data, hits, cursor, tmux)
    finally:
        if old:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\033[?1000l\033[?1006l\033[?25h")
        sys.stdout.flush()


def cmd_sidebar(cfg: Config, store: Store, tmux: Tmux, watch: bool = False,
                interval: float = 5.0) -> int:
    if not watch:
        print(_render_sidebar(cfg, store, tmux)[0])
        return 0
    _interactive_sidebar(cfg, store, tmux, interval)
    return 0


def cmd_sidebar_toggle(cfg: Config, tmux: Tmux, window: str | None) -> int:
    target = window or tmux._run("display-message", "-p", "#{window_id}").stdout.strip()
    out = tmux._run("list-panes", "-t", target, "-F",
                    "#{pane_id}|#{@pane_role}|#{pane_active}").stdout
    sidebar = active = None
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        pid, role, is_active = parts
        if role == "sidebar":
            sidebar = pid
        if is_active == "1":
            active = pid
    if sidebar:
        tmux.kill_pane(sidebar)
        return 0
    cols = _sidebar_cols(tmux, target)
    pid = tmux.split_window(target, SIDEBAR_CMD, lines=cols, full=True, before=True)
    _mark_sidebar_pane(tmux, pid)
    tmux.resize_pane(pid, cols)
    if active:
        tmux.select_pane(active)
    return 0


def cmd_up(cfg: Config, store: Store, tmux: Tmux, project_root: Path,
           boot_wait: float | None = None, stdout: Callable[..., None] | None = None,
           config_path: Path | None = None) -> int:
    if cfg.socket:
        Path(cfg.socket).parent.mkdir(parents=True, exist_ok=True)
    if tmux.has_session():
        print(f" sessão '{tmux.session}' já existe — use `sac attach`")
        return 0
    _out = stdout or (print if sys.stdout.isatty() else lambda s: None)
    agents = sorted(cfg.agents, key=lambda a: a.role != "leader")
    total = len(agents)
    use_bar = stdout is None and sys.stdout.isatty()
    prog = _Progress(total * 2 + 1, enabled=use_bar)
    env_base = _session_env(store, config_path or _default_config_path(project_root))

    def _notify(label: str) -> None:
        if use_bar:
            prog.step(label)
        else:
            _out(label)

    if cfg.windows:
        harness_ids = _materialize_grid(cfg, tmux, _notify, env_base)
        entry_window = next(iter(cfg.windows))
    else:
        harness_ids = _materialize_legacy(cfg, tmux, agents, _notify, env_base)
        entry_window = agents[0].name
    # aterrissar na entry window (leader)
    leader_name = agents[0].name
    tmux.select_window(entry_window)
    tmux.select_pane(harness_ids[leader_name])
    # memória de longo prazo: reescreve a seção do contrato do líder antes de injetar
    from .memory import refresh_leader_prompt
    refresh_leader_prompt(cfg, store.root, project_root)
    # boot wait + prompts (per-agent, com tempo decorrido)
    boot_start = time.monotonic()
    for agent in agents:
        _boot = boot_wait if boot_wait is not None else (agent.boot_wait if agent.boot_wait is not None else cfg.boot_wait)
        if _boot > 0:
            elapsed = time.monotonic() - boot_start
            remaining = max(0.0, _boot - elapsed)
            if remaining > 0:
                if use_bar:
                    prog.wait(remaining, f"{agent.name}: aguardando boot")
                else:
                    _out(f"[.../{total}] {agent.name}: aguardando {remaining:.0f}s para prompt...")
                    time.sleep(remaining)
            elif not use_bar:
                _out(f"[.../{total}] {agent.name}: pulando espera (já decorrido {elapsed:.0f}s)...")
        pid = harness_ids.get(agent.name)
        if pid:
            _notify(f"{agent.name}: injetando prompt")
            _inject_prompt(tmux, cfg, agent, project_root, pane_id=pid)
    prog.finish()
    if not cfg.windows:
        _install_legacy_resize_hook(cfg, tmux)
    else:
        _install_grid_resize_hook(cfg, tmux)
    _configure_appearance(cfg, tmux, project_root, harness_ids)
    tmux._run("bind-key", "e", "run-shell", "sac sidebar --toggle '#{window_id}'")
    print(f"sessão '{tmux.session}' no ar com {len(cfg.agents)} agentes + dashboard")
    if sys.stdin.isatty():
        _cmd = ["tmux"]
        if cfg.socket:
            _cmd += ["-S", cfg.socket]
        _cmd += ["attach", "-t", cfg.session_name]
        os.execvp("tmux", _cmd)
    return 0


def _materialize_legacy(cfg: Config, tmux: Tmux, agents, _out,
                        env_base: dict[str, str] | None = None) -> dict[str, str]:
    harness_ids = {}
    first = True
    total = len(agents)
    for idx, agent in enumerate(agents, 1):
        _out(f"[{idx}/{total}] {agent.name}: criando janela...")
        if first:
            sidebar_id = tmux.new_session(agent.name, SIDEBAR_CMD, env=env_base,
                                          width=cfg.session_width, height=cfg.session_height)
            first = False
        else:
            sidebar_id = tmux.new_window(agent.name, SIDEBAR_CMD, env=env_base)
        _mark_sidebar_pane(tmux, sidebar_id)
        harness_id = tmux.split_window(sidebar_id, [agent.command, *agent.args],
                                        env={**env_base, "SAC_AGENT": agent.name} if env_base else {"SAC_AGENT": agent.name})
        tmux.resize_pane(sidebar_id, SIDEBAR_WIDTH)
        tmux.set_pane_title(harness_id, agent.name)
        tmux.set_pane_option(harness_id, "@agent", agent.name)
        harness_ids[agent.name] = harness_id
    _materialize_dash(tmux, _out, total, env_base)
    return harness_ids


def _materialize_dash(tmux: Tmux, _out, total: int,
                      env_base: dict[str, str] | None = None) -> None:
    _out(f"[{total+1}/{total+1}] dash: criando dashboard...")
    d_side = tmux.new_window("dash", SIDEBAR_CMD, env=env_base)
    _mark_sidebar_pane(tmux, d_side)
    d_log = tmux.split_window(d_side, DASH_LOG_CMD, env=env_base)
    tmux.split_window(d_log, DASH_NOTIFY_CMD, vertical=True, env=env_base)
    tmux.resize_pane(d_side, SIDEBAR_WIDTH)


def _install_legacy_resize_hook(cfg: Config, tmux: Tmux) -> None:
    agent_names = " ".join(a.name for a in cfg.agents)
    tmux_bin = f"tmux -S {cfg.socket}" if cfg.socket else "tmux"
    hook_cmd = (
        f"run-shell 'for w in {agent_names}; do "
        f"id=$({tmux_bin} list-panes -t {tmux.session}:$w "
        f"-F \"##{{pane_id}} ##{{pane_start_command}}\" | grep \"sac sidebar\" | cut -d\" \" -f1); "
        f"if [ -n \"$id\" ]; then "
        f"ww=$({tmux_bin} display-message -p -t {tmux.session}:$w \"#{{window_width}}\"); "
        f"side=$(( ww * {SIDEBAR_PCT} / 100 )); "
        f"[ $side -lt {SIDEBAR_MIN_COLS} ] && side={SIDEBAR_MIN_COLS}; "
        f"{tmux_bin} resize-pane -t \"$id\" -x $side; "
        f"fi; "
        f"done; true'")
    tmux._run("set-hook", "-t", tmux.session, "client-resized", hook_cmd)


def _mark_sidebar_pane(tmux: Tmux, pid: str) -> None:
    tmux.set_pane_option(pid, "@pane_role", "sidebar")
    tmux.set_pane_option(pid, "pane-border-format", " #[fg=colour245] sidebar #[default] ")


SIDEBAR_MIN_COLS = 28
SIDEBAR_PCT = 18

AGENT_PALETTE = [203, 215, 114, 39, 75, 141, 176, 180]


def agent_color(name: str) -> int:
    """Cor estável por agente: hash do nome na paleta fixa."""
    h = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return AGENT_PALETTE[int(h, 16) % len(AGENT_PALETTE)]


def _configure_appearance(cfg: Config, tmux: Tmux, project_root: Path,
                          harness_ids: dict[str, str]) -> None:
    tmux._run("set-option", "-t", tmux.session, "mouse", "on")
    tmux._run("set-option", "-g", "pane-border-status", "top")
    tmux._run("set-option", "-g", "pane-border-lines", "heavy")
    for name, pid in harness_ids.items():
        color = agent_color(name)
        tmux.set_pane_option(pid, "@agent_color", f"colour{color}")
        tmux.set_pane_option(pid, "pane-border-format",
                             f" #[fg=colour{color},bold] #{{@agent}} #[default] ")
        tmux.set_pane_option(pid, "pane-border-style", "fg=colour240")
    # Status bar v4 — paleta Catppuccin CCB com separadores powerline
    workspace = project_root.name
    tmux._run("set-option", "-t", tmux.session, "status-style", "bg=#1e1e2e,fg=#cdd6f4")
    tmux._run("set-option", "-t", tmux.session, "status-left",
              "#[bg=#{?client_prefix,#f38ba8,"
              "#{?pane_in_mode,#fab387,#f5c2e7}}]"
              "#[fg=#1e1e2e,bold] "
              "#{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}} "
              "#[fg=#{?client_prefix,#f38ba8,"
              "#{?pane_in_mode,#fab387,#f5c2e7}},bg=#1e1e2e]\ue0b0"
              "#[align=centre]"
              f"#[fg=#6c7086] {workspace} "
              "#[align=left]")
    tmux._run("set-option", "-t", tmux.session, "status-right",
              "#[fg=#f38ba8,bg=#1e1e2e]"
              "#[fg=#1e1e2e,bg=#f38ba8,bold] #{@agent} "
              "#[fg=#cba6f7,bg=#f38ba8]\ue0b2"
               "#[fg=#1e1e2e,bg=#cba6f7,bold] SAC "
               "#(sac --version 2>/dev/null) "
               "#[fg=#89b4fa,bg=#cba6f7]\ue0b2"
              "#[fg=#1e1e2e,bg=#89b4fa] "
              "#(sac status --mini 2>/dev/null) "
              "#[fg=#fab387,bg=#89b4fa]\ue0b2"
              "#[fg=#1e1e2e,bg=#fab387,bold] "
              "#(date +\"%d/%m %a %H:%M\") #[default]")
    tmux._run("set-option", "-t", tmux.session, "status-left-length", "80")
    tmux._run("set-option", "-t", tmux.session, "status-right-length", "120")
    tmux._run("set-option", "-g", "window-status-format", "")
    tmux._run("set-option", "-g", "window-status-current-format", "")
    tmux_bin = f"tmux -S {cfg.socket}" if cfg.socket else "tmux"
    hook = (
        f"run-shell 'for p in $({tmux_bin} list-panes -s -t {tmux.session} "
        f"-F \"##{{pane_id}}\") ; do {tmux_bin} set -p -t \"$p\" pane-border-style fg=colour240; done; "
        f"{tmux_bin} set -p -t \"##{{pane_id}}\" pane-border-style \"fg=##{{@agent_color}}\"; true'")
    tmux._run("set-hook", "-t", tmux.session, "after-select-pane", hook)


def _install_grid_resize_hook(cfg: Config, tmux: Tmux) -> None:
    tmux_bin = f"tmux -S {cfg.socket}" if cfg.socket else "tmux"
    hook = (
        f"run-shell 'for p in $({tmux_bin} list-panes -s -t {tmux.session} "
        f"-F \"##{{pane_id}} ##{{@pane_role}}\" | awk \"$2 == \\\"sidebar\\\" {{print $1}}\"); do "
        f"w=$({tmux_bin} display-message -p -t \"$p\" \"##{{window_width}}\"); "
        f"c=$((w * {SIDEBAR_PCT} / 100)); [ $c -lt {SIDEBAR_MIN_COLS} ] && c={SIDEBAR_MIN_COLS}; "
        f"{tmux_bin} resize-pane -t \"$p\" -x $c; done; true'")
    tmux._run("set-hook", "-t", tmux.session, "client-resized", hook)


def _int(text: str, default: int) -> int:
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return default


def _sidebar_cols(tmux: Tmux, target: str) -> int:
    out = tmux._run("display-message", "-p", "-t", target, "#{window_width}").stdout
    return max(SIDEBAR_MIN_COLS, round(_int(out, 0) * SIDEBAR_PCT / 100))


def _materialize_grid(cfg: Config, tmux: Tmux, _out,
                      env_base: dict[str, str] | None = None) -> dict[str, str]:
    from .layout import build_plan
    plans = build_plan(cfg.windows)
    agents_by_name = {a.name: a for a in cfg.agents}
    harness_ids: dict[str, str] = {}
    total = len(cfg.agents)
    first = True
    for wplan in plans:
        if first:
            sidebar_id = tmux.new_session(wplan.name, SIDEBAR_CMD, env=env_base,
                                          width=cfg.session_width, height=cfg.session_height)
            first = False
        else:
            sidebar_id = tmux.new_window(wplan.name, SIDEBAR_CMD, env=env_base)
        _mark_sidebar_pane(tmux, sidebar_id)
        side = _sidebar_cols(tmux, sidebar_id)
        win_w = _int(tmux._run("display-message", "-p", "-t", sidebar_id,
                               "#{window_width}").stdout, 80)
        area_w = max(1, win_w - side)
        columns: list[list[str]] = [[]]
        for op in wplan.ops:
            if op.direction != "row" and columns[-1]:
                columns.append([])
            columns[-1].append(op.agent)
        weights = [len(c) for c in columns]
        total_w = sum(weights)
        widths = [max(1, round(w / total_w * area_w)) for w in weights]
        widths[-1] = max(1, area_w - sum(widths[:-1]))
        prev_col_first = prev_leaf = None
        for ci, col in enumerate(columns):
            for ri, agent_name in enumerate(col):
                agent = agents_by_name[agent_name]
                _out(f"{agent.name}: criando pane...")
                cmd = [agent.command, *agent.args]
                env = {**env_base, "SAC_AGENT": agent.name} if env_base else {"SAC_AGENT": agent.name}
                if ri == 0:
                    if ci == 0:
                        pid = tmux.split_window(sidebar_id, cmd, env=env, lines=widths[0])
                    else:
                        pid = tmux.split_window(prev_col_first, cmd, env=env,
                                                lines=widths[ci], full=True)
                    prev_col_first = pid
                else:
                    ph = _int(tmux._run("display-message", "-p", "-t", prev_leaf,
                                        "#{pane_height}").stdout, 24)
                    remaining = len(col) - ri
                    lines = max(1, round(ph * remaining / (remaining + 1)))
                    pid = tmux.split_window(prev_leaf, cmd, env=env,
                                            vertical=True, lines=lines)
                tmux.set_pane_title(pid, agent.name)
                tmux.set_pane_option(pid, "@agent", agent.name)
                harness_ids[agent.name] = pid
                prev_leaf = pid
        tmux.resize_pane(sidebar_id, side)
    _materialize_dash(tmux, _out, total, env_base)
    return harness_ids


def _inject_prompt(tmux: Tmux, cfg: Config, agent, project_root: Path, pane_id: str | None = None) -> None:
    if not pane_id:
        return
    contract = ESCALATION_CONTRACT_LEADER if agent.role == "leader" else ESCALATION_CONTRACT
    text = contract.format(leader=cfg.leader.name)
    if agent.prompt_file:
        p = project_root / agent.prompt_file
        if p.is_file():
            text += p.read_text(encoding="utf-8")
    tmux.paste(pane_id, text)
    tmux.press_enter(pane_id)


def cmd_inject(cfg: Config, tmux: Tmux, project_root: Path, agent_name: str) -> int:
    try:
        a = cfg.agent(agent_name)
    except ConfigError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    pid = tmux.find_pane_id(agent_name)
    if not pid:
        print(f"aviso: pane do agente '{agent_name}' não encontrado na sessão", file=sys.stderr)
        return 1
    _inject_prompt(tmux, cfg, a, project_root, pane_id=pid)
    return 0


def _kill_daemon(store: Store) -> None:
    pid_path = store.root / "daemon.pid"
    if not pid_path.exists():
        return
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except ValueError:
        pid_path.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):  # até 2s para o shutdown gracioso
            time.sleep(0.1)
            os.kill(pid, 0)
        os.kill(pid, signal.SIGKILL)  # teimoso: força
    except ProcessLookupError:
        pass
    except PermissionError:
        print(f"aviso: sem permissão para matar o daemon (pid {pid})", file=sys.stderr)
    pid_path.unlink(missing_ok=True)


def cmd_down(cfg: Config, store: Store, tmux: Tmux) -> int:
    if tmux.has_session():
        for agent in cfg.agents:
            pane = tmux.find_pane_id(agent.name)
            if pane:
                tmux.kill_pane(pane)
                time.sleep(0.3)
        _kill_daemon(store)
        tmux.kill_session()
        print(f"sessão '{tmux.session}' encerrada (.sac/ preservado)")
    else:
        _kill_daemon(store)
        print("nenhuma sessão ativa")
    return 0


def cmd_status(cfg: Config, store: Store, tmux: Tmux, clean: bool = False, yes: bool = False,
               mini: bool = False) -> int:
    if mini:
        claimed = sum(1 for a in cfg.agents if store.claimed(a.name))
        esc = len(_escalated_agents(store))
        parts = []
        if claimed:
            parts.append(f"{claimed}●")
        if esc:
            parts.append(f"{esc}!")
        print(" ".join(parts))
        return 0
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


def cmd_uninstall(root: Path, cfg: Config | None, tmux: Tmux | None = None,
                  stdin=None, stdout=None) -> int:
    """Remove a configuração do SAC no workspace: .sac/, prompts/ e sac.toml legado.

    Recusa se a sessão tmux estiver no ar; exige digitar o nome da sessão.
    Nada fora do diretório do workspace é tocado.
    """
    import shutil

    stdin = stdin or input
    stdout = stdout or print
    root = Path(root)

    if cfg is not None and tmux is not None and tmux.has_session():
        stdout(f"erro: sessão '{cfg.session_name}' no ar — rode `sac down` antes de desinstalar")
        return 1

    targets = [p for p in (root / ".sac", root / "prompts", root / "sac.toml") if p.exists()]
    if not targets:
        stdout("nada para remover — SAC não está configurado neste workspace")
        return 0

    stdout("os seguintes itens serão removidos:")
    for t in targets:
        stdout(f"  {t}")
    token = cfg.session_name if cfg is not None else "sac"
    stdout(f"para confirmar, digite o nome da sessão ({token}): ")
    try:
        answer = stdin()
    except (EOFError, KeyboardInterrupt):
        stdout("uninstall cancelado — nada removido")
        return 0
    if answer.strip() != token:
        stdout("confirmação não confere — nada removido")
        return 0

    for t in targets:
        if t.is_dir():
            shutil.rmtree(t)
        else:
            t.unlink()
    stdout("removido — nada fora do workspace foi tocado")
    return 0


def cmd_doctor(config_path: Path | None, stdout=print, which=None, tmux_version=None,
               py_version=None, cwd: Path | None = None) -> int:
    """Diagnóstico read-only do ambiente: Python, tmux, socket, config, harnesses.

    Exit 0 se todos os itens essenciais OK; 1 se algum essencial falhar.
    """
    import shutil
    import subprocess

    which = which or shutil.which
    if tmux_version is None:
        def tmux_version():
            return subprocess.run(["tmux", "-V"], capture_output=True, text=True).stdout.strip()
    py_version = tuple(py_version) if py_version else tuple(sys.version_info[:3])
    failed = False

    py_str = ".".join(str(v) for v in py_version)
    if py_version >= (3, 11):
        stdout(f"[OK]  Python {py_str}")
    else:
        stdout(f"[FAIL] Python {py_str} < 3.11 — upgrade Python to 3.11+")
        failed = True

    if which("tmux") is None:
        stdout("[FAIL] tmux not found — install with: apt install tmux / brew install tmux")
        failed = True
    else:
        ver = tmux_version().strip()
        m = re.search(r"(\d+)\.(\d+)", ver)
        if m and (int(m.group(1)), int(m.group(2))) >= (3, 2):
            stdout(f"[OK]  {ver}")
        else:
            stdout(f"[FAIL] {ver} < 3.2 — upgrade tmux to 3.2+ (o layout grid exige)")
            failed = True

    if which("openspec"):
        stdout("[OK]  openspec found in PATH")
    else:
        stdout("[WARN] openspec not found in PATH — stack canônica: "
               "npm i -g @fission-ai/openspec (ou equivalente)")

    if config_path is None:
        base0 = Path(cwd) if cwd is not None else Path(".")
        if (base0 / "sac.toml").is_file():
            stdout("[WARN] ./sac.toml existe na raiz mas é ignorado (fallback removido) — "
                   "mova para .sac/ ou apague — checagens dependentes puladas")
        else:
            stdout("[WARN] config not found (--config, $SAC_CONFIG, ./.sac/sac.toml) "
                   "— checagens dependentes puladas")
        return 1 if failed else 0
    config_path = Path(config_path)
    if not config_path.exists():
        stdout(f"[WARN] config not found ({config_path}) — checagens dependentes puladas")
        return 1 if failed else 0

    from .config import load_config
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        stdout(f"[FAIL] config inválida: {e}")
        return 1
    stdout(f"[OK]  config loads ({config_path}, {len(cfg.agents)} agents)")

    base = Path(cwd) if cwd is not None else Path(".")
    hidden = base / ".sac" / "sac.toml"
    legacy = base / "sac.toml"
    if hidden.is_file() and legacy.is_file() and config_path.resolve() == hidden.resolve():
        stdout("[WARN] ./sac.toml existe na raiz mas é ignorado (fallback removido) — "
               "mova para .sac/ ou apague")

    if cfg.socket:
        parent = Path(cfg.socket).expanduser().parent
        if parent.is_dir() and os.access(parent, os.W_OK):
            stdout(f"[OK]  socket dir {parent} is writable")
        else:
            stdout(f"[FAIL] socket dir {parent} not writable — crie o diretório ou ajuste `socket` no sac.toml")
            failed = True

    seen = set()
    for a in cfg.agents:
        if a.command in seen:
            continue
        seen.add(a.command)
        if which(a.command):
            stdout(f"[OK]  harness '{a.command}' found in PATH")
        else:
            stdout(f"[WARN] harness '{a.command}' not found in PATH (config may be for another machine)")

    return 1 if failed else 0
