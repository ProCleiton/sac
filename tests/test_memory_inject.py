import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sac.config import load_config
from sac.memory import (
    CURATION_INSTRUCTION, EMPTY_BLOCK, MARK_BEGIN, MARK_END, MemoryStore,
    inject_into,
)
from sac.store import Store

LEADER_MD = """# Papel: líder/orquestrador (SAC)

texto manual ANTES dos marcadores — não pode ser tocado.

""" + MARK_BEGIN + """
conteúdo velho da seção de memória
""" + MARK_END + """

texto manual DEPOIS dos marcadores — também preservado.
"""


class InjectIntoTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.prompt = self.d / "lider.md"
        self.prompt.write_text(LEADER_MD, encoding="utf-8")

    def test_rewrite_apenas_entre_marcadores(self):
        rc = inject_into(self.prompt, EMPTY_BLOCK)
        self.assertEqual(rc, "ok")
        text = self.prompt.read_text(encoding="utf-8")
        self.assertIn("texto manual ANTES", text)
        self.assertIn("texto manual DEPOIS", text)
        self.assertNotIn("conteúdo velho", text)
        self.assertIn(CURATION_INSTRUCTION, text)

    def test_idempotente_e_preserva_fora_byte_a_byte(self):
        ms = MemoryStore(self.d / ".sac")
        ms.remember("tarefa", "t1")
        inject_into(self.prompt, ms.pack())
        primeira = self.prompt.read_text(encoding="utf-8")
        inject_into(self.prompt, ms.pack())
        segunda = self.prompt.read_text(encoding="utf-8")
        self.assertEqual(primeira, segunda, "segunda injeção é idempotente")
        pre = LEADER_MD[: LEADER_MD.index(MARK_BEGIN)]
        pos = LEADER_MD[LEADER_MD.index(MARK_END) + len(MARK_END):]
        self.assertTrue(segunda.startswith(pre), "prefixo preservado byte a byte")
        self.assertTrue(segunda.endswith(pos), "sufixo preservado byte a byte")

    def test_secao_reflete_estado_do_banco(self):
        ms = MemoryStore(self.d / ".sac")
        ms.remember("tarefa", "migrar esteira", importance=4)
        inject_into(self.prompt, ms.pack())
        text = self.prompt.read_text(encoding="utf-8")
        self.assertIn("#1 [tarefa] (i4) migrar esteira", text)

    def test_sem_marcadores_nao_toca(self):
        p = self.d / "custom.md"
        p.write_text("contrato customizado sem marcadores\n", encoding="utf-8")
        rc = inject_into(p, EMPTY_BLOCK)
        self.assertEqual(rc, "sem-marcadores")
        self.assertEqual(p.read_text(encoding="utf-8"),
                         "contrato customizado sem marcadores\n")

    def test_arquivo_inexistente(self):
        rc = inject_into(self.d / "nada.md", EMPTY_BLOCK)
        self.assertEqual(rc, "missing")

    def test_marcadores_corrompidos_aviso_e_nao_toca(self):
        p = self.d / "corrompido.md"
        original = f"início\n{MARK_BEGIN}\nsem end\n"
        p.write_text(original, encoding="utf-8")
        err = io.StringIO()
        with patch.object(sys, "stderr", err):
            rc = inject_into(p, EMPTY_BLOCK)
        self.assertEqual(rc, "corrompido")
        self.assertIn("corrompidos", err.getvalue())
        self.assertEqual(p.read_text(encoding="utf-8"), original, "arquivo intacto")

    def test_marcadores_duplicados_e_corrompido(self):
        p = self.d / "dup.md"
        p.write_text(f"{MARK_BEGIN}\na\n{MARK_BEGIN}\nb\n{MARK_END}\n", encoding="utf-8")
        with patch.object(sys, "stderr", io.StringIO()):
            rc = inject_into(p, EMPTY_BLOCK)
        self.assertEqual(rc, "corrompido")


class LeaderTemplateTest(unittest.TestCase):
    def test_template_lider_contem_marcadores_e_instrucao(self):
        from sac.contracts import CONTRACTS, LEADER_CONTRACT
        lider = next(c for c in CONTRACTS if c["key"] == LEADER_CONTRACT)
        self.assertIn(MARK_BEGIN, lider["disciplina"])
        self.assertIn(MARK_END, lider["disciplina"])
        self.assertIn("sac memory remember", lider["disciplina"])
        self.assertIn("sac memory recall", lider["disciplina"])
        self.assertIn("sac memory forget", lider["disciplina"])
        self.assertIn("sac memory decay", lider["disciplina"])

    def test_init_gera_prompt_lider_com_memoria(self):
        from sac.init import cmd_init
        d = Path(tempfile.mkdtemp())
        inputs = iter(["sess", "", "5", "1", "lead", "kimi", "", "", "n", "n"])
        with patch("sac.init._list_models", return_value=[]):
            rc = cmd_init(stdin=lambda: next(inputs), stdout=lambda s: None,
                          root=d, is_interactive=True)
        self.assertEqual(rc, 0)
        content = (d / "prompts" / "lead.md").read_text(encoding="utf-8")
        self.assertIn(MARK_BEGIN, content)
        self.assertIn(MARK_END, content)
        self.assertIn(CURATION_INSTRUCTION, content)


TOML = """
[session]
name = "sac-mem-up"
boot_wait = 0

[[agents]]
name = "lider"
command = "kimi"
role = "leader"
prompt_file = "prompts/lider.md"
boot_wait = 0
"""


class UpInjectTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / ".sac").mkdir()
        (self.d / "prompts").mkdir()
        (self.d / ".sac" / "sac.toml").write_text(TOML, encoding="utf-8")
        (self.d / "prompts" / "lider.md").write_text(LEADER_MD, encoding="utf-8")
        self.cfg = load_config(self.d / ".sac" / "sac.toml")
        self.store = Store(self.d)

    def _cmd_up(self):
        from sac.commands import cmd_up
        from sac.tmux import Tmux
        from tests.test_tmux import FakeRunner
        r = FakeRunner(outputs={("rc", "has-session"): 1,
                                "list-windows": "lider\ndash\n"})
        t = Tmux("sac-mem-up", runner=r)
        return cmd_up(self.cfg, self.store, t, self.d, boot_wait=0)

    def test_up_reescreve_secao_antes_de_injetar(self):
        ms = MemoryStore(self.d / ".sac")
        ms.remember("tarefa", "migrar esteira")
        rc = self._cmd_up()
        self.assertEqual(rc, 0)
        text = (self.d / "prompts" / "lider.md").read_text(encoding="utf-8")
        self.assertIn("#1 [tarefa] (i3) migrar esteira", text)
        self.assertIn("texto manual ANTES", text, "conteúdo fora dos marcadores preservado")

    def test_up_sem_marcadores_nao_toca_contrato(self):
        (self.d / "prompts" / "lider.md").write_text("contrato antigo\n", encoding="utf-8")
        rc = self._cmd_up()
        self.assertEqual(rc, 0)
        self.assertEqual((self.d / "prompts" / "lider.md").read_text(encoding="utf-8"),
                         "contrato antigo\n")

    def test_up_sem_banco_nao_cria_memory_db(self):
        rc = self._cmd_up()
        self.assertEqual(rc, 0)
        self.assertFalse((self.d / ".sac" / "memory.db").exists(),
                         "sac up não deve criar o banco de memória")


class MemoryWriteRefreshTest(unittest.TestCase):
    """Writes do `sac memory` re-sincronizam o contrato do líder."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / ".sac").mkdir()
        (self.d / "prompts").mkdir()
        (self.d / ".sac" / "sac.toml").write_text(TOML, encoding="utf-8")
        (self.d / "prompts" / "lider.md").write_text(LEADER_MD, encoding="utf-8")
        self.cfg_path = str(self.d / ".sac" / "sac.toml")

    def _run(self, argv):
        from sac.cli import main
        out = io.StringIO()
        with patch.object(sys, "stdout", out):
            rc = main(["--config", self.cfg_path, "memory", *argv])
        return rc, out.getvalue()

    def _prompt(self):
        return (self.d / "prompts" / "lider.md").read_text(encoding="utf-8")

    def test_remember_atualiza_contrato(self):
        rc, _ = self._run(["remember", "tarefa", "migrar esteira"])
        self.assertEqual(rc, 0)
        self.assertIn("migrar esteira", self._prompt())

    def test_forget_atualiza_contrato(self):
        self._run(["remember", "tarefa", "temporária"])
        self.assertIn("temporária", self._prompt())
        self._run(["forget", "1"])
        self.assertNotIn("temporária", self._prompt())

    def test_write_sem_marcadores_nao_quebra(self):
        (self.d / "prompts" / "lider.md").write_text("sem marcadores\n", encoding="utf-8")
        rc, _ = self._run(["remember", "tarefa", "x"])
        self.assertEqual(rc, 0, "write funciona mesmo sem marcadores no contrato")
        self.assertEqual((self.d / "prompts" / "lider.md").read_text(encoding="utf-8"),
                         "sem marcadores\n")


if __name__ == "__main__":
    unittest.main()
