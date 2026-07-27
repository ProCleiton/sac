"""Fan-out: dispara o mesmo template para N agentes e agrega as replies.

O FanOutManager cria N mensagens com `fanout_id` comum e registra o estado da
coleta em `.sac/fanout/<id>.partial.json`. O daemon (dono do FanOutCollector)
coleta as replies com `reply_to_fanout`, persiste o parcial a cada reply
(crash-safe) e, quando todos respondem ou o timeout expira, entrega o agregado
`{agente: reply}` ao solicitante como mensagem única. Sem daemon, a coleta é
manual (`sac recv <agente>`).
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .store import Message, Store

TIMEOUT_DEFAULT = 600

_PARTIAL_SUFFIX = ".partial.json"


class FanOutManager:
    """Disparo: N mensagens com fanout_id comum + registro do estado da coleta."""

    def __init__(self, store: Store):
        self.store = store

    def disparar(self, sender: str, template: str, targets: list[str],
                 timeout: int = TIMEOUT_DEFAULT, now: datetime | None = None) -> str:
        now = now or datetime.now()
        fid = f"fanout-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        # estado antes das mensagens: uma reply imediata nunca é "tardia"
        FanOutCollector(self.store).registrar(fid, sender, targets, timeout, now=now)
        for target in targets:
            self.store.send(sender, target, template, now=now, fanout_id=fid)
        self.store.log("fanout", id=fid, sender=sender, targets=len(targets))
        return fid


class FanOutCollector:
    """Coleta chaveada de replies: parcial persistido a cada reply, agregado ao fechar."""

    def __init__(self, store: Store):
        self.store = store
        self._lock = threading.Lock()

    def _dir(self) -> Path:
        d = self.store.root / "fanout"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def partial_path(self, fid: str) -> Path:
        return self._dir() / f"{fid}{_PARTIAL_SUFFIX}"

    def final_path(self, fid: str) -> Path:
        return self._dir() / f"{fid}.json"

    def registrar(self, fid: str, solicitante: str, targets: list[str],
                  timeout: int, now: datetime | None = None) -> None:
        now = now or datetime.now()
        state = {
            "fanout_id": fid,
            "solicitante": solicitante,
            "targets": list(targets),
            "timeout": timeout,
            "created_at": now.isoformat(),
            "replies": {},
        }
        self._save(state)

    def _save(self, state: dict) -> None:
        self.partial_path(state["fanout_id"]).write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def estado(self, fid: str) -> dict | None:
        p = self.partial_path(fid)
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def pendentes(self) -> list[str]:
        """Fan-outs com coleta aberta (parcial sem agregado final)."""
        d = self.store.root / "fanout"
        if not d.is_dir():
            return []
        return [p.name[: -len(_PARTIAL_SUFFIX)]
                for p in sorted(d.glob(f"*{_PARTIAL_SUFFIX}"))
                if not self.final_path(p.name[: -len(_PARTIAL_SUFFIX)]).exists()]

    def coletar(self, msg: Message) -> str:
        """Registra a reply de um agente: 'parcial', 'completo' ou 'tardia'."""
        fid = msg.reply_to_fanout
        with self._lock:
            state = self.estado(fid)
            if state is None:
                self.store.log("fanout_late", id=fid, agent=msg.sender)
                return "tardia"
            state["replies"][msg.sender] = msg.body
            if all(t in state["replies"] for t in state["targets"]):
                self._fechar(state, expirado=False)
                return "completo"
            self._save(state)
            self.store.log("fanout_reply", id=fid, agent=msg.sender,
                           received=len(state["replies"]))
            return "parcial"

    def expirar(self, fid: str) -> None:
        """Fecha o fan-out pelo timeout: ausentes entram como TIMEOUT."""
        with self._lock:
            state = self.estado(fid)
            if state is None:
                return
            self._fechar(state, expirado=True)

    def _fechar(self, state: dict, expirado: bool) -> None:
        fid = state["fanout_id"]
        replies = state["replies"]
        agregado = {t: replies.get(t, "TIMEOUT") for t in state["targets"]}
        self.final_path(fid).write_text(
            json.dumps(agregado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.partial_path(fid).unlink(missing_ok=True)
        if expirado:
            ausentes = [t for t in state["targets"] if t not in replies]
            self.store.log("fanout_timeout", id=fid, missing=ausentes)
        self.store.log("fanout_complete", id=fid, received=len(replies),
                       timeout=expirado)
        corpo = (f"[SAC — FAN-OUT {fid}]\n"
                 + json.dumps(agregado, ensure_ascii=False, indent=2))
        self.store.send("daemon", state["solicitante"], corpo)
