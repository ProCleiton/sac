"""Questionário interativo para gerar sac.toml e prompts."""
from __future__ import annotations

import re
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Callable

from .config import AgentConfig, Config, LoopConfig

LEADER_PROMPT = """# Papel: leader (SAC)

Você é o leader de uma esteira coordenada pelo SAC. Tarefas aparecem
automaticamente no seu terminal.

## Contrato SAC (obrigatório)

- Tarefas chegam diretamente — você não precisa rodar `sac next`.
- Cada tarefa chega com cabeçalho `SAC <id> de <sender>:` na primeira linha.
- Trabalhe na tarefa. Ao terminar:
  1. Escreva `SAC_DONE` em uma linha separada.
  2. Rode `sac done <id> "<resumo>"` (o `<id>` está no cabeçalho).
- **Respostas** (mensagens que você recebe como retorno de uma tarefa que
  delegou) são concluídas automaticamente — NÃO rode `sac done` nelas.
- Para delegar a um auxiliar: `sac send <aux> "<tarefa>"`.
- Para cobrar revisão: `sac send <aux> "<o que revisar>"`.
- Para falar com o usuário: `sac send user "<mensagem>"`.

## Notas do harness ({harness})
{harness_note}
"""

AUX_PROMPT = """# Papel: aux (SAC)

Você é um auxiliar da esteira SAC. Tarefas chegam automaticamente.

## Contrato SAC (obrigatório)

- Tarefas chegam diretamente no seu terminal com cabeçalho `SAC <id> de <sender>:`.
- O `<remetente>` para `sac send` e o `<id>` para `sac done` vêm desse cabeçalho.
- Trabalhe com TDD: teste que falha primeiro, depois implementação mínima.
- Ao concluir:
  1. Envie o resultado ao remetente com `sac send <remetente> "<resumo>"`.
  2. Escreva `SAC_DONE`.
  3. Rode `sac done <id> "<resumo>"`.
- **Respostas** que você receber são concluídas automaticamente — NÃO rode
  `sac done` nelas, apenas leia e aja.
- Se o remetente for `user`, responda com `sac send user "<mensagem>".

## Notas do harness ({harness})
{harness_note}
"""

KIMI_NOTE = """- Kimi Code: respostas longas e analíticas.
- O modelo é o que você configurou nos args do agente (ex.: `--model <alias/modelo>`).
- Saídas muito longas podem ser colapsadas pela TUI (`Ctrl+O` para expandir).
"""

OPENCODE_NOTE = """- opencode: respostas diretas e código.
- Use `--auto` para aprovação automática de comandos shell seguros.
- Prefira `ask` para consultas e `edit/write` para alterações.
"""

PROMPT_TEMPLATES = {
    "leader": LEADER_PROMPT,
    "aux": AUX_PROMPT,
    "kimi": KIMI_NOTE,
    "opencode": OPENCODE_NOTE,
}

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


def _collect_config(stdin, stdout) -> Config:
    session = _ask("Nome da sessão", "sac", stdin, stdout, validate=_valid_name,
                   hint="nome da sessão tmux — usado no attach e na identificação")
    socket = _ask("Socket tmux (caminho, Enter vazio para sem socket dedicado)", "", stdin, stdout,
                  hint="socket dedicado isola a esteira do seu tmux pessoal (recomendado)")
    boot_wait = int(_ask("Boot wait (segundos)", "10", stdin, stdout,
                         validate=lambda v: v.isdigit(),
                         hint="tempo antes de injetar o prompt; harnesses lentos precisam de mais"))

    agents = []
    n_agents = int(_ask("Número de agentes", "3", stdin, stdout,
                        validate=lambda v: v.isdigit() and int(v) > 0,
                        hint="quantos agentes (panes) a esteira terá"))

    for i in range(n_agents):
        stdout(f"\n--- Agente {i+1} ---")
        name = _ask("Nome", f"agent-{i+1}", stdin, stdout, validate=_valid_name,
                    hint="identificador do agente — usado no sac send e no sac status")
        command = _ask("Comando (kimi/opencode)", "kimi" if i == 0 else "opencode", stdin, stdout,
                       hint="binário do harness — deve existir no PATH")
        while shutil.which(command) is None:
            stdout(f"  ⚠ harness '{command}' não encontrado no PATH — você pode corrigir "
                   "ou seguir assim (ex.: config para outra máquina)")
            corrigir = _ask("Corrigir o comando? (s/N)", "n", stdin, stdout)
            if corrigir.lower() != "s":
                break
            command = _ask("Comando (kimi/opencode)", command, stdin, stdout,
                           hint="binário do harness — deve existir no PATH")
        role = "leader" if i == 0 else _ask("Papel (leader/aux)", "aux", stdin, stdout,
                                            validate=lambda v: v in ("leader", "aux"),
                                            hint="leader coordena e delega; aux executa tarefas")
        model = _ask("Modelo (opcional — ex.: k3; vazio = não passar --model)", "", stdin, stdout,
                     hint="vazio = não passar --model (usa o default do harness)")
        args = ["--model", model] if model else []
        if command == "opencode":
            args.append("--auto")
        abw = _ask("Boot wait específico (Enter para usar o global)", "", stdin, stdout,
                   hint="sobrescreve o boot_wait global só para este agente")
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
            role=role, prompt_file=prompt_name,
            boot_wait=boot_wait_agent,
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

    return Config(
        session_name=session,
        boot_wait=boot_wait,
        socket=socket if socket else None,
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
        template_key = "leader" if a.role == "leader" else "aux"
        template = PROMPT_TEMPLATES[template_key]
        content = template.format(harness=_harness_name(cfg, a), harness_note=_harness_note(cfg, a))
        (prompts_dir / f"{a.name}.md").write_text(content, encoding="utf-8")
    return True


def _print_onboarding(stdout) -> None:
    stdout("=== Próximos passos ===")
    stdout("1. Pre-warm: rode o harness 1x no diretório para aprovar plugins/login")
    stdout("   → kimi . (ou o comando do seu harness)")
    stdout("2. Edite os prompts com as regras do seu projeto:")
    stdout("   → prompts/*.md")
    stdout("3. Suba a esteira:")
    stdout("   → sac up")
    stdout("4. Acompanhe:")
    stdout("   → sac attach")
    stdout("")
    stdout("Dica: configure o layout [windows] no sac.toml para agrupar agentes por função.")
    stdout("Veja o guia iniciante em docs/beginner-guide.md")


def cmd_init(stdin=None, stdout=None, root: Path | None = None, is_interactive: bool | None = None) -> int:
    stdin = stdin or input
    stdout = stdout or print
    root = root or Path(".")
    root = root.resolve()

    if is_interactive is None:
        is_interactive = _is_interactive()
    if not is_interactive:
        stdout("erro: init requer terminal interativo — use `sac --config <path>` para config existente")
        return 1

    try:
        sac_toml = root / "sac.toml"
        if sac_toml.exists():
            answer = _ask("sac.toml já existe. Sobrescrever? (s/N)", "n", stdin, stdout)
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
        sac_toml.write_text(toml_content, encoding="utf-8")
        stdout(f"sac.toml criado em {sac_toml}")

        _generate_prompts(cfg, root, stdin=stdin, stdout=stdout)
        stdout(f"prompts criados em {root / 'prompts'}/")

        sac_dir = root / ".sac"
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
