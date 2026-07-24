# SAC (Stupid Agentic Coordinator) — Plano de Implementação v1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o SAC v1 — coordenador multi-agente daemonless sobre tmux, com mensageria via filesystem (inbox/claimed/done), contrato de conclusão `SAC_DONE` + `sac done`, e watcher `sac notify`.

**Architecture:** CLI Python efêmera (`sac`) sobre 4 módulos pequenos (config, tmux, store, commands); estado 100% em `.sac/` (filesystem) + sessão tmux; sem daemon, sem dependências externas. Design completo em `sac/docs/2026-07-24-sac-design.md`.

**Tech Stack:** Python ≥ 3.11 stdlib apenas (tomllib, argparse, subprocess, unittest), tmux ≥ 3.0.

## Global Constraints

- **Zero dependências externas** — stdlib apenas; testes com `unittest` (não pytest).
- **Python ≥ 3.11** (tomllib); rodar testes com `python3 -m unittest discover -s tests -v` a partir de `/home/dev/Github/sac`.
- **TDD**: todo passo começa pelo teste que falha.
- **SEM git commit** — regra do workspace: commits só via deployment-officer com autorização explícita do usuário. Nenhuma task deste plano commita.
- **Toda chamada tmux passa por `sac/tmux.py`** (classe `Tmux` com `runner` injetável) — testes unitários nunca tocam tmux real.
- Mensagens da CLI em pt-BR; código/identificadores em inglês.
- Estrutura: repo `/home/dev/Github/sac/`, pacote `sac/`, testes `tests/`.

## Estrutura de arquivos

```
sac/                      # repo (/home/dev/Github/sac)
  sac/
    __init__.py           # vazio
    __main__.py           # from .cli import main; main()
    config.py             # parsing/validação de sac.toml (tomllib)
    tmux.py               # wrapper tmux com runner injetável
    store.py              # inbox/claimed/done/log.jsonl
    commands.py           # lógica dos 11 comandos
    cli.py                # argparse → commands
  prompts/                # prompt_file de exemplo (leader, dev, auditor)
  tests/                  # test_config, test_store, test_tmux, test_commands, test_notify, test_cli
  sac.toml                # config de exemplo
  pyproject.toml          # console_script sac (instalação opcional)
  README.md
```

---

### Task 1: Scaffold + `config.py`

**Files:**
- Create: `sac/__init__.py` (vazio), `sac/config.py`, `tests/__init__.py` (vazio), `tests/test_config.py`, `pyproject.toml`

**Interfaces:**
- Produces (usado por TODAS as tasks seguintes):
  - `class ConfigError(Exception)`
  - `@dataclass AgentConfig`: `name: str`, `command: str`, `args: list[str]`, `role: str`, `prompt_file: str | None = None`
  - `@dataclass LoopConfig`: `name: str`, `sequence: list[str]`, `max_iterations: int = 3`
  - `@dataclass Config`: `session_name: str`, `notify_interval: int`, `poke_stale_after: int`, `agents: list[AgentConfig]`, `loops: list[LoopConfig]`; propriedade `leader -> AgentConfig`; método `agent(name: str) -> AgentConfig`
  - `load_config(path: Path) -> Config` — levanta `ConfigError` em: arquivo inexistente, TOML inválido, zero ou 2+ leaders, nomes duplicados, role inválido, loop referenciando agente inexistente.

- [ ] **Step 1: Escrever o teste que falha** — `tests/test_config.py`

```python
import tempfile
import unittest
from pathlib import Path

from sac.config import ConfigError, load_config

VALID = """
[session]
name = "sac-test"
notify_interval = 30
poke_stale_after = 120

[[agents]]
name = "leader"
command = "kimi"
args = ["--model", "k3"]
role = "leader"
prompt_file = "prompts/leader.md"

[[agents]]
name = "dev-1"
command = "opencode"
args = ["-m", "x/y"]
role = "aux"

[[loops]]
name = "dev-review"
sequence = ["leader", "dev-1"]
max_iterations = 3
"""


class LoadConfigTest(unittest.TestCase):
    def _load(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "sac.toml"
        p.write_text(text, encoding="utf-8")
        return load_config(p)

    def test_valid_config(self):
        cfg = self._load(VALID)
        self.assertEqual(cfg.session_name, "sac-test")
        self.assertEqual(cfg.notify_interval, 30)
        self.assertEqual(cfg.poke_stale_after, 120)
        self.assertEqual(len(cfg.agents), 2)
        self.assertEqual(cfg.leader.name, "leader")
        self.assertEqual(cfg.agent("dev-1").command, "opencode")
        self.assertEqual(cfg.agent("dev-1").prompt_file, None)
        self.assertEqual(cfg.loops[0].max_iterations, 3)

    def test_defaults(self):
        cfg = self._load(VALID.replace("notify_interval = 30\n", "").replace("poke_stale_after = 120\n", ""))
        self.assertEqual(cfg.notify_interval, 30)
        self.assertEqual(cfg.poke_stale_after, 120)

    def test_no_leader_fails(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('role = "leader"', 'role = "aux"'))

    def test_two_leaders_fail(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('role = "aux"', 'role = "leader"'))

    def test_duplicate_names_fail(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('name = "dev-1"', 'name = "leader"'))

    def test_invalid_role_fails(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('role = "aux"', 'role = "chefe"'))

    def test_loop_unknown_agent_fails(self):
        with self.assertRaises(ConfigError):
            self._load(VALID.replace('sequence = ["leader", "dev-1"]', 'sequence = ["leader", "fantasma"]'))

    def test_missing_file_fails(self):
        with self.assertRaises(ConfigError):
            load_config(Path("/tmp/nao-existe-sac.toml"))

    def test_agent_unknown_raises(self):
        cfg = self._load(VALID)
        with self.assertRaises(ConfigError):
            cfg.agent("fantasma")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_config -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sac'`

- [ ] **Step 3: Implementar** — `sac/__init__.py` vazio; `sac/config.py`:

```python
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
```

`pyproject.toml`:

```toml
[project]
name = "sac"
version = "0.1.0"
description = "Stupid Agentic Coordinator — coordenador multi-agente daemonless sobre tmux"
requires-python = ">=3.11"

[project.scripts]
sac = "sac.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_config -v`
Expected: 9 testes PASS

---

### Task 2: `store.py` — inbox/claimed/done/log

**Files:**
- Create: `sac/store.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: nada de tasks anteriores (independente).
- Produces:
  - `@dataclass Message`: `id: str`, `sender: str`, `recipient: str`, `timestamp: str` (ISO), `body: str`
  - `class Store(root: Path)`:
    - `send(sender: str, recipient: str, body: str, now: datetime | None = None) -> str` (retorna msg id)
    - `next(agent: str) -> Message | None` — move mais antiga inbox→claimed
    - `done(agent: str, msg_id: str, summary: str, now: datetime | None = None) -> None` — claimed→done; `ConfigError`-análogo: levanta `StoreError` se id não está em claimed
    - `pending(agent: str) -> list[str]`, `claimed(agent: str) -> list[str]` — ids ordenados
    - `stale(agent: str, seconds: int, now: datetime | None = None) -> list[str]` — ids em inbox+claimed com timestamp mais antigo que `seconds`
    - `log(event: str, now: datetime | None = None, **fields) -> None` — append em `log.jsonl`
  - `class StoreError(Exception)`
  - Formato de arquivo: nome `<YYYYMMDD>-<HHMMSS>-<seq:03d>-from-<sender>.msg`; conteúdo: headers `id/from/to/ts` + linha em branco + corpo.

- [ ] **Step 1: Escrever o teste que falha** — `tests/test_store.py`

```python
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sac.store import Store, StoreError

T0 = datetime(2026, 7, 24, 10, 0, 0)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.store = Store(self.root)

    def test_send_creates_file_and_returns_id(self):
        mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        self.assertEqual(mid, "20260724-100000-001-from-leader")
        files = list((self.root / "inbox" / "dev-1").glob("*.msg"))
        self.assertEqual(len(files), 1)
        text = files[0].read_text(encoding="utf-8")
        self.assertIn("from: leader", text)
        self.assertTrue(text.endswith("faça X"))

    def test_seq_increments_within_same_second(self):
        a = self.store.send("leader", "dev-1", "m1", now=T0)
        b = self.store.send("leader", "dev-1", "m2", now=T0)
        self.assertTrue(a.endswith("-001-from-leader"))
        self.assertTrue(b.endswith("-002-from-leader"))

    def test_next_fifo_moves_to_claimed(self):
        self.store.send("leader", "dev-1", "primeira", now=T0)
        self.store.send("leader", "dev-1", "segunda", now=T0 + timedelta(seconds=1))
        msg = self.store.next("dev-1")
        self.assertEqual(msg.body, "primeira")
        self.assertEqual(msg.sender, "leader")
        self.assertEqual(msg.recipient, "dev-1")
        self.assertEqual(self.store.pending("dev-1"), ["20260724-100001-001-from-leader"])
        self.assertEqual(self.store.claimed("dev-1"), [msg.id])

    def test_next_empty_returns_none(self):
        self.assertIsNone(self.store.next("dev-1"))

    def test_done_moves_claimed_to_done(self):
        mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        self.store.next("dev-1")
        self.store.done("dev-1", mid, "feito", now=T0)
        self.assertEqual(self.store.claimed("dev-1"), [])
        done_files = list((self.root / "done" / "dev-1").glob("*.msg"))
        self.assertEqual(len(done_files), 1)

    def test_done_without_claim_fails(self):
        mid = self.store.send("leader", "dev-1", "faça X", now=T0)
        with self.assertRaises(StoreError):
            self.store.done("dev-1", mid, "feito", now=T0)

    def test_stale_finds_old_messages(self):
        old = self.store.send("leader", "dev-1", "velha", now=T0)
        new = self.store.send("leader", "dev-1", "nova", now=T0 + timedelta(seconds=300))
        stale = self.store.stale("dev-1", 120, now=T0 + timedelta(seconds=300))
        self.assertEqual(stale, [old])
        self.assertNotIn(new, stale)

    def test_log_appends_jsonl(self):
        self.store.log("send", now=T0, sender="leader", to="dev-1", id="x")
        self.store.log("poke", now=T0, agent="dev-1", count=2)
        lines = (self.root / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(first["event"], "send")
        self.assertEqual(first["ts"], "2026-07-24T10:00:00")
        self.assertEqual(first["to"], "dev-1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_store -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sac.store'`

- [ ] **Step 3: Implementar** — `sac/store.py`

```python
"""Estado do SAC no filesystem: inbox/claimed/done + log.jsonl (append-only)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class StoreError(Exception):
    """Operação inválida sobre mensagens."""


@dataclass
class Message:
    id: str
    sender: str
    recipient: str
    timestamp: str
    body: str


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _dir(self, kind: str, agent: str) -> Path:
        p = self.root / kind / agent
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _ids(self, kind: str, agent: str) -> list[str]:
        d = self.root / kind / agent
        if not d.is_dir():
            return []
        return sorted(f.stem for f in d.glob("*.msg"))

    @staticmethod
    def _parse(path: Path) -> Message:
        head, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in head.splitlines())
        return Message(meta["id"], meta["from"], meta["to"], meta["ts"], body)

    def send(self, sender: str, recipient: str, body: str, now: datetime | None = None) -> str:
        now = now or datetime.now()
        stamp = now.strftime("%Y%m%d-%H%M%S")
        existing = []
        for kind in ("inbox", "claimed", "done"):
            existing += [i for i in self._ids(kind, recipient) if i.startswith(stamp)]
        seq = max((int(i.split("-")[2]) for i in existing), default=0) + 1
        mid = f"{stamp}-{seq:03d}-from-{sender}"
        content = f"id: {mid}\nfrom: {sender}\nto: {recipient}\nts: {now.isoformat()}\n\n{body}"
        (self._dir("inbox", recipient) / f"{mid}.msg").write_text(content, encoding="utf-8")
        self.log("send", now=now, sender=sender, to=recipient, id=mid)
        return mid

    def next(self, agent: str) -> Message | None:
        ids = self._ids("inbox", agent)
        if not ids:
            return None
        src = self.root / "inbox" / agent / f"{ids[0]}.msg"
        msg = self._parse(src)
        src.rename(self._dir("claimed", agent) / src.name)
        self.log("next", agent=agent, id=msg.id)
        return msg

    def done(self, agent: str, msg_id: str, summary: str, now: datetime | None = None) -> None:
        src = self.root / "claimed" / agent / f"{msg_id}.msg"
        if not src.is_file():
            raise StoreError(f"mensagem não está claimed para {agent}: {msg_id}")
        src.rename(self._dir("done", agent) / src.name)
        self.log("done", now=now, agent=agent, id=msg_id, summary=summary)

    def pending(self, agent: str) -> list[str]:
        return self._ids("inbox", agent)

    def claimed(self, agent: str) -> list[str]:
        return self._ids("claimed", agent)

    def stale(self, agent: str, seconds: int, now: datetime | None = None) -> list[str]:
        now = now or datetime.now()
        out = []
        for mid in self._ids("inbox", agent) + self._ids("claimed", agent):
            ts = datetime.strptime(mid[:15], "%Y%m%d-%H%M%S")
            if (now - ts).total_seconds() > seconds:
                out.append(mid)
        return out

    def log(self, event: str, now: datetime | None = None, **fields) -> None:
        now = now or datetime.now()
        line = json.dumps({"ts": now.isoformat(), "event": event, **fields}, ensure_ascii=False)
        with (self.root / "log.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_store -v`
Expected: 8 testes PASS

---

### Task 3: `tmux.py` — wrapper com runner injetável

**Files:**
- Create: `sac/tmux.py`, `tests/test_tmux.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `class Tmux(session: str, runner: Callable | None = None)` — `runner(*args: str) -> subprocess.CompletedProcess`; default roda `subprocess.run(..., capture_output=True, text=True)`
  - Métodos: `has_session() -> bool`, `new_session(window: str, command: list[str])`, `new_window(name: str, command: list[str], env: dict[str, str] | None = None)`, `has_window(name: str) -> bool`, `send_keys(window: str, text: str)`, `capture_pane(window: str, lines: int = 200) -> str`, `kill_session()`
  - `env` é passado via prefixo `env KEY=VAL ...` no comando (portável, sem depender de `tmux -e`).

- [ ] **Step 1: Escrever o teste que falha** — `tests/test_tmux.py`

```python
import subprocess
import unittest

from sac.tmux import Tmux


class FakeRunner:
    def __init__(self, outputs=None, rc=0):
        self.calls = []
        self.outputs = outputs or {}
        self.rc = rc

    def __call__(self, *args):
        self.calls.append(args)
        key = args[1] if len(args) > 1 else ""
        out = self.outputs.get(key, "")
        rc = self.outputs.get(("rc", key), self.rc)
        return subprocess.CompletedProcess(args, rc, stdout=out, stderr="")


class TmuxTest(unittest.TestCase):
    def test_has_session_true(self):
        t = Tmux("sac", runner=FakeRunner(rc=0))
        self.assertTrue(t.has_session())

    def test_has_session_false(self):
        t = Tmux("sac", runner=FakeRunner(rc=1))
        self.assertFalse(t.has_session())

    def test_new_session_command(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.new_session("leader", ["kimi", "--model", "k3"])
        self.assertEqual(r.calls[0], ("tmux", "new-session", "-d", "-s", "sac", "-n", "leader", "kimi --model k3"))

    def test_new_window_with_env_prefix(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.new_window("dev-1", ["opencode", "-m", "x/y"], env={"SAC_AGENT": "dev-1"})
        self.assertEqual(
            r.calls[0],
            ("tmux", "new-window", "-t", "sac", "-n", "dev-1", "env SAC_AGENT=dev-1 opencode -m x/y"),
        )

    def test_send_keys_literal_then_enter(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.send_keys("dev-1", "SAC: mensagem nova — rode `sac next`")
        self.assertEqual(r.calls[0], ("tmux", "send-keys", "-t", "sac:dev-1", "-l", "--", "SAC: mensagem nova — rode `sac next`"))
        self.assertEqual(r.calls[1], ("tmux", "send-keys", "-t", "sac:dev-1", "Enter"))

    def test_capture_pane(self):
        r = FakeRunner(outputs={"capture-pane": "linha1\nlinha2\n"})
        t = Tmux("sac", runner=r)
        self.assertEqual(t.capture_pane("dev-1", 50), "linha1\nlinha2\n")
        self.assertEqual(r.calls[0], ("tmux", "capture-pane", "-p", "-t", "sac:dev-1", "-S", "-50"))

    def test_has_window(self):
        r = FakeRunner(outputs={"list-windows": "leader\ndev-1\n"})
        t = Tmux("sac", runner=r)
        self.assertTrue(t.has_window("dev-1"))
        self.assertFalse(t.has_window("fantasma"))

    def test_kill_session(self):
        r = FakeRunner()
        t = Tmux("sac", runner=r)
        t.kill_session()
        self.assertEqual(r.calls[0], ("tmux", "kill-session", "-t", "sac"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_tmux -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sac.tmux'`

- [ ] **Step 3: Implementar** — `sac/tmux.py`

```python
"""Wrapper fino do tmux. Toda chamada tmux do SAC passa por aqui (fakeável em testes)."""
from __future__ import annotations

import shlex
import subprocess
from collections.abc import Callable


def _default_runner(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


class Tmux:
    def __init__(self, session: str, runner: Callable[..., subprocess.CompletedProcess] | None = None):
        self.session = session
        self.runner = runner or _default_runner

    def _target(self, window: str) -> str:
        return f"{self.session}:{window}"

    def has_session(self) -> bool:
        return self.runner("tmux", "has-session", "-t", self.session).returncode == 0

    def new_session(self, window: str, command: list[str]) -> None:
        self.runner("tmux", "new-session", "-d", "-s", self.session, "-n", window, " ".join(command))

    def new_window(self, name: str, command: list[str], env: dict[str, str] | None = None) -> None:
        cmd = " ".join(command)
        if env:
            prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            cmd = f"env {prefix} {cmd}"
        self.runner("tmux", "new-window", "-t", self.session, "-n", name, cmd)

    def has_window(self, name: str) -> bool:
        out = self.runner("tmux", "list-windows", "-t", self.session, "-F", "#{window_name}").stdout
        return name in out.split()

    def send_keys(self, window: str, text: str) -> None:
        self.runner("tmux", "send-keys", "-t", self._target(window), "-l", "--", text)
        self.runner("tmux", "send-keys", "-t", self._target(window), "Enter")

    def capture_pane(self, window: str, lines: int = 200) -> str:
        return self.runner("tmux", "capture-pane", "-p", "-t", self._target(window), "-S", f"-{lines}").stdout

    def kill_session(self) -> None:
        self.runner("tmux", "kill-session", "-t", self.session)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_tmux -v`
Expected: 8 testes PASS

---

### Task 4: `commands.py` (parte 1) — send / next / done

**Files:**
- Create: `sac/commands.py`, `tests/test_commands.py`

**Interfaces:**
- Consumes: `Config`/`load_config` (Task 1), `Store`/`Message` (Task 2), `Tmux` (Task 3).
- Produces:
  - `POKE_TEXT = "SAC: mensagem nova na inbox — rode `sac next`"`
  - `cmd_send(cfg, store, tmux, to, body, sender="user") -> str` (msg id; persiste mesmo se a janela não existir — imprime aviso)
  - `cmd_next(store, env) -> int` — `env` é um mapping tipo `os.environ`; exige `SAC_AGENT`
  - `cmd_done(store, env, msg_id, summary) -> int`
  - `extract_reply(pane_text: str) -> tuple[bool, str]` — (terminou?, trecho da resposta até o último `SAC_DONE`)

- [ ] **Step 1: Escrever o teste que falha** — `tests/test_commands.py`

```python
import tempfile
import unittest
from pathlib import Path

from sac.commands import POKE_TEXT, cmd_done, cmd_next, cmd_send, extract_reply
from sac.config import load_config
from sac.store import Store
from sac.tmux import Tmux
from tests.test_tmux import FakeRunner

VALID = """
[session]
name = "sac-test"

[[agents]]
name = "leader"
command = "kimi"
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"
"""


class CommandsTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        self.runner = FakeRunner()
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_send_persists_and_pokes(self):
        mid = cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça X", sender="leader")
        self.assertIn("from-leader", mid)
        self.assertEqual(self.store.pending("dev-1"), [mid])
        self.assertEqual(self.runner.calls[0][:4], ("tmux", "send-keys", "-t", "sac-test:dev-1"))
        self.assertIn(POKE_TEXT, self.runner.calls[0][-1])

    def test_send_unknown_agent_raises(self):
        from sac.config import ConfigError
        with self.assertRaises(ConfigError):
            cmd_send(self.cfg, self.store, self.tmux, "fantasma", "oi")

    def test_next_prints_and_claims(self):
        cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça X", sender="leader")
        rc = cmd_next(self.store, {"SAC_AGENT": "dev-1"})
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.pending("dev-1"), [])
        self.assertEqual(len(self.store.claimed("dev-1")), 1)

    def test_next_without_agent_env_fails(self):
        self.assertEqual(cmd_next(self.store, {}), 2)

    def test_done_completes_cycle(self):
        mid = cmd_send(self.cfg, self.store, self.tmux, "dev-1", "faça X", sender="leader")
        cmd_next(self.store, {"SAC_AGENT": "dev-1"})
        rc = cmd_done(self.store, {"SAC_AGENT": "dev-1"}, mid, "feito")
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.claimed("dev-1"), [])

    def test_extract_reply_finished(self):
        pane = "pergunta...\n\nResposta do agente\ncom duas linhas\nSAC_DONE\n"
        done, text = extract_reply(pane)
        self.assertTrue(done)
        self.assertIn("Resposta do agente", text)
        self.assertNotIn("SAC_DONE", text)

    def test_extract_reply_in_progress(self):
        done, text = extract_reply("trabalhando...\nsem sentinela ainda\n")
        self.assertFalse(done)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_commands -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sac.commands'`

- [ ] **Step 3: Implementar** — `sac/commands.py` (parte 1; Tasks 5–8 acrescentam funções neste mesmo arquivo)

```python
"""Lógica dos comandos do SAC. Funções puras com dependências injetadas."""
from __future__ import annotations

import os
import sys
import time
from collections.abc import Mapping

from .config import Config, ConfigError
from .store import Store, StoreError
from .tmux import Tmux

POKE_TEXT = "SAC: mensagem nova na inbox — rode `sac next`"
SENTINEL = "SAC_DONE"


def cmd_send(cfg: Config, store: Store, tmux: Tmux, to: str, body: str, sender: str = "user") -> str:
    cfg.agent(to)  # valida destinatário (ConfigError se desconhecido)
    mid = store.send(sender, to, body)
    if tmux.has_session() and tmux.has_window(to):
        tmux.send_keys(to, POKE_TEXT)
    else:
        print(f"aviso: janela '{to}' não encontrada; mensagem persistida na inbox", file=sys.stderr)
    return mid


def _require_agent(env: Mapping[str, str]) -> str | None:
    return env.get("SAC_AGENT")


def cmd_next(store: Store, env: Mapping[str, str]) -> int:
    agent = _require_agent(env)
    if not agent:
        print("erro: SAC_AGENT não definido (rode dentro de um pane de agente)", file=sys.stderr)
        return 2
    msg = store.next(agent)
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
        store.done(agent, msg_id, summary)
    except StoreError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    print(f"ok: {msg_id} concluída")
    return 0


def extract_reply(pane_text: str) -> tuple[bool, str]:
    """Extrai a resposta até o último SAC_DONE. Retorna (terminou, texto)."""
    idx = pane_text.rfind(SENTINEL)
    if idx == -1:
        return False, pane_text
    end = pane_text.find("\n", idx)
    if end == -1:
        end = len(pane_text)
    return True, pane_text[:idx].rstrip("\n")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_commands -v`
Expected: 8 testes PASS

---

### Task 5: `commands.py` (parte 2) — up / down / status / log

**Files:**
- Modify: `sac/commands.py` (acrescentar funções)
- Test: `tests/test_commands.py` (acrescentar classe)

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `cmd_up(cfg, store, tmux, project_root: Path) -> int` — idempotente: sessão existe → imprime aviso e retorna 0; senão cria sessão com o leader e uma janela por aux, `env={"SAC_AGENT": name}`, comando = `[command, *args]`; se `prompt_file` existe (relativo a project_root), envia o conteúdo via `send_keys` após criar a janela
  - `cmd_down(cfg, tmux) -> int` — mata a sessão se existir (preserva `.sac/`)
  - `cmd_status(cfg, store, tmux) -> int` — imprime 1 linha por agente: nome, role, janela (sim/não), inbox N, claimed N
  - `cmd_log(store, follow=False) -> int` — imprime `log.jsonl`; com follow, faz tail -f até Ctrl-C

- [ ] **Step 1: Escrever os testes que falham** — acrescentar em `tests/test_commands.py`

```python
class UpDownStatusTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        (d / "prompts").mkdir()
        (d / "prompts" / "leader.md").write_text("Você é o leader.", encoding="utf-8")
        self.root = d
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        # has-session → rc 1 (sessão NÃO existe) por padrão; testes que precisam
        # de sessão existente criam seu próprio Tmux com FakeRunner(rc=0)
        self.runner = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\n"})
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_up_creates_session_and_windows(self):
        rc = cmd_up(self.cfg, self.store, self.tmux, self.root)
        self.assertEqual(rc, 0)
        kinds = [c[1] for c in self.runner.calls]
        self.assertIn("new-session", kinds)
        self.assertEqual(kinds.count("new-window"), 1)  # só o aux; leader vai na new-session
        env_calls = [c for c in self.runner.calls if "SAC_AGENT=dev-1" in c[-1]]
        self.assertEqual(len(env_calls), 1)
        # prompt do leader injetado via send-keys
        prompt_calls = [c for c in self.runner.calls if "Você é o leader." in c[-1]]
        self.assertEqual(len(prompt_calls), 1)

    def test_up_idempotent_when_session_exists(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0))  # sessão já existe
        rc = cmd_up(self.cfg, self.store, t, self.root)
        self.assertEqual(rc, 0)

    def test_down_kills_existing_session(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0))
        rc = cmd_down(self.cfg, t)
        self.assertEqual(rc, 0)

    def test_down_without_session(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=1))
        self.assertEqual(cmd_down(self.cfg, t), 0)

    def test_status_lists_agents(self):
        t = Tmux("sac-test", runner=FakeRunner(rc=0, outputs={"list-windows": "leader\ndev-1\n"}))
        self.store.send("leader", "dev-1", "t1")
        self.store.send("leader", "dev-1", "t2")
        self.assertEqual(cmd_status(self.cfg, self.store, t), 0)

    def test_log_prints_events(self):
        self.store.send("leader", "dev-1", "t1")
        self.assertEqual(cmd_log(self.store), 0)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_commands -v`
Expected: FAIL — `ImportError: cannot import name 'cmd_up'`

- [ ] **Step 3: Implementar** — acrescentar a `sac/commands.py`

```python
def cmd_up(cfg: Config, store: Store, tmux: Tmux, project_root: Path) -> int:
    if tmux.has_session():
        print(f" sessão '{tmux.session}' já existe — use `sac attach`")
        return 0
    leader = cfg.leader
    tmux.new_session(leader.name, [leader.command, *leader.args])
    _inject_prompt(tmux, leader, project_root)
    for agent in cfg.agents:
        if agent.name == leader.name:
            continue
        tmux.new_window(agent.name, [agent.command, *agent.args], env={"SAC_AGENT": agent.name})
        _inject_prompt(tmux, agent, project_root)
    print(f"sessão '{tmux.session}' no ar com {len(cfg.agents)} agentes")
    return 0


def _inject_prompt(tmux: Tmux, agent, project_root: Path) -> None:
    if not agent.prompt_file:
        return
    p = project_root / agent.prompt_file
    if p.is_file():
        tmux.send_keys(agent.name, p.read_text(encoding="utf-8"))


def cmd_down(cfg: Config, tmux: Tmux) -> int:
    if tmux.has_session():
        tmux.kill_session()
        print(f"sessão '{tmux.session}' encerrada (.sac/ preservado)")
    else:
        print("nenhuma sessão ativa")
    return 0


def cmd_status(cfg: Config, store: Store, tmux: Tmux) -> int:
    up = tmux.has_session()
    print(f"sessão '{tmux.session}': {'ativa' if up else 'inativa'}")
    for a in cfg.agents:
        win = up and tmux.has_window(a.name)
        inbox = len(store.pending(a.name))
        claimed = len(store.claimed(a.name))
        print(f"  {a.name:<12} {a.role:<7} janela={'sim' if win else 'não'}  inbox={inbox} claimed={claimed}")
    return 0


def cmd_log(store: Store, follow: bool = False) -> int:
    path = store.root / "log.jsonl"
    if not path.is_file():
        print("log vazio")
        return 0
    with path.open(encoding="utf-8") as f:
        while True:
            line = f.readline()
            if line:
                print(line, end="")
            elif follow:
                time.sleep(1)
            else:
                break
    return 0
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_commands -v`
Expected: 14 testes PASS

---

### Task 6: `commands.py` (parte 3) — recv / notify / run

**Files:**
- Modify: `sac/commands.py`
- Test: `tests/test_notify.py` (novo)

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces:
  - `cmd_recv(cfg, tmux, agent, lines=200) -> int` — capture_pane + `extract_reply`; imprime resposta ou "⏳ ainda processando"
  - `notify_sweep(cfg, store, tmux) -> dict[str, int]` — 1 varredura: para cada agente, `stale = store.stale(name, cfg.poke_stale_after)`; se stale, `tmux.send_keys(name, f"SAC: {len(stale)} mensagem(ns) aguardando — rode `sac next`")` + `store.log("poke", agent=name, count=len(stale))`; retorna {agente: n_pokes}
  - `cmd_notify(cfg, store, tmux, once=False) -> int` — se once, roda `notify_sweep` 1×; senão loop `while True: notify_sweep(...); time.sleep(cfg.notify_interval)` (KeyboardInterrupt → 0)
  - `cmd_run(cfg, store, tmux, loop_name, task) -> int` — acha o loop (ConfigError se desconhecido), `cmd_send(..., to=sequence[0], body=f"[loop {loop_name}] {task}", sender="user")`

- [ ] **Step 1: Escrever os testes que falham** — `tests/test_notify.py`

```python
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sac.commands import cmd_recv, cmd_run, notify_sweep
from sac.config import ConfigError, load_config
from sac.store import Store
from sac.tmux import Tmux
from tests.test_tmux import FakeRunner

VALID = """
[session]
name = "sac-test"
poke_stale_after = 120

[[agents]]
name = "leader"
command = "kimi"
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"

[[loops]]
name = "dev-review"
sequence = ["leader", "dev-1"]
max_iterations = 3
"""

NOW = datetime.now()


class NotifyTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        self.runner = FakeRunner()
        self.tmux = Tmux("sac-test", runner=self.runner)

    def test_sweep_pokes_only_stale(self):
        old = NOW - timedelta(seconds=300)
        self.store.send("leader", "dev-1", "velha", now=old)
        self.store.send("leader", "dev-1", "nova", now=NOW)
        result = notify_sweep(self.cfg, self.store, self.tmux)
        self.assertEqual(result, {"dev-1": 1})  # 1 poke para o agente (não por mensagem)
        poke_calls = [c for c in self.runner.calls if "aguardando" in c[-1]]
        self.assertEqual(len(poke_calls), 1)
        self.assertIn("1 mensagem", poke_calls[0][-1])  # só a velha é stale... ver nota abaixo

    def test_sweep_no_stale_no_poke(self):
        self.store.send("leader", "dev-1", "nova", now=NOW)
        result = notify_sweep(self.cfg, self.store, self.tmux)
        self.assertEqual(result, {})
        self.assertEqual([c for c in self.runner.calls if "send-keys" in c], [])

    def test_recv_finished(self):
        r = FakeRunner(outputs={"capture-pane": "resposta completa\nSAC_DONE\n"})
        t = Tmux("sac-test", runner=r)
        self.assertEqual(cmd_recv(self.cfg, t, "dev-1"), 0)

    def test_recv_in_progress(self):
        r = FakeRunner(outputs={"capture-pane": "trabalhando...\n"})
        t = Tmux("sac-test", runner=r)
        self.assertEqual(cmd_recv(self.cfg, t, "dev-1"), 1)

    def test_run_kicks_loop(self):
        mid = cmd_run(self.cfg, self.store, self.tmux, "dev-review", "implementar X")
        self.assertIn("from-user", mid)
        pending = self.store.pending("leader")
        self.assertEqual(len(pending), 1)

    def test_run_unknown_loop_fails(self):
        with self.assertRaises(ConfigError):
            cmd_run(self.cfg, self.store, self.tmux, "fantasma", "x")


if __name__ == "__main__":
    unittest.main()
```

Nota de implementação: `notify_sweep` conta mensagens stale por agente mas faz **1 poke por agente**; o texto do poke carrega o número de mensagens stale daquele agente (`"SAC: N mensagem(ns) aguardando — rode `sac next`"`). No teste `test_sweep_pokes_only_stale`, "velha" (300s) é stale e "nova" (0s) não → texto contém "1 mensagem".

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_notify -v`
Expected: FAIL — `ImportError: cannot import name 'notify_sweep'`

- [ ] **Step 3: Implementar** — acrescentar a `sac/commands.py`

```python
def cmd_recv(cfg: Config, tmux: Tmux, agent: str, lines: int = 200) -> int:
    cfg.agent(agent)
    done, text = extract_reply(tmux.capture_pane(agent, lines))
    if not done:
        print("⏳ ainda processando (sem SAC_DONE)")
        print(text[-500:])
        return 1
    print(text)
    return 0


def notify_sweep(cfg: Config, store: Store, tmux: Tmux) -> dict[str, int]:
    pokes = {}
    for a in cfg.agents:
        stale = store.stale(a.name, cfg.poke_stale_after)
        if stale:
            tmux.send_keys(a.name, f"SAC: {len(stale)} mensagem(ns) aguardando — rode `sac next`")
            store.log("poke", agent=a.name, count=len(stale))
            pokes[a.name] = len(stale)
    return pokes


def cmd_notify(cfg: Config, store: Store, tmux: Tmux, once: bool = False) -> int:
    if once:
        notify_sweep(cfg, store, tmux)
        return 0
    print(f"notify ativo (intervalo {cfg.notify_interval}s, stale após {cfg.poke_stale_after}s) — Ctrl-C para sair")
    try:
        while True:
            notify_sweep(cfg, store, tmux)
            time.sleep(cfg.notify_interval)
    except KeyboardInterrupt:
        return 0


def cmd_run(cfg: Config, store: Store, tmux: Tmux, loop_name: str, task: str) -> str:
    loop = next((l for l in cfg.loops if l.name == loop_name), None)
    if loop is None:
        raise ConfigError(f"loop desconhecido: {loop_name}")
    return cmd_send(cfg, store, tmux, loop.sequence[0], f"[loop {loop_name}] {task}", sender="user")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_notify -v`
Expected: 6 testes PASS (20 no total)

---

### Task 7: `cli.py` + `__main__.py`

**Files:**
- Create: `sac/cli.py`, `sac/__main__.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: `main(argv: list[str] | None = None) -> int` — entrypoint; flag global `--config` (default `sac.toml`); subcomandos `up send next done recv notify status log attach down run`. Root do estado = `<dir do config>/.sac`; project_root = dir do config.

- [ ] **Step 1: Escrever o teste que falha** — `tests/test_cli.py`

```python
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sac.cli import main
from sac.store import Store

VALID = """
[session]
name = "sac-cli-test"

[[agents]]
name = "leader"
command = "kimi"
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"

[[loops]]
name = "dev-review"
sequence = ["leader", "dev-1"]
"""


class CliTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg_path = str(self.d / "sac.toml")

    def test_send_via_cli(self):
        # sem tmux rodando: mensagem persiste e avisa no stderr, rc=0
        rc = main(["--config", self.cfg_path, "send", "dev-1", "faça X"])
        self.assertEqual(rc, 0)
        store = Store(self.d / ".sac")
        self.assertEqual(len(store.pending("dev-1")), 1)

    def test_next_without_agent_env_returns_2(self):
        with patch.dict(os.environ, {}, clear=True):
            rc = main(["--config", self.cfg_path, "next"])
        self.assertEqual(rc, 2)

    def test_run_via_cli(self):
        rc = main(["--config", self.cfg_path, "run", "dev-review", "implementar X"])
        self.assertEqual(rc, 0)
        store = Store(self.d / ".sac")
        self.assertEqual(len(store.pending("leader")), 1)

    def test_run_unknown_loop_returns_1(self):
        rc = main(["--config", self.cfg_path, "run", "fantasma", "x"])
        self.assertEqual(rc, 1)

    def test_missing_config_returns_1(self):
        rc = main(["--config", "/tmp/nao-existe.toml", "status"])
        self.assertEqual(rc, 1)

    def test_notify_once(self):
        rc = main(["--config", self.cfg_path, "notify", "--once"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_cli -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sac.cli'`

- [ ] **Step 3: Implementar** — `sac/cli.py`

```python
"""CLI do SAC: argparse → commands."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .commands import (
    cmd_done, cmd_down, cmd_log, cmd_next, cmd_notify,
    cmd_recv, cmd_run, cmd_send, cmd_status, cmd_up,
)
from .config import ConfigError, load_config
from .store import Store, StoreError
from .tmux import Tmux


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sac", description="Stupid Agentic Coordinator")
    p.add_argument("--config", default="sac.toml", help="caminho do sac.toml")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("up", help="sobe a sessão tmux com os agentes")
    sub.add_parser("down", help="encerra a sessão (preserva .sac/)")
    sub.add_parser("status", help="visão geral dos agentes e filas")
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

    sp = sub.add_parser("run", help="dá o pontapé em um loop declarado")
    sp.add_argument("loop")
    sp.add_argument("task")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cfg_path = Path(args.config).resolve()
    try:
        cfg = load_config(cfg_path)
    except ConfigError as e:
        print(f"erro de configuração: {e}", file=sys.stderr)
        return 1

    root = cfg_path.parent
    store = Store(root / ".sac")
    tmux = Tmux(cfg.session_name)

    try:
        match args.command:
            case "up":
                return cmd_up(cfg, store, tmux, root)
            case "down":
                return cmd_down(cfg, tmux)
            case "status":
                return cmd_status(cfg, store, tmux)
            case "attach":
                os.execvp("tmux", ["tmux", "attach", "-t", cfg.session_name])
            case "next":
                return cmd_next(store, os.environ)
            case "send":
                cmd_send(cfg, store, tmux, args.to, args.body)
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
    except (ConfigError, StoreError) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`sac/__main__.py`:

```python
from .cli import main

main()
```

Nota: `test_send_via_cli` roda sem tmux no ambiente → `has_session()` retorna rc≠0 → aviso no stderr e rc 0. Se houver um tmux server rodando com sessão de mesmo nome, o teste ainda passa (send_keys para janela inexistente falha silenciosamente no runner real? Não: `cmd_send` verifica `has_window` antes). Sem ação necessária.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd /home/dev/Github/sac && python3 -m unittest tests.test_cli -v`
Expected: 6 testes PASS (26 no total)

---

### Task 8: Prompts de contrato + `sac.toml` exemplo + README

**Files:**
- Create: `prompts/leader.md`, `prompts/dev.md`, `prompts/auditor.md`, `sac.toml`, `README.md`

**Interfaces:**
- Consumes: comandos finais da Task 7 (textos devem citar `sac next`, `sac send`, `sac done`, `SAC_DONE` exatamente como implementados).
- Produces: artefatos de configuração/documentação usados no `sac up`.

- [ ] **Step 1: Criar `sac.toml`** (exemplo funcional, espelhando a esteira real do workspace)

```toml
[session]
name = "sac"
notify_interval = 30
poke_stale_after = 120

[[agents]]
name = "leader"
command = "kimi"
args = ["--model", "esteira/k3"]
role = "leader"
prompt_file = "prompts/leader.md"

[[agents]]
name = "dev-1"
command = "opencode"
args = ["-m", "opencode-go/deepseek-v4-flash"]
role = "aux"
prompt_file = "prompts/dev.md"

[[agents]]
name = "auditor"
command = "kimi"
args = ["--model", "esteira/k3"]
role = "aux"
prompt_file = "prompts/auditor.md"

[[loops]]
name = "dev-review"
sequence = ["leader", "dev-1", "auditor"]
max_iterations = 3
```

- [ ] **Step 2: Criar `prompts/leader.md`**

```markdown
# Papel: leader (SAC)

Você é o leader de uma esteira coordenada pelo SAC. Você recebe as tarefas do
usuário e as distribui aos auxiliares.

## Contrato SAC (obrigatório)

- Quando cutucado com "SAC: mensagem nova", rode `sac next` para puxar a mensagem.
- Para delegar: `sac send dev-1 "<tarefa completa e autocontida>"`.
- Para cobrar revisão: `sac send auditor "<o que revisar + onde está o código>"`.
- Ao terminar de processar uma mensagem: escreva sua resposta terminando com uma
  linha contendo apenas `SAC_DONE` e rode `sac done <id> "<resumo>"`.
- Sem `sac done`, o notify re-cutucará periodicamente — é o esperado.

## Fluxo do loop dev-review (máx. 3 iterações)

1. Receba a tarefa do usuário → `sac send dev-1`.
2. Quando dev-1 terminar, `sac recv dev-1` → `sac send auditor` para revisão.
3. Se auditor REPROVAR: `sac send dev-1` com as correções (contra-fluxo).
4. Se APROVAR: reporte o resultado ao usuário.
```

- [ ] **Step 3: Criar `prompts/dev.md`**

```markdown
# Papel: dev (SAC)

Você é um desenvolvedor da esteira SAC. Recebe tarefas do leader, implementa com
TDD e devolve o resultado.

## Contrato SAC (obrigatório)

- Quando cutucado, rode `sac next` para puxar a tarefa.
- Trabalhe com TDD: teste que falha primeiro, depois implementação mínima.
- Ao terminar: escreva o relatório (o que fez, arquivos, resultado dos testes)
  terminando com uma linha contendo apenas `SAC_DONE` e rode
  `sac done <id> "<resumo>"`.
- Se receber correções do auditor (via leader), aplique e repita o ciclo.
```

- [ ] **Step 4: Criar `prompts/auditor.md`**

```markdown
# Papel: auditor (SAC)

Você é o revisor de código da esteira SAC. Recebe do leader o que revisar e emite
veredito objetivo.

## Contrato SAC (obrigatório)

- Quando cutucado, rode `sac next`.
- Revise o diff/código indicado contra os requisitos recebidos.
- Sua resposta DEVE começar com `APROVADO` ou `REPROVADO` na primeira linha,
  seguida de justificativa objetiva; se REPROVADO, liste as correções exigidas.
- Termine com uma linha contendo apenas `SAC_DONE` e rode `sac done <id> "<veredito>"`.
```

- [ ] **Step 5: Criar `README.md` — EM INGLÊS (repo público universal), com créditos**

Decisão do usuário (24/07): documentação em inglês; créditos ao projeto CCB (inspiração);
créditos a todas as tecnologias usadas; licença open-source mais permissiva (MIT, Step 5b).

```markdown
# SAC — Stupid Agentic Coordinator

A daemonless multi-agent coordinator built on tmux. The "switchboard" is a
directory (`.sac/`), not a process. Design doc: `docs/2026-07-24-sac-design.md`.

SAC manages AI harnesses (Kimi Code, opencode, or any interactive CLI) in tmux
windows and lets them exchange messages through the filesystem — no daemon, no
database, no screen-scraping heuristics. Completion is explicit: agents end
their replies with a `SAC_DONE` sentinel line and run `sac done <id>`.

## Quickstart

```bash
cd sac
python3 -m unittest discover -s tests -v   # test suite
python3 -m sac up                           # start the tmux session with agents
python3 -m sac status                       # overview
python3 -m sac send leader "implement X"    # task the leader
python3 -m sac run dev-review "feature Y"   # kick off a declared loop
python3 -m sac recv dev-1                   # read a reply (up to SAC_DONE)
python3 -m sac notify --once                # single re-poke sweep
python3 -m sac notify                       # continuous watcher (Ctrl-C exits)
python3 -m sac log -f                       # follow log.jsonl
python3 -m sac attach                       # attach to the tmux session
python3 -m sac down                         # stop the session
```

Optional install: `pip install -e .` exposes the `sac` command.

## Concepts

- **No daemon**: state is `.sac/` (inbox/claimed/done + log.jsonl) plus the tmux
  session. Crash of SAC takes nothing down; `sac up` is idempotent.
- **Explicit completion contract**: agents finish replies with `SAC_DONE` and run
  `sac done <id>` — no fragile turn-detection heuristics.
- **Configuration**: `sac.toml` declares exactly one leader, the auxiliaries and
  named loops. Loops are not enforced — the workflow lives in each agent's
  contract prompt (`prompts/`).

## Credits

- Inspired by the **CCB (Claude Code Bridge)** project, whose multi-agent tmux
  orchestration proved the concept — SAC reimplements the idea in its simplest
  possible form, replacing CCB's daemon and screen-state completion detection
  with a filesystem mailbox and an explicit sentinel contract.
- Built with **Python 3** (standard library only) and **tmux**.
- Designed to orchestrate AI harnesses such as **Kimi Code** (Moonshot AI) and
  **opencode**.

## License

MIT — see `LICENSE`.
```

- [ ] **Step 5b: Criar `LICENSE` (MIT)**

```text
MIT License

Copyright (c) 2026 ProCleiton

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 6: Verificar que a suíte continua verde** (docs não quebram nada)

Run: `cd /home/dev/Github/sac && python3 -m unittest discover -s tests -v`
Expected: 26 testes PASS

---

### Task 9: Teste de integração com tmux real + fechamento

**Files:**
- Create: `tests/test_integration.py`

**Interfaces:**
- Consumes: tudo.
- Produces: teste marcado `skipUnless(shutil.which("tmux"))` que sobe sessão real com agentes fake (`bash`), valida send/poke/capture e derruba.

- [ ] **Step 1: Escrever o teste de integração** — `tests/test_integration.py`

```python
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from sac.cli import main

TMUX = shutil.which("tmux")

VALID = """
[session]
name = "sac-itest"

[[agents]]
name = "leader"
command = "bash"
role = "leader"

[[agents]]
name = "dev-1"
command = "bash"
role = "aux"
"""


@unittest.skipUnless(TMUX, "tmux não disponível")
class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = str(self.d / "sac.toml")
        subprocess.run(["tmux", "kill-session", "-t", "sac-itest"],
                       capture_output=True)

    def tearDown(self):
        subprocess.run(["tmux", "kill-session", "-t", "sac-itest"],
                       capture_output=True)

    def test_up_send_capture_down(self):
        self.assertEqual(main(["--config", self.cfg, "up"]), 0)
        time.sleep(1)
        out = subprocess.run(["tmux", "list-windows", "-t", "sac-itest",
                              "-F", "#{window_name}"],
                             capture_output=True, text=True).stdout.split()
        self.assertIn("leader", out)
        self.assertIn("dev-1", out)
        self.assertEqual(main(["--config", self.cfg, "send", "dev-1", "echo oi"]), 0)
        time.sleep(1)
        pane = subprocess.run(["tmux", "capture-pane", "-p", "-t", "sac-itest:dev-1"],
                              capture_output=True, text=True).stdout
        self.assertIn("sac next", pane)
        self.assertEqual(main(["--config", self.cfg, "down"]), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar a suíte completa**

Run: `cd /home/dev/Github/sac && python3 -m unittest discover -s tests -v`
Expected: 27 testes PASS (integração incluída; skip só se não houver tmux)

- [ ] **Step 3: Fechamento**

- Reportar ao lead-coordinator: arquivos criados, resultado da suíte, como subir (`python3 -m sac up`).
- **Sem commit** — ciclo git fica para o deployment-officer, com autorização explícita do usuário.
- Gate do code-auditor sobre o working tree de `/home/dev/Github/sac` (obrigatório pela REGRA DE OURO do workspace).

---

## Self-Review (preenchido pelo autor do plano)

**1. Spec coverage** (contra `sac/docs/2026-07-24-sac-design.md`):
- §4 comandos: up→T5, send→T4, next→T4, done→T4, recv→T6, notify→T6, status→T5, log→T5, attach→T7 (execvp), down→T5, run→T6. ✅
- §5 notify (poke_stale_after, notify_interval, 1 poke por agente): T6. ✅
- §6 config (leader único, aux, loops declarados não-enforced, defaults 30/120): T1. ✅
- §7 contrato (SAC_DONE, sac done, prompt_file): T4 (extract_reply) + T8 (prompts). ✅
- §3.1 inbox/claimed/done/log.jsonl: T2. ✅
- §8 estrutura de código: T1–T8. ✅
- §9 testes stdlib unittest + integração marcada: T1–T9. ✅
- attach: design lista como comando; implementado via `os.execvp` no cli (T7), sem função em commands.py — decisão consciente (exec substitui o processo; não há lógica testável). ✅

**2. Placeholder scan:** nenhum TBD/TODO; todo passo de código tem bloco completo. A Task 5 contém uma "Nota" de ajuste do FakeRunner para `has-session` — instrução explícita, não placeholder. ✅

**3. Type consistency:** `FakeRunner` definido em `tests/test_tmux.py` (T3) e importado por T4/T5/T6 (`from tests.test_tmux import FakeRunner`) — assinatura única com suporte a `("rc", key)` em outputs. `Store.stale(agent, seconds, now)` usado em T6 com 2 args (now default) — consistente com T2. `cmd_send` retorna `str` (id) — usado em T4/T6. `extract_reply` definido em T4, usado em T6. `POKE_TEXT`/`SENTINEL` em commands.py. ✅
