"""CLI do SAC: argparse → commands."""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import sys
from pathlib import Path

from .commands import (
    cmd_done, cmd_doctor, cmd_down, cmd_inject, cmd_kill, cmd_log, cmd_next,
    cmd_notify, cmd_recv, cmd_run, cmd_send, cmd_sidebar, cmd_sidebar_toggle, cmd_status,
    cmd_uninstall, cmd_up,
)
from .config import ConfigError, load_config
from .init import cmd_init
from .daemon import run_daemon
from .store import Store, StoreError
from .tmux import Tmux, TmuxError

CONFIG_HIDDEN = Path(".sac") / "sac.toml"
CONFIG_LEGACY = Path("sac.toml")


def resolve_config_path(args_config: str | None) -> Path | None:
    """Cadeia de descoberta: --config > $SAC_CONFIG > ./.sac/sac.toml > ./sac.toml.

    Retorna o primeiro caminho existente, ou None se nenhum existir.
    """
    if args_config:
        return Path(args_config)
    env = os.environ.get("SAC_CONFIG")
    if env:
        return Path(env)
    if CONFIG_HIDDEN.is_file():
        return CONFIG_HIDDEN
    if CONFIG_LEGACY.is_file():
        return CONFIG_LEGACY
    return None


def workspace_root(cfg_path: Path) -> Path:
    """Raiz do workspace: dir do config, exceto quando o config é `.sac/sac.toml`."""
    parent = cfg_path.resolve().parent
    return parent.parent if parent.name == ".sac" else parent


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sac", description="Stupid Agentic Coordinator")
    p.add_argument("--config", default=None,
                   help="caminho do sac.toml (default: $SAC_CONFIG, ./.sac/sac.toml ou ./sac.toml)")
    p.add_argument("--sac-root", help="diretório raiz da fila (padrão: diretório do config / .sac)")
    p.add_argument("--version", action="version",
                   version=importlib.metadata.version("sac"))
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("up", help="sobe a sessão tmux com os agentes")
    sub.add_parser("down", help="encerra a sessão (preserva .sac/)")
    sp = sub.add_parser("status", help="visão geral dos agentes e filas")
    sp.add_argument("--clean", action="store_true", help="remove mensagens órfãs de agentes removidos do config")
    sp.add_argument("--yes", action="store_true", help="confirma execução do --clean (sem --yes, apenas simula)")
    sp.add_argument("--mini", action="store_true", help="resumo de uma linha (n● n!) para o status bar do tmux")
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

    sp_sidebar = sub.add_parser("sidebar", help="renderiza a sidebar com status dos agentes")
    sp_sidebar.add_argument("--toggle", nargs="?", const="", default=None, metavar="WINDOW",
                            help="cria/mata o pane da sidebar na window (default: atual)")
    sp_sidebar.add_argument("--watch", action="store_true",
                            help="loop de atualização in-place (sem flicker)")

    sp = sub.add_parser("run", help="dá o pontapé em um loop declarado")
    sp.add_argument("loop")
    sp.add_argument("task")

    sp = sub.add_parser("kill", help="mata e recria o harness de um agente")
    sp.add_argument("agent")

    sub.add_parser("init", help="cria .sac/sac.toml + prompts + .sac/ via questionário interativo")
    sub.add_parser("doctor", help="diagnóstico do ambiente (Python, tmux, socket, config, harnesses)")
    sub.add_parser("uninstall", help="remove .sac/, prompts/ e sac.toml legado do workspace (com confirmação)")
    sub.add_parser("daemon", help="daemon de mensageria (uso interno, sobe no dashboard)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    cfg_path = resolve_config_path(args.config)

    if args.command == "init":
        root = workspace_root(cfg_path) if cfg_path else Path(".")
        return cmd_init(root=root)

    if args.command == "doctor":
        return cmd_doctor(cfg_path)

    if args.command == "uninstall":
        root = workspace_root(cfg_path) if cfg_path else Path(".").resolve()
        cfg = None
        tmux = None
        if cfg_path and cfg_path.is_file():
            try:
                cfg = load_config(cfg_path)
            except ConfigError as e:
                print(f"aviso: config inválida ({e}) — sessão tmux não verificada", file=sys.stderr)
            else:
                tmux = Tmux(cfg.session_name, socket=cfg.socket)
        return cmd_uninstall(root, cfg, tmux)

    if cfg_path is None:
        print("erro: config não encontrado — caminhos tentados: --config, $SAC_CONFIG, "
              "./.sac/sac.toml, ./sac.toml — rode `sac init` para criar um", file=sys.stderr)
        return 1
    cfg_path = cfg_path.resolve()
    try:
        cfg = load_config(cfg_path)
    except ConfigError as e:
        print(f"erro de configuração: {e}", file=sys.stderr)
        return 1

    project_root = workspace_root(cfg_path)
    if args.sac_root:
        store_root = Path(args.sac_root)
    elif os.environ.get("SAC_ROOT"):
        store_root = Path(os.environ["SAC_ROOT"])
    elif cfg.root:
        store_root = Path(cfg.root)
    else:
        store_root = project_root
    store = Store(store_root)
    tmux = Tmux(cfg.session_name, socket=cfg.socket)

    try:
        match args.command:
            case "up":
                return cmd_up(cfg, store, tmux, project_root, config_path=cfg_path)
            case "inject":
                return cmd_inject(cfg, tmux, project_root, args.agent)
            case "down":
                return cmd_down(cfg, store, tmux)
            case "status":
                return cmd_status(cfg, store, tmux, clean=args.clean, yes=args.yes, mini=args.mini)
            case "sidebar":
                if args.toggle is not None:
                    return cmd_sidebar_toggle(cfg, tmux, args.toggle or None)
                return cmd_sidebar(cfg, store, tmux, watch=args.watch)
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
                return cmd_kill(cfg, store, tmux, project_root, args.agent, config_path=cfg_path)
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
