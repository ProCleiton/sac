"""Comando `sac plugins`: install/update/status/uninstall dos canônicos.

Toda operação externa (git/curl/npm) passa por `run` (default subprocess.run)
— testes injetam um fake e nunca tocam a rede.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from .plugins_manifest import (
    PLUGINS, alvo_presente, bin_dir, bin_path, plugin_dir, plugins_dir, sac_home,
)


def _git(d: Path, args: list[str], run) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(d), *args], capture_output=True, text=True)


def _current_ref(d: Path, run) -> str | None:
    """Tag exata do HEAD (ou hash curto); None se o clone está quebrado."""
    r = _git(d, ["describe", "--tags", "--exact-match"], run)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    r = _git(d, ["rev-parse", "--short", "HEAD"], run)
    return r.stdout.strip() if r.returncode == 0 else None


def _rtk_asset_url(plugin: dict) -> str:
    triples = {
        ("Linux", "x86_64"): "x86_64-unknown-linux-musl",
        ("Linux", "aarch64"): "aarch64-unknown-linux-gnu",
        ("Darwin", "x86_64"): "x86_64-apple-darwin",
        ("Darwin", "arm64"): "aarch64-apple-darwin",
    }
    triple = triples.get((platform.system(), platform.machine()))
    if triple is None:
        triple = f"{platform.machine()}-unknown-{platform.system().lower()}"
    asset = plugin["release_asset"].format(triple=triple)
    return f"{plugin['repo']}/releases/download/{plugin['ref']}/{asset}"


def _materializa_rtk(plugin: dict, home: Path, stdout, run) -> bool:
    import tarfile
    import tempfile

    b = bin_path(home, plugin)
    bin_dir(home).mkdir(parents=True, exist_ok=True)
    url = _rtk_asset_url(plugin)
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tarball = Path(tmp.name)
    r = run(["curl", "-fsSL", "-o", str(tarball), url], capture_output=True, text=True)
    if r.returncode != 0:
        stdout(f"erro: rtk: falha ao baixar o asset do release ({url}) — verifique a rede; "
               "se a plataforma não tiver release, instale manualmente")
        tarball.unlink(missing_ok=True)
        return False
    try:
        with tarfile.open(tarball) as tf:
            member = next((m for m in tf.getmembers()
                           if Path(m.name).name == "rtk" and m.isfile()), None)
            if member is None:
                stdout("erro: rtk: binário não encontrado no pacote do release")
                return False
            tf.extract(member, bin_dir(home), filter="data")
        extraido = bin_dir(home) / member.name
        extraido.replace(b)
        b.chmod(0o755)
    except (tarfile.TarError, OSError) as e:
        stdout(f"erro: rtk: falha ao extrair o pacote ({e})")
        return False
    finally:
        tarball.unlink(missing_ok=True)
    stdout(f"rtk: binário em {b}")
    return True


def _materializa_openspec(plugin: dict, home: Path, stdout, run) -> bool:
    versao = plugin["ref"].lstrip("v")
    prefix = plugin_dir(home, plugin) / ".npm"
    r = run(["npm", "install", "--prefix", str(prefix), f"{plugin['package']}@{versao}"],
            capture_output=True, text=True)
    if r.returncode != 0:
        stdout(f"erro: openspec: falha no npm install — verifique a rede")
        return False
    shim = bin_path(home, plugin)
    bin_dir(home).mkdir(parents=True, exist_ok=True)
    shim.write_text(f'#!/bin/sh\nexec "{prefix}/node_modules/.bin/openspec" "$@"\n',
                    encoding="utf-8")
    shim.chmod(0o755)
    stdout(f"openspec: shim em {shim}")
    return True


def _materializa_bin(plugin: dict, home: Path, stdout, run) -> bool:
    if plugin["tipo"] == "cli-binary":
        return _materializa_rtk(plugin, home, stdout, run)
    if plugin["tipo"] == "cli-npm":
        return _materializa_openspec(plugin, home, stdout, run)
    return True


def _install_one(plugin: dict, home: Path, stdout, run) -> bool:
    d = plugin_dir(home, plugin)
    if not d.is_dir():
        stdout(f"clonando {plugin['nome']} ({plugin['repo']})...")
        plugins_dir(home).mkdir(parents=True, exist_ok=True)
        r = run(["git", "clone", plugin["repo"], str(d)], capture_output=True, text=True)
        if r.returncode != 0:
            stdout(f"erro: {plugin['nome']}: falha ao clonar — verifique a rede")
            return False
    if _current_ref(d, run) == plugin["ref"] and alvo_presente(home, plugin):
        stdout(f"{plugin['nome']}: já instalado @ {plugin['ref']}")
        return True
    r = _git(d, ["checkout", plugin["ref"]], run)
    if r.returncode != 0:
        stdout(f"erro: {plugin['nome']}: falha no checkout de {plugin['ref']} — verifique a rede")
        return False
    stdout(f"{plugin['nome']}: checkout {plugin['ref']}")
    return _materializa_bin(plugin, home, stdout, run)


def _update_one(plugin: dict, home: Path, stdout, run) -> bool:
    d = plugin_dir(home, plugin)
    if not d.is_dir():
        stdout(f"{plugin['nome']}: não instalado — rode 'sac plugins install'")
        return True
    r = _git(d, ["fetch", "--tags"], run)
    if r.returncode != 0:
        stdout(f"erro: {plugin['nome']}: falha no fetch — verifique a rede")
        return False
    r = _git(d, ["checkout", plugin["ref"]], run)
    if r.returncode != 0:
        stdout(f"erro: {plugin['nome']}: falha no checkout de {plugin['ref']}")
        return False
    stdout(f"{plugin['nome']}: checkout {plugin['ref']}")
    return _materializa_bin(plugin, home, stdout, run)


def _latest_tag(plugin: dict, run) -> str | None:
    """Última tag ESTÁVEL do upstream (pré-releases com sufixo `-...` ignoradas)."""
    r = run(["git", "ls-remote", "--tags", "--sort=-version:refname", plugin["repo"]],
            capture_output=True, text=True)
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if "refs/tags/" not in line or line.rstrip().endswith("^{}"):
            continue
        tag = line.rsplit("refs/tags/", 1)[-1].strip()
        if "-" in tag:  # pré-release: v1.6.0-beta.1, v2.0.0-rc.1...
            continue
        return tag
    return None


def _check(home: Path, stdout, run) -> int:
    falhas = 0
    for p in PLUGINS:
        latest = _latest_tag(p, run)
        if latest is None:
            stdout(f"erro: {p['nome']}: não foi possível consultar o upstream — verifique a rede")
            falhas += 1
            continue
        extra = " (atualização disponível)" if latest != p["ref"] else ""
        stdout(f"{p['nome']}: pin {p['ref']} | upstream {latest}{extra}")
    return 1 if falhas else 0


def collect_status(home: Path | None = None, run=None) -> list[dict]:
    """Estado de cada canônico: instalado, ref atual, alvo (bin/skills), sincronizado."""
    run = run or subprocess.run
    home = sac_home() if home is None else Path(home)
    out = []
    for p in PLUGINS:
        d = plugin_dir(home, p)
        instalado = d.is_dir()
        ref_atual = _current_ref(d, run) if instalado else None
        alvo = alvo_presente(home, plugin=p) if instalado else False
        out.append({
            "nome": p["nome"], "ref": p["ref"], "instalado": instalado,
            "ref_atual": ref_atual, "alvo": alvo,
            "sincronizado": instalado and ref_atual == p["ref"] and alvo,
        })
    return out


def _status(home: Path, stdout, run) -> int:
    for st in collect_status(home, run=run):
        if not st["instalado"]:
            stdout(f"{st['nome']}: não instalado — rode 'sac plugins install'")
        elif st["ref_atual"] != st["ref"]:
            stdout(f"{st['nome']}: ref {st['ref_atual']} (pin {st['ref']}) — rode 'sac plugins update'")
        elif not st["alvo"]:
            stdout(f"{st['nome']}: @ {st['ref']} mas bin/skills ausente — rode 'sac plugins install'")
        else:
            stdout(f"{st['nome']}: OK @ {st['ref']}")
    return 0


def _uninstall(home: Path, stdin, stdout) -> int:
    targets = [p for p in (plugins_dir(home), bin_dir(home)) if p.exists()]
    if not targets:
        stdout("nada para remover — nenhum plugin instalado")
        return 0
    stdout("os seguintes itens serão removidos:")
    for t in targets:
        stdout(f"  {t}")
    stdout("confirmar? (s/N): ")
    try:
        answer = stdin()
    except (EOFError, KeyboardInterrupt):
        stdout("cancelado — nada removido")
        return 0
    if answer.strip().lower() != "s":
        stdout("cancelado — nada removido")
        return 0
    for t in targets:
        shutil.rmtree(t)
    stdout("removido — plugins canônicos desinstalados")
    return 0


def cmd_plugins(sub: str, *, check: bool = False, home: Path | None = None,
                stdin=None, stdout=None, run=None) -> int:
    stdin = stdin or input
    stdout = stdout or print
    run = run or subprocess.run
    home = sac_home() if home is None else Path(home)

    if sub == "install":
        falhas = sum(0 if _install_one(p, home, stdout, run) else 1 for p in PLUGINS)
        if falhas:
            stdout(f"erro: {falhas} plugin(s) com falha — corrija e rode novamente")
            return 1
        stdout(f"plugins canônicos instalados em {home}")
        return 0
    if sub == "update":
        if check:
            return _check(home, stdout, run)
        falhas = sum(0 if _update_one(p, home, stdout, run) else 1 for p in PLUGINS)
        return 1 if falhas else 0
    if sub == "status":
        return _status(home, stdout, run)
    if sub == "uninstall":
        return _uninstall(home, stdin, stdout)
    stdout(f"erro: subcomando desconhecido: {sub}")
    return 2
