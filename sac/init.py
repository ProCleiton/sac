"""Questionário interativo para gerar .sac/sac.toml e prompts."""
from __future__ import annotations

import re
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Callable

from .config import AgentConfig, Config, LoopConfig
from .contracts import AUX_CONTRACTS, CONTRACTS, DEFAULT_AUX_CONTRACT, LEADER_CONTRACT

KIMI_NOTE = """- Kimi Code: respostas longas e analíticas.
- O modelo é o que você configurou nos args do agente (ex.: `--model <alias/modelo>`).
- Saídas muito longas podem ser colapsadas pela TUI (`Ctrl+O` para expandir).
"""

OPENCODE_NOTE = """- opencode: respostas diretas e código.
- Use `--auto` para aprovação automática de comandos shell seguros.
- Prefira `ask` para consultas e `edit/write` para alterações.
"""

_HARNESS_PREFERENCE = ("kimi", "opencode", "claude")

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _valid_name(val: str) -> bool:
    return bool(_NAME_RE.fullmatch(val)) if val else False


class InitError(Exception):
    """Erro controlado durante o questionário init."""


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _ask(question: str, default: str, stdin, stdout, validate: Callable | None = None,
         hint: str | None = None) -> str:
    if hint:
        stdout(f"  ⤷ {hint}")
    display = f"{question} [{default}]: " if default else f"{question}: "
    while True:
        stdout(display)
        try:
            raw = stdin()
        except (EOFError, KeyboardInterrupt):
            raise InitError("init cancelado pelo usuário")
        val = raw.strip() or default
        if validate and not validate(val):
            stdout(f"  entrada inválida: {val}")
            continue
        return val


def _detect_harness() -> str | None:
    """Primeiro harness canônico encontrado no PATH (kimi → opencode → claude)."""
    for h in _HARNESS_PREFERENCE:
        if shutil.which(h):
            return h
    return None


def _contract_by_key(key: str) -> dict:
    return next(c for c in CONTRACTS if c["key"] == key)


def _ask_contract(stdin, stdout) -> dict:
    stdout("  Contrato (papel) do agente:")
    for i, c in enumerate(AUX_CONTRACTS, 1):
        stdout(f"    {i}. {c['titulo']} — {c['resumo']}")
    default_idx = next(i for i, c in enumerate(AUX_CONTRACTS, 1) if c["key"] == DEFAULT_AUX_CONTRACT)
    escolha = _ask("Contrato", str(default_idx), stdin, stdout,
                   validate=lambda v: v.isdigit() and 1 <= int(v) <= len(AUX_CONTRACTS),
                   hint="Enter = desenvolvedor; o contrato completo vai para prompts/<nome>.md")
    return AUX_CONTRACTS[int(escolha) - 1]


def _list_models(command: str, kimi_cfg: Path | None = None) -> list[str]:
    """Modelos válidos do harness: kimi (config do usuário) / opencode (CLI).

    Falha ou harness desconhecido → [] (o wizard cai em texto livre).
    """
    if command == "kimi":
        cfg = kimi_cfg or (Path.home() / ".kimi-code" / "config.toml")
        try:
            data = tomllib.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return []
        return sorted(data.get("models", {}).keys())
    if command == "opencode":
        import subprocess
        try:
            r = subprocess.run(["opencode", "models"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return []
        if r.returncode != 0:
            return []
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    return []


def _ask_windows(stdin, stdout, agents: list[AgentConfig]) -> dict[str, str]:
    agrupar = _ask("Agrupar agentes em janelas? (s/N)", "n", stdin, stdout,
                   hint="janelas agrupam panes lado a lado ou empilhados; "
                        "agentes fora de janelas ficam com janela própria")
    if agrupar.lower() != "s":
        return {}
    names = [a.name for a in agents]
    windows: dict[str, str] = {}
    used: set[str] = set()
    while True:
        wname = _ask("Nome da janela", f"win-{len(windows) + 1}", stdin, stdout,
                     validate=_valid_name)
        while True:
            raw = _ask("Agentes (nomes separados por espaço)", "", stdin, stdout,
                       hint=f"agentes disponíveis: {' '.join(names)}")
            sel = raw.split()
            unknown = [s for s in sel if s not in names]
            grouped = [s for s in sel if s in used]
            if not sel or len(set(sel)) != len(sel) or unknown or grouped:
                detalhe = ""
                if unknown:
                    detalhe += f"; desconhecidos: {', '.join(unknown)}"
                if grouped:
                    detalhe += f"; já agrupados: {', '.join(grouped)}"
                stdout(f"  entrada inválida — agentes válidos: {', '.join(names)}{detalhe}")
                continue
            break
        disp = "1"
        if len(sel) > 1:
            disp = _ask("Disposição (1 = lado a lado, 2 = empilhados)", "1", stdin, stdout,
                        validate=lambda v: v in ("1", "2"),
                        hint="lado a lado = colunas (;); empilhados = pilha (,)")
        sep = ";" if disp == "1" else ","
        windows[wname] = sep.join(sel)
        used.update(sel)
        stdout("preview do layout:")
        for w, spec in windows.items():
            stdout(f'  {w} = "{spec}"')
        mais = _ask("Adicionar outra janela? (s/N)", "n", stdin, stdout)
        if mais.lower() != "s":
            break
    return windows


def _collect_config(stdin, stdout) -> Config:
    session = _ask("Nome da sessão", "sac", stdin, stdout, validate=_valid_name,
                   hint="aparece em `sac attach` e `tmux ls` — ex.: esteira, nfi")
    socket = _ask("Socket tmux (caminho; Enter = sem socket)", "", stdin, stdout,
                  hint="ex.: ~/.sac-nfi/tmux.sock — isola a esteira do seu tmux pessoal; "
                       "Enter = sem socket (não recomendado)")
    boot_wait = int(_ask("Boot wait (segundos)", "10", stdin, stdout,
                         validate=lambda v: v.isdigit(),
                         hint="segundos antes de injetar o prompt; harness lento pede mais — ex.: 10 a 15"))

    agents = []
    n_agents = int(_ask("Número de agentes", "3", stdin, stdout,
                        validate=lambda v: v.isdigit() and int(v) > 0,
                        hint="quantos agentes (panes) a esteira terá"))

    detected = _detect_harness()
    for i in range(n_agents):
        if i == 0:
            stdout("\n--- Agente 1 (leader — o orquestrador) ---")
            stdout("  ⤷ recebe suas mensagens e delega aos demais; é o pane do `sac attach`")
        else:
            stdout(f"\n--- Agente {i+1} (aux) ---")
        name = _ask("Nome", f"agent-{i+1}", stdin, stdout, validate=_valid_name,
                    hint="usado no `sac send` e `sac status` — ex.: leader, dev-1")
        if detected:
            cmd_default, cmd_hint = detected, f"detectado no seu PATH ({detected})"
        else:
            cmd_default = "kimi" if i == 0 else "opencode"
            cmd_hint = "binário do harness — deve existir no PATH"
        command = _ask("Comando (kimi/opencode/claude)", cmd_default, stdin, stdout, hint=cmd_hint)
        while shutil.which(command) is None:
            stdout(f"  ⚠ harness '{command}' não encontrado no PATH — você pode corrigir "
                   "ou seguir assim (ex.: config para outra máquina)")
            corrigir = _ask("Corrigir o comando? (s/N)", "n", stdin, stdout)
            if corrigir.lower() != "s":
                break
            command = _ask("Comando (kimi/opencode/claude)", command, stdin, stdout,
                           hint="binário do harness — deve existir no PATH")
        contract = _contract_by_key(LEADER_CONTRACT) if i == 0 else _ask_contract(stdin, stdout)
        models = _list_models(command)
        if models:
            stdout("  Modelos disponíveis:")
            for mi, m in enumerate(models, 1):
                stdout(f"    {mi}. {m}")
            escolha = _ask("Modelo (número; Enter = não passar --model)", "", stdin, stdout,
                           validate=lambda v: v == "" or (v.isdigit() and 1 <= int(v) <= len(models)),
                           hint="Enter = default do harness")
            model = models[int(escolha) - 1] if escolha else ""
        else:
            model = _ask("Modelo (opcional — ex.: k3; vazio = não passar --model)", "", stdin, stdout,
                         hint="vazio = não passar --model (usa o default do harness)")
        args = ["--model", model] if model else []
        if command == "opencode":
            args.append("--auto")
        abw = _ask("Boot wait específico (Enter para usar o global)", "", stdin, stdout,
                   hint="só se ESTE harness demora mais que o global — ex.: harness pesado → 15; "
                        "Enter = usa o global")
        boot_wait_agent: float | None = None
        if abw:
            while True:
                try:
                    boot_wait_agent = float(abw)
                    break
                except ValueError:
                    stdout(f"  valor não numérico: {abw}")
                    abw = _ask("Boot wait específico (número)", "", stdin, stdout)
                    if not abw:
                        break
        prompt_name = f"prompts/{name}.md"
        agents.append(AgentConfig(
            name=name, command=command, args=args,
            role="leader" if i == 0 else "aux", prompt_file=prompt_name,
            boot_wait=boot_wait_agent, contract=contract["key"],
        ))

    loops = []
    add_loops = _ask("Adicionar loops? (s/N)", "n", stdin, stdout,
                     hint="loops encadeiam agentes em ciclo (ex.: dev → revisor)")
    if add_loops.lower() == "s":
        n_loops = int(_ask("Quantos loops", "1", stdin, stdout, validate=lambda v: v.isdigit()))
        for i in range(n_loops):
            stdout(f"\n--- Loop {i+1} ---")
            lname = _ask("Nome do loop", f"loop-{i+1}", stdin, stdout, validate=_valid_name)
            seq = _ask("Sequência (nomes separados por espaço)", " ".join(a.name for a in agents if a.role == "aux"), stdin, stdout,
                       hint="ordem dos agentes no ciclo")
            sequence = [s.strip() for s in seq.split() if s.strip()]
            max_it = int(_ask("Max iterações", "3", stdin, stdout, validate=lambda v: v.isdigit(),
                              hint="limite de voltas do ciclo antes de escalar ao leader"))
            loops.append(LoopConfig(name=lname, sequence=sequence, max_iterations=max_it))

    windows = _ask_windows(stdin, stdout, agents)
    if windows:
        # o config exige todos os agentes nos specs: quem ficou de fora ganha janela própria
        grouped = {n for spec in windows.values() for n in re.split(r"[;,]", spec)}
        for a in agents:
            if a.name not in grouped:
                windows[a.name] = a.name

    return Config(
        session_name=session,
        boot_wait=boot_wait,
        socket=socket if socket else None,
        windows=windows,
        agents=agents,
        loops=loops,
    )


def _generate_toml(cfg: Config) -> str:
    lines = [
        "[session]",
        f'name = "{cfg.session_name}"',
        "",
    ]
    if cfg.socket:
        lines.append(f'socket = "{cfg.socket}"')
        lines.append("")
    lines.append(f"boot_wait = {cfg.boot_wait}")
    lines.append("")
    if cfg.windows:
        lines.append("[windows]")
        for wname, spec in cfg.windows.items():
            lines.append(f'{wname} = "{spec}"')
        lines.append("")
    for a in cfg.agents:
        lines.append("[[agents]]")
        lines.append(f'name = "{a.name}"')
        lines.append(f'command = "{a.command}"')
        if a.args:
            lines.append(f'args = {a.args}')
        lines.append(f'role = "{a.role}"')
        lines.append(f'prompt_file = "prompts/{a.name}.md"')
        if a.boot_wait is not None:
            lines.append(f"boot_wait = {a.boot_wait}")
        lines.append("")
    for l in cfg.loops:
        lines.append("[[loops]]")
        lines.append(f'name = "{l.name}"')
        lines.append(f'sequence = {l.sequence}')
        lines.append(f"max_iterations = {l.max_iterations}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _harness_name(cfg: Config, agent: AgentConfig) -> str:
    return agent.command


def _harness_note(cfg: Config, agent: AgentConfig) -> str:
    h = agent.command
    if h == "kimi":
        return KIMI_NOTE
    elif h == "opencode":
        return OPENCODE_NOTE
    return ""


def _render_contract(contract: dict, harness: str, harness_note: str) -> str:
    """Contrato completo: papel + protocolo de mensageria SAC + disciplina + notas do harness."""
    parts = [
        f"# Papel: {contract['titulo']} (SAC)",
        contract["intro"],
        contract["mensageria"],
        contract["disciplina"],
        f"## Notas do harness ({harness})\n{harness_note}".rstrip(),
    ]
    return "\n\n".join(p.strip("\n") for p in parts if p.strip()) + "\n"


def _generate_prompts(cfg: Config, root: Path, stdin=None, stdout=None) -> bool:
    stdin = stdin or input
    stdout = stdout or print
    prompts_dir = root / "prompts"
    if prompts_dir.is_dir():
        existing = list(prompts_dir.glob("*.md"))
        if existing:
            answer = _ask("Arquivos de prompt já existem. Sobrescrever? (s/N)", "n", stdin, stdout)
            if answer.lower() != "s":
                stdout("prompts mantidos")
                return False
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for a in cfg.agents:
        key = a.contract or (LEADER_CONTRACT if a.role == "leader" else DEFAULT_AUX_CONTRACT)
        content = _render_contract(_contract_by_key(key), _harness_name(cfg, a), _harness_note(cfg, a))
        (prompts_dir / f"{a.name}.md").write_text(content, encoding="utf-8")
    return True


def _print_onboarding(stdout) -> None:
    stdout("=== Próximos passos ===")
    stdout("1. Pre-warm: rode o harness 1x no diretório para aprovar plugins/login")
    stdout("   → kimi . (ou o comando do seu harness)")
    stdout("2. Revise os contratos gerados (edite à vontade):")
    stdout("   → prompts/*.md")
    stdout("3. Ajuste a configuração da esteira se precisar:")
    stdout("   → .sac/sac.toml (layout [windows], boot_wait etc.)")
    stdout("4. Suba a esteira:")
    stdout("   → sac up")
    stdout("5. Acompanhe:")
    stdout("   → sac attach")
    stdout("")
    stdout("Veja o guia iniciante em docs/beginner-guide.md")


def cmd_init(stdin=None, stdout=None, root: Path | None = None, is_interactive: bool | None = None) -> int:
    stdin = stdin or input
    stdout = stdout or print
    root = root or Path(".")
    root = root.resolve()

    if is_interactive is None:
        is_interactive = _is_interactive()
    if not is_interactive:
        stdout("erro: modo interativo requer terminal — use --config para apontar um sac.toml existente")
        return 1

    try:
        stdout("SAC init — este wizard gera:")
        stdout("  .sac/sac.toml   (configuração da esteira)")
        stdout("  .sac/           (estado: inbox/claimed/done)")
        stdout("  prompts/*.md    (contrato de cada agente — edite à vontade depois)")
        stdout("")

        sac_dir = root / ".sac"
        config_path = sac_dir / "sac.toml"
        legacy = root / "sac.toml"
        if config_path.exists() or legacy.exists():
            answer = _ask("config já existe (.sac/sac.toml ou sac.toml). Sobrescrever? (s/N)", "n", stdin, stdout)
            if answer.lower() != "s":
                stdout("init cancelado")
                return 0

        cfg = _collect_config(stdin, stdout)

        toml_content = _generate_toml(cfg)
        try:
            tomllib.loads(toml_content)
        except Exception as e:
            stdout(f"erro interno: TOML gerado é inválido ({e}) — init abortado")
            return 1
        sac_dir.mkdir(parents=True, exist_ok=True)
        config_path.write_text(toml_content, encoding="utf-8")
        stdout(f"config criado em {config_path}")

        _generate_prompts(cfg, root, stdin=stdin, stdout=stdout)
        stdout(f"prompts criados em {root / 'prompts'}/")

        for sub in ("inbox", "claimed", "done"):
            (sac_dir / sub).mkdir(parents=True, exist_ok=True)
        stdout(f"estado .sac/ criado em {sac_dir}/")

        if cfg.socket:
            sock_path = Path(cfg.socket).expanduser()
            sock_path.parent.mkdir(parents=True, exist_ok=True)
            stdout(f"diretorio do socket criado: {sock_path.parent}")

        stdout("pronto!")
        _print_onboarding(stdout)
        return 0
    except InitError as e:
        stdout(str(e))
        return 1
