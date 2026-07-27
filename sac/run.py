"""Runs (v23c): agrupador nomeado de mensagens com journal append-only.

Uma run nasce implicitamente do primeiro `sac send ... --run <id>` — NÃO existe
comando `sac run`. O estado vive em `.sac/runs/<run_id>/journal.jsonl`
(append-only, fsync a cada entrada): `run_start`, `task_sent` e `task_done`.
A leitura tolera a última linha mal-formada (crash durante o append).
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class RunError(Exception):
    """Operação inválida sobre runs."""


class RunJournal:
    """Journal append-only de uma run em `.sac/runs/<run_id>/journal.jsonl`."""

    def __init__(self, sac_root: Path, run_id: str):
        if not RUN_ID_RE.match(run_id):
            raise RunError(f"run_id inválido: {run_id!r} "
                           "(use apenas letras, dígitos, '-', '_' e '.')")
        self.sac_root = Path(sac_root)
        self.run_id = run_id
        self.dir = self.sac_root / "runs" / run_id
        self.path = self.dir / "journal.jsonl"

    @staticmethod
    def list_ids(sac_root: Path) -> list[str]:
        """Run_ids conhecidos (diretório com journal.jsonl em `.sac/runs/`)."""
        d = Path(sac_root) / "runs"
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir()
                      if p.is_dir() and (p / "journal.jsonl").is_file())

    def exists(self) -> bool:
        return self.path.is_file()

    def ensure(self, now: datetime | None = None) -> None:
        """Cria a run (dir + entrada `run_start`) se ainda não existir."""
        if self.path.is_file():
            return
        self.log_entry("run_start", now=now)

    def log_entry(self, event: str, now: datetime | None = None, **fields) -> None:
        """Appenda uma entrada no journal com fsync antes do retorno."""
        now = now or datetime.now()
        line = json.dumps({"ts": now.isoformat(), "event": event,
                           "run": self.run_id, **fields}, ensure_ascii=False)
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def read_entries(self) -> list[dict]:
        """Lê o journal; linha mal-formada (crash no append) é ignorada com aviso."""
        if not self.path.is_file():
            return []
        entries = []
        for i, line in enumerate(self.path.read_text(encoding="utf-8").splitlines()):
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"aviso: journal da run '{self.run_id}': linha {i + 1} "
                      "mal-formada ignorada (crash durante append?)", file=sys.stderr)
        return entries

    def sent_entries(self) -> list[dict]:
        return [e for e in self.read_entries() if e.get("event") == "task_sent"]

    def done_ids(self) -> set[str]:
        return {e.get("msg_id") for e in self.read_entries()
                if e.get("event") == "task_done"}

    def pending_messages(self) -> list[dict]:
        """Entradas `task_sent` sem `task_done` correspondente."""
        done = self.done_ids()
        return [e for e in self.sent_entries() if e.get("msg_id") not in done]

    def is_complete(self) -> bool:
        return not self.pending_messages()

    def counts(self) -> dict[str, int]:
        sent = self.sent_entries()
        done = self.done_ids()
        pending = sum(1 for e in sent if e.get("msg_id") not in done)
        return {"sent": len(sent), "done": len(sent) - pending, "pending": pending}
