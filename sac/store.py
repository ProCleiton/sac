"""Estado do SAC no filesystem: inbox/claimed/done + log.jsonl (append-only)."""
from __future__ import annotations

import json
import os
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
    reply_to: str | None = None


class Store:
    def __init__(self, root: Path | None = None):
        if root is not None:
            self.root = Path(root) / ".sac"
        else:
            self.root = self._resolve_root()

    @staticmethod
    def _resolve_root() -> Path:
        env_root = os.environ.get("SAC_ROOT")
        if env_root:
            return Path(env_root) / ".sac"
        return Path.cwd() / ".sac"

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
        return Message(meta["id"], meta["from"], meta["to"], meta["ts"], body,
                       reply_to=meta.get("reply_to"))

    def send(self, sender: str, recipient: str, body: str, now: datetime | None = None) -> str:
        now = now or datetime.now()
        stamp = now.strftime("%Y%m%d-%H%M%S")
        existing = []
        for kind in ("inbox", "claimed", "done"):
            existing += [i for i in self._ids(kind, recipient) if i.startswith(stamp)]
        seq = max((int(i.split("-")[2]) for i in existing), default=0) + 1
        mid = f"{stamp}-{seq:03d}-from-{sender}"
        reply_to = self._infer_reply_to(sender, recipient)
        reply_line = f"reply_to: {reply_to}\n" if reply_to else ""
        content = f"id: {mid}\nfrom: {sender}\nto: {recipient}\nts: {now.isoformat()}\n{reply_line}\n{body}"
        (self._dir("inbox", recipient) / f"{mid}.msg").write_text(content, encoding="utf-8")
        self.log("send", now=now, sender=sender, to=recipient, id=mid)
        return mid

    def _infer_reply_to(self, sender: str, recipient: str) -> str | None:
        claimed = self._ids("claimed", sender)
        for cid in reversed(claimed):
            src = self.root / "claimed" / sender / f"{cid}.msg"
            msg = self._parse(src)
            if msg.sender == recipient:
                return msg.id
        return None

    def next(self, agent: str) -> Message | None:
        ids = self._ids("inbox", agent)
        if not ids:
            return None
        src = self.root / "inbox" / agent / f"{ids[0]}.msg"
        msg = self._parse(src)
        src.rename(self._dir("claimed", agent) / src.name)
        self.log("next", agent=agent, id=msg.id)
        return msg

    def done(self, agent: str, msg_id: str, summary: str, now: datetime | None = None) -> bool:
        src = self.root / "claimed" / agent / f"{msg_id}.msg"
        if not src.is_file():
            raise StoreError(f"mensagem não está claimed para {agent}: {msg_id}")
        self._log_done(agent, msg_id, summary, now=now)
        dst = self._dir("done", agent) / src.name
        try:
            shutil.move(str(src), str(dst))
        except OSError as e:
            self.log("loop_error", error=f"finish_move_failed: {e}", agent=agent, id=msg_id)
            return False
        if src.exists():
            self.log("loop_error", error=f"finish_move_orphan: src still exists after move", agent=agent, id=msg_id)
            return False
        return True

    def _log_done(self, agent: str, msg_id: str, summary: str, now: datetime | None = None) -> None:
        now = now or datetime.now()
        line = json.dumps({
            "ts": now.isoformat(),
            "event": "done",
            "agent": agent,
            "id": msg_id,
            "summary": summary,
        }, ensure_ascii=False)
        path = self.root / "log.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def finish_reply(self, agent: str, msg_id: str) -> None:
        src = self.root / "claimed" / agent / f"{msg_id}.msg"
        if not src.is_file():
            raise StoreError(f"reply não encontrada em claimed para {agent}: {msg_id}")
        src.rename(self._dir("done", agent) / src.name)
        self.log("deliver_reply", agent=agent, id=msg_id)

    def peek_next(self, agent: str) -> tuple[str, str | None] | None:
        ids = self._ids("inbox", agent)
        if not ids:
            return None
        src = self.root / "inbox" / agent / f"{ids[0]}.msg"
        msg = self._parse(src)
        return (msg.id, msg.reply_to)

    def ack(self, agent: str) -> Message | None:
        ids = self._ids("inbox", agent)
        if not ids:
            return None
        src = self.root / "inbox" / agent / f"{ids[0]}.msg"
        msg = self._parse(src)
        src.rename(self._dir("done", agent) / src.name)
        self.log("ack", agent=agent, id=msg.id)
        return msg

    def pending(self, agent: str) -> list[str]:
        return self._ids("inbox", agent)

    def claimed(self, agent: str) -> list[str]:
        return self._ids("claimed", agent)

    def inbox_count(self, agent: str) -> int:
        return len(self._ids("inbox", agent))

    def last_event_age(self, agent: str, now: datetime | None = None) -> float | None:
        """Segundos desde o último evento do agente no log.jsonl (None se não houver)."""
        now = now or datetime.now()
        path = self.root / "log.jsonl"
        if not path.is_file():
            return None
        last: datetime | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("agent") != agent and ev.get("sender") != agent:
                continue
            try:
                ts = datetime.fromisoformat(str(ev.get("ts", "")))
            except ValueError:
                continue
            if last is None or ts > last:
                last = ts
        if last is None:
            return None
        return (now - last).total_seconds()

    def clean_orphans(self, valid_agents: list[str], dry_run: bool = False) -> dict[str, int]:
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
                if not dry_run:
                    shutil.rmtree(agent_dir)
                if kind == "inbox":
                    inbox_files += files
                    removed_agents.append(agent_dir.name)
                else:
                    claimed_files += files
        self.log("clean", agents_removed=list(set(removed_agents)),
                 inbox_files=inbox_files, claimed_files=claimed_files,
                 dry_run=dry_run)
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
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "log.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
