"""Parsing e validação de sac.toml (stdlib tomllib)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Configuração inválida ou ausente."""


@dataclass
class AgentConfig:
    name: str
    command: str
    args: list[str]
    role: str  # "leader" | "aux"
    prompt_file: str | None = None


@dataclass
class LoopConfig:
    name: str
    sequence: list[str]
    max_iterations: int = 3


@dataclass
class Config:
    session_name: str
    notify_interval: int = 30
    poke_stale_after: int = 120
    agents: list[AgentConfig] = field(default_factory=list)
    loops: list[LoopConfig] = field(default_factory=list)

    @property
    def leader(self) -> AgentConfig:
        return next(a for a in self.agents if a.role == "leader")

    def agent(self, name: str) -> AgentConfig:
        for a in self.agents:
            if a.name == name:
                return a
        raise ConfigError(f"agente desconhecido: {name}")


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise ConfigError(f"arquivo de config não encontrado: {path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"TOML inválido em {path}: {e}") from e

    session = data.get("session", {})
    agents = [
        AgentConfig(
            name=a["name"],
            command=a["command"],
            args=list(a.get("args", [])),
            role=a.get("role", "aux"),
            prompt_file=a.get("prompt_file"),
        )
        for a in data.get("agents", [])
    ]
    loops = [
        LoopConfig(
            name=l["name"],
            sequence=list(l["sequence"]),
            max_iterations=int(l.get("max_iterations", 3)),
        )
        for l in data.get("loops", [])
    ]

    names = [a.name for a in agents]
    if len(names) != len(set(names)):
        raise ConfigError("nomes de agentes duplicados")
    for a in agents:
        if a.role not in ("leader", "aux"):
            raise ConfigError(f"role inválido em {a.name}: {a.role}")
    leaders = [a for a in agents if a.role == "leader"]
    if len(leaders) != 1:
        raise ConfigError(f"exatamente 1 agente leader é obrigatório (encontrados {len(leaders)})")
    for l in loops:
        for member in l.sequence:
            if member not in names:
                raise ConfigError(f"loop {l.name} referencia agente desconhecido: {member}")

    return Config(
        session_name=session.get("name", "sac"),
        notify_interval=int(session.get("notify_interval", 30)),
        poke_stale_after=int(session.get("poke_stale_after", 120)),
        agents=agents,
        loops=loops,
    )
