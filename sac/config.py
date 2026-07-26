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
    boot_wait: float | None = None
    contract: str | None = None  # chave do catálogo de contratos (init; não vem do TOML)


@dataclass
class Config:
    session_name: str
    notify_interval: int = 30
    poke_stale_after: int = 120
    poke_escalate_after: int = 3
    boot_wait: int = 8
    session_width: int = 220
    session_height: int = 50
    socket: str | None = None
    root: str | None = None
    windows: dict[str, str] = field(default_factory=dict)
    agents: list[AgentConfig] = field(default_factory=list)

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
    if "loops" in data:
        raise ConfigError(
            "seção [[loops]] removida na v26b — remova a seção do config; "
            "a delegação e os ciclos de revisão são disciplina do contrato do líder "
            "(delegar com `sac send`, cobrar revisão, iterar até convergir)"
        )
    agents = [
        AgentConfig(
            name=a["name"],
            command=a["command"],
            args=list(a.get("args", [])),
            role=a.get("role", "aux"),
            prompt_file=a.get("prompt_file"),
            boot_wait=a.get("boot_wait"),
        )
        for a in data.get("agents", [])
    ]
    for a in data.get("agents", []):
        if a.get("boot_wait") is not None:
            bw = a["boot_wait"]
            if not isinstance(bw, (int, float)):
                raise ConfigError(f"boot_wait deve ser numérico em agente '{a['name']}': {bw}")
            if bw < 0:
                raise ConfigError(f"boot_wait não pode ser negativo em agente '{a['name']}': {bw}")

    names = [a.name for a in agents]
    if len(names) != len(set(names)):
        raise ConfigError("nomes de agentes duplicados")
    for a in agents:
        if a.role not in ("leader", "aux"):
            raise ConfigError(f"role inválido em {a.name}: {a.role}")
    leaders = [a for a in agents if a.role == "leader"]
    if len(leaders) != 1:
        raise ConfigError(f"exatamente 1 agente leader é obrigatório (encontrados {len(leaders)})")

    session_root = session.get("root")
    if session_root is not None:
        if not Path(session_root).is_absolute():
            raise ConfigError(f"session.root deve ser um caminho absoluto: {session_root}")

    windows = {str(k): str(v) for k, v in data.get("windows", {}).items()}
    if windows:
        from .layout import leaf_names, parse_spec  # import tardio (evita ciclo)
        seen: list[str] = []
        for wname, spec in windows.items():
            for leaf in leaf_names(parse_spec(spec)):
                if leaf not in names:
                    raise ConfigError(f"window '{wname}': agente desconhecido no spec: {leaf}")
                seen.append(leaf)
        dups = sorted({n for n in seen if seen.count(n) > 1})
        if dups:
            raise ConfigError(f"agente em mais de um pane nos specs [windows]: {dups}")
        missing = [n for n in names if n not in seen]
        if missing:
            raise ConfigError(f"agente ausente dos specs [windows]: {missing}")

    poke_escalate_after = int(session.get("poke_escalate_after", 3))
    if poke_escalate_after < 1:
        raise ConfigError(f"session.poke_escalate_after deve ser >= 1: {poke_escalate_after}")

    def _session_size(key: str, default: int) -> int:
        v = session.get(key, default)
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise ConfigError(f"session.{key} deve ser inteiro positivo: {v}")
        return v

    return Config(
        session_name=session.get("name", "sac"),
        notify_interval=int(session.get("notify_interval", 30)),
        poke_stale_after=int(session.get("poke_stale_after", 120)),
        poke_escalate_after=poke_escalate_after,
        boot_wait=int(session.get("boot_wait", 8)),
        session_width=_session_size("width", 220),
        session_height=_session_size("height", 50),
        socket=(str(Path(session["socket"]).expanduser()) if session.get("socket") else None),
        root=session_root,
        windows=windows,
        agents=agents,
    )
