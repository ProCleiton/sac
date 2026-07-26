import io
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sac.memory import (
    DEFAULT_BUDGET, MARK_BEGIN, MARK_END, KINDS, MemoryError, MemoryStore,
)


def _store(d: Path) -> MemoryStore:
    return MemoryStore(d / ".sac")


class MemorySchemaTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_banco_criado_lazy_na_primeira_escrita(self):
        ms = _store(self.d)
        db = self.d / ".sac" / "memory.db"
        self.assertFalse(db.exists(), "banco não deve existir antes da primeira operação")
        ms.remember("tarefa", "primeira")
        self.assertTrue(db.exists(), "banco criado na primeira escrita")

    def test_schema_completo(self):
        ms = _store(self.d)
        ms.remember("tarefa", "x")
        conn = sqlite3.connect(self.d / ".sac" / "memory.db")
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','trigger')")}
        self.assertIn("memories", tables)
        self.assertIn("history", tables)
        self.assertIn("memories_fts", tables)
        self.assertIn("memories_ai", tables, "trigger de insert do FTS")
        self.assertIn("memories_au", tables, "trigger de update do FTS")
        self.assertIn("memories_ad", tables, "trigger de delete do FTS")

    def test_pragmas_wal_e_busy_timeout(self):
        ms = _store(self.d)
        ms.remember("tarefa", "x")
        conn = sqlite3.connect(self.d / ".sac" / "memory.db")
        self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
        self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 5000)

    def test_segunda_operacao_reutiliza_banco(self):
        ms = _store(self.d)
        id1 = ms.remember("tarefa", "a")
        ms2 = _store(self.d)
        id2 = ms2.remember("lição", "b")
        self.assertEqual(id2, id1 + 1, "mesmo banco, ids sequenciais")


class RememberRecallTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.ms = _store(self.d)

    def test_kinds_validos(self):
        for kind in ("tarefa", "lição", "referência"):
            mid = self.ms.remember(kind, f"título {kind}")
            self.assertIsInstance(mid, int)

    def test_kind_invalido_rejeitado(self):
        with self.assertRaises(MemoryError) as ctx:
            self.ms.remember("nota", "inválido")
        self.assertIn("nota", str(ctx.exception))

    def test_importance_default_3(self):
        mid = self.ms.remember("tarefa", "x")
        m = self.ms.get(mid)
        self.assertEqual(m.importance, 3)

    def test_importance_fora_de_faixa_rejeitada(self):
        for bad in (0, 6):
            with self.assertRaises(MemoryError):
                self.ms.remember("tarefa", "x", importance=bad)

    def test_agent_registrado(self):
        mid = self.ms.remember("tarefa", "x", agent="lider")
        self.assertEqual(self.ms.get(mid).agent, "lider")

    def test_recall_sem_query_retorna_recentes(self):
        self.ms.remember("tarefa", "antiga", now=datetime(2026, 1, 1))
        self.ms.remember("tarefa", "recente", now=datetime(2026, 7, 1))
        out = self.ms.recall()
        self.assertEqual(out[0].title, "recente")
        self.assertEqual(out[1].title, "antiga")

    def test_recall_com_query_fts(self):
        self.ms.remember("referência", "API E2E roda na porta 9000")
        self.ms.remember("tarefa", "migrar esteira")
        out = self.ms.recall("porta 9000")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].title, "API E2E roda na porta 9000")
        self.assertEqual(out[0].kind, "referência")

    def test_recall_incrementa_access_count(self):
        mid = self.ms.remember("referência", "porta 9000")
        self.ms.recall("porta")
        self.assertEqual(self.ms.get(mid).access_count, 1)
        self.ms.recall("porta")
        self.assertEqual(self.ms.get(mid).access_count, 2)

    def test_recall_filtra_por_kind(self):
        self.ms.remember("tarefa", "deploy da API")
        self.ms.remember("referência", "deploy docs")
        out = self.ms.recall("deploy", kind="tarefa")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, "tarefa")

    def test_recall_limit(self):
        for i in range(5):
            self.ms.remember("tarefa", f"t{i}")
        self.assertEqual(len(self.ms.recall(limit=2)), 2)

    def test_recall_nao_retorna_arquivada_sem_all(self):
        mid = self.ms.remember("tarefa", "concluída")
        self.ms.forget(mid)
        self.assertEqual(self.ms.recall(), [])
        out = self.ms.recall(include_archived=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].status, "arquivada")


class ReviseForgetRestoreTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.ms = _store(self.d)

    def test_revise_cria_nova_e_marca_superseded(self):
        old = self.ms.remember("lição", "archive exige nomes", content="v1")
        new = self.ms.revise(old, content="v2 atualizado")
        self.assertNotEqual(old, new)
        self.assertEqual(self.ms.get(new).content, "v2 atualizado")
        self.assertEqual(self.ms.get(new).kind, "lição", "revisão herda o kind")
        self.assertEqual(self.ms.get(old).superseded_by, new)

    def test_recall_retorna_nova_nao_antiga(self):
        old = self.ms.remember("lição", "lição X", content="v1")
        self.ms.revise(old, content="v2")
        out = self.ms.recall("lição X")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].content, "v2")

    def test_revise_permite_trocar_titulo_e_importance(self):
        old = self.ms.remember("tarefa", "título velho", importance=2)
        new = self.ms.revise(old, title="título novo", importance=5)
        m = self.ms.get(new)
        self.assertEqual(m.title, "título novo")
        self.assertEqual(m.importance, 5)

    def test_revise_id_inexistente_erro(self):
        with self.assertRaises(MemoryError):
            self.ms.revise(999, content="x")

    def test_forget_soft_delete(self):
        mid = self.ms.remember("tarefa", "x")
        self.ms.forget(mid)
        m = self.ms.get(mid)
        self.assertEqual(m.status, "arquivada", "soft-delete: registro permanece")

    def test_restore_volta_para_ativa(self):
        mid = self.ms.remember("tarefa", "x")
        self.ms.forget(mid)
        self.ms.restore(mid)
        self.assertEqual(self.ms.get(mid).status, "ativa")

    def test_forget_restore_id_inexistente_erro(self):
        for op in (self.ms.forget, self.ms.restore):
            with self.assertRaises(MemoryError):
                op(999)


class FtsFallbackTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_fallback_like_quando_fts5_indisponivel(self):
        with patch("sac.memory._fts5_available", return_value=False):
            ms = _store(self.d)
            ms.remember("referência", "API E2E roda na porta 9000")
            ms.remember("tarefa", "migrar esteira")
            err = io.StringIO()
            with patch.object(sys, "stderr", err):
                out = ms.recall("porta 9000")
        self.assertEqual(len(out), 1)
        self.assertIn("porta 9000", out[0].title)
        self.assertIn("FTS5", err.getvalue(), "aviso de degradação no stderr")

    def test_sem_fts5_nao_cria_tabela_fts(self):
        with patch("sac.memory._fts5_available", return_value=False):
            ms = _store(self.d)
            ms.remember("tarefa", "x")
        conn = sqlite3.connect(self.d / ".sac" / "memory.db")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        self.assertNotIn("memories_fts", tables)


class DecayTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.ms = _store(self.d)
        self.now = datetime(2026, 7, 26, 12, 0, 0)
        self.old = self.now - timedelta(days=40)

    def test_tarefa_velha_importance_baixa_sem_acesso_arquivada(self):
        mid = self.ms.remember("tarefa", "velha", importance=2, now=self.old)
        archived = self.ms.decay(days=30, now=self.now)
        self.assertEqual([m.id for m in archived], [mid])
        self.assertEqual(self.ms.get(mid).status, "arquivada")

    def test_licao_velha_importance_3_permanece(self):
        mid = self.ms.remember("lição", "velha i3", importance=3, now=self.old)
        archived = self.ms.decay(days=30, now=self.now)
        self.assertEqual(archived, [])
        self.assertEqual(self.ms.get(mid).status, "ativa")

    def test_licao_velha_importance_1_arquivada(self):
        mid = self.ms.remember("lição", "velha i1", importance=1, now=self.old)
        archived = self.ms.decay(days=30, now=self.now)
        self.assertEqual([m.id for m in archived], [mid])

    def test_referencia_velha_importance_1_arquivada(self):
        mid = self.ms.remember("referência", "ref velha", importance=1, now=self.old)
        archived = self.ms.decay(days=30, now=self.now)
        self.assertEqual([m.id for m in archived], [mid])

    def test_tarefa_recente_permanece(self):
        mid = self.ms.remember("tarefa", "recente", importance=1,
                               now=self.now - timedelta(days=5))
        self.assertEqual(self.ms.decay(days=30, now=self.now), [])
        self.assertEqual(self.ms.get(mid).status, "ativa")

    def test_tarefa_com_acessos_permanece(self):
        mid = self.ms.remember("tarefa", "acessada", importance=1, now=self.old)
        self.ms.recall("acessada")  # incrementa access_count
        self.assertEqual(self.ms.decay(days=30, now=self.now), [])

    def test_dry_run_nao_altera(self):
        mid = self.ms.remember("tarefa", "velha", importance=2, now=self.old)
        eligible = self.ms.decay(days=30, dry_run=True, now=self.now)
        self.assertEqual([m.id for m in eligible], [mid])
        self.assertEqual(self.ms.get(mid).status, "ativa", "dry-run não arquiva")


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.ms = _store(self.d)

    def test_export_agrupado_por_kind(self):
        self.ms.remember("tarefa", "migrar config", content="detalhe da tarefa")
        self.ms.remember("lição", "sempre rodar testes")
        self.ms.remember("referência", "porta 9000")
        md = self.ms.export()
        self.assertIn("## Tarefas", md)
        self.assertIn("## Lições", md)
        self.assertIn("## Referências", md)
        self.assertIn("migrar config", md)
        self.assertIn("detalhe da tarefa", md)
        self.assertLess(md.index("## Tarefas"), md.index("## Lições"))
        self.assertLess(md.index("## Lições"), md.index("## Referências"))

    def test_export_exclui_arquivadas_por_padrao(self):
        mid = self.ms.remember("tarefa", "feita")
        self.ms.forget(mid)
        self.assertNotIn("feita", self.ms.export())
        self.assertIn("feita", self.ms.export(include_archived=True))


class PackTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.ms = _store(self.d)

    def test_pack_contem_marcadores_e_instrucao(self):
        block = self.ms.pack()
        self.assertTrue(block.startswith(MARK_BEGIN))
        self.assertTrue(block.rstrip().endswith(MARK_END))
        self.assertIn("sac memory remember", block)
        self.assertIn("sac memory recall", block)
        self.assertIn("sac memory forget", block)
        self.assertIn("sac memory decay", block)

    def test_pack_sem_memorias(self):
        block = self.ms.pack()
        self.assertIn("sem memórias ativas", block)
        self.assertFalse((self.d / ".sac" / "memory.db").exists(),
                         "pack não deve criar o banco")

    def test_pack_ordem_tarefas_licoes_referencias(self):
        self.ms.remember("referência", "ref R", importance=5)
        self.ms.remember("lição", "lição L", importance=5)
        self.ms.remember("tarefa", "tarefa T", importance=5)
        block = self.ms.pack()
        self.assertIn("### Tarefas em aberto", block)
        self.assertIn("### Lições", block)
        self.assertIn("### Referências", block)
        self.assertLess(block.index("tarefa T"), block.index("lição L"))
        self.assertLess(block.index("lição L"), block.index("ref R"))

    def test_pack_importance_desc_dentro_do_grupo(self):
        self.ms.remember("tarefa", "baixa", importance=1)
        self.ms.remember("tarefa", "alta", importance=5)
        block = self.ms.pack()
        self.assertLess(block.index("alta"), block.index("baixa"))

    def test_pack_respeita_orcamento_e_sinaliza_truncamento(self):
        for i in range(30):
            self.ms.remember("tarefa", f"tarefa {i}: " + "x" * 180, importance=3)
        budget = DEFAULT_BUDGET
        block = self.ms.pack(budget=budget)
        self.assertLessEqual(len(block), budget)
        self.assertRegex(block, r"… e \d+ mais")
        full = self.ms.pack(budget=100000)
        self.assertNotIn("… e", full)

    def test_pack_linha_formato(self):
        self.ms.remember("tarefa", "migrar esteira", importance=4)
        block = self.ms.pack()
        self.assertRegex(block, r"#1 \[tarefa\] \(i4\) migrar esteira")

    def test_pack_exclui_arquivadas_e_superseded(self):
        mid = self.ms.remember("tarefa", "feita")
        self.ms.forget(mid)
        old = self.ms.remember("lição", "velha")
        self.ms.revise(old, title="nova lição")
        block = self.ms.pack()
        self.assertNotIn("feita", block)
        self.assertNotIn("velha", block)
        self.assertIn("nova lição", block)


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.ms = _store(self.d)

    def _ops(self):
        conn = sqlite3.connect(self.d / ".sac" / "memory.db")
        return conn.execute("SELECT op, memory_id, agent FROM history ORDER BY id").fetchall()

    def test_todas_as_ops_auditadas_com_agent(self):
        mid = self.ms.remember("tarefa", "x", agent="lider")
        new = self.ms.revise(mid, content="v2", agent="lider")
        self.ms.forget(new, agent="lider")
        self.ms.restore(new, agent="lider")
        velha = self.ms.remember("tarefa", "velha", importance=1, agent="lider",
                                 now=datetime(2026, 1, 1))
        self.ms.decay(days=30, now=datetime(2026, 7, 26), agent="lider")
        ops = [op for op, _, _ in self._ops()]
        self.assertEqual(ops, ["ADD", "REVISE", "FORGET", "RESTORE", "ADD", "DECAY"])
        for _, _, agent in self._ops():
            self.assertEqual(agent, "lider")
        decay = [r for r in self._ops() if r[0] == "DECAY"][0]
        self.assertEqual(decay[1], velha, "DECAY aponta para a memória arquivada")

    def test_export_history(self):
        mid = self.ms.remember("tarefa", "x", agent="lider")
        self.ms.forget(mid, agent="lider")
        out = self.ms.export_history()
        self.assertIn("ADD", out)
        self.assertIn("FORGET", out)
        self.assertIn("lider", out)


if __name__ == "__main__":
    unittest.main()
