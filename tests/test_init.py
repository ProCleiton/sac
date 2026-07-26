import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sac.config import AgentConfig, Config, load_config
from sac.contracts import CONTRACTS, DEFAULT_AUX_CONTRACT, LEADER_CONTRACT
from sac.init import (
    InitError, _collect_config, _generate_prompts, _generate_toml, _harness_note,
    _is_interactive, _valid_name, cmd_init,
)
from sac.init import _list_models as _REAL_LIST_MODELS  # capturada antes do patch de módulo


def FakeInput(answers):
    it = iter(answers)
    def _input(prompt=""):
        return next(it)
    return _input


def _run_init(d, inputs, saida=None):
    out = saida.append if saida is not None else (lambda s: None)
    return cmd_init(stdin=FakeInput(inputs), stdout=out, root=d, is_interactive=True)


# sequência base de 3 agentes (leader + dev-1 + dev-2), comandos no PATH mockado
AGENTS3 = ["lead", "kimi", "", "",
           "dev-1", "opencode", "", "", "",
           "dev-2", "opencode", "", "", ""]


class InitTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_init_creates_sac_toml(self):
        inputs = [
            "sessao",         # session name
            "",               # socket (vazio = sem socket dedicado)
            "8",              # boot_wait
            "2",              # number of agents
            "leader",         # agent1 name
            "kimi",           # agent1 command
            "esteira/k3",     # agent1 model (papel leader automático)
            "",               # agent1 boot_wait
            "dev-1",          # agent2 name
            "opencode",       # agent2 command
            "",               # agent2 contrato (default: desenvolvedor)
            "opencode-go/deepseek-v4-flash",  # agent2 model
            "",               # agent2 boot_wait
            "n",              # no windows
        ]
        rc = _run_init(self.d, inputs)
        self.assertEqual(rc, 0)
        toml_path = self.d / ".sac" / "sac.toml"
        self.assertTrue(toml_path.exists(), ".sac/sac.toml deve ser criado")
        self.assertFalse((self.d / "sac.toml").exists(), "sac.toml legado não deve ser criado")
        cfg = load_config(toml_path)
        self.assertEqual(cfg.session_name, "sessao")
        self.assertEqual(len(cfg.agents), 2)
        self.assertEqual(cfg.agents[0].name, "leader")
        self.assertEqual(cfg.agents[0].command, "kimi")
        self.assertEqual(cfg.agents[0].role, "leader")
        self.assertEqual(cfg.agents[1].name, "dev-1")
        self.assertEqual(cfg.agents[1].role, "aux")
        prompt_file = self.d / "prompts" / "leader.md"
        self.assertTrue(prompt_file.exists(), "prompt do leader deve ser criado")

    def test_wizard_sem_pergunta_de_loops_e_toml_sem_secao(self):
        # v26b: loops removidos — wizard não pergunta e o TOML nunca tem [[loops]]
        saida = []
        rc = _run_init(self.d, ["sess", "", "8", "1", "lead", "kimi", "", "", "n"], saida)
        self.assertEqual(rc, 0)
        self.assertNotIn("loops", "\n".join(saida).lower())
        toml = (self.d / ".sac" / "sac.toml").read_text(encoding="utf-8")
        self.assertNotIn("[[loops]]", toml)

    def test_init_no_tty(self):
        saida = []
        rc = cmd_init(stdin=lambda: "", stdout=saida.append, root=self.d, is_interactive=False)
        self.assertEqual(rc, 1)
        self.assertIn("modo interativo requer terminal", "\n".join(saida))

    def test_init_existing_legacy_config_aborts(self):
        (self.d / "sac.toml").write_text("", encoding="utf-8")
        rc = _run_init(self.d, ["n"])
        self.assertEqual(rc, 0)
        content = (self.d / "sac.toml").read_text(encoding="utf-8")
        self.assertEqual(content, "", "sac.toml não deve ser modificado")
        self.assertFalse((self.d / ".sac" / "sac.toml").exists())

    def test_init_existing_hidden_config_aborts(self):
        (self.d / ".sac").mkdir()
        (self.d / ".sac" / "sac.toml").write_text("", encoding="utf-8")
        rc = _run_init(self.d, ["n"])
        self.assertEqual(rc, 0)
        content = (self.d / ".sac" / "sac.toml").read_text(encoding="utf-8")
        self.assertEqual(content, "", ".sac/sac.toml não deve ser modificado")

    def test_validate_name_no_spaces(self):
        from sac.init import _ask, _valid_name
        called = []
        def fake_stdin():
            if not called:
                called.append(None)
                return "nome com espaco"
            return "nome-sem-espaco"
        result = _ask("Nome", "default", fake_stdin, lambda s: None, validate=_valid_name)
        self.assertEqual(result, "nome-sem-espaco")

    def test_valid_name_rejects_special_chars(self):
        self.assertFalse(_valid_name(""))
        self.assertFalse(_valid_name('foo"bar'))
        self.assertFalse(_valid_name('foo\\bar'))
        self.assertFalse(_valid_name("foo/bar"))
        self.assertFalse(_valid_name("foo..bar"))
        self.assertFalse(_valid_name("foo bar"))
        self.assertTrue(_valid_name("foo"))
        self.assertTrue(_valid_name("foo-bar"))
        self.assertTrue(_valid_name("foo_bar"))
        self.assertTrue(_valid_name("Foo123"))

    def test_harness_note_kimi(self):
        from sac.init import KIMI_NOTE
        a = AgentConfig(name="l", command="kimi", args=[], role="leader")
        cfg = Config(session_name="t", agents=[a])
        note = _harness_note(cfg, a)
        self.assertEqual(note, KIMI_NOTE)

    def test_harness_note_opencode(self):
        from sac.init import OPENCODE_NOTE
        a = AgentConfig(name="d", command="opencode", args=[], role="aux")
        cfg = Config(session_name="t", agents=[a])
        note = _harness_note(cfg, a)
        self.assertEqual(note, OPENCODE_NOTE)

    def test_templates_agnosticos_sem_referencias_de_ambiente(self):
        # SAC é gerenciador de harness agnóstico: templates e exemplos gerados
        # não podem mencionar aliases/modelos de nenhum ambiente específico
        import inspect
        import sac.contracts as contracts_mod
        import sac.init as init_mod
        from sac.init import KIMI_NOTE, OPENCODE_NOTE
        fonte = inspect.getsource(init_mod) + inspect.getsource(contracts_mod)
        for ref in ("esteira/", "deepseek", "DeepSeek", "/home/"):
            self.assertNotIn(ref, KIMI_NOTE, f"KIMI_NOTE com referência de ambiente: {ref}")
            self.assertNotIn(ref, OPENCODE_NOTE, f"OPENCODE_NOTE com referência de ambiente: {ref}")
        self.assertNotIn("esteira/", fonte, "init/contracts (incl. exemplos) devem ser agnósticos")

    def test_init_args_separate_entries(self):
        inputs = [
            "test", "", "5", "1",
            "lead", "kimi", "esteira/k3", "",
            "n",
        ]
        d = Path(tempfile.mkdtemp())
        _run_init(d, inputs)
        cfg = load_config(d / ".sac" / "sac.toml")
        self.assertEqual(cfg.agents[0].args, ["--model", "esteira/k3"])

    def test_init_toml_roundtrip(self):
        inputs = [
            "rt-sess", "", "6", "2",
            "lead", "kimi", "k3", "",
            "dev1", "opencode", "", "deepseek-v4", "",
            "n",
        ]
        d = Path(tempfile.mkdtemp())
        rc = _run_init(d, inputs)
        self.assertEqual(rc, 0)
        cfg = load_config(d / ".sac" / "sac.toml")
        self.assertEqual(len(cfg.agents), 2)

    def test_init_eof_raises_clean_exit(self):
        def eof_stdin():
            raise EOFError("EOF")
        rc = cmd_init(stdin=eof_stdin, stdout=lambda s: None, root=self.d, is_interactive=True)
        self.assertEqual(rc, 1, "EOF no questionário deve retornar 1 sem traceback")

    def test_init_keyboard_interrupt_clean_exit(self):
        def kb_stdin():
            raise KeyboardInterrupt()
        rc = cmd_init(stdin=kb_stdin, stdout=lambda s: None, root=self.d, is_interactive=True)
        self.assertEqual(rc, 1, "Ctrl-C no questionário deve retornar 1 sem traceback")

    def test_init_eof_mid_collect_config(self):
        """EOF no meio do questionário (após algumas respostas) → saída limpa"""
        inputs = iter(["sessao", "", "8", "2"])
        def partial_stdin():
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError("pipe esgotado")
        rc = cmd_init(stdin=partial_stdin, stdout=lambda s: None, root=self.d, is_interactive=True)
        self.assertEqual(rc, 1, "EOF no meio do questionário deve retornar 1 sem traceback")

    def test_init_rejects_invalid_name(self):
        d = Path(tempfile.mkdtemp())
        rc = _run_init(d, ["test", "", "5", "1", 'lead"bad', "lead-clean", "kimi", "", "", "n"])
        self.assertEqual(rc, 0)
        cfg = load_config(d / ".sac" / "sac.toml")
        self.assertEqual(cfg.agents[0].name, "lead-clean")

    def test_init_prompts_ask_before_overwrite(self):
        d = Path(tempfile.mkdtemp())
        (d / "prompts").mkdir()
        (d / "prompts" / "leader.md").write_text("old content", encoding="utf-8")
        inputs = [
            "p-sess", "", "5", "1",
            "leader", "kimi", "", "",
            "n",  # windows
            "n",  # prompts: não sobrescrever
        ]
        rc = _run_init(d, inputs)
        self.assertEqual(rc, 0)
        content = (d / "prompts" / "leader.md").read_text(encoding="utf-8")
        self.assertEqual(content, "old content", "prompt não deve ser sobrescrito")


class InitWizardUxTest(unittest.TestCase):
    """v24: abertura explicativa, hints com exemplos, header do leader."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_abertura_explica_o_que_sera_gerado(self):
        saida = []
        rc = _run_init(self.d, ["sess", "", "8", "1", "lead", "kimi", "", "", "n"], saida)
        self.assertEqual(rc, 0)
        texto = "\n".join(saida)
        self.assertIn(".sac/sac.toml", texto)
        self.assertIn(".sac/", texto)
        self.assertIn("prompts/*.md", texto)
        self.assertIn("inbox/claimed/done", texto)

    def test_hints_com_exemplos_concretos(self):
        saida = []
        _run_init(self.d, ["sess", "", "8", "1", "lead", "kimi", "", "", "n"], saida)
        texto = "\n".join(saida)
        for trecho in ("ex.: esteira", "~/.sac-", "10 a 15", "ex.: leader, dev-1"):
            self.assertIn(trecho, texto, f"hint com exemplo ausente: {trecho!r}")

    def test_agente1_header_leader_e_hint_orquestrador(self):
        saida = []
        _run_init(self.d, ["sess", "", "8", "2",
                           "lead", "kimi", "", "",
                           "dev-1", "opencode", "", "", "",
                           "n"], saida)
        texto = "\n".join(saida)
        self.assertIn("--- Agente 1 (leader", texto)
        self.assertIn("delega aos demais", texto)

    def test_agentes_aux_sem_pergunta_de_papel(self):
        saida = []
        _run_init(self.d, ["sess", "", "8", "2",
                           "lead", "kimi", "", "",
                           "dev-1", "opencode", "", "", "",
                           "n"], saida)
        texto = "\n".join(saida)
        self.assertNotIn("Papel (leader/aux)", texto, "pergunta de papel foi removida")
        self.assertIn("--- Agente 2 (aux) ---", texto)
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.agents[1].role, "aux", "agentes 2+ viram aux automaticamente")


class InitHarnessDetectionTest(unittest.TestCase):
    """v24: default inteligente de harness via detecção no PATH."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def _collect(self, inputs, which):
        saida = []
        with patch("sac.init.shutil.which", side_effect=which):
            cfg = _collect_config(stdin=FakeInput(inputs), stdout=saida.append)
        return cfg, "\n".join(saida)

    def test_kimi_detectado_vira_default(self):
        cfg, texto = self._collect(
            ["sess", "", "8", "1", "lead", "", "k3", "", "n"],
            lambda c: "/usr/bin/kimi" if c == "kimi" else None)
        self.assertEqual(cfg.agents[0].command, "kimi")
        self.assertIn("detectado no seu PATH", texto)

    def test_opencode_preferido_quando_kimi_ausente(self):
        cfg, texto = self._collect(
            ["sess", "", "8", "1", "lead", "", "k3", "", "n"],
            lambda c: None if c == "kimi" else f"/usr/bin/{c}")
        self.assertEqual(cfg.agents[0].command, "opencode",
                         "opencode tem preferência sobre claude")
        self.assertIn("detectado no seu PATH", texto)

    def test_nenhum_detectado_usa_placeholder(self):
        cfg, texto = self._collect(
            ["sess", "", "8", "2",
             "lead", "", "n", "k3", "",
             "dev", "", "n", "", "", "",
             "n"],
            lambda c: None)
        self.assertEqual(cfg.agents[0].command, "kimi", "placeholder do agente 1")
        self.assertEqual(cfg.agents[1].command, "opencode", "placeholder dos demais")
        self.assertNotIn("detectado no seu PATH", texto)
        self.assertIn("não encontrado no PATH", texto, "warning da v22 é mantido")


class InitContractsTest(unittest.TestCase):
    """v24: catálogo de contratos canônicos."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_catalogo_tem_7_papeis(self):
        self.assertEqual(len(CONTRACTS), 7)
        keys = [c["key"] for c in CONTRACTS]
        self.assertEqual(keys, ["lider", "desenvolvedor", "revisor", "documentacao",
                                "deploy", "seguranca", "auxiliar"])
        self.assertEqual(CONTRACTS[0]["key"], LEADER_CONTRACT)
        self.assertEqual(CONTRACTS[1]["key"], DEFAULT_AUX_CONTRACT)

    def test_mensageria_presente_em_todos_os_contratos(self):
        for c in CONTRACTS:
            for trecho in ("## Contrato SAC (obrigatório)", "SAC_DONE", "sac done", "sac send"):
                self.assertIn(trecho, c["mensageria"], f"{c['key']}: mensageria sem {trecho!r}")
            self.assertTrue(c["disciplina"].startswith("## Disciplina"), c["key"])

    def test_contratos_apontam_memoria_para_o_sac_memory(self):
        for c in CONTRACTS:
            self.assertIn("sac memory", c["mensageria"], c["key"])
            self.assertIn("AGENTS.md", c["mensageria"],
                          f"{c['key']}: deve orientar que lições NÃO vivem em AGENTS.md")

    def test_agente1_recebe_contrato_lider_sem_pergunta(self):
        saida = []
        rc = _run_init(self.d, ["sess", "", "8", "1", "lead", "kimi", "", "", "n"], saida)
        self.assertEqual(rc, 0)
        texto = "\n".join(saida)
        self.assertNotIn("Contrato (papel)", texto, "agente 1 não recebe pergunta de catálogo")
        content = (self.d / "prompts" / "lead.md").read_text(encoding="utf-8")
        self.assertIn("# Papel: líder/orquestrador", content)
        self.assertIn("## Contrato SAC (obrigatório)", content)
        self.assertIn("## Disciplina: líder/orquestrador", content)

    def test_catalogo_numerado_default_desenvolvedor(self):
        saida = []
        rc = _run_init(self.d, ["sess", "", "8", "2",
                                "lead", "kimi", "", "",
                                "dev-1", "opencode", "", "", "",
                                "n"], saida)
        self.assertEqual(rc, 0)
        texto = "\n".join(saida)
        self.assertIn("1. desenvolvedor", texto)
        self.assertNotIn("líder/orquestrador —", texto,
                         "v25b: catálogo dos agentes 2+ exclui líder (só há um)")
        self.assertIn("6. auxiliar genérico", texto)
        content = (self.d / "prompts" / "dev-1.md").read_text(encoding="utf-8")
        self.assertIn("## Disciplina: desenvolvedor", content, "Enter seleciona o default")
        self.assertIn("TDD", content)

    def test_escolha_invalida_repete_a_pergunta(self):
        saida = []
        rc = _run_init(self.d, ["sess", "", "8", "2",
                                "lead", "kimi", "", "",
                                "dev-1", "opencode", "9", "2", "", "",
                                "n"], saida)
        self.assertEqual(rc, 0)
        texto = "\n".join(saida)
        self.assertIn("entrada inválida", texto)
        content = (self.d / "prompts" / "dev-1.md").read_text(encoding="utf-8")
        self.assertIn("revisor de código", content)

    def test_contrato_contem_mensageria_e_disciplina(self):
        rc = _run_init(self.d, ["sess", "", "8", "2",
                                "lead", "kimi", "", "",
                                "rev", "opencode", "2", "", "",
                                "n"])
        self.assertEqual(rc, 0)
        content = (self.d / "prompts" / "rev.md").read_text(encoding="utf-8")
        for trecho in ("sac done", "SAC_DONE", "sac send", "bloqueantes", "warnings"):
            self.assertIn(trecho, content, f"contrato do revisor sem {trecho!r}")
        for ref in ("pip install", "npm i"):
            self.assertNotIn(ref, content,
                             "contrato aponta os plugins do SAC — nunca instrui instalação")

    def test_contrato_lider_tem_disciplina_de_delegacao_e_revisao(self):
        # v26b: delegação e ciclo de revisão viram disciplina do contrato do
        # líder (substituem os loops declarados removidos)
        lider = next(c for c in CONTRACTS if c["key"] == LEADER_CONTRACT)
        disc = lider["disciplina"]
        for trecho in ("sac send", "delegar", "revisão", "iterar", "escalar"):
            self.assertIn(trecho, disc, f"contrato do líder sem {trecho!r}")
        for ref in ("pip install", "npm i"):
            self.assertNotIn(ref, disc,
                             "contrato aponta os plugins do SAC — nunca instrui instalação")

    def test_aux_contracts_sem_lider(self):
        from sac.contracts import AUX_CONTRACTS
        self.assertEqual(len(AUX_CONTRACTS), 6)
        self.assertNotIn(LEADER_CONTRACT, [c["key"] for c in AUX_CONTRACTS])
        self.assertEqual(AUX_CONTRACTS[0]["key"], DEFAULT_AUX_CONTRACT)


class InitModelListTest(unittest.TestCase):
    """v25b: sugestão de modelos por harness."""

    def setUp(self):
        self.list_models = _REAL_LIST_MODELS
        self.d = Path(tempfile.mkdtemp())

    def test_kimi_lista_aliases_do_config(self):
        cfg = self.d / "config.toml"
        cfg.write_text('default_model = "kimi-code/k3"\n'
                       '[models."kimi-code/k3"]\nx = 1\n'
                       '[models."esteira/k3"]\nx = 1\n', encoding="utf-8")
        self.assertEqual(self.list_models("kimi", kimi_cfg=cfg),
                         ["esteira/k3", "kimi-code/k3"])

    def test_kimi_config_ausente_retorna_vazio(self):
        self.assertEqual(self.list_models("kimi", kimi_cfg=self.d / "nada.toml"), [])

    def test_kimi_config_invalido_retorna_vazio(self):
        cfg = self.d / "config.toml"
        cfg.write_text("toml quebrado [[[", encoding="utf-8")
        self.assertEqual(self.list_models("kimi", kimi_cfg=cfg), [])

    def test_opencode_parse_da_saida(self):
        from unittest.mock import MagicMock
        r = MagicMock(returncode=0, stdout="opencode/big-pickle\nopencode/claude-opus-5\n\n")
        with patch("subprocess.run", return_value=r):
            self.assertEqual(self.list_models("opencode"),
                             ["opencode/big-pickle", "opencode/claude-opus-5"])

    def test_opencode_erro_retorna_vazio(self):
        from unittest.mock import MagicMock
        with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="x")):
            self.assertEqual(self.list_models("opencode"), [])

    def test_opencode_timeout_retorna_vazio(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("opencode", 10)):
            self.assertEqual(self.list_models("opencode"), [])

    def test_harness_desconhecido_retorna_vazio(self):
        self.assertEqual(self.list_models("claude"), [])

    def test_wizard_resposta_por_numero(self):
        with patch("sac.init._list_models", return_value=["m1", "m2"]):
            rc = _run_init(self.d, ["sess", "", "8", "1", "lead", "kimi", "2", "", "n"])
        self.assertEqual(rc, 0)
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.agents[0].args, ["--model", "m2"])

    def test_wizard_numero_invalido_repete(self):
        with patch("sac.init._list_models", return_value=["m1", "m2"]):
            saida = []
            rc = _run_init(self.d, ["sess", "", "8", "1", "lead", "kimi", "9", "1", "", "n"], saida)
        self.assertEqual(rc, 0)
        self.assertIn("entrada inválida", "\n".join(saida))
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.agents[0].args, ["--model", "m1"])

    def test_wizard_enter_nao_passa_model(self):
        with patch("sac.init._list_models", return_value=["m1", "m2"]):
            rc = _run_init(self.d, ["sess", "", "8", "1", "lead", "kimi", "", "", "n"])
        self.assertEqual(rc, 0)
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.agents[0].args, [])

    def test_wizard_sem_lista_cai_em_texto_livre(self):
        # patch do módulo (setUpModule) já retorna [] → pergunta de texto livre
        rc = _run_init(self.d, ["sess", "", "8", "1", "lead", "kimi", "k3", "", "n"])
        self.assertEqual(rc, 0)
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.agents[0].args, ["--model", "k3"])


class InitWindowsTest(unittest.TestCase):
    """v24: agrupamento manual de janelas [windows]."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def _run(self, tail, saida=None):
        inputs = ["sess", "", "8", "3", *AGENTS3, *tail]
        with patch("sac.init.shutil.which", return_value="/usr/bin/x"):
            return _run_init(self.d, inputs, saida)

    def test_resposta_nao_nao_gera_windows(self):
        rc = self._run(["n"])
        self.assertEqual(rc, 0)
        toml = (self.d / ".sac" / "sac.toml").read_text(encoding="utf-8")
        self.assertNotIn("[windows]", toml)

    def test_janela_lado_a_lado(self):
        rc = self._run(["s", "dev", "dev-1 dev-2", "1", "n"])
        self.assertEqual(rc, 0)
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.windows["dev"], "dev-1;dev-2")

    def test_janela_empilhada(self):
        rc = self._run(["s", "dev", "dev-1 dev-2", "2", "n"])
        self.assertEqual(rc, 0)
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.windows["dev"], "dev-1,dev-2")

    def test_agente_desconhecido_rejeitado(self):
        saida = []
        rc = self._run(["s", "dev", "dev-9", "dev-1 dev-2", "1", "n"], saida)
        self.assertEqual(rc, 0)
        texto = "\n".join(saida)
        self.assertIn("desconhecidos: dev-9", texto)
        self.assertIn("agentes válidos", texto)
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.windows["dev"], "dev-1;dev-2")

    def test_preview_exibido(self):
        saida = []
        rc = self._run(["s", "dev", "dev-1 dev-2", "1", "n"], saida)
        self.assertEqual(rc, 0)
        texto = "\n".join(saida)
        self.assertIn("preview do layout", texto)
        self.assertIn('dev = "dev-1;dev-2"', texto)

    def test_agente_fora_de_janela_mantem_janela_propria(self):
        rc = self._run(["s", "dev", "dev-1 dev-2", "1", "n"])
        self.assertEqual(rc, 0)
        cfg = load_config(self.d / ".sac" / "sac.toml")
        self.assertEqual(cfg.windows["lead"], "lead",
                         "agente fora de janelas ganha janela própria (config exige todos nos specs)")
        self.assertEqual(set(cfg.windows), {"dev", "lead"})


class InitHintTest(unittest.TestCase):
    def test_ask_com_hint_exibe_hint_antes_da_pergunta(self):
        from sac.init import _ask
        saida = []
        _ask("Nome", "default", lambda: "x", saida.append, hint="identificador do agente")
        self.assertGreaterEqual(len(saida), 2, "hint deve gerar linha extra na saída")
        self.assertIn("identificador do agente", saida[0])
        self.assertIn("Nome", saida[1])

    def test_ask_sem_hint_nao_exibe_linha_extra(self):
        from sac.init import _ask
        saida = []
        _ask("Nome", "default", lambda: "x", saida.append)
        self.assertEqual(len(saida), 1)
        self.assertIn("Nome", saida[0])

    def test_collect_config_exibe_hints_em_todas_as_perguntas(self):
        inputs = [
            "sess", "", "8", "1",
            "lead", "kimi", "k3", "",
            "n",
        ]
        saida = []
        with patch("sac.init.shutil.which", return_value="/usr/bin/kimi"):
            _collect_config(stdin=FakeInput(inputs), stdout=saida.append)
        texto = "\n".join(saida)
        # um hint por pergunta do questionário (sessão, socket, boot_wait,
        # nº agentes, nome, comando, modelo, boot_wait específico, janelas)
        for trecho in ("tmux ls", "socket", "antes de injetar", "agentes",
                       "sac send", "PATH", "--model", "global", "janelas"):
            self.assertIn(trecho, texto, f"hint ausente contendo: {trecho!r}")


class InitHarnessValidationTest(unittest.TestCase):
    def _inputs(self, command_flow):
        return ["sess", "", "8", "1", "lead", *command_flow, "k3", "", "n"]

    def test_comando_ausente_warning_e_seguir(self):
        saida = []
        with patch("sac.init.shutil.which", return_value=None):
            cfg = _collect_config(stdin=FakeInput(self._inputs(["foo", "n"])), stdout=saida.append)
        texto = "\n".join(saida)
        self.assertIn("não encontrado no PATH", texto)
        self.assertIn("foo", texto)
        self.assertEqual(cfg.agents[0].command, "foo", "deve seguir com o comando informado")

    def test_comando_ausente_corrigir(self):
        saida = []
        def which(cmd):
            return None if cmd == "foo" else "/usr/bin/kimi"
        with patch("sac.init.shutil.which", side_effect=which):
            cfg = _collect_config(stdin=FakeInput(self._inputs(["foo", "s", "kimi"])), stdout=saida.append)
        texto = "\n".join(saida)
        self.assertIn("não encontrado no PATH", texto)
        self.assertEqual(cfg.agents[0].command, "kimi", "deve usar o comando corrigido")

    def test_comando_presente_sem_warning(self):
        saida = []
        with patch("sac.init.shutil.which", return_value="/usr/bin/kimi"):
            cfg = _collect_config(stdin=FakeInput(self._inputs(["kimi"])), stdout=saida.append)
        texto = "\n".join(saida)
        self.assertNotIn("não encontrado no PATH", texto)
        self.assertEqual(cfg.agents[0].command, "kimi")


class InitOnboardingTest(unittest.TestCase):
    def test_init_imprime_checklist_pos_criacao(self):
        d = Path(tempfile.mkdtemp())
        inputs = ["sess", "", "8", "1", "lead", "kimi", "k3", "", "n"]
        saida = []
        rc = _run_init(d, inputs, saida)
        self.assertEqual(rc, 0)
        texto = "\n".join(saida)
        self.assertIn("Próximos passos", texto)
        self.assertIn("Pre-warm", texto)
        self.assertIn("prompts/*.md", texto)
        self.assertIn(".sac/sac.toml", texto)
        self.assertIn("[windows]", texto)
        self.assertIn("sac up", texto)
        self.assertIn("sac attach", texto)
        self.assertIn("beginner-guide", texto)

    def test_init_instala_plugins_canonicos_automaticamente(self):
        # v27: o init instala os plugins sem pergunta/opção no wizard
        d = Path(tempfile.mkdtemp())
        inputs = ["sess", "", "8", "1", "lead", "kimi", "k3", "", "n"]
        saida = []
        with patch("sac.init._cmd_plugins", return_value=0) as m:
            rc = _run_init(d, inputs, saida)
        self.assertEqual(rc, 0)
        m.assert_called_once()
        self.assertEqual(m.call_args[0][0], "install")
        texto = "\n".join(saida)
        self.assertIn("Plugins canônicos", texto)
        self.assertNotIn("→ sac plugins install", texto,
                         "checklist não tem mais passo de plugins (automático)")

    def test_init_avisa_mas_nao_aborta_se_install_falha(self):
        d = Path(tempfile.mkdtemp())
        inputs = ["sess", "", "8", "1", "lead", "kimi", "k3", "", "n"]
        saida = []
        with patch("sac.init._cmd_plugins", return_value=1):
            rc = _run_init(d, inputs, saida)
        self.assertEqual(rc, 0, "falha de rede no install não aborta o init")
        texto = "\n".join(saida)
        self.assertIn("sac plugins install", texto, "aviso orienta o reparo manual")


class InitWorkspaceTest(unittest.TestCase):
    def test_init_creates_complete_workspace(self):
        d = Path(tempfile.mkdtemp())
        inputs = [
            "sac-test",       # session
            str(d / "sock" / "tmux.sock"),  # socket
            "10",             # boot_wait
            "1",              # 1 agent
            "leader",         # name
            "kimi",           # command
            "k3",             # model (papel leader automático)
            "",               # boot_wait
            "n",              # no windows
        ]
        rc = _run_init(d, inputs)
        self.assertEqual(rc, 0)

        sac_dir = d / ".sac"
        self.assertTrue((sac_dir / "inbox").is_dir(), "inbox/ deve existir")
        self.assertTrue((sac_dir / "claimed").is_dir(), "claimed/ deve existir")
        self.assertTrue((sac_dir / "done").is_dir(), "done/ deve existir")
        self.assertTrue((sac_dir / "sac.toml").is_file(), "config deve ficar em .sac/sac.toml")

        self.assertTrue((d / "sock").is_dir(), "diretorio do socket deve ser criado")

        cfg = load_config(sac_dir / "sac.toml")
        self.assertEqual(cfg.session_name, "sac-test")

        self.assertTrue((d / "prompts" / "leader.md").is_file())

    def test_init_without_socket_skips_mkdir(self):
        d = Path(tempfile.mkdtemp())
        inputs = [
            "no-sock",
            "",               # socket vazio
            "5",
            "1",
            "dev",
            "opencode",
            "",               # model vazio
            "",               # boot_wait
            "n",
        ]
        rc = _run_init(d, inputs)
        self.assertEqual(rc, 0)
        cfg = load_config(d / ".sac" / "sac.toml")
        self.assertIsNone(cfg.socket)


class BootWaitTest(unittest.TestCase):
    def test_boot_wait_elapsed_second_agent_sleeps_less(self):
        from unittest.mock import patch
        from sac.commands import cmd_up
        from sac.tmux import Tmux
        from tests.test_tmux import FakeRunner

        d = Path(tempfile.mkdtemp())
        config_toml = """
[session]
name = "sac-boot"
boot_wait = 10

[[agents]]
name = "leader"
command = "kimi"
role = "leader"
prompt_file = "prompts/leader.md"
boot_wait = 10.0

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"
prompt_file = "prompts/dev.md"
boot_wait = 10.0
"""
        (d / "sac.toml").write_text(config_toml, encoding="utf-8")
        (d / "prompts").mkdir(parents=True, exist_ok=True)
        (d / "prompts" / "leader.md").write_text("leader prompt")
        (d / "prompts" / "dev.md").write_text("dev prompt")
        cfg = load_config(d / "sac.toml")
        store = __import__("sac.store", fromlist=["Store"]).Store(d / ".sac")
        r = FakeRunner(outputs={("rc", "has-session"): 1, "list-windows": "leader\ndev-1\ndash\n"})
        t = Tmux("sac-boot", runner=r)

        fake_now = [1000.0, 1000.0, 1008.0]
        def monotonic():
            return fake_now.pop(0)
        with patch("sac.commands.time.sleep") as mock_sleep:
            with patch("sac.commands.time.monotonic", side_effect=monotonic):
                cmd_up(cfg, store, t, d, boot_wait=None)

        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list if c.args[0] > 0]
        self.assertGreaterEqual(len(sleep_calls), 2, "ambos agentes devem dormir")
        self.assertEqual(sleep_calls[0], 10, "leader dorme boot_wait cheio")
        self.assertLess(sleep_calls[1], 10, "segundo agente dorme menos pois tempo decorreu")


if __name__ == "__main__":
    unittest.main()
