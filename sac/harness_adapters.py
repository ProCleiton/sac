"""Adapters de injeção dos plugins canônicos por harness — tabela data-driven.

Cada entrada pode ter:
- `args_always`: args acrescentados sempre (independente de plugins);
- `args_skills`: args acrescentados SÓ com o superpowers instalado;
- `env_skills`: env acrescentada SÓ com o superpowers instalado.

Placeholders: `{skills}` = dir de skills do superpowers; `{plugin}` = raiz do
clone do superpowers. Harness fora da tabela não recebe nada — o fallback é o
ponteiro das skills no contrato (seção "Stack canônica SAC").

Isolamento só onde há mecanismo limpo por invocação que não quebra
autenticação (COPILOT_HOME/CODEX_HOME limpos quebrariam login); gemini, aider
e goose não têm mecanismo confiável por invocação.
"""
from __future__ import annotations

from pathlib import Path

from .plugins_manifest import PLUGINS, plugin_dir, sac_home, superpowers_skills_dir

_SUPERPOWERS = next(p for p in PLUGINS if p["nome"] == "superpowers")

ADAPTERS: dict[str, dict] = {
    # --skills-dir substitui a auto-descoberta: o agente usa SÓ as skills do SAC
    "kimi": {"args_skills": ["--skills-dir", "{skills}"]},
    # --pure: roda sem plugins externos (mimo é fork do opencode)
    "opencode": {"args_always": ["--pure"]},
    "mimo": {"args_always": ["--pure"]},
    # superpowers É um plugin Claude (com skills/ dentro); --bare pula a auto-descoberta
    "claude": {"args_skills": ["--bare", "--plugin-dir", "{plugin}"]},
    "copilot": {"env_skills": {"COPILOT_SKILLS_DIRS": "{skills}"}},
    "codex": {"args_skills": ["-c", 'skills.config=[{{path="{skills}",enabled=true}}]']},
}


def _render(template: str, home: Path) -> str:
    return template.format(skills=superpowers_skills_dir(home),
                           plugin=plugin_dir(home, _SUPERPOWERS))


def harness_args(command: str, home: Path | None = None) -> list[str]:
    """Args extras do adapter do harness ([] se desconhecido)."""
    home = sac_home() if home is None else Path(home)
    adapter = ADAPTERS.get(command, {})
    args = list(adapter.get("args_always", ()))
    if "args_skills" in adapter and superpowers_skills_dir(home).is_dir():
        args += [_render(a, home) for a in adapter["args_skills"]]
    return args


def harness_env(command: str, home: Path | None = None) -> dict[str, str]:
    """Env extra do adapter do harness ({} se desconhecido)."""
    home = sac_home() if home is None else Path(home)
    adapter = ADAPTERS.get(command, {})
    if "env_skills" in adapter and superpowers_skills_dir(home).is_dir():
        return {k: _render(v, home) for k, v in adapter["env_skills"].items()}
    return {}
