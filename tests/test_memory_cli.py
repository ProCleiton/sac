import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sac.memory import MARK_BEGIN, MemoryStore

VALID_TOML = """
[session]
name = "sac-mem-test"

[[agents]]
name = "lider"
command = "kimi"
role = "leader"
prompt_file = "prompts/lider.md"
"""


class MemoryCliTest(unittest.TestCase):
    def setUp(self):
        from sac.cli import main
        self.main = main
        self.d = Path(tempfile.mkdtemp())
        (self.d / ".sac").mkdir()
        (self.d / ".sac" / "sac.toml").write_text(VALID_TOML, encoding="utf-8")
        self.cfg = str(self.d / ".sac" / "sac.toml")

    def _run(self, argv, env=None):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
            with patch.dict(os.environ, env or {}):
                rc = self.main(["--config", self.cfg, "memory", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_remember_imprime_id_e_cria_banco(self):
        rc, out, _ = self._run(["remember", "tarefa", "migrar config"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "1")
        self.assertTrue((self.d / ".sac" / "memory.db").exists())

    def test_remember_kind_invalido_exit_1(self):
        rc, _, err = self._run(["remember", "nota", "x"])
        self.assertEqual(rc, 1)
        self.assertIn("kind inválido", err)

    def test_remember_registra_agent_da_env(self):
        rc, _, _ = self._run(["remember", "tarefa", "x"], env={"SAC_AGENT": "lider"})
        self.assertEqual(rc, 0)
        ms = MemoryStore(self.d / ".sac")
        self.assertEqual(ms.get(1).agent, "lider")

    def test_recall_imprime_linhas_no_formato(self):
        self._run(["remember", "referência", "API E2E roda na porta 9000", "-i", "4"])
        rc, out, _ = self._run(["recall", "porta 9000"])
        self.assertEqual(rc, 0)
        self.assertIn("#1 [referência] (i4) API E2E roda na porta 9000", out)

    def test_forget_id_inexistente_exit_1(self):
        self._run(["remember", "tarefa", "x"])
        rc, _, err = self._run(["forget", "999"])
        self.assertEqual(rc, 1)
        self.assertIn("999", err)

    def test_forget_restore_ok(self):
        self._run(["remember", "tarefa", "x"])
        rc, out, _ = self._run(["forget", "1"])
        self.assertEqual(rc, 0)
        self.assertIn("arquivada", out)
        rc, out, _ = self._run(["restore", "1"])
        self.assertEqual(rc, 0)
        self.assertIn("ativa", out)

    def test_revise_imprime_novo_id(self):
        self._run(["remember", "lição", "lição v1"])
        rc, out, _ = self._run(["revise", "1", "-c", "v2"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "2")
        ms = MemoryStore(self.d / ".sac")
        self.assertEqual(ms.get(1).superseded_by, 2)

    def test_decay_dry_run_nao_altera(self):
        self._run(["remember", "tarefa", "x"])
        rc, out, _ = self._run(["decay", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("dry-run", out)

    def test_export_history_via_cli(self):
        self._run(["remember", "tarefa", "auditar"], env={"SAC_AGENT": "lider"})
        rc, out, _ = self._run(["export", "--history"])
        self.assertEqual(rc, 0)
        self.assertIn("ADD", out)
        self.assertIn("lider", out)

    def test_pack_via_cli(self):
        self._run(["remember", "tarefa", "t1"])
        rc, out, _ = self._run(["pack"])
        self.assertEqual(rc, 0)
        self.assertIn(MARK_BEGIN, out)
        self.assertIn("t1", out)

    def test_sem_subcomando_imprime_help(self):
        rc, out, _ = self._run([])
        self.assertEqual(rc, 0)
        self.assertIn("remember", out)
        self.assertIn("recall", out)
