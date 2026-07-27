"""Budgets por run (v23e): tetos de tarefas, mensagens e wall time.

Os contadores são DERIVADOS do journal da run (`.sac/runs/<id>/journal.jsonl`),
nunca mantidos em memória — sobrevivem a crash/restart sem reset. Teto = 0
significa ilimitado (default). Ao atingir qualquer teto a run é suspensa:
o `sac send` rejeita novas mensagens com o run_id e o daemon bloqueia as
entregas. Wall time tem grace period de 30s para claimed em andamento concluir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .run import RunJournal

GRACE_PERIOD = 30  # segundos após o teto de wall time para claimed concluir

_LABELS = {"tasks": "tarefas", "messages": "mensagens", "wall_time": "tempo"}


@dataclass(frozen=True)
class Budgets:
    """Tetos efetivos de uma run (0 = ilimitado)."""

    max_tasks: int = 0
    max_messages: int = 0
    max_wall_time: int = 0

    def unlimited(self) -> bool:
        return not (self.max_tasks or self.max_messages or self.max_wall_time)

    def journal_value(self) -> str | dict:
        """Valor persistido na entrada `run_start` do journal."""
        if self.unlimited():
            return "unlimited"
        return {"max_tasks": self.max_tasks,
                "max_messages": self.max_messages,
                "max_wall_time": self.max_wall_time}

    @classmethod
    def from_journal(cls, value) -> "Budgets":
        """Reconstrói a partir do campo `budgets` da entrada `run_start`."""
        if not isinstance(value, dict):
            return cls()  # "unlimited" ou ausente (runs pré-v23e)
        return cls(max_tasks=int(value.get("max_tasks", 0)),
                   max_messages=int(value.get("max_messages", 0)),
                   max_wall_time=int(value.get("max_wall_time", 0)))

    def limit(self, dim: str) -> int:
        return {"tasks": self.max_tasks,
                "messages": self.max_messages,
                "wall_time": self.max_wall_time}[dim]


class BudgetTracker:
    """Verifica os budgets de uma run reconstruindo os contadores do journal."""

    def __init__(self, sac_root: Path, run_id: str):
        self.journal = RunJournal(sac_root, run_id)

    @staticmethod
    def label(dim: str) -> str:
        return _LABELS[dim]

    def budgets(self) -> Budgets:
        for e in self.journal.read_entries():
            if e.get("event") == "run_start":
                return Budgets.from_journal(e.get("budgets"))
        return Budgets()

    def counts(self) -> dict[str, int]:
        """tasks = `task_sent`; messages = `task_sent` + `reply_sent`."""
        tasks = 0
        replies = 0
        for e in self.journal.read_entries():
            ev = e.get("event")
            if ev == "task_sent":
                tasks += 1
            elif ev == "reply_sent":
                replies += 1
        return {"tasks": tasks, "messages": tasks + replies}

    def elapsed(self, now: datetime | None = None) -> float | None:
        """Segundos desde o `run_start` do journal (None se não houver)."""
        now = now or datetime.now()
        for e in self.journal.read_entries():
            if e.get("event") == "run_start":
                try:
                    start = datetime.fromisoformat(str(e.get("ts", "")))
                except ValueError:
                    return None
                return (now - start).total_seconds()
        return None

    def exceeded(self, now: datetime | None = None,
                 grace: bool = False) -> str | None:
        """Dimensão estourada ("tasks"/"messages"/"wall_time") ou None.

        `grace=True` aplica o grace period de 30s ao teto de wall time —
        usado para replies e entregas do daemon, permitindo que claimed
        em andamento concluam.
        """
        b = self.budgets()
        if b.unlimited():
            return None
        c = self.counts()
        if b.max_tasks and c["tasks"] >= b.max_tasks:
            return "tasks"
        if b.max_messages and c["messages"] >= b.max_messages:
            return "messages"
        if b.max_wall_time:
            el = self.elapsed(now)
            limite = b.max_wall_time + (GRACE_PERIOD if grace else 0)
            if el is not None and el > limite:
                return "wall_time"
        return None
