"""CLI do SAC: argparse → commands."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .commands import (
    cmd_done, cmd_down, cmd_inject, cmd_kill, cmd_log, cmd_next,
    cmd_notify, cmd_recv, cmd_run, cmd_send, cmd_sidebar, cmd_status, cmd_up,
)
from .config import ConfigError, load_config
from .init import cmd_init
from .daemon import run_daemon
from .store import Store, StoreError
from .tmux import Tmux, TmuxError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sac", description="Stupid Agentic Coordinator")
    p.add_argument("--config", default="sac.toml", help="caminho do sac.toml")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("up", help="sobe a sessão tmux com os agentes")
    sub.add_parser("down", help="encerra a sessão (preserva .sac/)")
    sp = sub.add_parser("status", help="visão geral dos agentes e filas")
    sp.add_argument("--clean", action="store_true", help="remove mensagens órfãs de agentes removidos do config")
    sp.add_argument("--yes", action="store_true", help="confirma execução do --clean (sem --yes, apenas simula)")
    sub.add_parser("attach", help="atacha à sessão tmux")
    sub.add_parser("next", help="puxa a próxima mensagem da sua inbox (agente)")

    sp = sub.add_parser("send", help="envia mensagem a um agente")
    sp.add_argument("to")
    sp.add_argument("body")

    sp = sub.add_parser("done", help="marca mensagem como concluída (agente)")
    sp.add_argument("msg_id")
    sp.add_argument("summary", nargs="*", default=[])

    sp = sub.add_parser("recv", help="lê a resposta de um agente")
    sp.add_argument("agent")
    sp.add_argument("--lines", type=int, default=200)

    sp = sub.add_parser("notify", help="watcher de re-cutucadas")
    sp.add_argument("--once", action="store_true")

    sp = sub.add_parser("log", help="mostra o log.jsonl")
    sp.add_argument("-f", "--follow", action="store_true")

    sp = sub.add_parser("inject", help="re-injeta o prompt_file de um agente")
    sp.add_argument("agent")

    sub.add_parser("sidebar", help="renderiza a sidebar com status dos agentes")

    sp = sub.add_parser("run", help="dá o pontapé em um loop declarado")
    sp.add_argument("loop")
    sp.add_argument("task")

    sp = sub.add_parser("kill", help="mata e recria o harness de um agente")
    sp.add_argument("agent")

    sub.add_parser("init", help="cria sac.toml + prompts + .sac/ via questionário interativo")
    sub.add_parser("daemon", help="daemon de mensageria (uso interno, sobe no dashboard)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "init":
        return cmd_init(root=Path(args.config).resolve().parent)

    cfg_path = Path(args.config).resolve()
    try:
        cfg = load_config(cfg_path)
    except ConfigError as e:
        print(f"erro de configuração: {e}", file=sys.stderr)
        return 1

    root = cfg_path.parent
    store = Store(root / ".sac")
    tmux = Tmux(cfg.session_name, socket=cfg.socket)

    try:
        match args.command:
            case "up":
                return cmd_up(cfg, store, tmux, root)
            case "inject":
                return cmd_inject(cfg, tmux, root, args.agent)
            case "down":
                return cmd_down(cfg, tmux)
            case "status":
                return cmd_status(cfg, store, tmux, clean=args.clean, yes=args.yes)
            case "sidebar":
                return cmd_sidebar(cfg, store, tmux)
            case "attach":
                cmd = ["tmux"]
                if cfg.socket:
                    cmd += ["-S", cfg.socket]
                cmd += ["attach", "-t", cfg.session_name]
                os.execvp("tmux", cmd)
            case "next":
                return cmd_next(store, os.environ)
            case "send":
                cmd_send(cfg, store, tmux, args.to, args.body,
                         sender=os.environ.get("SAC_AGENT", "user"))
                return 0
            case "done":
                return cmd_done(store, os.environ, args.msg_id, " ".join(args.summary))
            case "recv":
                return cmd_recv(cfg, tmux, args.agent, args.lines)
            case "notify":
                return cmd_notify(cfg, store, tmux, once=args.once)
            case "log":
                return cmd_log(store, follow=args.follow)
            case "run":
                cmd_run(cfg, store, tmux, args.loop, args.task)
                return 0
            case "kill":
                return cmd_kill(cfg, store, tmux, root, args.agent)
            case "daemon":
                return run_daemon(cfg, store, tmux)
    except (ConfigError, StoreError) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    except TmuxError as e:
        sock = f" ({cfg.socket})" if cfg.socket else ""
        print(f"erro tmux: {e} — verifique o socket{sock}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
