"""Manifest dos plugins canônicos do SAC — dados puros (sem lógica de rede).

Os 3 canônicos (superpowers, RTK, openspec) são gerenciados pelo próprio SAC:
clones em `$SAC_HOME/plugins/<nome>/` e binários em `$SAC_HOME/bin/`
(`SAC_HOME` default `~/.sac`). O SAC NÃO lê instalações de harness
(`~/.kimi-code/plugins`, `~/.claude` etc.) — dentro da esteira vale apenas a
cópia gerenciada pelo SAC.
"""
from __future__ import annotations

import os
from pathlib import Path

PLUGINS = [
    {"nome": "superpowers", "tipo": "skills",
     "repo": "https://github.com/obra/superpowers",
     "ref": "v6.1.1", "skills_dir": "skills"},
    {"nome": "rtk", "tipo": "cli-binary",
     "repo": "https://github.com/rtk-ai/rtk",
     "ref": "v0.43.0", "release_asset": "rtk-{triple}.tar.gz"},
    {"nome": "openspec", "tipo": "cli-npm",
     "repo": "https://github.com/Fission-AI/OpenSpec",
     "ref": "v1.6.0", "package": "@fission-ai/openspec"},
]


def sac_home(env: dict | None = None) -> Path:
    """Raiz SAC-owned: `$SAC_HOME` ou `~/.sac` (default)."""
    env = os.environ if env is None else env
    return Path(env.get("SAC_HOME") or (Path.home() / ".sac"))


def plugins_dir(home: Path) -> Path:
    return Path(home) / "plugins"


def bin_dir(home: Path) -> Path:
    return Path(home) / "bin"


def plugin_dir(home: Path, plugin: dict) -> Path:
    return plugins_dir(home) / plugin["nome"]


def bin_path(home: Path, plugin: dict) -> Path | None:
    """Binário materializado em $SAC_HOME/bin (None para plugin de skills)."""
    if plugin["tipo"] == "skills":
        return None
    return bin_dir(home) / plugin["nome"]


def superpowers_skills_dir(home: Path) -> Path:
    p = next(p for p in PLUGINS if p["nome"] == "superpowers")
    return plugin_dir(home, p) / p["skills_dir"]


def alvo_presente(home: Path, plugin: dict) -> bool:
    """Artefato de uso presente: dir de skills (superpowers) ou bin (rtk/openspec)."""
    if plugin["tipo"] == "skills":
        return superpowers_skills_dir(home).is_dir()
    b = bin_path(home, plugin)
    return b is not None and b.exists()
