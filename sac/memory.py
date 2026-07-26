"""Memória de longo prazo do SAC: SQLite (stdlib) por workspace + FTS5.

Banco em `<workspace>/.sac/memory.db`, criado lazy na primeira escrita.
Kinds em pt-BR: tarefa, lição, referência. Soft-delete sempre — NENHUMA
operação executa DELETE físico. Toda mudança de estado é auditada em
`history`. Se FTS5 estiver indisponível, a busca degrada para LIKE com
aviso no stderr.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

MARK_BEGIN = "<!-- SAC-MEMORY:BEGIN -->"
MARK_END = "<!-- SAC-MEMORY:END -->"

KINDS = ("tarefa", "lição", "referência")
DEFAULT_BUDGET = 4000
DEFAULT_DECAY_DAYS = 30

CURATION_INSTRUCTION = """Você é o curador desta memória. Regras:
1. Registre: `sac memory remember tarefa|lição|referência "<título>" -c "<conteúdo>"`.
2. Consulte: `sac memory recall "<query>"` antes de decidir — não redescubra.
3. Pode regularmente: tarefa concluída → `sac memory forget <id>`; lição superada →
   `sac memory revise <id>`; rode `sac memory decay` periodicamente.
4. Nunca delete fisicamente; tudo é auditado."""

EMPTY_BLOCK = (f"{MARK_BEGIN}\n"
               "## Memória de longo prazo (`.sac/memory.db`)\n\n"
               f"{CURATION_INSTRUCTION}\n"
               "\n(sem memórias ativas)\n"
               f"{MARK_END}")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('tarefa','lição','referência')),
  title TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '',
  importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
  status TEXT NOT NULL DEFAULT 'ativa' CHECK (status IN ('ativa','arquivada')),
  superseded_by INTEGER REFERENCES memories(id),
  access_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  last_accessed_at TEXT NOT NULL,
  agent TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, agent TEXT NOT NULL DEFAULT '',
  op TEXT NOT NULL, memory_id INTEGER, detail TEXT NOT NULL DEFAULT ''
);
"""

_SCHEMA_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
  title, content, tags, content='memories', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, title, content, tags)
  VALUES (new.id, new.title, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, title, content, tags)
  VALUES ('delete', old.id, old.title, old.content, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, title, content, tags)
  VALUES ('delete', old.id, old.title, old.content, old.tags);
  INSERT INTO memories_fts(rowid, title, content, tags)
  VALUES (new.id, new.title, new.content, new.tags);
END;
"""


class MemoryError(Exception):
    """Operação inválida sobre a memória (kind, id, importance...)."""


@dataclass
class Memory:
    id: int
    kind: str
    title: str
    content: str
    tags: str
    importance: int
    status: str
    superseded_by: int | None
    access_count: int
    created_at: str
    last_accessed_at: str
    agent: str

    def line(self) -> str:
        """Formato canônico de uma linha: `#<id> [<kind>] (i<importance>) <title>`."""
        return f"#{self.id} [{self.kind}] (i{self.importance}) {self.title}"


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp._fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE temp._fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _warn(msg: str) -> None:
    print(msg, file=sys.stderr)


def _row(row) -> Memory:
    return Memory(id=row[0], kind=row[1], title=row[2], content=row[3], tags=row[4],
                  importance=row[5], status=row[6], superseded_by=row[7],
                  access_count=row[8], created_at=row[9], last_accessed_at=row[10],
                  agent=row[11])


_SELECT = ("SELECT id, kind, title, content, tags, importance, status, superseded_by,"
           " access_count, created_at, last_accessed_at, agent FROM memories")


class MemoryStore:
    """Acesso ao banco de memória de um workspace (`<root>/memory.db`)."""

    def __init__(self, sac_root: Path):
        self.sac_root = Path(sac_root)
        self.db_path = self.sac_root / "memory.db"
        self._fts5: bool | None = None

    def _connect(self) -> sqlite3.Connection:
        self.sac_root.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = None
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(_SCHEMA)
        if self._fts5 is None:
            self._fts5 = _fts5_available(conn)
        if self._fts5:
            conn.executescript(_SCHEMA_FTS)
        return conn

    def _has_db(self) -> bool:
        return self.db_path.exists()

    def _history(self, conn, op: str, memory_id: int | None, detail: str, agent: str,
                 now: datetime) -> None:
        conn.execute(
            "INSERT INTO history (ts, agent, op, memory_id, detail) VALUES (?,?,?,?,?)",
            (now.isoformat(), agent, op, memory_id, detail))

    def get(self, memory_id: int) -> Memory:
        with self._connect() as conn:
            row = conn.execute(_SELECT + " WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            raise MemoryError(f"memória #{memory_id} não encontrada")
        return _row(row)

    def remember(self, kind: str, title: str, content: str = "", tags: str = "",
                 importance: int = 3, agent: str = "",
                 now: datetime | None = None) -> int:
        if kind not in KINDS:
            raise MemoryError(
                f"kind inválido: {kind!r} — use tarefa, lição ou referência")
        if not 1 <= importance <= 5:
            raise MemoryError(f"importance fora da faixa 1-5: {importance}")
        now = now or datetime.now()
        with self._connect() as conn:
            mid = self._insert(conn, kind, title, content, tags, importance, agent, now)
            self._history(conn, "ADD", mid, title, agent, now)
        return mid

    @staticmethod
    def _insert(conn, kind: str, title: str, content: str, tags: str,
                importance: int, agent: str, now: datetime) -> int:
        cur = conn.execute(
            "INSERT INTO memories (kind, title, content, tags, importance, status,"
            " created_at, last_accessed_at, agent) VALUES (?,?,?,?,?,'ativa',?,?,?)",
            (kind, title, content, tags, importance, now.isoformat(),
             now.isoformat(), agent))
        return cur.lastrowid

    def recall(self, query: str | None = None, kind: str | None = None,
               limit: int = 10, include_archived: bool = False) -> list[Memory]:
        if not self._has_db():
            return []
        now = datetime.now()
        with self._connect() as conn:
            rows = self._search(conn, query, kind, limit, include_archived)
            mems = [_row(r) for r in rows]
            if mems:
                ids = ",".join(str(m.id) for m in mems)
                conn.execute(
                    f"UPDATE memories SET access_count = access_count + 1,"
                    f" last_accessed_at = ? WHERE id IN ({ids})",
                    (now.isoformat(),))
        return mems

    def _search(self, conn, query: str | None, kind: str | None, limit: int,
                include_archived: bool):
        cond = ["superseded_by IS NULL"]
        params: list = []
        if not include_archived:
            cond.append("status = 'ativa'")
        if kind:
            cond.append("kind = ?")
            params.append(kind)
        where = " AND ".join(cond)
        if not query:
            return conn.execute(
                f"{_SELECT} WHERE {where}"
                " ORDER BY created_at DESC, id DESC LIMIT ?", (*params, limit)).fetchall()
        if self._fts5:
            try:
                return conn.execute(
                    f"{_SELECT} JOIN memories_fts f ON memories.id = f.rowid"
                    f" WHERE memories_fts MATCH ? AND {where}"
                    " ORDER BY rank LIMIT ?", (query, *params, limit)).fetchall()
            except sqlite3.OperationalError:
                pass  # query com sintaxe inválida para o FTS — cai no LIKE
        else:
            _warn("aviso: FTS5 indisponível — busca degradada para LIKE")
        like = f"%{query}%"
        return conn.execute(
            f"{_SELECT} WHERE {where} AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
            " ORDER BY created_at DESC, id DESC LIMIT ?",
            (*params, like, like, like, limit)).fetchall()

    def revise(self, memory_id: int, title: str | None = None,
               content: str | None = None, importance: int | None = None,
               agent: str = "", now: datetime | None = None) -> int:
        now = now or datetime.now()
        with self._connect() as conn:
            row = conn.execute(_SELECT + " WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                raise MemoryError(f"memória #{memory_id} não encontrada")
            old = _row(row)
            new_id = self._insert(
                conn, old.kind,
                title if title is not None else old.title,
                content if content is not None else old.content,
                old.tags,
                importance if importance is not None else old.importance,
                agent, now)
            conn.execute("UPDATE memories SET superseded_by = ? WHERE id = ?",
                         (new_id, memory_id))
            self._history(conn, "REVISE", memory_id, f"nova=#{new_id}", agent, now)
        return new_id

    def forget(self, memory_id: int, agent: str = "", now: datetime | None = None) -> None:
        self._set_status(memory_id, "arquivada", "FORGET", agent, now)

    def restore(self, memory_id: int, agent: str = "", now: datetime | None = None) -> None:
        self._set_status(memory_id, "ativa", "RESTORE", agent, now)

    def _set_status(self, memory_id: int, status: str, op: str, agent: str,
                    now: datetime | None) -> None:
        now = now or datetime.now()
        self.get(memory_id)  # erro claro se não existe
        with self._connect() as conn:
            conn.execute("UPDATE memories SET status = ? WHERE id = ?",
                         (status, memory_id))
            self._history(conn, op, memory_id, f"status={status}", agent, now)

    def decay(self, days: int = DEFAULT_DECAY_DAYS, dry_run: bool = False,
              now: datetime | None = None, agent: str = "") -> list[Memory]:
        """Arquiva deterministicamente o que envelheceu sem uso.

        Elegível: last_accessed_at mais velha que `days` dias, access_count = 0,
        ativa e não superada; tarefas exigem importance ≤ 2, lições/referências ≤ 1.
        """
        if not self._has_db():
            return []
        now = now or datetime.now()
        cutoff = (now - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                f"{_SELECT} WHERE status = 'ativa' AND superseded_by IS NULL"
                " AND access_count = 0 AND last_accessed_at < ?"
                " AND ((kind = 'tarefa' AND importance <= 2)"
                "      OR (kind IN ('lição','referência') AND importance <= 1))"
                " ORDER BY id", (cutoff,)).fetchall()
            mems = [_row(r) for r in rows]
            if not dry_run:
                for m in mems:
                    conn.execute("UPDATE memories SET status = 'arquivada' WHERE id = ?",
                                 (m.id,))
                    self._history(conn, "DECAY", m.id,
                                  f"days={days} importance={m.importance}", agent, now)
        return mems

    def _active_by_kind(self, include_archived: bool = False) -> dict[str, list[Memory]]:
        out: dict[str, list[Memory]] = {k: [] for k in KINDS}
        if not self._has_db():
            return out
        cond = "superseded_by IS NULL" if include_archived else \
            "status = 'ativa' AND superseded_by IS NULL"
        with self._connect() as conn:
            rows = conn.execute(
                f"{_SELECT} WHERE {cond}"
                " ORDER BY importance DESC, last_accessed_at DESC, id DESC").fetchall()
        for r in rows:
            out[_row(r).kind].append(_row(r))
        return out

    def export(self, include_archived: bool = False) -> str:
        """Markdown agrupado por kind (ativas; arquivadas só com include_archived)."""
        groups = self._active_by_kind(include_archived)
        titulos = {"tarefa": "Tarefas", "lição": "Lições", "referência": "Referências"}
        parts = ["# Memória de longo prazo (`.sac/memory.db`)"]
        for kind in KINDS:
            parts.append(f"\n## {titulos[kind]}")
            for m in groups[kind]:
                extra = " _(arquivada)_" if m.status == "arquivada" else ""
                parts.append(f"\n- **{m.line()}**{extra}")
                if m.content:
                    parts.append(f"  {m.content}")
                if m.tags:
                    parts.append(f"  tags: {m.tags}")
        return "\n".join(parts) + "\n"

    def export_history(self) -> str:
        """Rastro de auditoria: uma linha por operação, cronológica."""
        if not self._has_db():
            return "(sem histórico — banco ainda não criado)\n"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, op, memory_id, agent, detail FROM history ORDER BY id").fetchall()
        lines = ["# Histórico da memória (auditoria)", ""]
        for ts, op, memory_id, agent, detail in rows:
            who = f" [{agent}]" if agent else ""
            mid = f" #{memory_id}" if memory_id is not None else ""
            det = f" — {detail}" if detail else ""
            lines.append(f"- {ts} {op}{mid}{who}{det}")
        return "\n".join(lines) + "\n"

    def pack(self, budget: int = DEFAULT_BUDGET) -> str:
        """Bloco de injeção no contrato do líder, dentro do orçamento de chars.

        Ordem: tarefas → lições → referências (importance desc, recentes).
        Truncamento sinalizado com `… e N mais (sac memory recall)`.
        Não cria o banco: sem `memory.db`, o bloco sai vazio.
        """
        header = (f"{MARK_BEGIN}\n"
                  "## Memória de longo prazo (`.sac/memory.db`)\n\n"
                  f"{CURATION_INSTRUCTION}\n")
        footer = f"\n{MARK_END}"
        secoes = (("### Tarefas em aberto", "tarefa"),
                  ("### Lições", "lição"),
                  ("### Referências", "referência"))
        groups = self._active_by_kind()
        entradas: list[str] = []  # headers de seção intercalados com as linhas
        for titulo, kind in secoes:
            if groups[kind]:
                entradas.append(titulo)
                entradas.extend(m.line() for m in groups[kind])
        if not entradas:
            return EMPTY_BLOCK

        body = ""
        incluidas = 0
        for i, entrada in enumerate(entradas):
            restantes = len(entradas) - (i + 1)
            trunc = f"\n… e {restantes} mais (sac memory recall)" if restantes else ""
            candidato = body + "\n" + entrada
            if len(header + candidato + trunc + footer) <= budget:
                body = candidato
                incluidas = i + 1
            else:
                break
        # não deixar header de seção órfão como última linha incluída
        while incluidas and entradas[incluidas - 1].startswith("### "):
            incluidas -= 1
            body = body[: body.rfind("\n" + entradas[incluidas])]
        faltam = len(entradas) - incluidas
        if faltam:
            body += f"\n… e {faltam} mais (sac memory recall)"
        return header + body + footer

    # -- injeção no contrato do líder --------------------------------------

    def inject_leader_prompt(self, prompt_path: Path,
                             budget: int = DEFAULT_BUDGET) -> str:
        """Reescreve a seção de memória do contrato do líder. Ver inject_into()."""
        return inject_into(Path(prompt_path), self.pack(budget))


def inject_into(path: Path, block: str) -> str:
    """Reescreve APENAS o trecho entre os marcadores SAC-MEMORY de `path`.

    Retorna o status: "ok", "missing" (arquivo inexistente), "sem-marcadores"
    (nada a fazer — contratos antigos/customizados não são tocados) ou
    "corrompido" (marcadores quebrados: avisa no stderr e não toca o arquivo).
    """
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8")
    n_begin, n_end = text.count(MARK_BEGIN), text.count(MARK_END)
    if n_begin == 0 and n_end == 0:
        return "sem-marcadores"
    if n_begin != 1 or n_end != 1 or text.index(MARK_BEGIN) > text.index(MARK_END):
        _warn(f"aviso: marcadores SAC-MEMORY corrompidos em {path} — arquivo não modificado")
        return "corrompido"
    pre = text[: text.index(MARK_BEGIN)]
    post = text[text.index(MARK_END) + len(MARK_END):]
    path.write_text(pre + block + post, encoding="utf-8")
    return "ok"


def refresh_leader_prompt(cfg, store_root: Path, project_root: Path) -> str:
    """Reinjeta o bloco de memória no contrato do líder (após writes e no `sac up`)."""
    prompt_file = getattr(cfg.leader, "prompt_file", None)
    if not prompt_file:
        return "missing"
    ms = MemoryStore(store_root)
    return ms.inject_leader_prompt(Path(project_root) / prompt_file)


def cmd_memory(cfg, store, project_root: Path, args, env,
               stdout=None) -> int:
    """Despacha os subcomandos de `sac memory`. Writes re-sincronizam o contrato."""
    stdout = stdout or print
    agent = env.get("SAC_AGENT", "")
    ms = MemoryStore(store.root)
    sub = args.memory_command

    def _after_write() -> None:
        refresh_leader_prompt(cfg, store.root, project_root)

    try:
        if sub == "remember":
            mid = ms.remember(args.kind, args.title, content=args.content,
                              tags=args.tags, importance=args.importance, agent=agent)
            stdout(str(mid))
        elif sub == "recall":
            for m in ms.recall(args.query, kind=args.kind, limit=args.limit,
                               include_archived=args.all):
                stdout(m.line())
            return 0
        elif sub == "revise":
            new_id = ms.revise(args.id, title=args.title, content=args.content,
                               importance=args.importance, agent=agent)
            stdout(str(new_id))
        elif sub == "forget":
            ms.forget(args.id, agent=agent)
            stdout(f"ok: #{args.id} arquivada")
        elif sub == "restore":
            ms.restore(args.id, agent=agent)
            stdout(f"ok: #{args.id} ativa")
        elif sub == "decay":
            mems = ms.decay(days=args.days, dry_run=args.dry_run, agent=agent)
            for m in mems:
                stdout(m.line())
            if args.dry_run:
                stdout(f"{len(mems)} elegível(eis) — dry-run: nada alterado")
                return 0
            else:
                stdout(f"{len(mems)} arquivada(s)")
        elif sub == "export":
            stdout(ms.export_history() if args.history
                   else ms.export(include_archived=args.all), end="")
            return 0
        elif sub == "pack":
            stdout(ms.pack(budget=args.budget))
            return 0
        else:
            args._help_parser.print_help()
            return 0
    except MemoryError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    _after_write()
    return 0
