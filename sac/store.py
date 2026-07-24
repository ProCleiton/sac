"""Estado do SAC no filesystem: inbox/claimed/done + log.jsonl (append-only)."""
from __future__ import annotations

import json
import shutil
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

    def clean_orphans(self, valid_agents: list[str]) -> dict[str, int]:
        valid = set(valid_agents)
        inbox_files = 0
        claimed_files = 0
        removed_agents = []
        for kind in ("inbox", "claimed"):
            d = self.root / kind
            if not d.is_dir():
                continue
            for agent_dir in d.iterdir():
                if not agent_dir.is_dir():
                    continue
                if agent_dir.name in valid:
                    continue
                files = len(list(agent_dir.glob("*.msg")))
                shutil.rmtree(agent_dir)
                if kind == "inbox":
                    inbox_files += files
                    removed_agents.append(agent_dir.name)
                else:
                    claimed_files += files
        self.log("clean", agents_removed=list(set(removed_agents)),
                 inbox_files=inbox_files, claimed_files=claimed_files)
        return {"inbox_files": inbox_files, "claimed_files": claimed_files, "agents_removed": removed_agents}

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
